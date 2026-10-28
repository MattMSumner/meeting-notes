Select complete source sentences containing meaningful figures, constraints and
availability from this meeting transcript. They will be quoted directly in the note.
Reply with JSON only: an object with a "details" list. Use an empty list if there are none.

For each distinct claim about a price, budget, target, quantity, measurement, constraint
or availability:
- "speaker": the EXACT transcript label ("{name}" or "Them"). Do not infer a name.
- "subject": a neutral noun phrase naming the topic, without adding numbers or
  interpreting the speaker's stance. Keep component prices distinct from totals. Do not
  call something a ceiling, maximum, target or agreement unless the speaker said that.
  For availability, use a neutral topic such as the person's schedule.
- "quote": copy the COMPLETE sentence containing the claim, from its first word to its
  ending punctuation. Include adjacent sentences from that same turn if needed for
  context, including the person referred to by a pronoun. If punctuation is missing,
  copy the whole turn. Do not shorten a sentence to its number or trim off its opening
  context or qualifications. Preserve the original
  words, capitalization and punctuation; do not convert words to digits, add units, join
  separate excerpts, or paraphrase. Exclude timestamps and speaker labels.

Cover both sides' positions, including rejected amounts, tentative targets and constraints
such as payment terms. Include absent or zero budgets expressed in words, even without a
numerical amount. Keep each range intact. Keep words such as "about", "probably",
"aiming for", "too low" and "doable" with their figures. A feasible amount is not a maximum.
Separate distinct claims even when they occur in the same turn. Do not calculate missing
amounts. A quote consisting only of a quantity or range is incomplete evidence.

Include absences, returns and related planned start dates, preserving which is which.
Keep the source's qualifications about whether a schedule is proposed or agreed. When
another turn supplies relevant timing context, quote that turn in its own detail rather
than joining separate excerpts. Do not infer a return date from an absence.

Skip incidental numerical expressions and repeated identical claims. Routine action-item
due dates are handled separately, unless they provide context for a selected detail.
Use only the transcript as evidence, not the meeting title, date or attendee list. List claims in the
order they occur in the transcript.
