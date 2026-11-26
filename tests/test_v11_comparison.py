import pytest
from pydantic import ValidationError

from meeting_notes.comparison_v11 import (
    Account,
    Claim,
    Comparison,
    Meaning,
    claim_ids,
    request_schema,
    resolve,
    validate,
)
from meeting_notes.spans_v11 import Anchor, snapshot


def account(identifier: str, text: str, **dimensions: str | None) -> Account:
    values: dict[str, str | None] = dict.fromkeys(["quantity", "unit", "period", "scope", "status"])
    values.update(dimensions)
    return Account(
        source_id=identifier,
        quote=text,
        kind="fact",
        meaning=Meaning(subject="service", unresolved=[], **values),
    )


def additional(*notes: Account) -> Comparison:
    return Comparison(
        claims=[
            Claim(note=note, transcript=[], outcome="additional", reason="No counterpart.")
            for note in notes
        ]
    )


def test_claim_anchors_retain_multiclaim_separators_in_code() -> None:
    saved = snapshot(
        "[0:00:01] Mira: The queue is green.",
        "Release: the queue is green, and the bill is pending, review the guide.",
    )
    quotes = ["Release", "the queue is green", "the bill is pending", "review the guide"]
    response = additional(*(account("N1", quote) for quote in quotes))
    response.claims[0].note.kind = "context"
    response.claims[-1].note.kind = "request"
    result = resolve(response, saved.sources)
    assert not result.errors
    assert [c.id for c in result.claims] == ["N1.C1", "N1.C2", "N1.C3", "N1.C4"]
    pieces = [c.note.span for c in result.claims] + result.gaps
    assert "".join(p.text for p in sorted(pieces, key=lambda s: s.start)) == saved.notes
    assert [g.text for g in result.gaps] == [": ", ", and ", ", ", "."]
    for piece in pieces:
        assert saved.notes is not None
        assert saved.notes[piece.absolute_start : piece.absolute_end] == piece.text


@pytest.mark.parametrize("gap", [" not ", " maybe ", " unless ", " if ", " or ", " but ", " only "])
def test_semantic_qualifier_gaps_are_rejected(gap: str) -> None:
    saved = snapshot("", f"alpha{gap}beta")
    response = additional(account("N1", "alpha"), account("N1", "beta"))
    assert any("Uncovered semantic" in e for e in validate(response, saved.sources))


def test_uncovered_heading_and_nonfactual_request_need_claims() -> None:
    saved = snapshot("", "Review priorities: the queue is green, ask about backups")
    assert validate(additional(account("N1", "the queue is green")), saved.sources)
    response = additional(
        account("N1", "Review priorities"),
        account("N1", "the queue is green"),
        account("N1", "ask about backups"),
    )
    response.claims[0].note.kind = "context"
    response.claims[2].note.kind = "request"
    assert not validate(response, saved.sources)


def test_repeated_literals_require_explicit_occurrence() -> None:
    saved = snapshot("", "ready, and ready")
    response = additional(account("N1", "ready"), account("N1", "ready"))
    assert any("Repeated anchor" in e for e in validate(response, saved.sources))
    response.claims[0].note.occurrence = 1
    response.claims[1].note.occurrence = 2
    assert not validate(response, saved.sources)
    assert [c.note.span.start for c in resolve(response, saved.sources).claims] == [0, 11]


@pytest.mark.parametrize(
    ("quotes", "expected"),
    [
        (["alpha", "absent"], "Anchor absent"),
        (["alpha", "alpha"], "duplicate"),
        (["alpha beta", "beta"], "overlapping"),
        (["beta", "alpha"], "Reversed"),
        ([" "], "Empty anchor"),
    ],
)
def test_invalid_anchor_maps_fail_closed(quotes: list[str], expected: str) -> None:
    saved = snapshot("", "alpha beta")
    errors = validate(additional(*(account("N1", quote) for quote in quotes)), saved.sources)
    assert expected.lower() in " ".join(errors).lower()


def test_empty_anchor_rejected_by_model() -> None:
    with pytest.raises(ValidationError):
        Anchor(source_id="N1", quote="")


def test_original_passage_order_and_absolute_offsets_are_preserved() -> None:
    saved = snapshot("", "  heading\n\nnext item  \n")
    response = additional(account("N1", "heading"), account("N2", "next item"))
    result = resolve(response, saved.sources)
    assert not result.errors
    assert saved.notes == "  heading\n\nnext item  \n"
    assert result.claims[1].note.span.absolute_start == 11
    response.claims.reverse()
    assert any("Reversed" in e for e in validate(response, saved.sources))


def test_related_distinct_retains_period_and_scope_without_matching() -> None:
    saved = snapshot(
        "[0:00:01] Mira: Regional service costs 220 dollars in April.",
        "Global service costs 330 dollars in May.",
    )
    response = Comparison(
        claims=[
            Claim(
                note=account(
                    "N1",
                    saved.sources[1].text,
                    quantity="330",
                    unit="dollars",
                    period="May",
                    scope="Global",
                ),
                transcript=[
                    account(
                        "T1",
                        saved.sources[0].text,
                        quantity="220",
                        unit="dollars",
                        period="April",
                        scope="Regional",
                    )
                ],
                outcome="related-distinct",
                reason="Different stated scopes and periods.",
            )
        ]
    )
    assert not validate(response, saved.sources)
    response.claims[0].outcome = "additional"
    assert any("unmatched" in e for e in validate(response, saved.sources))


def test_equal_numbers_do_not_create_a_relation_or_invent_units() -> None:
    saved = snapshot("[0:00:01] Mira: The archive has 220 entries.", "The service costs 220.")
    response = additional(account("N1", saved.sources[1].text, quantity="220"))
    assert not validate(response, saved.sources)
    assert response.claims[0].transcript == []
    assert response.claims[0].note.meaning.unit is None


@pytest.mark.parametrize("value", ["", " ", "null", " NULL ", "None"])
@pytest.mark.parametrize("dimension", ["subject", "quantity", "unit", "period", "scope", "status"])
def test_blank_and_literal_null_dimensions_are_invalid(dimension: str, value: str) -> None:
    saved = snapshot("", "The queue is green")
    note = account("N1", saved.sources[0].text)
    setattr(note.meaning, dimension, value)
    assert any("Blank/literal-null" in e for e in validate(additional(note), saved.sources))


def test_absence_and_unresolved_extraction_are_different_and_do_not_invent_values() -> None:
    saved = snapshot("", "The service costs 220 dollars")
    note = account("N1", saved.sources[0].text)
    assert any("Explicit quantity" in e for e in validate(additional(note), saved.sources))
    note.meaning.unresolved = ["quantity", "unit"]
    assert not validate(additional(note), saved.sources)
    assert note.meaning.quantity is None and note.meaning.unit is None
    note.meaning.quantity = "220"
    assert any("Unresolved dimension" in e for e in validate(additional(note), saved.sources))


@pytest.mark.parametrize(
    ("text", "period"),
    [
        ("Model Q7 is ready", None),
        ("Model RX-4090 is ready", None),
        ("The launch is in 2027", "2027"),
        ("The launch is on 2027-04-12", "2027-04-12"),
    ],
)
def test_identifier_and_extracted_period_digits_are_not_missing_quantities(
    text: str,
    period: str | None,
) -> None:
    saved = snapshot("", text)
    note = account("N1", text, period=period)
    assert not validate(additional(note), saved.sources)
    assert note.meaning.quantity is None


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Confirmed", "confirmed"),
        ("approved", "confirmed"),
    ],
)
def test_compatible_literal_status_wording_does_not_block_factual_conflict(
    left: str, right: str
) -> None:
    saved = snapshot(
        f"[0:00:01] Mira: The {right} cost is 220 dollars", f"The {left} cost is 330 dollars"
    )
    response = Comparison(
        claims=[
            Claim(
                note=account(
                    "N1", saved.sources[1].text, quantity="330", unit="dollars", status=left
                ),
                transcript=[
                    account(
                        "T1", saved.sources[0].text, quantity="220", unit="dollars", status=right
                    )
                ],
                outcome="conflicting",
                reason="Two accounts of the same cost.",
            )
        ]
    )
    assert not validate(response, saved.sources)


@pytest.mark.parametrize(("left", "right"), [("estimate", "approved"), ("tentative", "confirmed")])
def test_obvious_epistemic_mismatch_needs_visible_review(left: str, right: str) -> None:
    saved = snapshot(
        f"[0:00:01] Mira: The {right} cost is 220 dollars", f"The {left} cost is 220 dollars"
    )
    response = Comparison(
        claims=[
            Claim(
                note=account(
                    "N1", saved.sources[1].text, quantity="220", unit="dollars", status=left
                ),
                transcript=[
                    account(
                        "T1", saved.sources[0].text, quantity="220", unit="dollars", status=right
                    )
                ],
                outcome="consistent",
                reason="Epistemic relation unresolved.",
            )
        ]
    )
    assert any("tentative/confirmed" in e for e in validate(response, saved.sources))
    response.claims[0].outcome = "uncertain"
    assert not validate(response, saved.sources)


def test_relation_requires_accounts_and_nonfactual_notes_cannot_conflict() -> None:
    saved = snapshot("[0:00:01] Mira: The queue is green", "Ask about the queue")
    response = additional(account("N1", saved.sources[1].text))
    response.claims[0].outcome = "conflicting"
    response.claims[0].note.kind = "request"
    errors = validate(response, saved.sources)
    assert any("requires transcript" in e for e in errors)
    assert any("Nonfactual" in e for e in errors)


def test_runtime_source_kinds_and_quotes_still_checked() -> None:
    saved = snapshot("[0:00:01] Mira: The queue is green", "The queue is blue")
    response = additional(account("T1", "The queue is green"))
    assert any("Invalid notes source" in e for e in validate(response, saved.sources))
    assert request_schema(saved.sources)["$defs"]["Account"]["properties"]["source_id"]["enum"] == [
        "T1",
        "N1",
    ]
    with pytest.raises(ValueError):
        claim_ids(response, saved.sources)
