# Security Policy

## Scope

This repository contains documentation, diagrams, synthetic examples, and the validator script with its CI workflow. There is no runnable product code here, so the usual application security surface does not apply.

In scope for reports:

- accidental disclosure of a secret, credential, token, or connection string;
- accidental inclusion of personal data, customer data, or confidential material;
- a link added to this repository that points at something private or unsafe.

Out of scope:

- security findings about the private FinSentinel product (it is not in this repository);
- requests for implementation details, prompts, schemas, or configuration;
- scanning the private repository or any infrastructure.

## Reporting

Do **not** open a public issue containing secret values or personal data. Use the contact route in [README.md](README.md) — the author's GitHub profile — and describe the location (file and line) without reproducing the value.

## What the repository does to protect itself

- [scripts/validate-public-case-study.py](scripts/validate-public-case-study.py) runs on every push and pull request (see [.github/workflows/public-docs-check.yml](.github/workflows/public-docs-check.yml)) and fails closed: it blocks known secret patterns, credential files, private hostnames, personal-data-like content in examples, copied source directories, broken or unapproved links, and unbalanced Markdown.
- Every example is fabricated and marked synthetic. See [examples/](examples/synthetic-transaction.json).

## History

This repository contains documentation revisions only. It does not import the private product's git history, branches, or code.
