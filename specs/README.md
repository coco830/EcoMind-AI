# Specs

This directory holds BDD behavior specs and stable project terminology.

Use `.feature` files for behavior that changes user workflows, business rules, AI output, reports, compliance wording, data interpretation, or domain judgement. Historical planning material stays in its existing subdirectories and should not be rewritten unless the task is explicitly about spec maintenance.

Run:

```powershell
python .\verify.py spec
```

The verifier parses `specs/**/*.feature` with `gherkin-v39 --predictable-ids -f ndjson` and requires `source`, `gherkinDocument`, and `pickle` events.
