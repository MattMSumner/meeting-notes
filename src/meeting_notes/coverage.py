"""Narrow omission diagnostic, not a classifier or a source of generated tasks."""

import re

from meeting_notes.compiler_v4 import Source

# Deliberately limited to explicit first-person task verbs. Predictions such as
# "I will be away" and unrecognized paraphrases are outside this diagnostic.
_EXPLICIT = re.compile(
    r"^(?:I will|I'll|I’ll|I shall|I am going to|I'm going to|I’m going to)\s+"
    r"(?:send|review|test|compare|verify|check|tag|prepare|update|write|share|"
    r"schedule|ask|contact|investigate|fix|create|publish|follow up)\b",
    re.I,
)
_UNCERTAIN = re.compile(
    r"\b(?:maybe|perhaps|might|could|if|unless|whether|suppose|hypothetical|"
    r"example|quote|not|never|won't|cannot|can't)\b|[?\"“”]",
    re.I,
)
_RETRACTED = re.compile(
    r"\b(?:not committing|not a commitment|won't|will not|can't|cannot|"
    r"never mind|scratch that|cancel that|only an example|just an example|"
    r"only a quote|just a quote)\b",
    re.I,
)


def uncovered_commitments(sources: list[Source], selected: set[str]) -> list[Source]:
    missing: list[Source] = []
    spoken = [s for s in sources if s.source == "transcript"]
    for index, source in enumerate(spoken):
        if source.id in selected or not _EXPLICIT.search(source.text):
            continue
        if _UNCERTAIN.search(source.text):
            continue
        # An adjacent same-speaker disclaimer can retract the apparent promise.
        neighbors = spoken[max(0, index - 1) : index] + spoken[index + 1 : index + 2]
        if any(s.speaker == source.speaker and _RETRACTED.search(s.text) for s in neighbors):
            continue
        missing.append(source)
    return missing


_AGREEMENT = re.compile(r"^(?:Agreed\s*[,.:]|We (?:agreed|decided)\b)", re.I)


def uncovered_agreements(sources: list[Source], selected: set[str]) -> list[Source]:
    """Flag explicit agreement markers for correction, never generate decisions."""
    spoken = [s for s in sources if s.source == "transcript"]
    missing: list[Source] = []
    for index, source in enumerate(spoken):
        if source.id in selected or not _AGREEMENT.search(source.text):
            continue
        if _UNCERTAIN.search(source.text):
            continue
        neighbors = spoken[max(0, index - 1) : index] + spoken[index + 1 : index + 2]
        if any(s.speaker == source.speaker and _RETRACTED.search(s.text) for s in neighbors):
            continue
        missing.append(source)
    return missing
