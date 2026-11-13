"""Shared V11 request accounting and raw response rules for runtime and replay."""

import json
from typing import Any, cast

# Conservative English transcript estimate, including room for thinking and reply.
CHARS_PER_TOKEN = 3
REPLY_TOKENS = 4096

OVERSIZED_ERROR = "Complete request exceeds context; not sent"
LENGTH_ERROR = "Model ran out of context"
MISSING_MESSAGE_ERROR = "Ollama reply had no message"


def request_budget(body: dict[str, Any]) -> tuple[int, int]:
    """Validate runtime settings and count the complete serialized request body."""
    options = body.get("options")
    if not isinstance(options, dict):
        raise ValueError("Request options must be an object")
    options = cast(dict[str, Any], options)
    context = options.get("num_ctx")
    if type(context) is not int or context <= 0:
        raise ValueError("Request num_ctx must be a positive integer")
    if (
        set(options) != {"num_ctx", "temperature"}
        or type(options.get("temperature")) is not int
        or options["temperature"] != 0
        or type(body.get("think")) is not bool
        or body.get("stream") is not False
    ):
        raise ValueError("Request settings differ from the V11 runtime contract")
    model = body.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Request model must be a nonempty string")
    if not isinstance(body.get("format"), dict):
        raise ValueError("Request format must be an object")
    size = len(json.dumps(body, ensure_ascii=False, allow_nan=False))
    return (size + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN + REPLY_TOKENS, context


def response_result(response: dict[str, Any]) -> tuple[str | None, str | None]:
    """Keep raw content even on truncation; length failure takes precedence."""
    message = response.get("message")
    reply = (
        str(cast(dict[str, Any], message)["content"])
        if isinstance(message, dict) and "content" in message
        else None
    )
    error = (
        LENGTH_ERROR
        if response.get("done_reason") == "length"
        else MISSING_MESSAGE_ERROR
        if reply is None
        else None
    )
    return reply, error


def verify_exchange(
    request: dict[str, Any],
    response: dict[str, Any] | None,
    reply: str | None,
    error: str | None,
) -> None:
    """Reject exchanges that runtime could not have produced for this body."""
    estimate, context = request_budget(request)
    if estimate > context:
        if error != OVERSIZED_ERROR or response is not None or reply is not None:
            raise ValueError("Oversized request must be unsent with only its size failure")
        return
    if error == OVERSIZED_ERROR:
        raise ValueError("Claimed unsent size failure for a request that fits its context")
    if response is None:
        if error is None or reply is not None or error in (LENGTH_ERROR, MISSING_MESSAGE_ERROR):
            raise ValueError("Transport failure must have an error and no raw response or reply")
        return
    expected_reply, expected_error = response_result(response)
    if reply != expected_reply:
        raise ValueError("Saved reply differs from its raw response")
    if error != expected_error:
        raise ValueError("Saved response error differs from its raw response")
