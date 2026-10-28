"""Summarizer backed by a local model served by Ollama (https://ollama.com)."""

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from importlib import resources
from typing import Any, cast

from pydantic import BaseModel

from meeting_notes.figures import unsaid_numbers, verify_figures
from meeting_notes.meeting import Meeting
from meeting_notes.summary import Figures, Narrative, Summary, SummaryError, parse_response

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


def default_figures_prompt() -> str:
    return resources.files("meeting_notes").joinpath("prompts/figures.md").read_text()


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
        figures_prompt: str | None = None,
    ) -> None:
        self.model = model
        self.num_ctx = num_ctx
        self.post = post
        self.prompt = (prompt if prompt is not None else default_prompt()).replace(
            "{name}", my_name
        )
        self.think = think
        self.figures_prompt = (
            figures_prompt if figures_prompt is not None else default_figures_prompt()
        ).replace("{name}", my_name)

    def summarize(self, meeting: Meeting, transcript: str) -> Summary:
        context = (
            f"Meeting: {meeting.title}\n"
            f"Date: {meeting.started_at:%A %Y-%m-%d %H:%M}\n"
            + (f"Others invited: {', '.join(meeting.attendees)}\n" if meeting.attendees else "")
            + f"\nTranscript:\n\n{transcript}"
        )
        _, evidence = self._ask(
            [
                {"role": "system", "content": self.figures_prompt},
                {"role": "user", "content": context},
            ],
            Figures,
            lambda response: verify_figures(response.figures, transcript),
        )
        messages = [
            {"role": "system", "content": self.prompt},
            {
                "role": "user",
                "content": context + f"\n\nVerified figures:\n{evidence.model_dump_json()}",
            },
        ]
        reply, narrative = self._ask(messages, Narrative)
        summary = Summary(**narrative.model_dump(), figures=evidence.figures)
        # The model sometimes works out a number nobody said, like the rest of a total.
        # One retry, told which; the retry is kept only if it has fewer such numbers, and
        # any left are flagged in the note.
        # Generated evidence must never become the source for the unsaid-number check.
        said = context
        unsaid = unsaid_numbers(summary, said)
        if not unsaid:
            return summary
        try:
            _, retried_narrative = self._ask(
                [
                    *messages,
                    {"role": "assistant", "content": reply},
                    {
                        "role": "user",
                        "content": f"Nobody said these numbers: {', '.join(unsaid)}. Use only "
                        "numbers someone said, and don't work out new ones. Reply again with "
                        "JSON only.",
                    },
                ],
                Narrative,
            )
        except SummaryError:
            return summary
        retried = Summary(**retried_narrative.model_dump(), figures=evidence.figures)
        return retried if len(unsaid_numbers(retried, said)) < len(unsaid) else summary

    def _ask[T: BaseModel](
        self,
        messages: list[dict[str, str]],
        model: type[T],
        verify: Callable[[T], None] | None = None,
    ) -> tuple[str, T]:
        """Parse and verify a structured reply, with one correction attempt."""

        def read(reply: str) -> T:
            response = parse_response(reply, model)
            if verify is not None:
                verify(response)
            return response

        schema = model.model_json_schema()
        reply = self._chat(messages, schema)
        try:
            return reply, read(reply)
        except SummaryError as error:
            # One chance to correct malformed output or unverified evidence.
            reply = self._chat(
                [
                    *messages,
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": f"{error}. Reply again with JSON only."},
                ],
                schema,
            )
            return reply, read(reply)

    def _chat(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> str:
        # Check every request, including corrections: Ollama can silently truncate input.
        estimate = (
            sum(len(m["content"]) for m in messages) + len(json.dumps(schema))
        ) // CHARS_PER_TOKEN + REPLY_TOKENS
        if estimate > self.num_ctx:
            raise OllamaError(
                f"The transcript is too long for the model's context (about {estimate} tokens "
                f"needed, {self.num_ctx} set), so the summary would miss part of it. "
                f"Raise MEETING_NOTES_NUM_CTX to at least {estimate}."
            )
        response = self.post(
            "/api/chat",
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "think": self.think,
                # Constrains the reply to the schema, so it's almost always valid.
                "format": schema,
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
