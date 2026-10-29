# RQ1 Kill Test — Go/No-Go Note

Version 3, 29 Oct 2026 (v2: 29 Oct 2026; v1: 28 Oct 2026). **v2 is not overwritten** —
it remains at `docs/04_rq1_killtest_note.md`.

Data: SMARD 15-min (Bundesnetzagentur, CC BY 4.0), 1 Oct 2025 00:00 – 28 Oct 2026 23:45
Europe/Berlin. Netztransparenz redispatch: **not obtained — see §4.**

Code (rebuilt from scratch; the v2 scripts were lost): `src/smard_config.py`,
`src/ingest_smard.py`, `src/build_panel.py`, `src/stats_boot.py`, `src/kill_test.py`,
`src/check_da_vs_id.py`, `src/redispatch_control.py`, `src/make_figures.py`.
Seed 42, 5,000 bootstrap draws resampling whole Berlin-local event-days.

---

## Verdict

**GO**, under the stated rule: the DE negative-quarter-hour bias is
**−1,684.4 MW, 95% CI [−2,693.6, −806.5]** — the interval excludes zero — and the sample
(2,059 negative QHs on 99 event-days) clears the pivot thresholds of ~150 QHs / ~20 days
by more than an order of magnitude. The over-forecast is significant in DE, 50Hertz,
Amprion and TransnetBW; **not** in TenneT.

**One qualification v2 did not have.** v2's verdict line said the bias "survives the
redispatch control". **v3 cannot confirm that**: the Netztransparenz redispatch export is
not reachable without credentials, so Check 2 (test C) was not computed (§4). The GO rests
on the bias and sample-size criteria you specified, which do not include the redispatch
control — but the "redispatch does not explain it" claim is **unverified in v3** and
should not be repeated to a supervisor as if it had been reproduced.

---

## Reproduction status against v2

| v2 section | Reproduced? | Note |
|---|---|---|
| §1 sample size | ✅ exact | all four counts identical |
| §2 band table, point estimates | ✅ exact | every mean e matches to <0.1% |
| §2 band table, CIs | ✅ within 8% | bootstrap RNG differs; no bound moves >10% |
| §2 robustness, ex-Easter | ✅ exact | −1,113.9 vs −1,114 |
| §2 robustness, ex-worst-5 | ✅ after resolving a definition ambiguity | ⚠️ see F2 |
| §3 Check 1, MAE + ID bias | ✅ | DE ID bias −1,394.3 vs −1,394 |
| §3 Check 1, "DA == ID" share | ⚠️ differs >10% | see F1 |
| §3 intraday vintage | ➕ new in v3 | settled from the SMARD manual — no fixed vintage; leakage risk |
| §4 Check 2 (redispatch) | ❌ **not computed** | blocked on data access |
| §5 Check 3 (TSO forecast times) | ➖ carried over, **not re-verified** | documentary, see §5 |

---

## Definitions

- wind = onshore + offshore. Offshore is a **structural zero** in Amprion and TransnetBW
  (confirmed, see Data provenance), not a missing value.
- e_t = actual wind feed-in − TSO day-ahead wind forecast, MW (quarter-hour average).
  Negative = over-forecast.
- Negative QH: DE-LU day-ahead price < 0. Event-day: Berlin-local date with ≥1 negative QH.
- Price bands partition the line as `p ≤ −50`, `−50 < p ≤ −20`, `−20 < p ≤ −5`,
  `−5 < p < 0`, `0 ≤ p ≤ 5`, `p > 5`. The first four are exactly the negative QHs.
- All CIs: 95% percentile intervals, 5,000 draws, resampling whole Berlin-local
  event-days. No i.i.d. quarter-hour bootstrap anywhere in this project.

## Data provenance (all verified 29 Oct 2026, nothing guessed)

SMARD filter IDs were read from SMARD's own chart configuration,
`https://www.smard.de/app/chart_configuration/market_data_configuration.json`
(`version 1, created 2026-10-02`), archived at
`data/raw/smard_market_data_configuration_2026-10-29.json`.

| Series | Config subcategory | filter | regions used |
|---|---|---|---|
| Day-ahead forecast, wind onshore | Prognostizierte Erzeugung **Day-Ahead** | **123** | DE, 50Hertz, Amprion, TenneT, TransnetBW |
| Day-ahead forecast, wind offshore | Prognostizierte Erzeugung **Day-Ahead** | **3791** | DE, 50Hertz, TenneT |
| Intraday forecast, wind onshore | Prognostizierte Erzeugung **Intraday** | **5127** | all five |
| Intraday forecast, wind offshore | Prognostizierte Erzeugung **Intraday** | **5128** | DE, 50Hertz, TenneT |
| Actual feed-in, wind onshore | Realisierte Erzeugung | **4067** | all five |
| Actual feed-in, wind offshore | Realisierte Erzeugung | **1225** | DE, 50Hertz, TenneT |
| DE-LU day-ahead price | Markt → Großhandelspreise | **4169** | fetched once (identical in every region) |

All seven are `source_resolution: quarterhour`. The four v2 forecast IDs (123, 3791, 5127,
5128) are **confirmed correct**.

Three things were checked rather than assumed:

1. **Offshore really is absent in Amprion and TransnetBW.** The config lists offshore
   regions as `DE, DE-AT-LU, 50Hertz, TenneT, DE-LU` only, and filters 3791 / 5128 / 1225
   return **HTTP 404** for Amprion and TransnetBW while every onshore filter returns 200.
   Only then was offshore set to 0 there.
2. **`DE` is the exact sum of the four control areas**, verified quarter-hour by
   quarter-hour. `DE-LU` is ~0.2% larger (it adds Luxembourg). `DE` is used throughout so
   that DE decomposes exactly into the four areas.
3. **Unit.** SMARD's quarter-hour values are **MWh per quarter-hour, not MW** — verified
   by checking that the hourly series equals the *sum* of its four quarter-hours
   (35,298.69 = 8,844.80 + 8,813.77 + 8,821.85 + 8,818.27). Everything here is converted to
   MW (× 4). v2 reported MW and reproduces exactly, so v2 applied the same conversion.
   **Independently confirmed by SMARD's own manual** (Benutzerhandbuch 02/2025, §1.2.2 and
   §1.3, archived at `data/raw/smard_benutzerhandbuch_02-2025.pdf`): publication on the
   ENTSO-E platform is "in der Einheit [MW] je Viertelstunde", and for SMARD "werden die von
   ENTSO-E bereitgestellten Daten **durch vier dividiert**". Multiplying by 4 inverts exactly
   that, recovering the ENTSO-E MW value.

**Panel integrity.** 37,732 quarter-hours × 5 areas = 188,660 rows, stored UTC.
DST checks all pass: **100 QH** on 2025-10-26 and 2026-10-25, **92 QH** on 2026-03-29,
**96 QH** on all 388 other days, no duplicate `(timestamp, area)`, no gaps.
Missing source values are ≤0.5% per series (max 192 QH, TransnetBW day-ahead);
`results/00_data_quality.csv` logs every count. Quarter-hours missing price, forecast or
actual are dropped from the analysis (391 of 188,660 rows, 0.2%).

---

## 1. Sample size vs pivot thresholds

| Metric | v3 | v2 | Threshold | Passes |
|---|---|---|---|---|
| Negative QHs (price < 0) | **2,059** | 2,059 | ~150 | ✅ |
| Event-days (≥1 negative QH) | **99** | 99 | ~20 | ✅ |
| Negative QHs, DE DA wind forecast ≥ 10 GW | **1,347** | 1,347 | ~150 | ✅ |
| Event-days, DE DA wind forecast ≥ 10 GW | **65** | 65 | ~20 | ✅ |

Exact reproduction. Passes by a wide margin.

## 2. Bias by price band (DE)

| Price band (€/MWh) | QHs | Days | Mean e (MW) | 95% CI | e / forecast | v2 mean e | Δ |
|---|---|---|---|---|---|---|---|
| ≤ −50 | 149 | 12 | **−7,641.2** | [−13,686.3, −2,415.5] | −54.7% | −7,641 | 0.0% |
| −50 to −20 | 148 | 20 | **−2,654.1** | [−4,800.3, −1,282.7] | −20.8% | −2,654 | 0.0% |
| −20 to −5 | 301 | 38 | **−1,692.9** | [−3,005.1, −528.4] | −12.2% | −1,693 | 0.0% |
| −5 to 0 | 1,461 | 99 | **−976.9** | [−1,623.2, −344.6] | −4.7% | −977 | 0.0% |
| 0 to 5 | 1,274 | 138 | **−724.1** | [−1,332.4, −189.5] | −2.9% | −724 | 0.0% |
| > 5 | 34,303 | 391 | **+186.1** | [+59.3, +314.4] | +1.1% | +184 | +1.1% |

Every point estimate, QH count and day count reproduces v2. The monotone deepening of the
over-forecast with price depth — the core of H1 — is reproduced exactly. CI bounds move by
at most 7.7% (`−5 to 0` upper bound), which is ordinary bootstrap resampling noise at a
different RNG draw order; **no bound differs by more than 10%**. The `> 5` band gained 47
quarter-hours (+0.14%) — a routine SMARD data revision between v2's run and this one.

### Overall negative-QH bias, per area

| Area | Negative QHs | Days | Mean e (MW) | 95% CI | e / forecast | CI excludes 0 | v2 |
|---|---|---|---|---|---|---|---|
| DE | 2,059 | 99 | **−1,684.4** | [−2,693.6, −806.5] | −9.1% | ✅ | −1,684 |
| 50Hertz | 2,059 | 99 | **−832.7** | [−1,207.6, −500.3] | −14.1% | ✅ | −833 |
| Amprion | 2,059 | 99 | **−431.3** | [−624.4, −257.2] | −13.1% | ✅ | −431 |
| TenneT DE | 2,059 | 99 | **−325.9** | [−838.3, +137.6] | −3.6% | ❌ | −326 |
| TransnetBW | 2,059 | 99 | **−94.4** | [−132.4, −57.6] | −24.9% | ✅ | −94 |

All five reproduce v2 to <0.5%. TenneT is the one area whose CI includes zero, as in v2.
In relative terms TransnetBW is the most biased area (−24.9% of its forecast), despite
being the smallest in MW.

### Robustness (DE, all negative QHs)

Reported both in MW and as **relative bias** (mean e ÷ mean day-ahead forecast over the
same quarter-hours). The relative column is the one to read across subsamples: the MW bias
scales with how much wind was forecast, so a deeper MW bias on windy days is not by itself
a larger forecasting failure. Both CIs resample the same event-days; for the ratio the
numerator and denominator are resampled together.

| Variant | QHs | Days | Mean e (MW) | 95% CI (MW) | Mean forecast (MW) | **Relative bias** | 95% CI (rel) | v2 (MW) |
|---|---|---|---|---|---|---|---|---|
| All negative QHs | 2,059 | 99 | **−1,684.4** | [−2,693.6, −806.5] | 18,579.6 | **−9.1%** | [−13.2, −4.8] | −1,684 |
| Without 5–6 Apr 2026 | 1,951 | 97 | **−1,113.9** | [−1,671.3, −558.1] | 17,698.5 | **−6.3%** | [−8.8, −3.5] | −1,114 |
| Without 5 worst days *(by mean e — v2's definition)* | 1,915 | 94 | **−994.2** | [−1,546.3, −466.6] | 17,336.3 | **−5.7%** | [−8.2, −3.0] | −994 |
| Without 5 worst days *(by total error contributed)* | 1,781 | 94 | **−773.8** | [−1,211.5, −316.2] | 15,392.1 | **−5.0%** | [−7.8, −2.1] | ⚠️ new |
| Windy only (DE DA forecast ≥ 10 GW) | 1,347 | 65 | **−2,402.3** | [−3,748.3, −1,172.1] | 25,812.0 | **−9.3%** | [−13.8, −4.9] | new |
| Not windy (DE DA forecast < 10 GW) | 712 | 44 | **−326.3** | [−678.8, **+17.7**] | 4,896.9 | **−6.7%** | [−13.3, **+0.4**] | new |

Share of total negative-QH error from the top 5 days:
**45.1%** under v2's ranking (by mean e), **60.3%** when days are ranked by the error they
actually contribute. See F2.

**The windy subsample is not more biased — it is the same bias on a bigger base.**
In MW the windy bias looks 43% deeper (−2,402 vs −1,684 MW), but the mean forecast is also
39% higher (25.8 vs 18.6 GW). In relative terms the two are **indistinguishable: −9.3%
[−13.8, −4.9] versus −9.1% [−13.2, −4.8]**, with almost completely overlapping intervals.
*(An earlier draft of this note read the MW figures as "the bias is larger in windy
quarter-hours". That was a scale artefact and is withdrawn.)*

What the relative view shows instead is cleaner and more useful: the over-forecast behaves
as a roughly **constant ~9% proportional haircut** on the day-ahead forecast whenever prices
are negative, not as a fixed MW offset. A multiplicative correction is therefore the more
natural model form than an additive one — worth testing explicitly in RQ2.

The non-windy subsample is the only one whose CI touches zero, in both MW and relative
terms, on 712 QHs / 44 days. Heavy tails are real: the five worst days are 5% of event-days
and 45–60% of the error. But the bias survives every exclusion tested, and in relative
terms it never falls below −5.0% with an interval excluding zero.

Figures: `figures/bias_by_price_band_<area>.png` (one per area) and
`figures/bias_by_price_band_all_areas.png`.

## 3. Check 1 — is the SMARD day-ahead series really a day-ahead forecast? PASSED

**Documentary.** SMARD's own chart configuration puts 123 / 3791 under
"Prognostizierte Erzeugung **Day-Ahead**" and 5127 / 5128 under a separate
"Prognostizierte Erzeugung **Intraday**" subcategory. Reproduces v2. Archived in `data/raw`.

**Empirical — forecast accuracy.** A later forecast should be clearly more accurate, and it is:

| Area | QHs | MAE day-ahead (MW) | MAE intraday (MW) | Intraday MAE reduction |
|---|---|---|---|---|
| DE | 37,636 | 1,441.9 | 972.0 | **32.6%** |
| 50Hertz | 37,725 | 609.4 | 314.4 | **48.4%** |
| Amprion | 37,540 | 377.8 | 301.7 | **20.2%** |
| TenneT DE | 37,636 | 883.3 | 658.2 | **25.5%** |
| TransnetBW | 37,348 | 91.0 | 65.7 | **27.8%** |

v2 reported "20–50% lower in every area". v3: **20.2% – 48.4%**. Reproduced.

**Empirical — are the two series the same product?** ⚠️ **F1 — differs from v2 by >10%.**
v2 reported the two series identical in "≤3% of QHs"; v3 finds **≤0.17%**. The number is
entirely a function of what counts as "identical", which v2 did not state, so both are
consistent with the same data:

| Area | Exact | ≤0.05 MW | ≤1 MW | ≤10 MW | ≤0.5% relative |
|---|---|---|---|---|---|
| DE | 0.00% | 0.01% | 0.10% | 1.00% | 5.46% |
| 50Hertz | 0.02% | 0.03% | 0.28% | 2.44% | 3.26% |
| Amprion | 0.02% | 0.05% | 0.50% | 4.97% | 4.06% |
| TenneT DE | 0.08% | 0.08% | 0.28% | 1.78% | 5.36% |
| TransnetBW | 0.10% | 0.17% | 2.83% | 23.37% | 2.06% |

**Cause: a method difference, not a data revision or a bug.** v2's "≤3%" is reproducible
under a loose tolerance (~≤10 MW absolute, or ~0.5% relative). v3 uses ≤0.05 MW — SMARD's
own published precision — giving ≤0.17%. **v3's number is the stronger form of the same
conclusion**: the two series are almost never equal, so the day-ahead series is not a
relabelled intraday series. Use the tolerance-explicit table above in the thesis; "≤3%"
without a stated tolerance should not be quoted.

### Which intraday vintage does SMARD publish? **Answered — and it is not a fixed vintage**

Settled from the primary source: SMARD **Benutzerhandbuch 02/2025, §1.3**
(archived at `data/raw/smard_benutzerhandbuch_02-2025.pdf`). The TSOs produce intraday
wind/solar forecasts for the delivery day under **Art. 14(2)(d) of Reg. (EU) 543/2013**, and:

> "Die Daten des untertäglichen Handels werden **regelmäßig aktualisiert**, wobei
> **mindestens eine Aktualisierung um 08:00 Uhr am Tag der tatsächlichen Lieferung** an die
> ENTSO-E Transparenzplattform übermittelt wird."

Three consequences, and the first two are the important ones:

1. **There is no single intraday vintage.** The series is *regularly updated*, with 08:00 on
   the delivery day being a stated **minimum**, not the freeze time. The published value for
   a given quarter-hour may come from a much later run — possibly close to delivery. SMARD's
   API serves one value per timestamp, with no vintage snapshots, so the vintage of any
   individual quarter-hour **cannot be recovered from this dataset**.
2. **The intraday series is therefore unusable as a model input — it is leakage.** For a
   22:00 quarter-hour, an intraday forecast refreshed at 20:00 is close to a nowcast. It
   must be treated exactly like the redispatch data: evaluation and diagnostics only, never
   a feature. This is a new constraint that v2 did not record.
3. **It makes the §3 side finding stronger, not weaker.** The comparison below is against a
   forecast of *unknown but no-earlier-than-08:00-on-delivery-day* vintage — in places
   probably hours fresher than that. Even so it leaves most of the negative-QH bias intact.

Contrast with the day-ahead series (**§1.2.2** of the same manual): day-ahead wind/solar
forecasts are made under **Art. 14(1)(d)** and "werden **spätestens bis 18.00 Uhr des
Vortages** an die ENTSO-E Transparenzplattform übermittelt". The manual states no update
cycle for them, and for the *total* day-ahead generation forecast (§1.2.1) it says
explicitly "Eine nachträgliche Aktualisierung der veröffentlichten Daten ist **nicht
vorgesehen**". Note that the "no later updating" sentence sits in §1.2.1 (Gesamt), **not**
in §1.2.2 (wind/PV) — so for the wind day-ahead series specifically, the absence of updates
is implied by the asymmetry with §1.3's explicit "regelmäßig aktualisiert", not stated
outright. Worth one line in the TSO email (see Open items).

This resolves Check 1's remaining ambiguity: 123/3791 and 5127/5128 are not just different
labels, they are **different regulatory products under different articles of Reg. 543/2013,
with different publication regimes**.

**Side finding — the intraday forecast is also biased in negative QHs**, and per area this
is more interesting than v2 recorded (v2 gave DE only):

| Area | DA bias (MW) | ID bias (MW) | ID 95% CI | ID excludes 0 | Residual |
|---|---|---|---|---|---|
| DE | −1,684.4 | **−1,394.3** | [−2,203.4, −701.3] | ✅ | 82.8% |
| 50Hertz | −832.7 | **−447.4** | [−734.3, −200.2] | ✅ | 53.7% |
| Amprion | −430.0 | **−559.2** | [−753.0, −373.3] | ✅ | **130.0%** |
| TenneT DE | −325.9 | **−304.3** | [−700.2, +70.3] | ❌ | 93.4% |
| TransnetBW | −94.4 | **−82.4** | [−114.8, −50.5] | ✅ | 87.2% |

DE: −1,394.3 vs v2's −1,394 — exact. **New in v3:** the intraday forecast removes only
17% of DE's negative-QH bias and in **Amprion it makes the bias 30% worse**. Even a forecast
made *after* prices are known does not correct for price-driven switch-off. That is a point
in favour of the thesis, and a candidate second baseline for RQ2.

*(Amprion and TransnetBW rows use the 2,045 negative QHs where both forecasts exist; the
other rows use all 2,059. This is why Amprion's DA bias reads −430.0 here and −431.3 in §2.)*

## 4. Check 2 — does grid redispatch explain the bias? **NOT COMPUTED — BLOCKED**

**This section of v2 could not be reproduced.** No number from v2's §4 is restated as
verified here. The Netztransparenz redispatch export for 2025-10 – 2026-10 is not
obtainable without credentials:

- `https://ds.netztransparenz.de/api/v1/data/...` returns **HTTP 401**. Netztransparenz's
  FAQ requires registering on netztransparenz.de for the **`WebAPIReader`** role and then
  creating a **Client** in the WebAPI-Portal to obtain a **ClientID + ClientSecret**
  (OAuth 2.0 client-credentials grant; machine-to-machine use is explicitly supported
  *once registered*).
- The "Download CSV" control on the public Redispatch page is an **ASP.NET WebForms
  postback** — no GET URL exists for a script to call.
- The Datencenter is a **Blazor single-page app**; downloading is a browser action.
- The only anonymous file link on the page covers **2013–2020** only.
- ENTSO-E also publishes redispatch, but that needs the API token this project has not yet
  received.

Replaying the postback or driving the SPA was **not attempted** — both would be working
around an access restriction.

`src/redispatch_control.py` is written and ready. It implements exactly the v2 method:
renewable ("Erneuerbar") reductions only, solar-named plants excluded, each measure's
energy spread evenly over its quarter-hours (energy ÷ duration), assigned to the
instructing TSO; then test C — per area, excess error = mean e in negative QHs minus mean e
in positive-price QHs in the same stratum (5 redispatch-volume bins × forecast-level
decile, bin 0 being exactly zero redispatch and bins 1–4 the quartiles of the positive
values), weighted by negative-QH counts, with an event-day bootstrap CI; plus the raw
negative-QH bias, the share of negative QHs with any RE redispatch, and the 50Hertz bias in
zero-redispatch quarter-hours. It exits with code 2 and writes
`results/04_test_c_BLOCKED.txt` until the data is present.

**To unblock:** either a WebAPI ClientID + ClientSecret, or a manual CSV export from the
Redispatch page (Von 01.10.2025, Bis 28.10.2026, timezone **UTC**) dropped into
`data/raw/netztransparenz/`. Then `python src/redispatch_control.py`.

**Licence is still unverified** — no terms-of-use text appears on any readable
Netztransparenz page. This must be settled before redispatch data goes into the thesis.

## 5. Check 3 — TSO forecast method (carried over from v2, **not re-verified in v3**)

The following are v2's documentary findings from TSO web pages read on 29 Oct 2026. They
were **not re-read for v3** and are reproduced here only so the note is self-contained.
Mark them as v2 evidence, not v3 evidence:

- TenneT: day-ahead forecast based on several wind forecasts "mit Stand 8:00 Uhr für den
  Folgetag", published 18:00 (netztransparenz.tennet.eu).
- 50Hertz: forecast values are "those of 09:00 hrs the previous day" (50hertz.com).
- SDAC day-ahead gate closure 12:00 CET, results 12:57 CET.
- Conclusion: at least TenneT and 50Hertz freeze their forecasts **before** day-ahead
  prices exist, so those forecasts are price-blind by construction. v1's "TenneT is
  price-aware" hypothesis stays rejected.

v3 adds one piece of **new** evidence bearing on TenneT's weak bias: TenneT's intraday
forecast is also unbiased-at-95% in negative QHs (−304.3 MW, CI [−700.2, +70.3]), while
50Hertz's and Amprion's intraday forecasts remain significantly biased. Whatever makes
TenneT different is not fixed by a later forecast either. v2's candidate explanations
(reference-park extrapolation; overlap with heavy redispatch; a different EEG plant mix)
all remain open — and the redispatch one cannot be tested until §4 is unblocked.

---

## Differences from v2 — flagged

**F1 — "day-ahead == intraday" share: ≤3% (v2) vs ≤0.17% (v3). Cause: method.**
v2 did not state its equality tolerance. v2's figure is reproducible at a loose tolerance
(~≤10 MW); v3 uses SMARD's own published precision (≤0.05 MW). Same data, same conclusion,
stronger form. §3 gives the full tolerance sweep — quote that, not a bare percentage.

**F2 — "5 worst days": ranking definition was ambiguous. Cause: method. Now resolved.**
v2 reported −994 MW without the 5 worst days and a 45% top-5 error share. Ranking days by
**total error contributed** gives −773.8 MW and 60.3%; ranking by **mean e on the day**
gives −994.2 MW and 45.1% — v2 to the decimal. So v2 ranked by mean. v3 reports both.
The by-total-error ranking is the more honest answer to "how much does the tail drive
this?" and gives a **heavier** tail than v2 reported (60.3%, not 45%). Neither version
changes the conclusion: the bias survives the exclusion with a CI excluding zero.

**F3 — `> 5 €/MWh` band gained 47 quarter-hours (34,256 → 34,303, +0.14%). Cause: data
revision.** Immaterial; the band mean moved from +184 to +186.1 MW.

**F4 — §4 not computed. Cause: data access.** See §4. v2's §4 numbers
(DE excess −1,713 MW, 50Hertz −741, Amprion −501, TenneT −402, TransnetBW −93, and the
"96% of negative QHs have RE redispatch" figure) are **neither confirmed nor contradicted**
by v3.

**F5 — v2 cites a "SMARD user manual (04/2026)"; no such edition could be found.
Cause: citation error in v2.** The latest edition locatable on smard.de is
**Benutzerhandbuch 02/2025** (German; the English user guide is older still, 09/2021). The
substance v2 attributed to it — day-ahead forecasts produced by the TSOs under Reg.
543/2013 Art. 14(1)(d) and sent to ENTSO-E by 18:00 D-1 — **is correct and is confirmed
verbatim in §1.2.2 of the 02/2025 edition**. Only the date of the citation is wrong. Fix
the citation before it reaches the thesis.

**F6 — the "windy quarter-hours are more biased" reading is withdrawn.
Cause: a scale artefact in an earlier v3 draft, not present in v2.** See §2: in MW the
windy bias is 43% deeper, but on a 39% larger forecast base; in relative terms the windy
and overall biases are statistically indistinguishable (−9.3% vs −9.1%).

No difference >10% was found in any number that v3 and v2 both computed by the same
definition.

---

## Reproducing this note

```
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python src/ingest_smard.py        # ~1,425 files, ~27 MB, a few minutes
.venv/bin/python src/build_panel.py         # panel + DST and integrity checks
.venv/bin/python src/kill_test.py           # analyses 1 and 2
.venv/bin/python src/check_da_vs_id.py      # check 1
.venv/bin/python src/redispatch_control.py  # check 2 — exits 2 until data is supplied
.venv/bin/python src/make_figures.py
```

Built and tested on Python 3.13.13; polars 2.1.0, pyarrow 26.0.0, numpy 2.5.4,
matplotlib 3.11.2, requests 2.34.2. Seed 42 throughout. `data/` is not committed;
`data/raw` is append-only and never modified in place.

Result tables: `results/00_data_quality.csv`, `00_dst_check.csv`, `01_sample_size.csv`,
`02_bias_by_price_band.csv`, `02_overall_negative_qh_bias.csv`, `02_robustness_de.csv`,
`02_worst_days_de.csv`, `03_da_vs_id.csv`, `03_da_id_identity_tolerance.csv`,
`03_id_bias_negative_qh.csv`. `04_*` pending §4.

---

## Implications for the method (unchanged from v2 unless noted)

- **Fair-comparison trap.** The model's forecast time must be after 12:57 CET D-1, so it
  also gets 4–5 h fresher weather than the TSO forecast. Mandatory ablation: same model and
  forecast time *without* price and MaStR features. Only the gain over that ablation counts
  as price-information value for RQ2.
- **A second baseline, new in v3 — but as a *reference*, never as an input.** The published
  **intraday** forecast is made no earlier than 08:00 on the delivery day and is refreshed
  repeatedly after that (§3), yet still leaves 83% of DE's negative-QH bias and *adds* 30%
  in Amprion. That makes it a demanding reference point: a forecast with far more
  information than yours will have still fails in the same quarter-hours. It **cannot be a
  model feature** — unknown, possibly near-delivery vintage is leakage.
- **Leakage.** Redispatch is published after the fact. Use it only to stratify the
  evaluation, never as a model input.
- **Evaluation focus.** 50Hertz and Amprion are primary (clean, significant signal, and
  both have significantly biased intraday forecasts too). TransnetBW is small in MW but has
  the largest *relative* bias (−24.9%). TenneT is secondary — its CI includes zero for both
  forecasts.
- **Measurement limitation.** "Actual" wind is an extrapolation from metered reference
  plants. Errors are measured against the TSOs' own published actuals.
- **Tail risk.** 5 of 99 event-days carry 45–60% of the total error, depending on ranking.
  Any model evaluation must be blocked by event-day, and headline MAE gains will be
  dominated by a handful of days. Report per-day results.

## Open items

- [ ] **Obtain the Netztransparenz redispatch data** (ClientID/ClientSecret or a manual CSV
      export) and run `src/redispatch_control.py`. Until then the "redispatch does not
      explain the bias" claim is v2-only and unverified. **Highest priority — it is the
      main alternative explanation for the whole result.**
- [ ] Verify the Netztransparenz **licence/terms** before using the data in the thesis.
- [ ] Email TSO forecasting teams (50Hertz, TenneT, Amprion): (1) does the day-ahead
      forecast include expected redispatch or market-driven curtailment? (2) do the
      reference plants include direct-marketed plants that switch off at negative prices?
      (3) exact forecast freeze time (Amprion publishes none)?
- [ ] Re-verify the §5 TSO forecast-time citations for v4 — v3 carried them over unchecked.
- [ ] Add to the TSO email: is the published **day-ahead** wind forecast ever revised after
      its 18:00 D-1 transmission? The manual states "no subsequent updating" only for the
      *total* generation forecast (§1.2.1), not explicitly for wind/PV (§1.2.2). If the
      wind day-ahead series were revised, e_t would be measured against a partly
      after-the-fact forecast and the whole kill test would need rechecking.
- [ ] Optional: ENTSO-E 14.1.D value cross-check once the API token arrives.

## Known gaps

- §4 is absent. Everything v2 concluded about redispatch is unreproduced.
- Whether DSO-initiated Redispatch 2.0 measures are included remains unverified (and
  untestable until §4 is unblocked).
- The wind/solar split in the redispatch data is by plant name only; pooled entries
  ("UW …", DSO pools) may contain PV. `src/redispatch_control.py` logs the excluded share
  so this is auditable once the data arrives.
- Effective sample is ~20 deep-negative event-days; one weekend (5–6 Apr 2026) carries 37%
  of the total negative-QH error on its own.
- `DE` here excludes Luxembourg (~0.2% of DE-LU wind). The price is the DE-LU
  bidding-zone price. This mismatch is immaterial at these magnitudes but is stated for
  completeness.
