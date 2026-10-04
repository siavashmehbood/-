# Language Foundation Evaluation

The tracked repository contains DEV and PUBLIC-EVAL material only. Promotion-only
HIDDEN-GATE cases must be supplied from an external/private path at evaluation time
and must never be committed, copied into training data, or used for adaptation.

A candidate is evaluated in two rounds:

1. quality baseline at a reasonable reference configuration;
2. deployment configuration under IRAN's actual local resource budget.

Rubric-only cases remain unscored until a blind judgment with provenance is applied.
A non-empty answer is never treated as proof of naturalness or correctness.

Hard promotion gates run before the weighted ranking:
Persian 45%, multilingual retention 20%, reasoning/knowledge 12%,
context/instruction 8%, code 5%, tool/agent 5%, safety/uncertainty 5%.

Current foundation candidates are pinned in candidates.json. Heavy or license-limited
models can be references/teachers without becoming production foundations.
