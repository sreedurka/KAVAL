# CLAUDE.md

This directory holds **KAVAL**, an in-progress submission to the FarmwiseAI Campus Product
Challenge (Task 3). Work on it is continuing from an earlier session.

**Before doing anything else, read `SESSION_HANDOFF.md` in this directory.** It stands in
for the conversation history you don't have: what has been built, the decisions already
made, what was running, and where to pick up. Treat it as a compacted summary of your own
earlier turns, and continue from its §9 "Next actions" without re-planning anything it
marks as settled.

Then:

- `KAVAL/plan.md` is **authoritative**. If another file disagrees with it, `plan.md` wins.
- Keep `KAVAL/progress.md` up to date as you go. The user reads it to track work.
- Every number in a document comes from a script writing to `KAVAL/docs/evidence/`. Never
  hand-edit evidence, and never quote a metric without its validation split regime.
- Use `uv pip install --python .venv/bin/python …`. The venv has no pip.
- Run the API on port **8077**. Port 8000 belongs to an unrelated app.
