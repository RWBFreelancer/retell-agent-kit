---
name: check-agent-info
description: Checklist for reading a Retell agent's current state across versions - which version is published and which is draft, node count, agent settings, analysis fields, and what changed between versions. Use before editing an agent, when asked what is live, when comparing versions, before a publish, or whenever a file names a version number.
---

# Check agent info

Version numbers written in files go stale within hours. The client or Rey
edits and publishes by hand. Always pull.

## Checklist

- [ ] **Which version is live.** `python $K/kit/agentkit.py delivery --client <name> --agent <slug>`. The "phone number -> agent version" row is the only trustworthy answer.
- [ ] **Which version is the draft.** List agent versions, newest first. The newest with `is_published: false` is the draft.
- [ ] **Pull both by explicit version.** Pull the published version with its own suffix, then the same for the draft. With no version given, a pull returns the latest, which is the draft.
- [ ] **Diff the flows.** Report the global prompt, nodes added or removed, and every node whose instruction or edges changed.
- [ ] **Diff the agent too.** A flow diff cannot see agent settings: webhook, responsiveness, interruption, analysis fields, voice, ambient sound, transcription mode.
- [ ] **Before a publish, diff the published and draft agent objects field by field.** Settings changed in the Retell UI show up nowhere else.
- [ ] **Say which version every number came from.** Never quote a node count or a setting without its version.

## Older and newer versions

- Agent vN carries flow vN.
- `<client>/agents/<slug>/exports/vNN.json` is the canonical snapshot of a version. Suffixed files are point-in-time pulls.
- Post-call analysis field **descriptions** change between versions even when the field names do not. Before comparing a field across versions, find where its description changed. See `check-agent-data`.

## Traps

- A pass on one agent says nothing about another agent for the same client. Check every agent named in the request.
- The client may be editing in the Retell dashboard right now. If a value moves between two pulls minutes apart, ask before assuming a platform fault.
- Voice and audio settings (`stt_mode`, `denoising_mode`, `ambient_sound`) can differ between two agents that look alike. Never assume they match.
