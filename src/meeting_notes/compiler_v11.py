"""Pure V11 compilation and replay; no transport, original reads or inference.

Pass a Snapshot to retain complete effective transcript/notes including separators.
List[Source] callers retain every source but cannot reconstruct omitted separators.
Wrappers must save original/preprocessing inputs separately when they differ from the
effective snapshot. Evidence is JSON serializable and recomputed by replay().

Only narrow source-grounding errors are diagnosed in generated prose: wrong kinds,
invalid literal quotations, verbatim notes leakage and uncited numbers. Supported
paraphrase still needs semantic evaluation. CommitmentCheck documents its own limits.
Partial retractions are diagnosed for selected and omitted sources alike and saved as
uncertain commitment checks with full source/retraction warnings. Automatic acceptance
context is diagnostic evidence; exact supplied anchors remain in the saved draft and
among the resolved context spans. Timing spans remain the exact
model selections; complete source context comes from the saved snapshot. Automatic due
suffixes are narrow: recognized approximation/comparative/adverb boundaries stay
full-source review. These lexical checks cannot prove qualifier scope in arbitrary English.
"""

import re

from meeting_notes.commitments_v11 import CommitmentCheck, check, explicit_agreement, has_timing
from meeting_notes.comparison_v11 import Comparison, Resolution, epistemic_review
from meeting_notes.comparison_v11 import resolve as resolve_comparison
from meeting_notes.contract_v11 import Action, Draft, SupportedText
from meeting_notes.figures import unsaid_numbers
from meeting_notes.grounding import Record
from meeting_notes.spans_v11 import Anchor, Snapshot, Source, Span, resolve, source_errors, span
from meeting_notes.summary import ActionItem, Conflict, Summary


class TimingEvidence(Record):
    original_commitment_id: str
    span: Span


class Evidence(Record):
    snapshot: Snapshot
    draft: Draft
    comparison: Comparison
    context: str
    resolution: Resolution
    commitments: list[CommitmentCheck]
    timing_updates: list[TimingEvidence]
    agreements: list[Span]
    blocking: list[str]
    warnings: list[str]


class Checked(Record):
    summary: Summary | None
    blocking: list[str]
    warnings: list[str]
    evidence: Evidence


_DUE = re.compile(
    r"\b(?:(?:not\s+)?(?:before|after|by|on|at|within|in|until)|no later than|no earlier than)\s+"
    r"(?:(?:next|this|following|coming|at least|at most|about|around)\s+)?"
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|today|tomorrow|tonight|"
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"\d+|one|two|three|four|five|six|seven)\b|"
    r"\b(?:(?:next|this|following|coming)\s+)?"
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|today|tomorrow|tonight)\b",
    re.I,
)
_TIMING_MODIFIER = re.compile(
    r"\b(?:around|about|approximately|roughly|no|sooner|later|than|almost|just|right|"
    r"very|quite|rather|too|well|long|much|late|earliest|latest|at least|at most|"
    r"a little|a bit|sometime|some time|\w+ly)\b",
    re.I,
)


def _probe(text: str) -> Summary:
    return Summary(overview=text, key_points=[], decisions=[], action_items=[])


def _due(
    candidate: CommitmentCheck, source: Source, disputed: bool, later: list[Span]
) -> str | None:
    """Copy a complete suffix only; uncertain boundaries leave the full task intact."""
    timing = candidate.timing
    matches = list(_DUE.finditer(source.text))
    match = matches[0] if len(matches) == 1 else None
    if (
        timing is None
        or timing.source_id != source.id
        or match is None
        or later
        or disputed
        or candidate.owner is None
    ):
        return None
    before = source.text[: match.start()]
    if (
        not before.strip()
        or has_timing(before)
        or _TIMING_MODIFIER.search(before)
        or re.search(
            r"\b(?:if|unless|when|once|provided|depending|whether|and|or|but|not|only)\b",
            before,
            re.I,
        )
        or re.search(r"\b(?:and|but|whether)\b", source.text, re.I)
        or timing.start < match.start()
        or timing.start >= match.end()
    ):
        return None
    # Use the code-determined suffix, including relative dates/conditions/alternatives,
    # even if the supplied anchor only selected the weekday within it.
    return source.text[match.start() :].rstrip(".!?;")


def validate(
    draft: Draft,
    sources: list[Source] | Snapshot,
    comparison: Comparison,
    context: str = "",
) -> Checked:
    saved = sources if isinstance(sources, Snapshot) else Snapshot(sources=sources)
    source_list = saved.sources
    lookup = {s.id: s for s in source_list}
    resolution = resolve_comparison(comparison, source_list)
    blocking = list(dict.fromkeys([*source_errors(saved), *resolution.errors]))
    warnings: list[str] = []
    checks = [check(action, source_list) for action in draft.action_items]

    def findings(candidate: CommitmentCheck) -> None:
        if candidate.disposition == "rejected":
            blocking.append(f"Noncommitment {candidate.source_id}: {'; '.join(candidate.reasons)}")
        elif candidate.disposition == "uncertain":
            source = lookup.get(candidate.source_id)
            warnings.append(
                f"Commitment review required ({candidate.source_id}), "
                f"{source.speaker if source else 'Unknown speaker'}: “{candidate.task}” "
                + "; ".join(candidate.reasons)
                + "".join(f" Context ({s.source_id}): “{s.text}”" for s in candidate.context)
                + "".join(f" Retraction ({s.source_id}): “{s.text}”" for s in candidate.retractions)
            )

    selected: set[str] = set()
    for candidate in checks:
        if candidate.source_id in selected:
            blocking.append(f"Duplicate original commitment: {candidate.source_id}")
        selected.add(candidate.source_id)
        findings(candidate)

    # Omission checking uses exactly the same admissibility rules. Rejected selections
    # can't protect invented tasks during a correction, and never become fallback actions.
    spoken = [s for s in source_list if s.source == "transcript"]
    for index, source in enumerate(spoken):
        if source.id in selected:
            continue
        # An immediately preceding direct request can diagnose an omitted acceptance.
        # This synthetic check never creates an executable action from inferred context.
        prior_context = (
            [Anchor(source_id=spoken[index - 1].id, quote=spoken[index - 1].text)] if index else []
        )
        possible = check(
            Action(
                original_commitment_id=source.id,
                undertaking=Anchor(source_id=source.id, quote=source.text),
                context=prior_context,
                basis="explicit",
                disposition="committed",
                timing=None,
            ),
            source_list,
        )
        if possible.disposition == "admissible":
            blocking.append(f"Possible omitted commitment: {source.id}; recheck source undertaking")
        elif possible.disposition == "uncertain" and possible.retractions:
            # A partially cancelled coordination cannot silently vanish with the draft.
            # Keep the complete source and retraction outside the executable checklist.
            checks.append(possible)
            findings(possible)

    conflicts: list[Conflict] = []
    notes: list[str] = []
    disputed: set[str] = set()
    disputed_tasks: set[str] = set()
    for claim in resolution.claims:
        written = claim.note.span.text
        spoken = " ".join(a.span.text for a in claim.transcript)
        if claim.outcome == "conflicting":
            conflicts.append(
                Conflict(
                    topic="Unresolved cross-source claim",
                    transcript=spoken,
                    handwritten=written,
                )
            )
        elif claim.outcome != "uncertain":
            notes.append(written)
        needs_review = (
            claim.outcome == "uncertain"
            or bool(claim.note.meaning.unresolved)
            or any(
                a.meaning.unresolved or epistemic_review(claim.note.meaning, a.meaning)
                for a in claim.transcript
            )
        )
        if needs_review:
            warnings.append(
                f"Comparison review required ({claim.id}): handwritten: {written} "
                f"Transcript: {spoken or 'No match established.'} "
                f"Relation: {claim.outcome}. {claim.reason}"
            )
        if claim.outcome in ("conflicting", "uncertain"):
            disputed.update(a.span.source_id for a in claim.transcript)
            disputed_tasks.update(
                a.span.source_id for a in claim.transcript if a.kind == "commitment"
            )

    updates: list[TimingEvidence] = []
    by_action: dict[str, list[Span]] = {}
    for update in draft.timing_updates:
        original = lookup.get(update.original_commitment_id)
        if update.original_commitment_id not in selected:
            blocking.append(
                f"Timing update has no original action: {update.original_commitment_id}"
            )
        for anchor in update.evidence:
            try:
                resolved = resolve(anchor, source_list, "transcript")
                source = lookup[resolved.source_id]
                if (
                    original is None
                    or source.start <= original.start
                    or not has_timing(resolved.text)
                ):
                    blocking.append(f"Invalid later timing evidence: {resolved.source_id}")
                    continue
                updates.append(
                    TimingEvidence(
                        original_commitment_id=update.original_commitment_id, span=resolved
                    )
                )
                by_action.setdefault(update.original_commitment_id, []).append(resolved)
            except ValueError as error:
                blocking.append(str(error))

    actions: list[ActionItem] = []
    for candidate in checks:
        if candidate.disposition != "admissible":
            continue
        source = lookup[candidate.source_id]
        later = list(by_action.get(source.id, []))
        if candidate.timing and candidate.timing.source_id != source.id:
            later.append(candidate.timing)
        due = _due(candidate, source, source.id in disputed_tasks, later)
        review: list[str] = []
        if due is None and (candidate.timing or later or has_timing(source.text)):
            review.append(f"Timing is unassigned; review original commitment: {source.text}")
        if later:
            review.extend(
                f"Other spoken timing (association unverified), selected ({s.source_id}): "
                f"“{s.text}” Full source: “{lookup[s.source_id].text}”"
                for s in later
            )
        if source.id in disputed_tasks:
            review.append("Commitment needs cross-source review; see Conflicts and warnings.")
        actions.append(
            ActionItem(
                owner=candidate.owner, task=candidate.task or source.text, due=due, review=review
            )
        )

    agreements: list[Span] = []

    def section(name: str, items: list[SupportedText]) -> list[str]:
        output: list[str] = []
        quoted: set[str] = set()
        for item in items:
            evidence: list[Source] = []
            for identifier in dict.fromkeys(item.sources):
                source = lookup.get(identifier)
                if source is None or source.source != "transcript":
                    blocking.append(f"Invalid transcript source: {identifier}")
                else:
                    evidence.append(source)
            cited = "\n".join(s.text for s in evidence)
            if not item.text.strip():
                blocking.append(f"{name}: blank supported prose")
            if re.search(
                r"\bN\d+(?:\.C\d+)?\b|\bhandwritten\b|"
                r"\b(?:from|according to) (?:your |the )?notes\b",
                item.text,
                re.I,
            ):
                blocking.append(f"{name}: written-source prose in spoken section")
            for literal in re.findall(r'[“"]([^”"]+)[”"]', item.text):
                if literal not in cited:
                    blocking.append(f"{name}: quotation absent from cited transcript evidence")
            for source in source_list:
                literal = source.text.strip().rstrip(".!?;").casefold()
                if (
                    source.source == "notes"
                    and len(literal.split()) >= 3
                    and literal in item.text.casefold()
                    and literal not in cited.casefold()
                ):
                    blocking.append(f"{name}: verbatim notes prose cites transcript IDs")
            for number in unsaid_numbers(_probe(item.text), cited):
                own = "\n".join(s.text for s in source_list if s.source == "transcript")
                other = "\n".join(s.text for s in source_list if s.source == "notes")
                reason = (
                    "elsewhere in transcript"
                    if not unsaid_numbers(_probe(number), own)
                    else "in notes"
                    if not unsaid_numbers(_probe(number), other)
                    else "only in metadata"
                    if not unsaid_numbers(_probe(number), context)
                    else "in neither source nor metadata"
                )
                warnings.append(f"{name}: number {number} absent from cited evidence ({reason})")
            if name == "decisions":
                agreements.extend(
                    span(s, 0, len(s.text)) for s in evidence if explicit_agreement(s.text)
                )
            removed = set(item.sources) & (selected | disputed)
            if removed:
                if set(item.sources) & disputed:
                    output.append(
                        "Cross-source accounts remain unresolved; "
                        "see Conflicts and review warnings."
                    )
                for source in evidence:
                    if source.id not in quoted and (
                        source.id not in removed or explicit_agreement(source.text)
                    ):
                        output.append(f"{source.speaker or 'Transcript'}: “{source.text}”")
                        quoted.add(source.id)
            else:
                output.append(item.text)
        return list(dict.fromkeys(output))

    overview = section("overview", draft.overview)
    points = section("key_points", draft.key_points)
    decisions = section("decisions", draft.decisions)
    cited_agreements = {s.source_id for s in agreements}
    for source in source_list:
        if (
            source.source == "transcript"
            and explicit_agreement(source.text)
            and source.id not in cited_agreements
        ):
            blocking.append(
                f"Possible omitted agreement: {source.id}; cite independent agreement in decisions"
            )
    # A partial disputed span cannot erase other content in its original statement.
    for source in source_list:
        if source.id in disputed and any(
            a.span.source_id == source.id and a.span.text != source.text
            for claim in resolution.claims
            if claim.outcome in ("conflicting", "uncertain")
            for a in claim.transcript
        ):
            points.append(f"Transcript (contains unresolved account): “{source.text}”")
    if actions:
        overview.append("See Action items for spoken commitments and timing.")
    if not any((overview, points, decisions, notes, conflicts, actions, warnings)):
        blocking.append("No supported content was generated")
    blocking = list(dict.fromkeys(blocking))
    warnings = list(dict.fromkeys(warnings))
    summary = (
        None
        if blocking
        else Summary(
            overview=" ".join(overview) or "See the supported items and review evidence below.",
            key_points=points,
            decisions=decisions,
            action_items=actions,
            notes_context=notes,
            conflicts=conflicts,
        )
    )
    return Checked(
        summary=summary,
        blocking=blocking,
        warnings=warnings,
        evidence=Evidence(
            snapshot=saved,
            draft=draft,
            comparison=comparison,
            context=context,
            resolution=resolution,
            commitments=checks,
            timing_updates=updates,
            agreements=agreements,
            blocking=blocking,
            warnings=warnings,
        ),
    )


def replay(evidence: Evidence) -> Checked:
    """Recompute saved evidence; refuse altered findings/spans even if inputs compile."""
    checked = validate(evidence.draft, evidence.snapshot, evidence.comparison, evidence.context)
    if checked.evidence != evidence:
        checked.blocking.append("Saved V11 compilation evidence differs from recomputation")
        checked.summary = None
    return checked


def correction_errors(previous: Checked, candidate: Checked) -> list[str]:
    """Integration selection guard; never splice drafts or protect rejected actions.

    A correction must be fully valid and preserve admitted undertakings/timing and
    independently cited agreements. Only a fully valid previous Checked may serve
    as fallback. The caller owns attempt selection and persists its selection findings.
    """
    errors = list(candidate.blocking)
    if candidate.summary is None and not errors:
        errors.append("Correction has no valid compiled summary")
    for old in previous.evidence.commitments:
        if old.disposition != "admissible":
            continue
        if not any(
            new.disposition == "admissible"
            and new.undertaking == old.undertaking
            and new.task == old.task
            and new.timing == old.timing
            for new in candidate.evidence.commitments
        ):
            errors.append(f"Correction lost admissible commitment/timing: {old.source_id}")
    for agreement in previous.evidence.agreements:
        if agreement not in candidate.evidence.agreements:
            errors.append(f"Correction lost independent agreement: {agreement.source_id}")
    admissible = {
        c.source_id for c in previous.evidence.commitments if c.disposition == "admissible"
    }
    for timing in previous.evidence.timing_updates:
        if (
            timing.original_commitment_id in admissible
            and timing not in candidate.evidence.timing_updates
        ):
            errors.append(f"Correction lost timing evidence: {timing.span.source_id}")
    return list(dict.fromkeys(errors))
