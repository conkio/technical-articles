# AI-Assisted WordPress Forensics

This is a three-part technical article exploring whether an AI-assisted forensic tool can determine if a WordPress site has been compromised.

The goal is deliberately limited: **identify evidence of compromise and explain why it matters**.

The tool does not attempt to automatically clean or repair a site, nor does it provide advice on how to do so. Once a compromise has been identified, any action taken afterward remains the responsibility of the site administrator.

## The experiment

The project is divided into three parts.

### Part 1 — Building the investigator from a real compromise

The first case is a recently compromised WordPress multisite installation.

This incident acts as the project's guinea pig. Starting from a filesystem backup, a read-only forensic workflow is built that combines deterministic analysis with an AI agent.

The investigation evolves through several iterations:

- deterministic filesystem and WordPress core analysis;
- a report-only AI baseline;
- a constrained AI agent with read-only forensic tools;
- a second-generation tool interface that exposes structured evidence first and raw file contents only when justified.

The aim is not only to determine whether the site was compromised, but to examine how the design of an agent's tools affects the quality and reliability of its conclusions.

[Read Part 1 →](article/README.md)

### Part 2 — The clean-site control

The same forensic tool will be run against a known-clean WordPress installation.

The purpose is to test the opposite problem: **does the investigator incorrectly interpret legitimate WordPress, plugin, cache, or generated files as evidence of compromise?**

This provides a way to examine false positives without changing the tool to fit the new case.

### Part 3 — An unrelated compromise

The final test will use a WordPress site compromised in a substantially different way.

The V2 investigator from Part 1 will be used without first adapting it to the new incident.

This is intended to answer the most important question raised by the first experiment:

> Did we build a forensic tool for WordPress sites, or merely a good investigator for the particular compromise it was developed around?

## Who is this for?

The workflow is designed so that determining whether a WordPress installation shows evidence of compromise should not require specialist WordPress forensic knowledge.

It is not completely non-technical: the operator needs to be comfortable creating or obtaining a site archive and running scripts from the command line.

The forensic decisions themselves are intended to come from deterministic analysis and the AI investigator rather than from the operator already knowing which WordPress files should or should not be present.

## Scope and safety

The project is intentionally read-only.

The investigation:

- does not execute files from the compromised site;
- does not give the AI unrestricted shell access;
- does not delete or repair files;
- separates deterministic evidence collection from AI interpretation;
- treats compromised file contents as untrusted input.

Malware samples, credentials, customer data, and the original compromised archive are not included in this repository.

## Repository structure

```text
article/       Article series
images/        Diagrams and article assets
scripts/       Forensic and AI investigation code
experiments/   Reproducibility data and experiment metadata
