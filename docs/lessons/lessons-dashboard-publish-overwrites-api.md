# A dashboard publish can undo an API write to the same draft

2026-10-19. An API PATCH added three `post_call_analysis_data` fields to an
agent's draft. A fresh pull right after the PATCH showed all ten fields. The
client then published that version from the dashboard. The published version
had only the original seven fields. The `webhook_url` change in the same PATCH
survived.

The likely cause: the dashboard agent page was open from before the API write.
On publish, the page saved its own stale copy of the agent over the draft.

## Lesson - after an API write, the dashboard page must be reloaded before anyone saves or publishes

A fresh pull proves the write landed. It does not prove the write survives a
publish. Any open dashboard page holds the agent as it was when the page
loaded.

- When you hand a draft to someone who publishes in the dashboard, tell them
  to reload the agent page first.
- After every publish, pull the published version and diff it against the
  draft you wrote. Do not stop at the pull you made right after the PATCH.
- A partial loss is easy to miss. Here one field set was lost and another
  field in the same PATCH survived.
