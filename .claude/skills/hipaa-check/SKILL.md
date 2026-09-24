---
name: hipaa-check
description: Walks the HIPAA settings checklist for an agent that handles health data. Use when a client's agent collects or discusses protected health information, or when choose-model recommends the HIPAA priority.
---

# HIPAA check

Read `$K/docs/reference/hipaa.md` in full before this checklist. It
holds the settings Retell documents as HIPAA-eligible, and what is
outside that boundary.

## Before anything else

- [ ] Confirm a BAA (Business Associate Agreement) with Retell is in
  place for this account. Without one, no setting makes the account
  HIPAA-eligible. This is a business step, not a technical one; ask
  Rey to confirm it, do not assume.
- [ ] Confirm the same for every downstream integration that will
  receive call data.

## Settings to confirm

- [ ] Only HIPAA-eligible models and voice providers are selected, per
  `docs/reference/hipaa.md`.
- [ ] Call recording and storage settings match what the BAA covers.
- [ ] Transcript and PII redaction settings, if the client needs them.
- [ ] The webhook target and every field it receives are covered by that
  target's own BAA or equivalent, not assumed safe by default.

## Write the result

Record the check in `<client>/CLIENT.md` under a HIPAA line: date
checked, pass or gap, and what closed each gap. A gap that is not closed
yet must be named as open, never implied as handled.
