# AI usage disclosure

The submission guidelines allow any LLM tool and ask for transparency about where AI accelerated the
work, where I relied heavily on it, and what I personally reviewed, changed or validated. This file is
that disclosure. All my prompts are in [../prompts/prompt_history.md](../prompts/prompt_history.md).

## Tools used

| tool | used for |
|---|---|
| Claude (Anthropic, Opus model, claude.ai app with code execution) | design, code generation, debugging, tests, documentation, and step-by-step help with installing Python/Git and publishing to GitHub |

## Where AI accelerated / where I relied heavily on it

* **Heavy reliance:** the first complete version of the code base (schema, generator, planner,
  validator, evaluator, exporter, tests) and the documentation were produced by Claude from my prompt in
  one working session. Claude ran the pipeline at tiny, starter and full scale and iterated on it.
* **Setup help:** I am new to this tooling, so I also used Claude to guide me through installing Python and
  Git on Windows, creating the public GitHub repository, pushing the code and fixing the commit author.
* **Issues found and fixed during that AI session:**
  1. Too many shortages: the first version made ~38% of SKU-locations short because an early backlog was
     never recovered. Fix: the generator tops up the first receipt to clear the opening shortfall.
  2. Demand-spike cause was firing on lumpy BOM (dependent) demand of components. Fix: spikes are judged
     on forecast demand only, against a +/-6-week local median (robust to seasonality).
  3. Labelled demand spikes produced no shortages because POs were sized *after* the spike. Fix: spikes are
     added after inbound planning (a late forecast change), which is also more realistic.
  4. Evaluation bugs in parsing IDs of LOW_OPENING_STOCK / PRODUCTION_CONSTRAINED labels.
  5. Cancelled POs were an unlabelled cause; they are now labelled as a scenario so cause precision is measurable.

## Note on the commit history

The first eight commits group the AI-generated files by component (scaffold -> schema -> engine ->
generator -> validation/export -> tests -> docs -> starter output). They were created at the end of the AI
session, so they show the structure of the work rather than a minute-by-minute history. They were first
authored under a different name and email; I rewrote the author on all commits to my GitHub identity
(`laharipenti`) before submitting. The commit messages keep the `Co-Authored-By: Claude` line on purpose,
as part of this disclosure. Every commit after the first eight is my own follow-up work.

## What I personally did and verified

- [x] Installed Python 3.14.7 and Git 2.56 on my Windows laptop
- [x] Created a virtual environment and installed the project (`pip install -e ".[test]"`). The first attempt
      failed with `No module named ssp` because I had not installed it into the venv yet; installing fixed it.
- [x] Ran the test suite: 29 passed in 7.4 s (Python 3.14.7, pytest 9.2.0)
- [x] Ran `python -m ssp run --scale starter` on my machine and confirmed the data matches the committed files
- [x] Ran `python -m ssp run --scale full` - 235/235 checks passed in about 71 s on my laptop (Python 3.14.7, pandas 3.1.0)
- [x] Ran `python -m ssp reproduce --scale starter` - reproducible=True (54/54 files identical; a different seed
      changed 53 files). Regenerating the starter dataset on Windows with pandas 3.1.0 gave the same content as the
      committed files: `git diff --ignore-cr-at-eol` showed no differences, only Windows line endings.
- [x] Created the public repository, pushed the history, and set the commit author to my account
- [x] Traced one shortage by hand (SHORT-2026-000014): stock went 60 -> -42 -> -149 -> -202 because
      PO-2026-000030 (624 units) was due 29 Dec but the carrier delayed it to 21 Jan (event log: CREATED 13 Nov,
      CONFIRMED 15 Nov, SHIPPED 16 Dec, DELAYED 24 Dec); it recovered to 333 in week 4 when the goods arrived
- [ ] Read `engine.py` and can explain: projection formula, episode definition, cause attribution, priority score, greedy allocation
- [ ] Read `generator.py` and can explain how each of the 5 edge cases is injected and labelled

## My notes (in my own words)

- What I learned:
- What I would improve:

## Limitations of this disclosure

The prompt history contains my prompts verbatim (including photos I sent of my screen, described in
brackets). Claude's responses are not included (optional per the FAQ), but the resulting code and the
commit history show what was produced.
