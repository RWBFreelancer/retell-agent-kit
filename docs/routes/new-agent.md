# Route: new agent

Follow these steps in order. Stop and report after each one.

1. **Intake.** Run `intake`. Answer the route and source-type questions.
   Save every source file into `<client>/sources/`. Write `intake.md`.
2. **Pick the architecture.** Read `docs/reference/agent-type-choice.md`.
   A flow is right when a required field, an exact-once line, an exact
   branch, or more than three or four conditional paths is involved.
   Otherwise a single prompt is cheaper.
3. **Pick the model.** Run `choose-model`. Write the choice into
   `intake.md`.
4. **Design in prose, before any JSON.** Node list, edges, variable
   registry, global nodes (flow), or the sectional prompt outline
   (single prompt). Name every gap. Do not fill one by guessing.
5. **Write the traces before the prompt or the node text.** Use
   `<client>/tests/TRACES.md`. This step is the one that gets skipped and
   the one that pays.
6. **Build.** Use `build-flow` or `build-single-prompt`. Start from
   `templates/flow-skeleton.json` or `templates/single-prompt.md`.
7. **Lint.** Offline, free. Fix every FAIL. Read every WARN.
8. **Walk the traces** against a throwaway sandbox. Run `cost-gate` first.
   Record pass or fail and the path taken for each one.
9. **Hand it over.** No API key: give the client folder the JSON file to
   import by hand. With a key: run `create-agent` (`tools/agentcreate.py`)
   in the client's Retell account. It dry-runs, creates the engine and the
   agent, reads both back, and records the ids in `AGENT.md`. Never publish
   without the ladder in `AGENTS.md` section 7.
9a. **Wire delivery.** Run `integration-setup` for the receiver (n8n, Make,
   Modal) in the client's account, and `delivery-check` before any publish.
10. **Log it.** Run `log-results`. Write the changelog entry, even for a
    first build.
