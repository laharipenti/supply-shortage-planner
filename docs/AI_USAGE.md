# AI usage disclosure

The submission guidelines allow any LLM tool and ask for transparency about where AI accelerated the
work, where I relied heavily on it, and what I personally reviewed, changed or validated. This file is
that disclosure. All prompts are in [../prompts/prompt_history.md](../prompts/prompt_history.md).

## Tools used

| tool | used for |
|---|---|
| Claude (Anthropic, Opus model, claude.ai app with code execution) | design, code generation, debugging, tests, documentation |
| _add any other tool you used (ChatGPT, Copilot, ...)_ | |

## Where AI accelerated / where I relied heavily on it

* **Heavy reliance:** the first complete version of the code base (schema, generator, planner,
  validator, evaluator, exporter, tests) and the documentation were produced by Claude from my prompt in
  one working session. Claude ran the pipeline at tiny, starter and full scale and iterated on it.
* **Issues found and fixed during that AI session (visible in the reasoning, not just in the final code):**
  1. Too many shortages: the first version made ~38% of SKU-locations short because an early backlog was
     never recovered. Fix: the generator tops up the first receipt to clear the opening shortfall.
  2. Demand-spike cause was firing on lumpy BOM (dependent) demand of components. Fix: spikes are judged
     on forecast demand only, against a +/-6-week local median (robust to seasonality).
  3. Labelled demand spikes produced no shortages because POs were sized *after* the spike. Fix: spikes are
     added after inbound planning (a late forecast change), which is also more realistic.
  4. Evaluation bugs in parsing IDs of LOW_OPENING_STOCK / PRODUCTION_CONSTRAINED labels.
  5. Cancelled POs were an unlabelled cause; they are now labelled as a scenario so cause precision is measurable.

## Note on the commit history

The first commits group the AI-generated files by component (scaffold -> schema -> engine -> generator ->
validation/export -> tests -> docs -> starter output). They were created at the end of the AI session, so
they show the structure of the work rather than a minute-by-minute history. Every commit after those is
my own follow-up work.

## What I personally reviewed, changed or validated

> **Fill this in honestly before submitting** - reviewers will ask you to walk through the solution.
> Suggested checklist (tick what you actually did, add notes in your own words):

- [ ] Ran `pip install -e ".[test]"`, `pytest`, `python -m ssp run --scale starter` and `--scale full` on my machine
- [ ] Ran `python -m ssp reproduce --scale starter` and checked the checksums match
- [ ] Opened `output/starter/derived/shortage.csv` and traced one shortage by hand through
      `projected_balance.csv`, `inbound_effective.csv` and `po_event.csv`
- [ ] Checked one mitigation option's arrival date against `lead_time.csv` and the supplier's remaining capacity
- [ ] Read `engine.py` and can explain: projection formula, episode definition, cause attribution, priority score, greedy allocation
- [ ] Read `generator.py` and can explain how each of the 5 edge cases is injected and labelled
- [ ] Changes I made myself: ...
- [ ] Things I disagree with / would do differently: ...

## Limitations of this disclosure

The prompt history contains my prompts verbatim. Claude's responses are not included (optional per the
FAQ) but the resulting code and the commit history show what was produced.
