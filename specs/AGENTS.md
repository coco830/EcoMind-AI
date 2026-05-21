# Specs Agent Guide

## Scope

`specs` contains BDD behavior specs, domain terms, open questions, feature plans, and historical product decisions.

## Rules

- Treat specs as context, not automatically as current implementation truth.
- Use `.feature` files for active BDD scenarios that must pass `python .\verify.py spec`.
- Use `.feature.md` files for human/AI-readable background, examples, business rationale, and forbidden behavior.
- Keep `.feature` files valid Gherkin only; do not add Markdown sections to machine-parseable contracts.
- Keep `_glossary.md` limited to confirmed terms and `_open-questions.md` limited to unresolved business questions.
- Do not invent domain knowledge. Capture uncertain rules in `_open-questions.md` until a human confirms them.
- When specs conflict with `README.md`, `CODEMAP.md`, or current code, verify against code before editing behavior.
- Do not regenerate or rewrite historical specs unless the task explicitly asks for spec maintenance.
