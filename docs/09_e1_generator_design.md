# 09 — E1 generator (`e1_generator.py`): SUPERSEDED, with one salvageable part

**Status as of 8 Nov 2026:** do not use `e1_generator.py` for thesis results. It is
wrong on the law, and `src/censoring/synthetic.py` — already committed in the repo —
is right. This doc is kept because two of its claims were wrong in ways worth
recording.

*Original version of this doc: 8 Nov 2026, written before the repo state was checked.
First committed to the repo 8 Nov 2026 on branch `identification-fix`; it had existed
only as a working note until then, which is why `docs/10` §0.2 records it as absent.*

> **Checked against the repo on commit.** Six claims below have moved since this
> version was written, and each is marked inline: ① the `[VERIFY]` on §100 Abs. 45 is
> now **verified** against the statute; ② the "rank 6 of 8 / 34.6%" figure is
> **arm-specific**; ③ θ equality is sufficient but **not necessary**, so the merge key
> is not θ; ④ `src/censoring/` now **does** compute rank and conditioning; ⑤
> `synthetic.py`'s rate control **does not** saturate, so nothing was ported; ⑥ the
> validator **has** been repointed. Two figures were checked and stand exactly as
> written: the −5…0 band count and the 393-day / 99-event-day window. One quote could
> not be sourced and is marked `[VERIFY]`.

## Why it is superseded

Two reasons, in order of seriousness.

### 1. It misreads §51 (fatal)

`e1_generator.py` evaluates the hourly-clock cohort's exposure against the hourly mean
price, so a quarter-hour whose own price is positive, sitting inside a qualifying
negative hour, is treated as switched off.

That is wrong, and spec 06 §3 already said so — verifiably, at
`docs/06_pivot_mechanism_aware_censoring.md:266` (the θ branches) and `:302`
(`s_k,t = 1[p_t < θ_k,t]`). The clock decides θ, not which price the plant compares
against:

* §51 zeroes the *anzulegender Wert* (the support reference value). It does not mandate
  switch-off — the statute commentary is explicit that §51 "schreibt keine automatische
  Abschaltung vor".
  **[VERIFY]** that quotation is not sourced anywhere in this repo and was not read for
  this note. The conclusion does not depend on it: §51's own text zeroes the AW and says
  nothing about switching off, and the economic argument below carries on its own. But
  the quote needs a citation before it appears in the write-up (hard rule 9).
* Since the 15-minute market time unit went live for delivery day 1 Oct 2025 (SDAC, all
  European bidding zones), a plant's day-ahead revenue is settled per quarter-hour.
* So a plant whose support is zeroed still earns the quarter-hour price. If that price
  is positive, it has no reason to switch off.

The correct structure, which is what spec 06 §3 specifies and what `cohorts.py`
implements:

```
theta_k,t = 0            if support is zeroed (§51 triggered, or out of support)
          = -MP_k,t      otherwise
s_k,t     = 1[ p_qh,t < theta_k,t ]        -- always the QUARTER-HOUR price
```

The hourly clock and the run-length thresholds (6 h / 4 h / 2 h) decide which branch of
θ applies; they never change which price is compared.

`retro_run = True` is right about the law — the pre-2025 wording zeroes the value "für
den gesamten Zeitraum, in dem der Spotmarktpreis ohne Unterbrechung negativ ist" — but
that governs the support payment, not the switch-off decision. Conflating the two is the
bug.

> **Confirmed, and `cohorts.py` gets the pairing right.** It applies the retroactive
> zeroing *to θ* and still compares the quarter-hour price. Tested directly: for a
> 6-hour negative run, θ = 0 at the **first** hour — before the run has reached six —
> via `cohorts.py:230 _maximal_run_lengths`, while sub-threshold runs never trigger.
> `docs/12` §A.2. So there is no second law bug.

Worse: validation check 6 in `e1_validate.py` asserts that such rows must exist. A test
that requires the bug would have locked it in. It was rewritten from a correct assertion
to an incorrect one during the build, on the strength of the generator's own behaviour.

> **① `[VERIFY]` discharged.** The original text read: *"[VERIFY] §100 Abs. 45 EEG
> reportedly defines, post-MTU change, that the surviving hourly regimes use the negative
> arithmetic mean of the four quarter-hours of a calendar hour. Sourced from commentary,
> not yet read at gesetze-im-internet.de. Confirm before citing."*
>
> **Verified** 8 Nov 2026 at `gesetze-im-internet.de/eeg_2014/__100.html` (page headed
> "§ 100 EEG 2023 – Einzelnorm"; EEG 2023 content under the `eeg_2014` slug). §100
> Abs. 45, second sentence: where the applicable version of §51(1) uses hours as the
> *maßgebliche Zeiteinheit*, "ist … eine Kalenderstunde dann zu berücksichtigen, wenn
> das arithmetische Mittel aus den Spotmarktpreisen der Viertelstunden dieser
> Kalenderstunde negativ ist". Full text in `docs/12` §A.1.
>
> **One nuance the original framing missed.** The provision keys to an **event, not a
> calendar date**: "ab dem Tag, an dem die Strombörsen erstmals in der vortägigen
> Auktion am Day-Ahead-Markt Stromviertelstundenkontrakte der Kopplung der Orderbücher
> zugrunde legen". The statute never names that day. So 1 Oct 2025 is a *market fact*
> requiring its own source, not a date readable off the statute — which is how the
> **Window** section below justifies it. The page carries no "Stand" line; cite it as
> EEG 2023 as fetched 2026-11-08.

### 2. It duplicated existing work

`src/censoring/synthetic.py` was already committed (`fec1390`) implementing spec 06 §7,
with `metrics.py`, `baselines.py`, `gate_verdict.py` and three grid arms behind it. The
original version of this doc said "next build: the metrics module and baselines B1–B4",
which was already false of the repo. `PROJECT_CONTEXT.md` says the repo wins on any
difference; the repo was not checked before building.

## Corrections to the original version of this doc

* The energy-share band was wrong. It claimed a 20% quarter-hour rate corresponds to
  roughly 6–10% energy share. Measured: 4.3% (half), 7.8% (logistic), 20.4% (step). The
  usable conversion is a stable per-shape ratio of the quarter-hour rate: ×1.00 step,
  ×0.39 logistic, ×0.21 half. Since the point of recording it was to stop the two
  measures being confused, a wrong band was worse than none.
* The "thin direction" was not a data problem. The original doc flagged that only 7 rows
  had a positive quarter-hour price inside a negative hour, and asked whether real data
  would be as thin. Real data gave 1–11 rows across all rates and gammas. That is not
  scarcity — those rows should not exist at all. The scarcity was the bug announcing
  itself.

## What to keep

The validation suite, minus check 6. `e1_validate.py`'s 17 assertions are the reusable
artefact: the observation identity, c ∈ [0,1], the cohort-sum decomposition, I1, I3
monotonicity, seed determinism, confounding monotone in gamma, response shapes correctly
ordered, all rates reached. Repoint it at `synthetic.py` and delete or invert check 6.

> **⑥ Done.** `src/censoring/validate_synthetic.py`. Check 6 deleted and replaced by its
> inverse (no cohort may be exposed at a non-negative quarter-hour price), plus two
> identification assertions. **17/19 unmerged, 19/19 merged**, for both the placeholder
> and MaStR cohort sets. The archived files are at `archive/e1_generator.py` and
> `archive/e1_validate.py`, each with a header naming the supersession.
>
> **Two of the ported assertions were themselves wrong** and had to be rewritten, which
> is worth recording since this doc calls the suite "the reusable artefact":
> * *the minimum-run check* assumed hourly exposure can only arise via the §51 trigger.
>   It cannot: a cohort is also exposed at θ = −MP with no trigger and no run condition,
>   because the price fell below the premium it stands to lose. All 1,211 apparent
>   violations were trigger-inactive at θ = −17.
> * *"step > logistic > half"* encoded the archived generator's parameterisation.
>   `synthetic.py`'s `half` is a **constant** r\* = 0.5 whenever exposed — the shape built
>   to hurt B4 (spec §6, H2) — not a logistic capped at 50%, so `half > logistic` is
>   correct there. The invariant worth asserting is that step is the most aggressive.
>
> So the suite transfers, but not unexamined: two of its 17 assertions were specific to
> the generator it grew up against. `docs/12` §E.

The rate-control design (single monotone `intensity` knob, bisection, `max_day_fraction`
cap so day-level confounding keeps biting at high rates, two-level confounding on day
selection and within-day block placement) solved real problems and may be worth porting
if `synthetic.py`'s rate control has the same saturation issue.

> **⑤ Checked — it does not, so nothing was ported.** `synthetic.py` hits every target
> exactly in all four validator configurations: `0.05→0.050  0.10→0.100  0.20→0.200
> 0.30→0.300  0.40→0.400`. It places episodes until the target negative share is met and
> raises if it cannot, rather than bisecting an intensity knob. Note the definitions are
> **not** the same quantity: `synthetic.py`'s rate is the share of quarter-hours given a
> negative synthetic price, and its realised censored share is reported separately, so it
> must not be compared directly with the archived generator's `qh_share`.

## The finding that outlives the generator

Both implementations pass the pre-registered I4 check while large capacity shares are
exactly unidentified. `exposure_differs_by_day` asks whether cohorts differ *somewhere*;
it cannot see rank. In the Phase-3 MaStR set, `s` is rank 6 of 8 with 34.6% of fleet
capacity in exactly-collinear pairs, while `results/38_rule18_settings.csv` reports
"K-cohort stands" at all four AW settings.

> **② That figure is arm-specific — attach the arm wherever it is quoted.** It is exact
> for `synthetic.py`, which uses the flat placeholder `mv_eur_mwh = 45.0`, and therefore
> for the 81 stored gate artifacts. On the **real panel** with real monthly market values
> the same cohort set is **rank 7 of 8 with 29.3%** at the `low`/`main`/`high` award
> settings, and **rank 6 of 8 with 62.9%** at `stress`, where forcing
> `pre2016_in_support_no_s51` (33.6% of capacity, the largest single cohort) onto θ = 0
> creates a *three*-cohort collinear group. The `stress` case is worse than anything this
> doc or `docs/11` recorded. `docs/12` §B.
>
> **The `pilot_exempt` / `size_exempt` pair was a placeholder artefact and has already
> dissolved** under real award values and per-cohort reference periods. The θ = 0 pair is
> structural and will not.
>
> **All 81 stored gate cells pass the old I4 day count and fail a criterion that actually
> tests identification** (81/81 each way). `docs/12` §D.

This is predictable a priori, not an empirical surprise: s_k depends on the cohort only
through θ_k. Two cohorts with the same θ have bit-identical exposure, always.
`pre2016_out_of_support` and `post_feb2025_qh` are collinear because both sit at θ = 0.
`pilot_exempt` and `size_exempt` are collinear because both carry AW = 66.

> **③ True, but it is only half the story, and the missing half changes the remedy.** θ
> equality is **sufficient** for indistinguishability, not **necessary**. Cohort k enters
> `c = Σ_k w_k s_k r*(depth_k)` only through `(s_k, depth_k)`, so i and j are
> indistinguishable **iff** θ agrees *on the exposed set* — off it, θ may differ freely
> and the difference is invisible. Measured: at the `high` award setting the collinear
> pair's θ **differ**, and a θ-keyed merge finds **zero** groups while keying on the
> realised `(s, depth)` block finds one. `docs/12` §C.

So identification comes from θ separation, and from nothing else. Concretely:

* the gap between θ = 0 (support zeroed) and θ = −MP (support intact) — this is why the
  shallow band between −MP and 0 carries the information, and the kill test shows that
  band is the most populated (1,461 of 2,059 negative quarter-hours sit in −5 to 0
  €/MWh);
* the run-length thresholds, which decide when a cohort's θ flips from −MP to 0;
* the spread of MP across cohorts, which comes from the award-value range.

> **Both figures check out exactly**, with one convention to state. Over the E1/E2 window
> (from 2025-10-01) there are **2,059** negative quarter-hours, of which **1,461** satisfy
> `−5 < p < 0`. The band is **open at −5**: exactly 8 quarter-hours sit at −5.00, so the
> half-open `[−5, 0)` reading gives 1,469 instead. Worth stating, because the two differ
> by more than rounding. And −5…0 is indeed the most populated band in every window
> tested — 1,469 of 2,059 (71.3%) in the E1/E2 window, against 159 in −10…−5 and 68 below
> −100.

Pre-registration to add before the week-6 gate:

* `rank(s) == K` over the evaluation window, reported per arm;
* a per-cohort uniqueness floor (no two cohorts with identical exposure vectors);
* cohorts defined by distinct θ, merging any legal cohorts that share one;
* the condition number of `s`, since near-collinearity is as damaging as exact.

> **Two amendments to that list, both from measurement.**
>
> *Third bullet — the key is wrong.* Merge on the realised `(s, depth)` block, not on θ
> (see ③). A θ-keyed merge misses the collinear pair entirely at the `high` setting.
> Keyed correctly, the merge restores full rank in all four award settings, with
> `cond(s)` between 16.5 and 39.4.
>
> *Fourth bullet — pick the right matrix, and do not let it bind.* `cond(w·s)` is
> **nearly blind** to near-collinearity: perturbing the worst pair to differ on just one
> quarter-hour gives 543.6 against 602.2 for the untouched design, and it *falls* as
> duplication worsens. `cond(s)` is sensitive (inf → 138 at n=1 → 44 at n=10 → 23 at
> n≥50). So the binding test should be a **per-pair floor of 10 quarter-hours** —
> inheriting the pre-registered 10, moved from "event-days on which *some* pair differs"
> to "quarter-hours on which *every* pair differs" — with `cond(s) ≤ 100` as a derived
> backstop and `cond(w·s)` reported only. Implemented as the proposed criterion (d) in
> `gate_verdict.py`, marked PROPOSED and excluded from the verdict until pre-registered.
> `docs/12` §D.

Nothing in `src/censoring/` currently computes rank or conditioning.

> **④ No longer true** as of branch `identification-fix`:
> `src/censoring/identification.py` computes rank (explicit SVD tolerance, printed),
> exact-versus-weak duplicate diagnosis, per-cohort and per-pair counts, and both
> condition numbers; `run_identification.py` and `gate_verdict.py` consume it.

## Window

Use the study window from 1 Oct 2025 (393 days, 99 event-days), not the 1032-day panel
on disk. Not because the config says so, but because the 15-minute day-ahead auction
only began with delivery day 1 Oct 2025. Before that there was no quarter-hour day-ahead
price: the quarter-hour series is the hourly price repeated, so θ = 0 and θ = −MP cohorts
cannot be told apart on sub-hourly variation, and the two clocks collapse into one.
Running E1 or E2 across the boundary would mix two different market designs.

The pre-Oct-2025 hourly data remains the right input for E3 (transfer across the
1 Jan 2026 staircase change), where only the hourly regime exists anyway.

> **Confirmed exactly, on both counts.** The window is **393 days with 99 event-days**,
> matching to the day. And the "hourly price repeated" claim is not approximately true
> but exactly true: **15,335 of 15,335** calendar hours before 2025-10-01 have all four
> quarter-hour prices identical (mean within-hour spread **0.000** EUR/MWh), against
> 0.30% flat afterwards (mean spread 23.95). The switch is sharp at the month boundary —
> September 2025 is 100% flat, October 2025 is 0%. The identification consequence is
> equally sharp: of the hours containing a negative quarter-hour, **0 of 982** before the
> boundary have mixed sign inside the hour, against 218 of 626 (34.8%) after.
>
> Now a named constant with that justification: `src/censoring/window.py`
> (`MTU15_FIRST_DELIVERY_DAY`, `E1_E2_WINDOW_START`), which also states explicitly that
> it must **not** be applied to E3. Verified by `src/censoring/check_window.py`.
> It is deliberately distinct from `src/smard_config.py:23 PERIOD_START_BERLIN`, the
> ingestion period, since the panel on disk is wider than either.
>
> **Not yet applied.** `synthetic.py:235 load_base` still takes the whole panel, so no
> E1/E2 result has been produced on the restricted window. `docs/12` §G item 5.

---

## Where the rest of this is written up

| | |
|---|---|
| `docs/10_e1_first_run_report.md` | first run of `e1_generator.py` against the real panel; the thin-direction measurements quoted above |
| `docs/11_e1_identification_audit.md` | `synthetic.py` versus `e1_generator.py`; the rank-deficiency finding |
| `docs/12_identification_fix.md` | statute verification, the merge, the proposed gate criterion, the ported validator, the window check, and the gate fix |
