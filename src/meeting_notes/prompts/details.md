Select source turns for the Details section of meeting notes. Each supplied turn has
an id, start time, speaker and complete text. The start time is recording metadata,
not a spoken figure. Use only the spoken text to choose turns.

Read every turn in order. Select every turn that contains any of these facts:
- A price, budget, target, quantity or measurement. Keep both sides' positions,
  including rejected amounts, tentative targets, payment terms and zero or absent budgets.
- An operational count or interval: how often a process runs, how many times something
  failed, staffing or capacity, how long work takes, or how much time an option buys.
  These current-state facts and reasons for a decision belong in Details even when
  they are background to the main decision.
- A constraint or availability fact: absences, return dates and intended start dates.
  Include these even when the same turn also commits to an action.

Then include any other turns needed to understand the person, scope or qualifications
of a selected fact. A question can state a fact that the next speaker confirms: retain
the turn stating that fact as well as the confirmation when needed for context.
A turn that meets an inclusion rule must be selected even if it is a question, begins
with an acknowledgment or also contains an action item.

Skip turns containing only greetings, acknowledgments or agenda setup, and incidental
numerical expressions. There is no fixed selection limit, but each chosen turn must
contain a relevant fact or its necessary context.

Reply with JSON only: {"turn_ids": ["t3", "t5"]}. Use an empty list if nothing qualifies.
Return only IDs from the supplied turns, in source order, without repeats. Do not return
quotes, speaker names, topic labels or rewritten text. Code copies each selected turn
in full with its source speaker and time, preserving every claim within that turn.
