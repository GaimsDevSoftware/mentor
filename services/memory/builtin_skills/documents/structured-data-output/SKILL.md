---
name: structured-data-output
description: "Keep structured output byte-exact — no compression."
version: 1.0.0
category: documents
status: published
confidence: 0.9
tags: [caveman-off, caveman, token-compression]
source: built-in
owner: admin
created: "2026-06-11T16:20:00Z"
---

## When to Use

Producing or extracting JSON, YAML, CSV, tables, API payloads, or any other structured or strict-format data.

## Procedure

1. Emit the structure exactly as required — keys, quoting, indentation and delimiters are load-bearing.
2. Do not abbreviate field names or values; validity beats brevity.
