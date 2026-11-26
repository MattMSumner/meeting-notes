"""Summarizer backed by a local model served by Ollama (https://ollama.com)."""

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from importlib import resources
from typing import Any, cast

from meeting_notes.evidence import meeting_context
from meeting_notes.figures import evidence_issues
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

    def summarize(
        self, meeting: Meeting, transcript: str, *, handwritten_text: str = ""
    ) -> Summary:
        messages = [
            {"role": "system", "content": self.prompt},
            {
                "role": "user",
                "content": meeting_context(meeting)
                + f"\nTranscript:\n\n{transcript}"
                + f"\n\nHandwritten notes:\n\n{handwritten_text}",
            },
        ]
        reply, summary = self._ask(messages)
        # The model sometimes works out a number nobody said, like the rest of a total.
        # One retry, told which; the retry is kept only if it has fewer such numbers, and
        # any left are flagged in the note.
        context = meeting_context(meeting)
        unsaid = evidence_issues(summary, transcript, handwritten_text, context)
        if not unsaid:
            return summary
        try:
            _, retried = self._ask(
                [
                    *messages,
                    {"role": "assistant", "content": reply},
                    {
                        "role": "user",
                        "content": "Source-specific number issues: "
                        + "; ".join(unsaid)
                        + ". Correct these using the assigned source; do not transfer numbers "
                        "between sources or work out new ones. Reply again with JSON only.",
                    },
                ]
            )
        except SummaryError:
            return summary
        return (
            retried
            if len(evidence_issues(retried, transcript, handwritten_text, context)) < len(unsaid)
            else summary
        )

    def _ask(self, messages: list[dict[str, str]]) -> tuple[str, Summary]:
        """The model's reply and the summary in it."""
        reply = self._chat(messages)
        try:
            return reply, parse_summary(reply)
        except SummaryError as error:
            # Local models occasionally break the format; one retry, told what was wrong,
            # almost always fixes it.
            reply = self._chat(
                [
                    *messages,
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": f"{error}. Reply again with JSON only."},
                ]
            )
            return reply, parse_summary(reply)

    def _chat(self, messages: list[dict[str, str]]) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "format": Summary.model_json_schema(),
            "options": {"num_ctx": self.num_ctx, "temperature": 0},
        }
        # Include both sources, schema, settings and correction history on every call.
        estimate = (
            len(json.dumps(body, ensure_ascii=False)) + CHARS_PER_TOKEN - 1
        ) // CHARS_PER_TOKEN + REPLY_TOKENS
        if estimate > self.num_ctx:
            raise OllamaError(
                f"The complete request is too long for the model's context (about {estimate} "
                f"tokens needed, {self.num_ctx} set). "
                f"Raise MEETING_NOTES_NUM_CTX to at least {estimate}."
            )
        response = self.post("/api/chat", body)
        if response.get("done_reason") == "length":
            raise OllamaError(
                f"The model ran out of context ({self.num_ctx} tokens) before finishing its "
                "reply. Raise MEETING_NOTES_NUM_CTX."
            )
        try:
            return str(response["message"]["content"])
        except (KeyError, TypeError):
            raise OllamaError(f"Ollama's reply had no message: {response!r:.200}") from None
