# Specs Agent Guide

## Scope

`specs` contains BDD behavior specs, domain terms, open questions, feature plans, and historical product decisions.

## Rules

- Treat specs as context, not automatically as current implementation truth.
- Use `.feature` files for active BDD scenarios that must pass `python .\verify.py spec`.
- Keep `_glossary.md` limited to confirmed terms and `_open-questions.md` limited to unresolved business questions.
- When specs conflict with `README.md`, `CODEMAP.md`, or current code, verify against code before editing behavior.
- Do not regenerate or rewrite historical specs unless the task explicitly asks for spec maintenance.
