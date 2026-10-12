# How to build in this repo

The person building this is learning. They must be able to open any file and explain it
in a technical interview. Optimize for **clarity over cleverness** in every choice.

## Read first
- `SPEC.md` is the source of truth for what we're building and in what order.
- Only build the **one build step** you're asked for. Never jump ahead.

## Code rules
- Python 3.12, managed with `uv` (`uv add <pkg>`, `uv run <cmd>`). Don't use pip directly.
- Every file starts with a 2-4 line comment: what this file is for and how it fits the app.
- Every function has a short plain-English docstring: what it does and why it exists.
- Add a brief inline comment wherever a beginner might ask "why?".
- Keep files under ~200 lines. Prefer simple functions over classes. No async unless required.
- Use the libraries named in SPEC.md. Don't add new dependencies without saying why.
- Secrets only come from `.env` (never hard-coded, never printed, never committed).
- Model name and other settings live in `scout/config.py`.

## After every build step, finish with this report
1. **Files changed**: each file and one sentence on what it does.
2. **How it works**: a plain-English walkthrough of the new code, in the order it runs.
3. **Decisions**: each meaningful choice you made and why (and the alternative you didn't pick).
4. **How to test it**: exact commands to run and what I should see.
5. **Questions I might get asked**: 3 likely interview questions about this step, with short answers.
Then STOP and wait. Don't start the next step.
