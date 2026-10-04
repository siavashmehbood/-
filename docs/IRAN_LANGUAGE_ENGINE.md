# IRAN Language Engine

## Invariant

CognitiveSystem remains the ONE BRAIN. IranLanguageEngine is a subordinate,
replaceable multilingual generation boundary. It does not own long-term memory,
reasoning orchestration, learning governance, tool policy, or final authority.

## Active language target

Persian is the primary excellence target. English remains very strong. Arabic,
Turkish, French, German, Spanish, Portuguese, Russian, Chinese, Japanese, Korean,
Hindi, Urdu, Italian, Indonesian, Dutch, Polish, Ukrainian and Hebrew are active
Tier-1 retention languages.

The underlying foundation may support more languages; IRAN v1 actively gates these 20.

## Evaluation stages

1. DEV: development and debugging only.
2. PUBLIC-EVAL: comparable public benchmark.
3. HIDDEN-GATE: promotion-only cases, never training material.
4. Existing IRAN runtime regressions remain mandatory after model selection.

Quality and deployment feasibility are reported separately. A cheap/fast model does
not receive correctness credit for speed, and a high-quality model cannot ship if it
does not fit the deployment budget.

## Promotion hard gates

- Persian >= 80.
- non-Persian Tier-1 average >= 75.
- no Tier-1 language < 60.
- average multilingual loss after adaptation <= 3 points.
- English, Arabic and Turkish loss <= 2 points each.
- reasoning, code and instruction loss <= 3 points.
- zero canonical IRAN regression.
- ONE BRAIN, offline and hidden gates must pass.

## Adaptation rule

Do not tune by default. First measure the gap. Prefer fixing IRAN when the weakness
belongs to memory, orchestration, tools or verification. For language/style/data
gaps use the least invasive adaptation. Distill only when a teacher has a repeated,
measured advantage and its license permits transfer. Blind cross-family weight
merging is not a production strategy.

Model weights are external artifacts and must not be committed to this repository.
CI must remain deterministic and offline-capable.
