---
name: intake
description: Asks the route question, the source-type question, and clarify questions before any build or edit, then writes the answers to intake.md. Use before designing a new agent, and before any change whose requirement is not already written down.
---

# Intake

Ask only what the sources do not already answer. Use `AskUserQuestion`,
at most 4 questions per call. Record every answer in `<client>/intake.md`.
The full question bank is `$K/templates/intake-questions.md`.

## 1. Route question (always first)

"Is this a new agent, or an existing agent to check, test, or modify?"

- New -> `$K/docs/routes/new-agent.md`.
- Existing -> ask: check only, test, or modify? Then
  `$K/docs/routes/existing-agent.md`.

## 2. Source-type question (always, multi-select)

"Where does the content come from?"

| Source | What to do next |
|---|---|
| PRD | Top precedence for its own scope. List every requirement with an id. |
| Prompt instructions | Check each rule for a structural home: an edge, a branch, a variable. |
| Flowchart (image or file) | Rebuild it as a node and edge table. Ask about every unlabeled arrow. |
| Docs, call scripts, FAQ | Extract requirements. Mark each as stated or inferred. |
| Copy of an existing agent | Pull or import it. Save as `exports/v00-source.json`. List what must change. |
| Chat or email thread | Evidence of wants. Never approval. |
| Nothing written | Run the full discovery questions from `build-single-prompt` or `build-flow`. |

Save every source file into `<client>/sources/`. Never edit a source
file.

## 3. Clarify rule

After reading the sources, list every gap and conflict. Ask about each
one that changes the build. Do not guess. Do not build past a gap. Name
it in `intake.md` under "Open". Stop asking once every build-changing gap
is closed. Do not ask about things with a safe default; state the
default and move on.

## 4. Minimum facts before a new build

Business name and what it does. The agent's one job. Phone number setup.
Hours and after-hours behavior. Required fields to collect. Where each
call's data goes (webhook target). Who approves changes and who
publishes. Hard "never say" items (price, diagnosis, ETA, medical
advice). Transfer target, if any. Languages. HIPAA or other compliance
need.

## Writing intake.md

```markdown
# Intake: <client>

## Answered
- <question>: <answer>, source: <doc/message/default>

## Open
- <gap>: asked <date>, waiting / resolved as <answer>

## Sources
- <file>: <one-line what it is>
```
