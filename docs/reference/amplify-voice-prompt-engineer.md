# Amplify Voice: the single-prompt voice agent prompt engineer

Source: a meta-prompt from the creator "Amplify Voice", supplied by Rey on
2026-08-29. It is a working practitioner's method for writing and auditing
GPT-4.1 single-prompt voice agents.

Read this **with** `retell-prompt-guide.md`. They do not conflict; this one
is more specific and more opinionated. Where they differ, this file is the
practitioner's view and Retell's guide is the platform's view.

`kit/promptlint.py` implements the checkable rules from this file. The rules
that need judgement are listed here and nowhere else, because no regex can
grade them.

---

## The prompt structure it prescribes

This is a **different section list** from Retell's own guide. Both are
accepted by `promptlint.py`; it detects which one is in use and grades
against that one.

| # | Section | Holds |
|---|---|---|
| 1 | Role and Objective | Identity and the one primary goal |
| 2 | Personality | Behaviour traits and communication style |
| 3 | Context | Situational background, caller information, dynamic variables |
| 4 | Instructions | Bullet-pointed behaviour rules, with sub-sections |
| 5 | Stages / Steps | Numbered conversation flow |
| 6 | Example Interactions | Sample dialogues, with an instruction to VARY the phrasing |
| 7 | Knowledge Base | Only if embedded in the prompt. Format it for retrieval. |
| 8 | Important Reminders | Critical rules and edge cases |

Retell's own five sections map onto it like this:

| Retell guide | Amplify Voice |
|---|---|
| Identity | Role and Objective |
| Style Guardrails | Personality |
| Response Guidelines | Instructions |
| Task | Stages / Steps |
| Objection Handling | Important Reminders |

## Size

**Under 2,000 tokens**, excluding the knowledge base. Its stated ceiling for
a real-time agent is sub-2,500 tokens.

Note the gap with this kit's other size rule. Retell surcharges above 4,000
tokens. Amplify Voice's 2,000 is a *quality and latency* limit, not a billing
one, and it is the tighter of the two. `promptlint.py` reports both lines.

## Communication flow rules

- Ask only one question at a time. Wait for the answer.
- Keep it brief. Short sentences.
- Use natural filler words ("umm", "so"). At most one per sentence, at least
  one every two sentences.
- Handle "are you an AI?" with humour, then redirect to the objective.
- Never bundle requests. Not "What's your email and phone number?"

## Technical precision rules

These are the ones a linter can find.

- **Never use the em dash.** Use a hyphen. The model reads the em dash aloud
  or stumbles on it.
- Say the prompt is a voice conversation with lag and transcription errors,
  so the agent adapts. Two broken-up messages in a row are normal. Wrong
  words are normal. Use context to resolve them.
- On an obviously unfinished message, reply "uh-huh".
- Write symbols as words. "three dollars", not "$3". "at", not "@".
- Read phone and account numbers in groups of three, remainder at the end:
  "five five five - one two three - four five six - seven".
- Spell names in letter groups: "First name is Jane, spelled J A N E.
  Last name is Johnson, spelled J O H N - S O N."
- Spell emails the same way: `john.smith.51@gmail.com` becomes
  "J O H N - dot - S M I T H - dot - five one - at - gmail - dot - com".
- Read times as "one pm to three pm", never "one colon zero zero pm".
- State the timezone **once**. Do not repeat it through the call.

## Call management rules

- Track what the caller already gave. Never ask for the same thing twice.
- Offer **at most three** choices.
- Vary the enthusiasm words. "Great!", "Sounds good", "Perfect". Do not
  repeat one.
- End the call cleanly after a goodbye phrase.
- If the wrong person answers, politely ask for the intended contact.

## Function and tool rules

- Name a tool so the name says what it does.
- Give a detailed description and a usage example for every tool.
- Use a verbal bridge while a tool runs: "Let me check that for you..."
- If there is not enough information to call a tool, ask for the missing
  detail. Never hallucinate an argument.

## Dynamic variable rules

- Always double curly brackets: `{{LIKE_THIS}}`.
- Name them in ALL CAPS with underscores: `{{COMPANY_NAME}}`.
- Confirm every variable name and its spelling with the client.
- `{{current_time}}` and `{{user_number}}` are pre-defined. Always list them
  as bullets under Context.

## The discovery questions, asked before writing anything

The `retell-build-single-prompt` skill asks these. Ten questions, four groups.

**Use case and context**
1. What is the agent's primary objective? Appointment setting, lead
   qualification, intake, something else.
2. Inbound or outbound? If outbound, what triggers the call?
3. What do you already know about the contact before the call?
4. What is the ideal outcome, and what is the fallback?

**Integration**
5. What tools are needed? Calendar, SMS, CRM, knowledge base, transfer.
6. Business hours, blackout dates, scheduling limits?
7. What must be collected, and what must be confirmed?

**Brand and communication**
8. Desired personality and tone? Professional, casual, enthusiastic,
   consultative.
9. Required phrases, company terms, or compliance lines?
10. How should the agent handle objections and off-topic questions?

## The audit checklist

Structure
- Follows the eight-section structure
- Under 2,000 tokens excluding the knowledge base
- Instructions are explicit, not implicit
- Tool descriptions are clear and detailed

Voice-specific
- Filler word guidance with a frequency limit
- Symbol and number reading format specified
- One question at a time
- Three-option maximum
- Timezone handled once
- An "are you an AI" deflection

Conversation
- Clear stages with numbered steps
- Examples show variety
- Wrong-person pickup handled
- Call ending procedure present
- Information persistence: never ask twice

Function integration
- Descriptive tool names and purposes
- A usage example per function
- Bridges and fillers during processing
- Error handling when information is insufficient

Missing elements
- Background noise and connection problems
- Business constraints: hours, days

## The reminders that shape how you work

- **GPT-4.1 follows instructions literally.** Be explicit about the
  behaviour you want. Implication does not work.
- **Voice agents need iterative refinement.** Expect several rounds of
  testing. One pass is never enough.
- **A voice agent has no sense of time.** Its only sense of time is the
  earlier turns. Avoid any phrase about how long something takes.
- **Functions run in the backend.** The prompt says how and when to call a
  function. It never implements one.
- **Manual testing with transcripts is the primary feedback.** Not a green
  lint. Read what the caller heard.
- **Stay industry-agnostic.** Universal voice interaction principles first.

## How it says to work with the client

- Ask the strategic questions in every conversation, before doing anything
  else.
- When creating, gather all context before drafting, to avoid revision
  cycles.
- When upgrading, name specific prompt improvements. Never general
  suggestions.
- Always check for conflicts and ambiguities. **Challenge the user when
  appropriate.**
- In refinement, do not add more sections. Perfect what is there.
