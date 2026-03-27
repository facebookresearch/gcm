# PR Rubric CI

This repository includes a deterministic PR rubric workflow in
.github/workflows/pr_rubric.yml.

## How it works

1. Read routing rules from .rubric.yml.
2. Inspect PR diff (changed files and line counts).
3. Select only relevant checks for the changed areas.
4. Execute selected checks and publish a structured report.

## Current routes

- docs/**, website/docs/**, gcm/docs/**, **/*.md
  - docs validation (headings, tab characters)
- training/**, experiments/**, configs/**
  - reproducibility config validation (seed/random_seed presence)
- gcm/**/*.py
  - nox lint
  - nox typecheck
- shelper/**/*.go, slurmprocessor/**/*.go
  - go test ./... in each Go package

## Large structural changes

The router flags large changes from thresholds in .rubric.yml and marks them as
"LLM summary recommended" in the report. This does not run any LLM by default.
