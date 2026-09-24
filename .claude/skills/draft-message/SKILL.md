---
name: draft-message
description: Checklist for drafting a message Rey sends to a client or their developer - read what they actually said, check every claim against the published agent, the live draft, the integration code, and real calls, then write it short, Grade 5, Slack style, and human. Use for any reply, update, question, correction, or status message to a client or their developer, in a group chat or privately.
---

# Draft a message

Get the facts right first. Then make it short.

## Step 1: read what they said

- [ ] Read the newest messages in full. Not a summary. Find the thread
  the client actually uses; the client's `CLIENT.md` says where.
- [ ] List each thing they asked, claimed, or decided. Quote the line.
- [ ] Find Rey's last message in the chat so you do not repeat it or
  claim something unsent was sent.
- [ ] Note every hold or instruction still in force. A client hold on
  agent changes stands until they lift it.

## Step 2: check every claim against the system

For every fact you will state, and every claim they made:

- [ ] **Published agent**, what callers get today. See `check-agent-info`.
- [ ] **Live draft**, what ships next. Say which one you mean.
- [ ] **Integration code.** Pull the live workflow and quote the real
  line. See `check-integration`.
- [ ] **Real calls.** Count it in the right schema window, with the
  sample size. See `check-agent-data`.
- [ ] If they are right and we were wrong, say so plainly. If they are
  wrong, show the number, not an opinion.
- [ ] Mark each claim proven or not tested. Never imply a result you did
  not run.
- [ ] Leave out anything Rey said to leave out.

## Step 3: write it

- **First person, always.** Rey sends it under his own name, so the body
  says "I". "Then I publish", never "then Rey publishes". "Say the word
  and I will put it in", never "and Rey applies it". The notes and
  fact-check header above the message are for a future session, so `Rey`
  is correct there. Grep the body for `Rey` before handing it over.
- **Grade 5.** Small words. Short sentences. One idea each. "It broke",
  not "it experienced a failure".
- **Slack style.** No greeting paragraph, no sign-off. Open with the
  point. Short blocks with blank lines between.
- **Short.** Answer first, reason second, nothing else. Cut any update
  nobody asked for.
- **No em dash or en dash, ever.** Use a full stop, a comma, or a new
  sentence.
- **No headings, bullets, or bold** unless listing three or more
  separate items.
- **Human rhythm.** Mix very short sentences with longer ones. Use
  contractions. Some paragraphs are one line.
- **Banned words:** delve, tapestry, realm, landscape, testament,
  underscore, pivotal, multifaceted, intricate, meticulous, robust,
  seamless, leverage, harness, unlock, elevate, foster, showcase,
  game-changer.
- **Banned shapes:** "It's not just X, it's Y", "It's important to
  note", "In conclusion", "Let's dive in".
- **Exact** field names, call ids, numbers, and dates.
- **No caller personal detail** unless the reader already named it.
- Explain a technical term right after using it.
- When two people need different things, write one message each.

## Step 4: check before handing it over

- [ ] Grade level about 5 on the body.
- [ ] Zero dashes. Zero banned words.
- [ ] Every number traces to a pull, a count, or a code line from Step 2.
- [ ] Save the draft in the session scratchpad. Use `<client>/docs/`
  only if Rey will send it later, and delete it once sent.
