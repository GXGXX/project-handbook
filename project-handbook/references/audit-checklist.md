# Audit checklist

Use this checklist before writing pages. The goal is not to describe every
file; it is to collect the facts a new maintainer needs to act safely.

## Evidence inventory

- Identify the runnable entry point and the shortest supported start command.
- Trace one representative request or job from input to output.
- Name module boundaries and the direction of their dependencies.
- Locate persistence, queues, caches, scheduled jobs, and external services.
- Find configuration classes or schemas; distinguish accepted settings from
  environment variables that are merely mentioned in documentation.
- Locate tests, CI, deployment manifests, health checks, and rollback steps.

## Drift and confidence

For each important statement, record:

| Field | Meaning |
| --- | --- |
| claim | A short, testable statement |
| source | A repository-relative file or directory |
| confidence | `verified`, `inferred`, or `unknown` |
| page | The handbook slug that uses the claim |

Treat code and executable configuration as `verified` evidence. Mark claims
that come only from prose as `inferred` until checked. Never turn an absence
of a search result into a definitive “not supported” claim without checking
the runtime path.

## High-risk facts

Put ports, table names, field names, feature flags, thresholds, command names,
and security-sensitive behavior in `evidence/facts.json`. Keep the exact token
that should appear in the page; the verifier checks presence, not truth. Truth
still requires comparing the claim with its source during authoring.

## Scope decisions

- Exclude generated files, secrets, dependency caches, and vendor trees from
  the evidence inventory unless they explain runtime behavior.
- Do not infer business rules from naming alone.
- Prefer one page with a clear boundary over several pages that repeat the same
  facts.
