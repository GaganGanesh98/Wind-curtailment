# §51 EEG Negative-Price Rules — Plain-English Guide

Companion to `data/reference/eeg_negative_price_rules.csv`. Compiled 29 October 2026
from the consolidated statutory texts (see Sources). Written for a non-lawyer.

**This is a research note, not legal advice.** Every row cites the provision it came
from; check the provision before any number goes into the thesis.

---

## 1. What §51 actually does

§51 EEG does **not** order anyone to switch off. It removes the subsidy.

German renewables outside the fixed feed-in tariff are paid a **sliding market premium**.
The operator sells on the spot market and the premium tops that up to the
*anzulegender Wert* (AW) — the award value from the auction, or the statutory tariff.
Roughly:

```
revenue per MWh  ≈  spot price  +  market premium
market premium   ≈  AW − monthly market value   (floored at zero)
```

When §51 bites, the AW is **set to zero** for that period. The premium disappears, and the
operator is left with the bare spot price. If that price is negative, producing *costs*
money. That is the moment a rational operator switches off.

So §51 converts a price signal into a **plant-specific break-even price**, and the rule
table is what tells you which plants face which trigger at which moment.

## 2. The one thing that changed everything: 25 February 2025

Before 25 Feb 2025 the rule had a **duration threshold**. Prices had to be negative for a
run of consecutive hours — six, then four, then a shrinking staircase — before the AW
dropped. A single negative hour cost the operator nothing, so the rational response was to
keep producing through short dips.

From 25 Feb 2025 the threshold is **gone**. §51(1) now reads, in essence: for periods in
which the spot price is negative, the AW falls to zero. No run length. No grace period.

This is the single most important fact for the thesis: **two cohorts of plants face
structurally different incentives in the same quarter-hour**, and which cohort a plant
belongs to is set by its commissioning date (or its auction bid date).

## 3. Which rule applies to which plant

A plant keeps the rule that applied when it was commissioned; later tightenings do not
reach back. Reading the table in order of commissioning date:

| Commissioned | Rule | What it means in practice |
|---|---|---|
| before 1 Jan 2016 | **R01** — exempt | §24(3) no. 1 EEG 2014 excluded them by name; §51 never applied. These plants have *no* statutory reason to stop. Many are also past their 20-year support period and sell merchant, which gives them a different reason to stop — at roughly 0 €/MWh. |
| 2016 – 2020 | **R02/R03** — 6-hour rule | Six consecutive negative hours. Wind below 3 MW and other plants below 500 kW were exempt entirely, as were demonstration projects. The rule lived in **§24 EEG 2014** until 31 Dec 2016 and became §51 on 1 Jan 2017 with the same trigger. |
| 2021 – 2022 | **R04** — 4-hour rule | Four consecutive hours. Exemption drops to below 500 kW. |
| 2023 – 24 Feb 2025 | **R05–R08** — staircase | 4 h in 2023, 3 h in 2024–2025, **2 h in 2026**, 1 h from 2027. Exemption below 400 kW. |
| from 25 Feb 2025 | **R09** — any negative quarter-hour | No duration threshold at all. Exemptions shrink to below 100 kW (until smart meter) and below 2 kW. |

Two side doors:
- **R13, opt-in.** An operator whose plant is *not* subject to any reduction may volunteer
  for §51/§51a and receive **+0.6 ct/kWh** on the AW in exchange (§100(47) EEG 2023). This
  matters: some pre-2016 plants may behave like new-rule plants because they opted in, and
  nothing in the public data reveals who did.
- **R14, biogas in tenders.** A separate regime under §51b, triggered at 2 ct/kWh or less.

### The staircase: exact wording, and which year it is keyed to

§51(1) EEG 2023 in the version in force **1 January 2023 – 24 February 2025**
(buzer.de version page, accessed 29 Oct 2026). German statutory text is free of copyright
under §5 UrhG, so it is reproduced in full:

> (1) Wenn der Spotmarktpreis 1. im Jahr 2023 für die Dauer von mindestens vier
> aufeinanderfolgenden Stunden, 2. in den Jahren 2024 und 2025 für die Dauer von mindestens
> drei aufeinanderfolgenden Stunden, 3. im Jahr 2026 für die Dauer von mindestens zwei
> aufeinanderfolgenden Stunden und 4. ab dem Jahr 2027 für die Dauer von mindestens einer
> Stunde negativ ist, verringert sich der anzulegende Wert für den gesamten Zeitraum, in dem
> der Spotmarktpreis ohne Unterbrechung negativ ist, auf null.

**Keyed to the calendar year of the negative prices — not the commissioning year.** The
sentence construction is *"Wenn der Spotmarktpreis [im Jahr X] … negativ ist"*: the year
qualifies **when the price is negative**. The provision never mentions the installation at
all. A plant commissioned in 2023 and one commissioned in 2024 face the **same** threshold
in any given year.

The apparent conflict with sources that describe the staircase "by commissioning year" is a
**category difference, not a contradiction**. Two separate questions:

| Question | Answered by | Keyed to |
|---|---|---|
| *Which version* of §51 applies to this plant? | §100(46) EEG 2023 | **Commissioning date** (or auction bid date), 1 Jan 2023 – 24 Feb 2025 |
| *Which step* of the staircase applies right now? | §51(1) nos. 1–4 | **Calendar year in which prices are negative** |

Secondary summaries that tabulate "commissioned 01.01.2023–24.02.2025 → staircase" are
answering the first question. Within that cohort the step still moves by calendar year.

*Caveat on sourcing:* the Rödl & Partner note (Feb 2025) cited as describing this by
commissioning year could not be retrieved, so what it actually says is unverified here. The
statutory wording above is primary and unambiguous on the second question; if a secondary
source asserts a commissioning-year staircase, that is a secondary-source error rather than
an ambiguity in the law.

**During the kill-test window (1 Oct 2025 – 28 Oct 2026) the live triggers are:** R01
(exempt), R02/R03 (6 h), R04 (4 h), R06 then R07 (3 h in 2025, **2 h from 1 Jan 2026**),
and R09 (any quarter-hour).

**The natural experiment.** Because the step is keyed to the calendar year, the whole
2023 – Feb 2025 cohort moved from a three-hour to a two-hour threshold **simultaneously, at
midnight on 1 January 2026** — inside the sample. That is a sharp, common, exogenous date
affecting one identifiable cohort and no other, which is a cleaner design than a
per-plant anniversary would have been. Everything else about those plants is unchanged
across the boundary. Worth an explicit before/after comparison in RQ2.

## 4. Hours versus quarter-hours — the §100(45) trap

Since 1 October 2025 the day-ahead auction clears in quarter-hours, but most of the rules
above are written in **hours**. §100(45) EEG 2023 resolves this, and the resolution is not
what you would guess.

From the day the exchanges first used quarter-hour contracts in the coupled day-ahead
order books, where the applicable version of §51(1) counts *hours*, a calendar hour counts
as negative when the **arithmetic mean of its four quarter-hour prices** is negative —
in the statute's words, the hour counts if
"das arithmetische Mittel aus den Spotmarktpreisen der Viertelstunden dieser Kalenderstunde negativ ist".

So there are **two different clocks running at once**:

- **New-rule plants (R09):** judged per **quarter-hour**, on the quarter-hour price.
- **Hour-rule plants (R02–R08):** judged per **calendar hour**, on the **mean of the four
  quarter-hour prices** — and then on whether enough such hours run consecutively.

This has a direct consequence for the model. A quarter-hour at −10 €/MWh inside an hour
averaging +5 €/MWh is a switch-off signal for a new-rule plant and **no signal at all** for
an hour-rule plant. The two cohorts can rationally do opposite things in the same
quarter-hour. Any switch-off curve that collapses them onto one price series will be wrong
in exactly the quarter-hours the thesis is about.

## 5. How this maps to a switch-off price per plant

For each plant in the MaStR snapshot, the chain is:

1. **Find the cohort** from the commissioning date (or auction bid date, which governs
   under §100(46) for the 2023 – 24 Feb 2025 window) → gives the rule row.
2. **Check the size exemption** for that row. Use §24 EEG for aggregation: nearby
   installations of the same technology can count as one plant, so a cluster of small
   turbines may be over the threshold even if each is under it.
3. **Pick the price clock** — quarter-hour for R09, hourly mean for R02–R08.
4. **Compute the break-even price** (for hour-rule plants, evaluate the trigger against the
   *calendar year* step then in force):
   - *Support ended (older than 20 years), merchant:* break-even ≈ **0 €/MWh**, since
     there is no premium to lose. Stop whenever the price is below zero.
   - *Market-premium plant, trigger NOT met* (run too short): the premium still flows, so
     the plant keeps earning until `spot + premium < 0`, i.e. break-even ≈
     **−(market premium)** ≈ **−(AW − monthly market value)**. This is deeply negative —
     the historical −65 €/MWh estimate for 2014 direct-marketed wind is of this kind.
   - *Market-premium plant, trigger MET:* the AW is zero for that period, so the premium is
     zero and break-even jumps to **0 €/MWh**.
5. **Aggregate** the MW whose break-even price lies above the clearing price, per control
   area, to get the "MW that should switch off" curve.

The sharp edge in step 4 is the point. For an hour-rule plant the break-even price is not a
constant — it **jumps from roughly −(premium) to 0** the moment the consecutive-hour
threshold is crossed. The switch-off curve is therefore a function of the *run length* of
negative prices, not of the instantaneous price alone. That is why the brief lists
consecutive-negative-period count as a feature, and it is why the 2-hour threshold that
took effect on 1 January 2026 is a natural experiment sitting inside the sample.

## 6. What this does not tell you

- **The AW per plant is not in MaStR as a price.** Auction award values are published per
  tender round by the Bundesnetzagentur, not joined to unit IDs. Without that join, the
  premium — and therefore the negative branch of the break-even price — has to be estimated
  by commissioning-year cohort from the statutory tariff and auction tables. Still open in
  the brief's §13.
- **Opt-ins (R13) are invisible.** No public field records them.
- **Direct-marketing status is not the same as support status.** A plant can be directly
  marketed and still hold a premium that shields it.
- **§51 governs money, not behaviour.** Operators may keep producing through a loss for
  technical reasons (fatigue, restart cost, heat supply) or stop earlier for others.
  Hirth's finding that only about half of incentivised wind actually stopped is precisely
  this gap, and closing it empirically is the contribution.

## Sources

All accessed 29 October 2026.

| What | Where |
|---|---|
| §51, §51a, §51b, §100 EEG 2023, current consolidated text | gesetze-im-internet.de/eeg_2014/ (`__51.html`, `__51a.html`, `__51b.html`, `__100.html`) |
| §51 version history, all eight earlier versions | buzer.de/51_EEG.htm and its per-version comparison pages |
| Pre-2016 exemption, as enacted | buzer.de/gesetz/12213/a201265.htm (Art. 1 EEAusG, G. v. 13.10.2016, BGBl. I S. 2258) |
| 25 Feb 2025 amendment | Art. 4 EnWGEÜVÄndG, G. v. 21.02.2025, BGBl. 2025 I Nr. 51 |
| §24 EEG 2023, aggregation of installations | gesetze-im-internet.de/eeg_2014/__24.html |
| **§24 EEG 2014**, "Verringerung der Förderung bei negativen Preisen", in force 1 Aug 2014 – 31 Dec 2016 | haufe.de/id/norm/erneuerbare-energien-gesetz-2014-bis-31122016-24-verringerung-der-foerderung-bei-negativen-preisen-HI7054784_p24.html (commercial host of the statutory text; authoritative original: BGBl. I 2014 S. 1066) |
| §51(1) EEG 2023 as in force 1 Jan 2023 – 24 Feb 2025 | buzer.de/gesetz/11230/al211220-0.htm |

**Previously unresolved, now closed (29 Oct 2026): the pre-2017 section number.** The rule
was **§24 EEG 2014**, headed "Verringerung der Förderung bei negativen Preisen", in force
1 Aug 2014 – 31 Dec 2016. §24(1) required six consecutive negative hours on the EPEX Spot
SE hourly contracts for the DE/AT price zone; §24(3) exempted (1) installations commissioned
before 1 Jan 2016, (2) wind below 3 MW or other installations below 500 kW, with §32(1)
sentence 1 EEG 2014 for aggregation, and (3) demonstration projects. Note the aggregation
cross-reference is to **§32**, not §24, under the 2014 numbering. The rule became §51 on
1 January 2017 with an unchanged six-hour trigger.
