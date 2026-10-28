Extract the complete sentences containing meaningful figures from this meeting transcript
before its summary is written.
Reply with JSON only: an object with a "figures" list. Use an empty list if there are none.

For each distinct claim about a price, budget, target, quantity, measurement or constraint:
- "speaker": the EXACT transcript label ("{name}" or "Them"). Do not infer a name.
- "subject": a neutral noun phrase naming what it measures, without adding numbers or
  interpreting the speaker's stance. Keep component prices distinct from totals. Do not
  call something a ceiling, maximum, target or agreement unless the speaker said that.
- "quote": copy the COMPLETE sentence containing the figure, from its first word to its
  ending punctuation. Include adjacent sentences from that same turn if needed for
  context. If punctuation is missing, copy the whole turn. Do not shorten a sentence to
  its number or trim off its opening context or qualifications. Preserve the original
  words, capitalization and punctuation; do not convert words to digits, add units, join
  separate excerpts, or paraphrase. Exclude timestamps and speaker labels.

Cover both sides' positions, including rejected amounts, tentative targets and constraints
such as payment terms. Include absent or zero budgets expressed in words, even without a
numerical amount. Keep each range intact. Keep words such as "about", "probably",
"aiming for", "too low" and "doable" with their figures. A feasible amount is not a maximum.
Separate distinct claims even when they occur in the same turn. Do not calculate missing
amounts. A quote consisting only of a quantity or range is incomplete evidence.

Skip incidental numerical expressions, action-item due dates and repeated identical claims.
Use only the transcript as evidence, not the meeting title, date or attendee list. List claims in the
order they occur in the transcript.
