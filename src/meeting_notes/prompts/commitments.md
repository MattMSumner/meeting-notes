Extract every explicit decision and commitment from this meeting, including closing
follow-ups. Read the full ordered transcript. The notes are for {name}; that speaker's
own actions belong to {name}. Each source turn has an id, speaker, start time and text.
Return JSON only with exactly two lists: "decisions" and "action_items". Empty lists
are valid. Use the supplied schema; include every field, even empty lists and nulls.

Decisions contain turn_ids and text. Record choices explicitly made or agreed, including
deferrals, with their subject, qualifications and original time period. A proposal,
existing policy, feasible price or conditional promise is not itself an agreement.
"We haven't agreed" does not mean a decision against it or a decision to keep it.
A follow-up at planning does not replace a decision to leave something unchanged this
month. Keep that decision and the separate planning action. Resolve pronouns in decision text
as well as tasks: name the subject rather than writing "not change it".

For each action, first identify the supporting turns, then name the owner and task,
then classify the times by what they schedule:
- kind: "promise" for a speaker's own commitment; "accepted_request" for a request
  accepted in the conversation, even when the acceptance says "I'll"; "reported_commitment"
  when someone reports another person's promise. Unanswered requests are not actions.
- commitment_turn_ids: the turns containing the promise, acceptance or reported promise.
- request_turn_ids: for accepted_request, include the original request as well as the
  acceptance in commitment_turn_ids, even when they are separated by other turns.
  Otherwise this list is empty. "Yes, I'll have it done" needs the request naming "it".
- context_turn_ids: other turns needed to resolve the work, identity or conditions.
  Use known source IDs only. Different actions may share sources; don't add unrelated turns.
- owner: use a name established anywhere in the conversation, including greetings and
  farewells. If {name} says "Hi Morgan" or "Thanks, Morgan" to the other speaker, that
  speaker's actions belong to Morgan. Use "Them" only for an unnamed responsible speaker.
  Use null for an unknown responsible person; don't assign a reported promise to its narrator.
- task: start with a verb, name the work and resolve pronouns so it makes sense alone.
  Keep conditions and uncertainty in the task text itself. A promise to notify someone
  that an event might occur must say "possible" or "might", not merely name the event.
  A related work date may stay attached to that work in task; do not make it the time
  of a conversation. Unknown ownership or timing does not erase a commitment.
- related_timing: dates belonging to work being discussed or someone's availability.
  Each entry has turn_id, quote and value. Copy a source clause showing what the time
  schedules into quote, and copy the time phrase from that clause into value.
- action_timing: the same evidence shape, or null. Fill this ONLY if the transcript
  schedules executing task's main verb. Start with null; a date in related_timing does not
  become an action deadline. If timing is unclear, leave this null.

Examples of the evidence fields (use the actual input's IDs and words):
- Request: "Could you prepare the review plan?" Acceptance: "Yes, I'll finish it by
  Wednesday." Reference the request in request_turn_ids and the reply in
  commitment_turn_ids. kind is accepted_request, despite "I'll". related_timing is [];
  action_timing quotes "Yes, I'll finish it by Wednesday." with value "by Wednesday".
- Source: "I'll email Rowan about starting tests Tuesday."
  related_timing: [{"turn_id": "source_id", "quote": "starting tests Tuesday", "value": "Tuesday"}]
  action_timing: null
  The tests are timed; the email is not. Do not duplicate related_timing into action_timing.
- Source: "I'll email Rowan by Monday about starting tests Tuesday."
  related_timing: [{"turn_id": "source_id", "quote": "starting tests Tuesday", "value": "Tuesday"}]
  action_timing: {"turn_id": "source_id", "quote": "I'll email Rowan by Monday", "value": "by Monday"}
  The email and the tests have different schedules, evidenced by their own clauses.
- "I'll talk to Rowan about starting the audit on Monday when she's back": the date
  still schedules starting the audit, even with the return clause. related_timing
  quotes "starting the audit on Monday when she's back", value "on Monday";
  action_timing is null. Do not infer when the conversation must happen.
- "I'll talk to Rowan on Monday about starting the audit": the date explicitly
  schedules talking. action_timing quotes "I'll talk to Rowan on Monday", value
  "on Monday"; related_timing is []. The position of the time phrase matters.
- "Rowan returns Friday. I'll contact Rowan": the return belongs in related_timing;
  action_timing is null. Availability does not schedule the contact.
- "I'll raise it at planning": related_timing is []; action_timing quotes the promise
  and has value "at planning". Resolve "it" using the referenced context.

Copy quotes and time phrases verbatim, including punctuation. Recording timestamps and
meeting metadata are not spoken evidence. These fields establish where the timing came
from; choose action_timing versus related_timing by which event is actually scheduled.

Check every turn before finishing. Keep independent commitments separate, even within
one turn or alongside a decision. Include reported promises with unknown owners and
conditional promises without inventing a decision. Do not omit small follow-ups, infer
agreements or deadlines, calculate amounts, or turn feasible amounts into ceilings.
