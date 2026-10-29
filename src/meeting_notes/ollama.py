"""Summarizer backed by a local model served by Ollama (https://ollama.com)."""

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict
from importlib import resources
from typing import Any, cast

from pydantic import BaseModel

from meeting_notes.commitments import action_item, commitment_texts, verify_commitments
from meeting_notes.figures import unsaid_numbers_in
from meeting_notes.meeting import Meeting
from meeting_notes.summary import (
    Commitments,
    Overview,
    Summary,
    SummaryError,
    TurnSelection,
    parse_response,
)
from meeting_notes.turns import parse_turns, selected_details, verify_selection

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


def default_details_prompt() -> str:
    return resources.files("meeting_notes").joinpath("prompts/details.md").read_text()


def default_commitments_prompt() -> str:
    return resources.files("meeting_notes").joinpath("prompts/commitments.md").read_text()


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
        details_prompt: str | None = None,
        commitments_prompt: str | None = None,
    ) -> None:
        self.model = model
        self.num_ctx = num_ctx
        self.post = post
        self.prompt = (prompt if prompt is not None else default_prompt()).replace(
            "{name}", my_name
        )
        self.think = think
        self.details_prompt = (
            details_prompt if details_prompt is not None else default_details_prompt()
        ).replace("{name}", my_name)
        self.commitments_prompt = (
            commitments_prompt if commitments_prompt is not None else default_commitments_prompt()
        ).replace("{name}", my_name)

    def summarize(self, meeting: Meeting, transcript: str) -> Summary:
        context = (
            f"Meeting: {meeting.title}\n"
            f"Date: {meeting.started_at:%A %Y-%m-%d %H:%M}\n"
            + (f"Others invited: {', '.join(meeting.attendees)}\n" if meeting.attendees else "")
            + f"\nTranscript:\n\n{transcript}"
        )
        turns = parse_turns(transcript)
        _, selection = self._ask(
            [
                {"role": "system", "content": self.details_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"turns": [asdict(turn) for turn in turns]}, ensure_ascii=False
                    ),
                },
            ],
            TurnSelection,
            lambda response: verify_selection(response.turn_ids, turns),
        )
        details = selected_details(selection.turn_ids, turns)
        commitments = self._ask_with_number_check(
            [
                {"role": "system", "content": self.commitments_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "meeting": {
                                "title": meeting.title,
                                "date": meeting.started_at.strftime("%A %Y-%m-%d %H:%M"),
                                "attendees": meeting.attendees,
                            },
                            "turns": [asdict(turn) for turn in turns],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            Commitments,
            commitment_texts,
            context,
            lambda response: verify_commitments(response, turns),
        )
        # Each task reads the original conversation; only code combines their outputs.
        overview = self._ask_with_number_check(
            [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": context},
            ],
            Overview,
            lambda response: [response.overview],
            context,
        )
        return Summary(
            overview=overview.overview,
            decisions=[decision.text for decision in commitments.decisions],
            action_items=[action_item(item) for item in commitments.action_items],
            details=details,
        )

    def _ask_with_number_check[T: BaseModel](
        self,
        messages: list[dict[str, str]],
        model: type[T],
        texts: Callable[[T], list[str]],
        said: str,
        verify: Callable[[T], None] | None = None,
    ) -> T:
        reply, result = self._ask(messages, model, verify)
        # The model sometimes works out a number nobody said, like the rest of a total.
        # One retry, told which; the retry is kept only if it has fewer such numbers, and
        # any left are flagged in the note.
        unsaid = unsaid_numbers_in(texts(result), said)
        if not unsaid:
            return result
        try:
            _, retried = self._ask(
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
                model,
                verify,
            )
        except SummaryError:
            return result
        return retried if len(unsaid_numbers_in(texts(retried), said)) < len(unsaid) else result

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
