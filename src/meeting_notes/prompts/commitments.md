Extract every explicit decision and commitment from this meeting. Read the full ordered
transcript, including the closing turns. The notes are for {name}; that speaker's own
actions belong to {name}. Each source turn has an id, speaker, start time and text.

Return JSON only, with exactly these two lists (empty lists are valid):
{"decisions": [{"turn_ids": ["t4"], "text": "..."}],
 "action_items": [{"turn_ids": ["t8"], "owner": null, "due": null, "task": "..."}]}

Decisions: record choices explicitly made or agreed, including a decision to defer a
change. Retain the decision's subject, qualifications and time period. A follow-up's
schedule does not replace the decision's time period. A proposal is not a decision.
"We haven't agreed" does not mean "we decided against it" or "we decided to keep it".
Existing policies and feasible prices are facts, not new agreements. A conditional promise
alone does not establish a decision: if the conversation says the decision is still
pending, keep the conditional promise in actions without inventing a decision.

Actions: record explicit promises, accepted requests and reported commitments by others.
An unanswered request is not a commitment. Unknown ownership or timing does not erase an
explicit commitment: use null for the unknown field. Include small follow-ups and closing
comments. A turn may supply both a decision and an action, or several independent actions.
Keep independent tasks separate; steps in one follow-up may stay together.

For every action:
- task: start with a verb and name the work. Resolve "it", "that" and "you" from context
  so the task makes sense on its own. Preserve conditions and uncertainty: "if approved"
  must not disappear, and notifying someone of a possible event must not announce it
  as certain.
- owner: resolve names from the WHOLE conversation, including greetings and farewells.
  If {name} addresses the other speaker with "Hi Morgan" or "Thanks, Morgan", that
  speaker's actions belong to Morgan, not "Them". Use "Them" only for a clearly
  responsible speaker whose name is never established. Use null when the responsible
  person is unknown; don't assign another person's reported commitment to its narrator.
- due: default to null. Fill it only when the transcript schedules this action itself.
  For "I'll ask Morgan about starting the project next week", due is null: next week
  schedules the project, not the asking. "I'll ask Morgan by Friday" has due "by Friday".
  An absence or return does not schedule another person's action. Keep explicit relative
  timing as spoken, such as "this week" or "at planning"; do not calculate dates.

Choose the supporting source turns before writing each item. Cite their known turn IDs. Include a request and its acceptance when
the acceptance alone doesn't name the work. Include neighboring context needed to resolve
the subject, owner, timing or conditions. Every item needs at least one source ID;
different items may share IDs. Recording timestamps and meeting metadata aren't evidence.

Check each turn for commitments before finishing. An action still needs its own entry
when a related decision is listed. Do not omit a commitment for brevity, infer an unstated
agreement or deadline, calculate an amount, or turn feasibility into a ceiling.

Final deadline check: for a promise to talk, ask, contact or coordinate about another
activity, due must be null when the only dated event is that other activity's start or
someone's return. Do not copy that date into due even if it is the only date in the turn.
Keep the related activity's date in task if needed. Only a separate explicit schedule
for the communication itself can fill due.
