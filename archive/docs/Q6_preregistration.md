# Q6 — is the real-data floor behavioural heterogeneity? Pre-registration

**Written and committed 15 November 2026, before any Q6 number was computed.** Q6 is the
last pre-registered phase. Experiments freeze after it. No phase follows without the
student's written decision.

**The question.** Q5 found that with the projection `H` as the potential, ε falls by more
than half but the irreducible within-row floor's share of the residual *rises*
(`docs/Q5_results.md` §3). One explanation is that the response differs from day to day
inside a (depth, run-length) cell, which no model of `r` in depth and run length can fit.
Q6a looks for that day-to-day variation in the real data. Q6b asks whether putting it into
the synthetic generator reproduces Q5.

**Order.** Q6a runs first. If Q6a finds no heterogeneity, Q6b still runs, and its results
note opens by saying the hypothesis is already weakened.

## Q6a — real data

### Data

| | |
|---|---|
| region | 50Hertz + Amprion + TransnetBW, as Q5. TenneT stays excluded under T-D(vii), `docs/Q_STOP_Q0c.md` |
| series | `G`, `H` (quality-assured) and `R` exactly as Q0b, from `q0b_validate_h.load_frames("quality-assured")`, three-area sum |
| window | 2025-10-01 to 2026-10-28, every Berlin day the series cover. No market-value restriction: Q6a needs no θ |
| quarter-hours | negative day-ahead price only |

### Cells

Each negative-price quarter-hour is placed in one **price band × run-length band** cell:

| price band, EUR/MWh (`src/postauction/common.py` `BANDS`) | run-length band, hours |
|---|---|
| (−5, 0) | 0.25 to 1 |
| (−20, −5] | over 1 to 3 |
| (−50, −20] | over 3 to 6 |
| ≤ −50 | over 6 |

The run length is the length of the maximal run of consecutive negative-price quarter-hours
containing the quarter-hour (`build_clock_features`, `qh_run_length / 4`). The price band
stands in for depth: per-cohort depth needs θ, which needs the market value, which Q6a does
not restrict to.

### The statistic

For each cell and each event-day with at least one quarter-hour in that cell:

```
c_d = 1 - sum(G) / sum(H)      over that day's quarter-hours in the cell
```

`V_between` is the sample variance, with one degree of freedom removed, of `c_d` across the
cell's event-days.

**Measurement-only variance, primary.** Suppose every day shares one curtailed share `c`
and `H = A·exp(e)` with `e ~ N(0, σ²)`, σ = **0.066** (Anchor H, `docs/Q0_preregistration.md`).
Q6a takes `e` to be **constant within a day**. Then `c_d = 1 − (1 − c)·exp(−e_d)` exactly,
whatever the day's quarter-hours, and

```
V_meas = (1 - c_bar)^2 * (exp(sigma^2) - 1) * exp(sigma^2)
```

with `c_bar = 1 − ΣG/ΣH` pooled over the cell. A day-constant error is the **largest**
day-to-day variance an error of size σ can produce. Any within-day independence averages
some of it away. The primary comparison is therefore the one least likely to find
heterogeneity.

**Reported beside it, deciding nothing:**

1. `V_meas` with `e` independent across quarter-hours, by the delta method:
   `(1 − c_bar)²·σ²·Σw²/(Σw)²` per day with `w = G`, averaged over the cell's days.
2. The break-even σ at which the primary `V_meas` equals `V_between`.
3. The same test on `c_d = 1 − (ΣG + ΣR)/ΣH`. Grid redispatch varies from day to day and
   is not market behaviour, so this shows how much of any heterogeneity it accounts for.

### Uncertainty

Event-day block bootstrap within each cell: 5,000 draws of the cell's event-days with
replacement, seed 42. Each draw recomputes `c_bar`, `V_meas` and `V_between`. The 95%
interval is the percentile interval of `V_between − V_meas`.

### Verdict — fixed now

> **Heterogeneity is PRESENT** if, among the cells with **at least 5 event-days**, a
> **strict majority** have a 95% interval for `V_between − V_meas` whose lower bound is
> above zero. Otherwise it is **NOT FOUND**. If no cell has 5 event-days, the verdict is
> **NOT TESTABLE**.

### What Q6a cannot show

1. **Q0 Amendment 1's caveat applies.** σ = 0.066 is the agreement of two outputs of the
   same TSO extrapolation, a lower bound on `H`'s error against true potential. If the true
   error is larger, `V_meas` is understated and PRESENT can be produced by measurement alone.
   The break-even σ is reported so a reader can see how large it would have to be.
2. **Heterogeneity is not shown to be behavioural.** Day-to-day variation in `c_d` inside a
   cell can come from behaviour, from redispatch (item 3 above), or from anything else that
   varies by day and is not in the cell definition, such as the exposed cohort mix.

## Q6b — synthetic

### The generator change

In the P3 synthetic generator, which Arm O and Arm D share
(`src/censoring/synthetic.py`, called by `run_p3_synthetic.prepare_cell`), add a
**day-level random effect** to `r*`:

```
r*_k,t = clip( r*_k(depth_k,t) + u_d(t), 0, 1 )   on exposed quarter-hours,   u_d ~ N(0, sigma_r^2)
```

`u_d` is one draw per synthetic Berlin day, **common to all cohorts**: a day-level shift in
how much of the exposed fleet responds. `c_true` and `G` are recomputed from the new `r*`.
Observation noise in the generator is zero by default, so `G = A·(1 − c_true)` holds
exactly. The truth that coverage is scored against is the realised `r*`, as P3 scores it.

The effect is applied after `prepare_cell`, so the price process, exposure, depth, run
lengths and the bounds design are P3's unchanged. Only `r*`, `c_true` and `G` change.

| | |
|---|---|
| **σ_r grid** | **0, 0.05, 0.10, 0.20, 0.30** |
| `u_d` seed | `7_000_000 + round(1000·σ_r)`, common across cells, as Q1's noise seed is |
| cells | Q1's 54: rates × γ × shapes × {homogeneous, split}, generator seed 45 |
| potential | Q1's dial, `P = A·exp(e)`, `e` i.i.d. N(0, σ²), Q1's noise seed |
| **noise levels** | **σ = 0.066 (Anchor H)**, and σ = 0.18 (Anchor T) |

**Anchor T is added to the instruction's Anchor H**, because the second signature below
asks what happens to the floor share *when ε falls*. In Q5 ε fell between `F` and `H`. In
the synthetic dial the matching change is from Anchor T's noise to Anchor H's.

**Port check before Q6b runs.** At σ_r = 0, every row at σ = 0.066 and σ = 0.18 must
reproduce the corresponding row of `artifacts/Q1/q1_variance_dial.csv` exactly. A mismatch
stops Q6b.

### The two signatures — fixed now

**S1, the informative share.** At σ = 0.066, the share of (cell, functional) pairs that are
informative, over the fleet functionals **λ₁ and λ₂**, lies inside **[0.004, 0.117]**. That
is the Clopper–Pearson 95% interval for 2 of 59, the student's stated target. Informative
is Q0 §5's: width below 0.25 of the logical maximum.

**A definitional note, stated before any Q6b number.** Q5's 2 of 59 counts pairs that
*become* informative, across all seven functionals. Q5's fleet functionals under `H` are
informative in **3 of 11** main-setting months (λ₁ 2 of 8, λ₂ 1 of 3; `q5_real.csv`).
S1 uses the student's 2/59. The synthetic share is also reported against 3 of 11 and its
Clopper–Pearson interval, deciding nothing.

**S2, the floor share rises when ε falls.** At the same σ_r, going from σ = 0.18 to
σ = 0.066, the median over the 54 cells of ε **falls** and the median of
`rms_floor / rms_point` **rises**.

### Verdict — fixed now

> **SUPPORTED** if at least one σ_r > 0 meets **both** S1 and S2. The results note reports
> every σ_r that does. Otherwise **NOT SUPPORTED**, and the note says that no level does.

σ_r = 0 is the control. If it already meets both signatures, the day effect is not what
produces them, and the note says so.

Coverage of the realised truth is reported per level. A level below 95% coverage is
reported as such, and its widths are still used for S1, because S1 is about what the data
can pin, not about whether the bounds are honest.

### What Q6b cannot show

1. A σ_r that reproduces both signatures shows the mechanism **can** produce Q5, not that
   it **does**. Other mechanisms are not tested.
2. The synthetic design has five placeholder cohorts and a synthetic price process, not
   Q5's eight MaStR cohorts and real prices.
