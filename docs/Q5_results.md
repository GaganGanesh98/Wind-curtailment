# Q5 — results: real-data bounds with the projection as the potential

Pre-registration `docs/Q5_preregistration.md`, commit **`60efa6e`**, recorded on every row.
Runner `src/identification/run_q5.py` and reduction `src/identification/summarise_q5.py`,
both committed (`cd3b1cb`) before Q5 ran. Artifacts `artifacts/Q5/q5_real.csv` (504 rows)
and `artifacts/Q5/q5_summary.csv`. Every figure below is re-derived by
`tests/test_reported_numbers.py`.

**Region: 50Hertz + Amprion + TransnetBW**, TenneT excluded under T-D(vii)
(`docs/Q_STOP_Q0c.md`). **`H` is ex post: these are T1 bounds, never a day-ahead input.**

## 0. Port check: passed

With its defaults, the generalised loader reproduces all 252 rows of
`artifacts/P3/p3_real.csv` field for field, `git_head` and `run_date` aside. P3's published
DE results are untouched.

## 1. Headline

> **2 of 59 main-setting functional-months, 3.4%, become informative when `H` replaces `F`.**

| `main`, months | count | share of 59 |
|---|---|---|
| **not informative under F, informative under H** | **2** | **0.034** |
| informative under F, not under H (reverse, not netted) | 5 | 0.085 |
| informative under both | 1 | |
| informative under F | 6 | 0.102 |
| informative under H | 3 | 0.051 |

**More functional-months stop being informative than start.** Eleven pairs are undefined
in both arms, the same eleven in each. No pair is defined in only one arm.

The nine main-setting pairs informative under either arm, from `q5_real.csv`:

| period | functional | width, F | width, H | informative under |
|---|---|---|---|---|
| window | λ₁ fleet | 0.474 | 0.208 | H only |
| 2025-10 | λ₁ fleet | 0.156 | 0.148 | both |
| 2026-01 | λ₃ cohort | 0.070 | 0.532 | F only |
| 2026-01 | λ₄ group | 0.075 | 0.569 | F only |
| 2026-01 | λ₆ contrast | 0.144 | 1.101 | F only |
| 2026-01 | λ₇ member | 0.124 | 0.945 | F only |
| 2026-02 | λ₃ cohort | 0.148 | 0.269 | F only |
| 2026-04 | λ₁ fleet | 0.571 | 0.175 | H only |
| 2026-04 | λ₂ deep | 0.983 | 0.196 | H only |

**The gains are all in the fleet-level functionals λ₁ and λ₂. The losses are all in the
cohort-level functionals,** in January and February 2026. The window arm is outside the
headline; under H its λ₁ becomes informative, at every setting.

## 2. The other settings

| setting | pairs in both arms | become informative | reverse | informative F | informative H |
|---|---|---|---|---|---|
| **main** | 59 | 2 (0.034) | 5 (0.085) | 0.102 | 0.051 |
| low | 59 | 3 (0.051) | 4 (0.068) | 0.085 | 0.068 |
| high | 53 | 3 (0.057) | 2 (0.038) | 0.057 | 0.075 |

Window arm, every setting: 1 of 7 functionals becomes informative, none reverses.

## 3. The mechanism P3 traced

Medians over the eleven plain arms per setting (`q5_summary.csv`, `per_arm`):

| | ε, F | ε, H | floor ÷ residual, F | floor ÷ residual, H | median width excl. λ₅, F | H |
|---|---|---|---|---|---|---|
| main | 0.267 | 0.107 | 0.924 | 0.963 | 0.943 | 1.000 |
| low | 0.267 | 0.107 | 0.936 | 0.963 | 0.942 | 1.000 |
| high | 0.267 | 0.107 | 0.918 | 0.930 | 0.977 | 0.908 |

**ε falls by more than half under H. The floor's share of the residual does not fall: it
rises at every setting.** The pre-registration said that if `H` helps, the floor share
should fall. It does not, and the median width across functionals does not narrow at
`main` or `low`. Q5 does not establish why.

## 4. Against Q1's dial

Q1 places Anchor H at σ = 0.066, where synthetic λ₁ is informative in all 54 cells and
λ₃ and λ₆ are too (`docs/Q1_results.md` §3). On the real three-area panel under H, λ₁ is
informative in 2 of the 8 main-setting months where it is defined, and no cohort-level
functional is informative in any month. **The synthetic dial at Anchor H is far more
optimistic than the real panel**, as it was at Anchor T.

## 5. What this cannot show

The pre-registration's §5 applies unchanged: nothing about TenneT; informative is not
correct; and `H`'s error against true potential may exceed its 0.066 agreement with
output, which would place it further up the dial.

## 6. A correction to the reduction, made after the first run

The summariser first reported 11 pairs as "defined in one arm only". All 11 are undefined
in **both** arms. `summarise_q5.py` now counts the two separately. The headline
denominator, pairs defined in both arms, was 59 before and after.
