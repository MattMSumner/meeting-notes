"""Narrow, English-language commitment diagnostics, not a semantic classifier.

Recognized undertakings use agent + future/accepted-task verbs, 'on me'/'leave ...
to/with me', or a short acceptance of an anchored earlier direct task request
('can/could/will/would you [please] <task verb>', or 'please <task verb>'). Factual
questions and indirect/unrecognized requests stay review, even with a 'Yes'. Known descriptive
cost/status/prediction, questions/proposals, quoted examples, negated undertakings
and same-speaker retractions are rejected. Other forms stay attributed review.

The task-verb vocabulary limits automatic admission, not what can be retained for
review. Names/agency, sarcasm, reported speech without markers, distant anaphora,
entailment and completeness remain evaluation concerns. Retractions recognize an
immediately following same-speaker 'scratch/cancel that', or later explicit negatives
repeating the same task predicate and object after removal of articles/timing. Accepted
requests use the requested task and the accepting speaker, not the bare acceptance.
A leading cancellation applies to the previous source, not a new undertaking after it.
Literal partial coordination cancellations retain the full original and retraction for
review; no replacement clauses are synthesized. Ellipsis, paraphrased cancellations and
general clause scope remain semantic evaluation concerns. Shared verbs or dates alone
never establish retraction or cross-source claim identity. Conditions aren't negation
of a task.
"""

import re
from typing import Literal

from meeting_notes.contract_v11 import Action
from meeting_notes.grounding import Record
from meeting_notes.spans_v11 import Source, Span, formatting_gap, resolve, span

_VERBS = (
    r"send|review|test|compare|verify|check|tag|prepare|update|write|share|schedule|ask|"
    r"contact|investigate|fix|create|publish|follow up|deliver|handle|own|take care of|"
    r"book|arrange|file|compile|draft|implement|deploy|run|finish|process|analyze|"
    r"organise|organize|call|pay|bring|provide|coordinate|collect|confirm|upload|sign|"
    r"complete|migrate|audit|recheck|measure|monitor|record"
)
_NAME = r"[A-Z][\w'-]*(?: [A-Z][\w'-]*)?"
_AGENT = rf"(?P<agent>(?i:I|we)|{_NAME})"
_FUTURE = r"(?i:will|shall|(?:am|are|is) going to|(?:have |has )?agreed to|promised to)"
_POSITIVE = re.compile(rf"\b{_AGENT}(?:\s+{_FUTURE}|(?i:'ll|’ll))\s+(?P<verb>(?i:{_VERBS}))\b")
_NEGATIVE = re.compile(
    r"\b(?:will not|won't|won’t|shall not|cannot|can't|can’t|not going to|"
    r"not committing|not a commitment)\b",
    re.I,
)
_PROPOSAL = re.compile(r"\b(?:could|should|might|maybe|perhaps|suggest|propose)\b", re.I)
_EXAMPLE = re.compile(
    r"\b(?:for example|as an example|only an example|just an example|hypothetical|"
    r"only a quote|just a quote|quoted example)\b|^Example\s*:|"
    r"[\"“'‘](?:I|we|\w+) (?:will|shall)\b",
    re.I,
)
_META_NEGATION = re.compile(
    r"^(?:Actually,?\s+)?(?:I (?:am not committing|am not promising|did not agree|"
    r"did not say|never said)|I'm not (?:committing|promising)|"
    r"(?:that|this) (?:is|was) not a commitment)\b",
    re.I,
)
_DESCRIPTION = re.compile(
    r"\b(?:costs?|priced?|prices?|status|completed|finished|already|"
    r"has been|have been|is ready|are ready|is complete|are complete|"
    r"will (?:be|cost|increase|decrease|rise|fall|remain|rain))\b|"
    r"^(?:I|we|\w+) (?:sent|reviewed|tested|checked|delivered|deployed)\b",
    re.I,
)
_CANCEL = re.compile(r"\b(?:scratch that|cancel that|never mind|withdraw that)\b", re.I)
_DISCLAIMER = re.compile(
    r"^(?:(?:that|it|the previous statement) (?:was|is) )?"
    r"(?:just|only) (?:an example|a quote)[.! ]*$|"
    r"^(?:I am not committing to that|I'm not committing to that|"
    r"that is not a commitment|that was not a commitment)[.! ]*$",
    re.I,
)
_ACCEPT = re.compile(r"^(?:yes|agreed|on it|consider it done|will do)[.! ,]*$", re.I)
_REQUEST = re.compile(
    rf"^(?:(?:can|could|will|would) you\s+(?:please\s+)?|please\s+)"
    rf"(?P<verb>{_VERBS})\b(?P<object>.*)",
    re.I,
)
_IMPLIED = re.compile(r"\b(?:is on me|leave .+ (?:with|to) me)\b", re.I)
_RETRACTION = re.compile(
    rf"^(?:(?:actually|sorry),?\s+)?{_AGENT}\s+(?:will not|won't|won’t|cannot|can't)\s+"
    rf"(?P<verb>{_VERBS})\b(?P<object>.*)",
    re.I,
)
_TIMING = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|today|tomorrow|"
    r"tonight|days?|weeks?|months?|years?|hours?|minutes?|January|February|March|"
    r"April|May|June|July|August|September|October|November|December|after|before|"
    r"when|once|until|by|soon|later)\b|\b\d{1,4}[-/:]\d{1,2}",
    re.I,
)


class CommitmentCheck(Record):
    source_id: str
    disposition: Literal["admissible", "uncertain", "rejected"]
    reasons: list[str]
    undertaking: Span | None
    context: list[Span]
    retractions: list[Span]
    timing: Span | None
    owner: str | None
    owner_evidence: list[Span]
    task: str | None


def _task_words(text: str, agent: str) -> tuple[str, ...]:
    # Keep coordination intact. Normalizing a repeated same-agent future only permits
    # literal task matching; it does not split or rewrite the source for publication.
    text = _POSITIVE.sub(
        lambda match: match["verb"] if match["agent"].casefold() == agent else match[0], text
    )
    text = re.split(r"\b(?:if|unless|when|once|provided)\b", text, flags=re.I)[0]
    text = _TIMING.sub(" ", text)
    return tuple(
        word
        for word in re.findall(r"[a-z]+", text.lower())
        if word not in {"the", "a", "an", "by", "on", "at", "this", "next"}
    )


def _partial_task(original: tuple[str, ...], negative: tuple[str, ...]) -> bool:
    """Recognize an exact conjunct only; never manufacture the surviving task."""
    conjunctions = {"and", "but", "or"}
    if not negative or not conjunctions.intersection(original):
        return False
    for start in range(len(original) - len(negative) + 1):
        end = start + len(negative)
        if (
            original[start:end] == negative
            and (start == 0 or original[start - 1] in conjunctions)
            and (end == len(original) or original[end] in conjunctions)
            and original != negative
        ):
            return True
    return False


def _retractions(
    source: Source, sources: list[Source], request: re.Match[str] | None
) -> tuple[list[Span], bool]:
    spoken = [s for s in sources if s.source == "transcript"]
    index = next(i for i, s in enumerate(spoken) if s.id == source.id)
    positive = _POSITIVE.search(source.text)

    agent = positive["agent"].casefold() if positive else "i"
    task = (
        source.text[positive.start() :]
        if positive
        else request["verb"] + request["object"]
        if request
        else ""
    )
    original = _task_words(task, agent)
    result: list[Span] = []
    whole = False
    cancel = _CANCEL.search(source.text)
    if cancel and positive and cancel.start() > positive.start():
        # Within-source revisions cannot safely be split into replacement task prose.
        result.append(span(source, 0, len(source.text)))
    for position, later in enumerate(spoken[index + 1 :], start=index + 1):
        # Anonymous passages cannot establish same-speaker identity.
        if source.speaker is None or later.speaker != source.speaker:
            continue
        adjacent = position == index + 1
        negative = _RETRACTION.search(later.text)
        if adjacent and (_CANCEL.match(later.text) or _DISCLAIMER.fullmatch(later.text)):
            result.append(span(later, 0, len(later.text)))
            whole = True
        elif negative and original and agent == negative["agent"].casefold():
            words = _task_words(negative["verb"] + negative["object"], agent)
            same_task = original == words and (len(words) > 1 or adjacent)
            if same_task or _partial_task(original, words):
                result.append(span(later, 0, len(later.text)))
                whole = whole or same_task
    return result, bool(result) and not whole


def check(action: Action, sources: list[Source]) -> CommitmentCheck:
    """Validate anchors and diagnose admissibility against complete source context."""
    reasons: list[str] = []
    undertaking: Span | None = None
    context: list[Span] = []
    timing: Span | None = None
    for anchor, target in [
        (action.undertaking, "undertaking"),
        *[(a, "context") for a in action.context],
    ]:
        try:
            resolved = resolve(anchor, sources, "transcript")
            if target == "undertaking":
                undertaking = resolved
            else:
                context.append(resolved)
        except ValueError as error:
            reasons.append(str(error))
    primary = next(
        (s for s in sources if s.id == action.original_commitment_id and s.source == "transcript"),
        None,
    )
    if primary is None:
        reasons.append(f"Invalid transcript source: {action.original_commitment_id}")
    if undertaking and undertaking.source_id != action.original_commitment_id:
        reasons.append("Undertaking must anchor the original commitment")
    if primary and undertaking and undertaking.source_id == primary.id:
        if not formatting_gap(primary.text[: undertaking.start]) or not formatting_gap(
            primary.text[undertaking.end :]
        ):
            reasons.append("Undertaking must retain the complete statement and its qualifiers")
    if action.timing:
        try:
            timing = resolve(action.timing, sources, "transcript")
            if not _TIMING.search(timing.text):
                reasons.append("Timing anchor has no recognized timing expression")
            timed = next(s for s in sources if s.id == timing.source_id)
            if primary and timed.id != primary.id and timed.start <= primary.start:
                reasons.append("External timing must follow the original commitment")
        except ValueError as error:
            reasons.append(str(error))
    result = CommitmentCheck(
        source_id=action.original_commitment_id,
        disposition="rejected" if reasons else "uncertain",
        reasons=reasons,
        undertaking=undertaking,
        context=context,
        retractions=[],
        timing=timing,
        owner=None,
        owner_evidence=[],
        task=primary.text if primary else None,
    )
    if reasons or primary is None:
        return result
    text = primary.text
    positive = _POSITIVE.search(text)
    accepted: list[Source] = []
    if _ACCEPT.fullmatch(text):
        accepted = [
            s
            for s in sources
            if s.source == "transcript"
            and any(a.source_id == s.id and a.text == s.text for a in context)
            and s.start < primary.start
            and _REQUEST.match(s.text)
            and not _EXAMPLE.search(s.text)
        ]
    request = _REQUEST.match(accepted[0].text) if len(accepted) == 1 else None
    if request:
        result.task = f"Request: {accepted[0].text} Acceptance: {primary.text}"
    result.retractions, partial = _retractions(primary, sources, request)
    rejection = (
        "Same-speaker retraction or example disclaimer"
        if result.retractions and not partial
        else "Quoted or hypothetical example"
        if _EXAMPLE.search(text)
        else "Question or unanswered proposal"
        if "?" in text or (not positive and _PROPOSAL.search(text))
        else "Negated undertaking"
        if _META_NEGATION.search(text) or (not positive and _NEGATIVE.search(text))
        else "Descriptive fact, status or prediction"
        if not positive and _DESCRIPTION.search(text)
        else None
    )
    if rejection:
        result.disposition = "rejected"
        result.reasons.append(rejection)
        return result
    recognized = bool(positive or _IMPLIED.search(text) or request)
    # A hedge before the undertaking leaves it for review. Negated/conditional
    # prerequisites (if not/unless) don't negate the positive task predicate.
    hedge = bool(re.search(r"\b(?:maybe|perhaps|might|could)\b", text, re.I))
    if partial:
        result.reasons.append("Retraction scope unresolved; retain full undertaking and retraction")
    if action.disposition == "committed" and recognized and not hedge and not partial:
        result.disposition = "admissible"
        result.reasons.append("Recognized source undertaking; semantic evaluation still required")
    else:
        result.reasons.append("Admissibility unresolved; attributed review only")
    if positive:
        agent = positive["agent"]
        result.owner = primary.speaker if agent.casefold() in ("i", "we") else agent
        agents = {m["agent"].casefold() for m in _POSITIVE.finditer(text)}
        if agent.casefold() == "we" or len(agents) > 1:
            result.owner = None
    elif _IMPLIED.search(text) or request:
        result.owner = primary.speaker
    if result.owner == "Them":
        introductions: list[tuple[str, Span]] = []
        for source in sources:
            if (
                source.source != "transcript"
                or source.turn != primary.turn
                or source.speaker != primary.speaker
            ):
                continue
            for pattern in (
                r"(?:^|\s)([A-Z][\w'-]*(?: [A-Z][\w'-]*)?) here\.",
                r"(?i:I am|I'm|this is|my name is) "
                r"([A-Z][\w'-]*(?: [A-Z][\w'-]*)?)(?=[.!?,]|$)",
            ):
                for match in re.finditer(pattern, source.text):
                    introductions.append((match[1], span(source, match.start(), match.end())))
        result.owner_evidence = [evidence for _, evidence in introductions]
        if len({name for name, _ in introductions}) == 1:
            result.owner = introductions[0][0]
    return result


def has_timing(text: str) -> bool:
    return bool(_TIMING.search(text))


def explicit_agreement(text: str) -> bool:
    return bool(re.match(r"^(?:Agreed\s*[,.:]|We (?:agreed|decided)\b)", text, re.I))
