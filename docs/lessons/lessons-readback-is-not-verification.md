# A readback is not verification. It is an invitation to object.

**Learned 2026-09-07, from call_xxxxxxxxxxxxxxxxxxxxxxxxxxx on a second example agent v37.**

## The rule

A spoken readback only catches an error when the caller pushes back. A caller
who stays quiet has not confirmed anything. Silence after a readback is absence
of evidence, not evidence of agreement.

So a readback proves nothing about a field. It only lowers the error rate,
and it lowers it least on exactly the values that are hardest to hear.

## The case

A caller rang a second example agent on 2026-09-04 at 16:41 UTC. The opening turns, verbatim
from the Retell transcript:

    Agent: Can I get your name and a good callback number?
    User:  My name is Corwen.
    Agent: Thanks, Tomas. And a good callback number?
    ...
    Agent: Thanks, Tomas. Just to confirm, six two six, seven eight six,
           three two two eight. Is that correct?
    User:  Yes.

The agent said the name back **twice**. `caller_name` was stored as `Tomas`
and went to the client CRM that way.

The caller's real name is **Corwen**, and there is no surname. Rey listened to
the recording on 2026-09-07: the voice is a woman's.

Four systems heard four different things off that one fast utterance:

| System | Heard |
|---|---|
| Retell post-call analysis | Tomas |
| the call tracking service transcript | Kim Singh |
| Whisper, on the downstream owner's machine | Tomas Seen |
| The caller, spelling it herself on a later call | T-A-M-S-I-N |

Only the fourth is right, and only the fourth asked for letters.

the client took a later call from the same number at 10:12 Pacific and asked twice.
He got "my name is Corwen" the first time and the letter-by-letter spelling the
second time. That is the only place anybody actually got it.

## Why the readback failed

Three reasons, and all three transfer:

- **The readback used the misheard value.** "Thanks, Tomas" cannot prompt a
  correction from someone who said Corwen, because Tomas and Corwen start the
  same way and the caller is half-listening for her turn to talk.
- **The readback was bundled.** The second "Thanks, Tomas" was glued to the phone
  number confirmation. The caller's "Yes" answers the number, which was right.
  It does not answer the name, and nothing separated the two.
- **A non-English name has no prior to fall back on.** Speech-to-text guesses
  toward common words. Every one of the four systems guessed toward an English
  name. The mishearing is systematic, not random, so a second listen by the same
  model produces the same wrong answer.

## What was believed before

That an agent that reads a value back has verified it. This repository has
treated readback as the safety net for name and number capture, and section 18
of the flow standard said only "confirm anything that could be misheard".

That is now known to be too weak. It says to confirm. It does not say a
confirmation can pass while being wrong.

## What to do instead

- **Never bundle two facts into one confirmation.** One "Is that correct?" can
  only answer for one field. Bundling makes a "yes" unattributable.
- **For a name, ask for the spelling when the caller gave it in under about a
  second, or when it is not a common English name.** The phone-number rule in
  section 18 already accepts that digits need grouping and pauses; a name needs
  letters for the same reason.
- **Treat a stored name as low confidence until something outside the audio
  agrees with it.** A spelling, a text reply, or an existing customer record.
- **Do not raise confidence because a readback happened.** Count corrections,
  not readbacks.

## What this does NOT mean

It is not a defect in a second example agent, and it was not reported to the client as one.
No rule in the flow was broken and no routing went wrong. The lead reached
the client CRM with a working phone number, a correct vehicle, and a correct issue.
One field was wrong, and the design could not have caught it.

the downstream owner corrected the record on his side on 2026-09-06 and cleared the surname.
The first and display names were already right.

## The wider lesson

Any check that needs the other party to act is not a check. It is a request.
The same shape shows up elsewhere in this repository: a green trace that only
counts the sentences its author listed
([lessons-green-verdict-blindness.md](lessons-green-verdict-blindness.md)), and
an empty `missing_fields` on a call that hung up before the check node ran
([lessons-open-intake-reask.md](lessons-open-intake-reask.md)).

Ask of every safety net: what does it do when nobody does anything?
