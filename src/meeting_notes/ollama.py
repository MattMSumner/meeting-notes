"""Summarizer backed by a local model served by Ollama (https://ollama.com)."""

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from importlib import resources
from typing import Any, cast

from meeting_notes.meeting import Meeting
from meeting_notes.summary import Summary, SummaryError, parse_summary

# Sends a JSON request to an Ollama API path and returns the JSON reply.
Post = Callable[[str, dict[str, Any]], dict[str, Any]]

TIMEOUT_SECONDS = 600

# English transcripts run about 3.5 characters per token with qwen3; 3 errs on the side of
# saying a transcript won't fit.
CHARS_PER_TOKEN = 3
# Room left in the context for the model's thinking and its reply.
REPLY_TOKENS = 4096


def default_prompt() -> str:
    """The prompt, with {name} standing for the person who recorded the meeting."""
    return resources.files("meeting_notes").joinpath("prompts/summary.md").read_text()


class OllamaError(SummaryError):
    pass


def http_post(base_url: str) -> Post:
    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            base_url.rstrip("/") + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                reply: Any = json.loads(response.read())
            if not isinstance(reply, dict):
                raise ValueError(f"expected a JSON object, got {reply!r:.100}")
            return cast(dict[str, Any], reply)
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            try:
                detail = json.loads(detail)["error"]
            except (ValueError, KeyError, TypeError):
                pass
            if error.code == 404 and "not found" in detail:
                raise OllamaError(
                    f"Ollama doesn't have the model: {detail}. Download it with `ollama pull`."
                ) from None
            raise OllamaError(f"Ollama returned HTTP {error.code}: {detail}") from None
        except (urllib.error.URLError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise OllamaError(
                f"Couldn't reach Ollama at {base_url} ({reason}). "
                "Is it running? Start it with `brew services start ollama`."
            ) from None
        except (ValueError, http.client.HTTPException) as error:
            raise OllamaError(f"Ollama sent a reply that couldn't be read ({error})") from None

    return post


class OllamaSummarizer:
    def __init__(
        self,
        model: str,
        num_ctx: int,
        post: Post,
        my_name: str,
        prompt: str | None = None,
        think: bool = True,
    ) -> None:
        self.model = model
        self.num_ctx = num_ctx
        self.post = post
        self.prompt = (prompt if prompt is not None else default_prompt()).replace(
            "{name}", my_name
        )
        self.think = think

    def summarize(self, meeting: Meeting, transcript: str) -> Summary:
        messages = [
            {"role": "system", "content": self.prompt},
            {
                "role": "user",
                "content": f"Meeting: {meeting.title}\n"
                f"Date: {meeting.started_at:%A %Y-%m-%d %H:%M}\n\n"
                f"Transcript:\n\n{transcript}",
            },
        ]
        # Ollama doesn't refuse a prompt that's too long: it quietly drops part of it (in a
        # test, 7.4k tokens became 2k with a 4k context) and reports only what it kept. So
        # the check has to happen before sending.
        estimate = sum(len(m["content"]) for m in messages) // CHARS_PER_TOKEN + REPLY_TOKENS
        if estimate > self.num_ctx:
            raise OllamaError(
                f"The transcript is too long for the model's context (about {estimate} tokens "
                f"needed, {self.num_ctx} set), so the summary would miss part of it. "
                f"Raise MEETING_NOTES_NUM_CTX to at least {estimate}."
            )
        reply = self._chat(messages)
        try:
            return parse_summary(reply)
        except SummaryError as error:
            # Local models occasionally break the format; one retry, told what was wrong,
            # almost always fixes it.
            messages += [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": f"{error}. Reply again with JSON only."},
            ]
            return parse_summary(self._chat(messages))

    def _chat(self, messages: list[dict[str, str]]) -> str:
        response = self.post(
            "/api/chat",
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "think": self.think,
                # Constrains the reply to the schema, so it's almost always valid.
                "format": Summary.model_json_schema(),
                "options": {
                    # Ollama's default context is a few thousand tokens and it drops the
                    # start of anything longer without saying so. An hour-long meeting is
                    # about 10-15k tokens.
                    "num_ctx": self.num_ctx,
                    "temperature": 0,
                },
            },
        )
        if response.get("done_reason") == "length":
            raise OllamaError(
                f"The model ran out of context ({self.num_ctx} tokens) before finishing its "
                "reply. Raise MEETING_NOTES_NUM_CTX."
            )
        try:
            return str(response["message"]["content"])
        except (KeyError, TypeError):
            raise OllamaError(f"Ollama's reply had no message: {response!r:.200}") from None
