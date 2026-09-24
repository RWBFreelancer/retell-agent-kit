# HIPAA settings checklist

Read this in full before `hipaa-check` runs on an agent handling health
information.

## The one thing a setting cannot fix

A HIPAA-eligible configuration on Retell means nothing without a signed
Business Associate Agreement (BAA) between the client and Retell. Confirm
the BAA is in place, in writing, before treating any agent as compliant.
This is a business step Rey confirms; do not assume it from a setting
screen.

The same applies to every downstream system that will receive call data:
a CRM, a scheduling tool, an email service. Each one needs its own BAA
with the client, or the data must not reach it.

## Settings to confirm, against Retell's current docs

Retell's HIPAA-eligible model and voice-provider list changes. Pull the
current list from docs.retellai.com before confirming an agent's setup;
do not assume last month's list still holds.

- [ ] LLM and voice provider are both on Retell's current HIPAA-eligible
      list.
- [ ] Call recording and storage settings match what the BAA covers. Some
      accounts must disable recording or transcript storage entirely.
- [ ] Data retention settings match the client's own policy, not Retell's
      default.
- [ ] PII and transcript redaction settings, if the client's compliance
      program requires them.
- [ ] The webhook target and every field it carries are covered by that
      target's own BAA, or the field must not be sent.
- [ ] Post-call analysis fields do not carry more health information than
      the downstream system is cleared to receive.

## Recording consent

Some states require two-party consent to record a call. Confirm the
client's own states of operation and the agent's opening line meets that
state's rule. This is separate from HIPAA and applies to every agent that
records, not only ones handling health data.

## Record the result

Write the check into `<client>/CLIENT.md`: date checked, pass or gap, and
what closed each gap. Never leave a known gap unstated.
