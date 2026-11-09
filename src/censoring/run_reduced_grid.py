"""The reduced E1 grid and its arms, for the week-6 gate (spec v1.8).

    python -m src.censoring.run_reduced_grid              everything
    python -m src.censoring.run_reduced_grid --only grid  one phase

Four phases, each writing its own CSV **incrementally** -- one row flushed per
finished cell -- so that a run of several hours cannot lose its work to a crash in
the last cell.

  grid     rates {10, 20, 40}% x gamma {0, 0.5, 1} x shape {step, logistic, half}
           x seeds {42, 43, 44} = 81 cells. This is what the gate is judged on.
  ladder   the ablation rungs, including A2b, on all three shapes at each gamma.
  proxy    weather-proxy quality as a dimension: corr with A_true 0.6 / 0.8 / 0.9,
           calibrated by noise level rather than set by hand.
  hetero   cohort-specific r*, so that the A3 ablation has something to detect.

Cohort shares are the REAL ones from the MaStR snapshot
(`results/30_mastr_cohort_shares.csv`), not the invented dict E1 used until
31 Oct 2026. Eight cohorts, led by pre-2016-in-support at 33.6% and out-of-support
at 16.7%; the fleet is far more weighted to old plants than the placeholders
assumed, which changes how much capacity sits at theta = 0 rather than at minus
the market premium.
"""

from __future__ import annotations

import argparse
import csv
import time
import traceback
from pathlib import Path

import numpy as np

from src.censoring import baselines as bl
from src.censoring.cohorts import mastr_cohort_set
from src.censoring.metrics import paired_abs_bias, paired_difference, recovery_skill
from src.censoring.model import TAUS, Ablation, TrainConfig, fit_m1, m1_response_curve
from src.censoring.metrics import score_method
from src.censoring.run_ablations import LADDER
from src.censoring.run_synthetic import DEPTH_GRID
from src.censoring.synthetic import SyntheticConfig, generate, true_response_curve

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
ARTIFACT_DIR = REPO_ROOT / "data" / "processed" / "e1_gate_artifacts"
#: Set by `main` when --merge-cohorts is passed, so a merged run writes beside the
#: original rather than over it. The originals are what docs/11, 12 and 17 were measured on.
MERGED_ARTIFACT_DIR = REPO_ROOT / "data" / "processed" / "e1_gate_artifacts_merged"
_artifact_dir = ARTIFACT_DIR


def artifact_path(cfg: SyntheticConfig) -> Path:
    """One file per grid cell. Not committed -- it is regenerable from the seed."""
    return _artifact_dir / (f"cell_r{int(round(cfg.censoring_rate * 100)):02d}"
                           f"_g{cfg.gamma}_{cfg.r_shape}_s{cfg.seed}.npz")

RATES = (0.10, 0.20, 0.40)
GAMMAS = (0.0, 0.5, 1.0)
SHAPES = ("step", "logistic", "half")
SEEDS = (42, 43, 44)
PROXY_CORRS = (0.6, 0.8, 0.9)

METHODS = ["M1", "B0", "B1", "B2", "B3", "B4", "B5", "Proxy", "Oracle"]
GATE_RIVALS = ["B1", "B2", "B3", "B4"]

# A2b: the honest counterfactual to the rule table -- one common threshold at zero,
# which is what a modeller without the register would assume. A2 (everyone always
# exposed) asserts a false structure instead, so its cost is an upper bound.
A2B = Ablation(label="A2b", name="common threshold at price < 0",
               piece_removed="the EEG rule table (common zero threshold instead)",
               exposure_mode="common_zero")
FULL_LADDER = list(LADDER) + [A2B]


PAIRED_FIELDS = ("paired_mae_diff", "paired_mae_sig", "m1_better_mae",
                 "paired_absbias_diff", "paired_absbias_sig", "m1_better_absbias")


class Writer:
    """Append-as-you-go CSV, header fixed by the first row plus `extra_fieldnames`.

    The extras exist because not every row carries every column. The M1 row has no
    paired-comparison columns -- it is the thing the others are paired against -- and
    M1 is written first, so until 1 Nov 2026 `extrasaction="ignore"` silently dropped
    the paired columns from the entire file. The 81-cell run of 31 Oct 2026 therefore
    could not be judged on gate criteria (b) and (c) at all. The action is now
    "raise": a column missing from the header stops the run instead of vanishing from
    it.
    """

    def __init__(self, path: Path, extra_fieldnames: tuple[str, ...] = ()):
        self.path = path
        self.extra = tuple(extra_fieldnames)
        self.fh = None
        self.writer = None

    def write(self, row: dict) -> None:
        if self.writer is None:
            fields = list(row) + [f for f in self.extra if f not in row]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.fh = open(self.path, "w", newline="", encoding="utf-8")
            self.writer = csv.DictWriter(self.fh, fieldnames=fields,
                                         lineterminator="\n", restval="",
                                         extrasaction="raise")
            self.writer.writeheader()
        self.writer.writerow(row)
        self.fh.flush()

    def close(self) -> None:
        if self.fh:
            self.fh.close()


def fit_all(data, train_cfg) -> dict:
    fits = {"M1": fit_m1(data, train_cfg)}
    for name in ("B0", "B1", "B2", "B3", "B4", "B5", "Proxy", "Oracle"):
        fits[name] = (bl.ALL_BASELINES[name](data) if name == "B0"
                      else bl.ALL_BASELINES[name](data, train_cfg))
    return fits


def save_artifact(path: Path, cfg: SyntheticConfig, data, fits: dict,
                  r_true: np.ndarray, r_hat: dict) -> None:
    """Per-quarter-hour predictions for one cell, so the gate needs no refit.

    The week-6 gate wants a paired event-day block bootstrap **pooled over seeds**
    (spec section 7). A per-cell row cannot carry that: pooling needs the individual
    quarter-hours of all three seeds in one resample. Scoring the gate off the CSV
    alone was therefore never possible, and re-fitting 729 models every time a gate
    criterion is re-read costs about four hours. These arrays are the fix.

    Everything is float32 and compressed. `depth` and `s` are (K, T) and mostly zero,
    so they compress to a fraction of their nominal size.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "censoring_rate": cfg.censoring_rate, "gamma": cfg.gamma,
        "r_shape": cfg.r_shape, "seed": cfg.seed, "area": cfg.area,
        "a_true": data.a_true_mw.astype(np.float32),
        "g_obs": data.g_obs_mw.astype(np.float32),
        "forecast": data.forecast_mw.astype(np.float32),
        "c_true": data.c_true.astype(np.float32),
        "censored": data.censored,
        "berlin_date": data.berlin_date.astype(str),
        "real_berlin_date": data.real_berlin_date.astype(str),
        "shares": np.asarray(data.cohorts.shares, dtype=np.float32),
        # Added 8 Nov 2026: a merged cohort set has K != 8, so `shares` alone no
        # longer identifies the rows of `s` and `depth`. Consumers that predate this
        # key fall back to mastr_cohort_set("DE").ids, which is correct for the
        # unmerged artifacts they were written against.
        "cohort_ids": np.asarray(data.cohorts.ids, dtype=str),
        "depth": data.depth.astype(np.float32),
        "s": data.s.astype(np.float32),
        "depth_grid": DEPTH_GRID.astype(np.float32),
        "r_curve_true": r_true.astype(np.float32),
        "r_curve_M1": r_hat["M1"].astype(np.float32),
        "r_curve_B3": r_hat["B3"].astype(np.float32),
        "struct_c_M1": np.asarray(fits["M1"]["c_hat"], dtype=np.float32),
    }
    for name, fit in fits.items():
        payload[f"a_hat_{name}"] = np.asarray(fit["a_hat"], dtype=np.float32)
    np.savez_compressed(path, **payload)


def score_cell(cfg: SyntheticConfig, train_cfg: TrainConfig, cohorts,
               artifact_path: Path | None = None) -> list[dict]:
    data = generate(cfg, cohorts=cohorts)
    r_true = true_response_curve(cfg, DEPTH_GRID)
    fits = fit_all(data, train_cfg)
    r_hat = {"M1": m1_response_curve(fits["M1"], data, DEPTH_GRID),
             "B3": bl.b3_response_curve(fits["B3"], DEPTH_GRID)}
    if artifact_path is not None:
        save_artifact(artifact_path, cfg, data, fits, r_true, r_hat)

    mae = lambda f: float(np.abs(f["a_hat"] - data.a_true_mw)[data.censored].mean())
    mae_b0, mae_oracle = mae(fits["B0"]), mae(fits["Oracle"])

    err = {n: np.abs(f["a_hat"] - data.a_true_mw) for n, f in fits.items()}
    signed = {n: f["a_hat"] - data.a_true_mw for n, f in fits.items()}

    rows = []
    for name in METHODS:
        row = score_method(fits[name], data, DEPTH_GRID, r_hat.get(name), r_true, TAUS)
        row.update(
            censoring_rate=cfg.censoring_rate, gamma=cfg.gamma, r_shape=cfg.r_shape,
            seed=cfg.seed, area=cfg.area,
            weather_corr=round(data.diagnostics["weather_corr_with_a_true"], 4),
            n_cohorts=len(data.cohorts),
            heterogeneous_r=cfg.r_cohort_offsets is not None,
            mae_b0=round(mae_b0, 1), mae_oracle=round(mae_oracle, 1),
            headroom_mw=round(mae_b0 - mae_oracle, 1),
            recovery_skill=recovery_skill(row["censored_mae_mw"], mae_b0, mae_oracle),
        )
        if name != "M1":
            pm = paired_difference(err["M1"], err[name], data.censored, data.berlin_date)
            pb = paired_abs_bias(signed["M1"], signed[name], data.censored,
                                 data.berlin_date)
            row.update(
                paired_mae_diff=round(pm["diff"], 2), paired_mae_sig=pm["significant"],
                m1_better_mae=pm["a_better"],
                paired_absbias_diff=round(pb["diff"], 2),
                paired_absbias_sig=pb["significant"], m1_better_absbias=pb["a_better"],
            )
        rows.append(row)
    return rows


def phase_grid(train_cfg, cohorts, writer: Writer) -> None:
    cells = [(r, g, sh, sd) for r in RATES for g in GAMMAS
             for sh in SHAPES for sd in SEEDS]
    print(f"\n=== GRID: {len(cells)} cells ===", flush=True)
    for i, (rate, gamma, shape, seed) in enumerate(cells, 1):
        t0 = time.perf_counter()
        cfg = SyntheticConfig(censoring_rate=rate, gamma=gamma, r_shape=shape, seed=seed)
        try:
            for row in score_cell(cfg, train_cfg, cohorts,
                                  artifact_path=artifact_path(cfg)):
                writer.write(row)
            print(f"  [{i:>3}/{len(cells)}] rate {rate:.0%} gamma {gamma} "
                  f"{shape:<9} seed {seed}  {time.perf_counter() - t0:6.1f}s", flush=True)
        except Exception:
            print(f"  [{i:>3}/{len(cells)}] FAILED rate {rate} gamma {gamma} "
                  f"{shape} seed {seed}", flush=True)
            traceback.print_exc()


def phase_ladder(train_cfg, cohorts, writer: Writer) -> None:
    print(f"\n=== LADDER: {len(SHAPES) * len(GAMMAS)} cells "
          f"x {len(FULL_LADDER)} rungs ===", flush=True)
    for shape in SHAPES:
        for gamma in GAMMAS:
            cfg = SyntheticConfig(censoring_rate=0.20, gamma=gamma, r_shape=shape,
                                  seed=42)
            data = generate(cfg, cohorts=cohorts)
            r_true = true_response_curve(cfg, DEPTH_GRID)
            b0 = bl.fit_b0(data)
            oracle = bl.fit_oracle(data, train_cfg)
            mae = lambda f: float(
                np.abs(f["a_hat"] - data.a_true_mw)[data.censored].mean())
            mae_b0, mae_oracle = mae(b0), mae(oracle)
            full_err = None
            for ab in FULL_LADDER:
                t0 = time.perf_counter()
                try:
                    fit = fit_m1(data, train_cfg, ablation=ab)
                    row = score_method(fit, data, DEPTH_GRID,
                                       m1_response_curve(fit, data, DEPTH_GRID),
                                       r_true, TAUS)
                    e = np.abs(fit["a_hat"] - data.a_true_mw)
                    if ab.label == "M1":
                        full_err = e
                    p = (paired_difference(e, full_err, data.censored, data.berlin_date)
                         if full_err is not None and ab.label != "M1" else {})
                    row.update(
                        ablation=ab.label, ablation_name=ab.name,
                        piece_removed=ab.piece_removed,
                        differs_from_full=";".join(ab.differs_from_full()) or "-",
                        r_shape=shape, gamma=gamma, seed=42, censoring_rate=0.20,
                        mae_b0=round(mae_b0, 1), mae_oracle=round(mae_oracle, 1),
                        recovery_skill=recovery_skill(row["censored_mae_mw"],
                                                      mae_b0, mae_oracle),
                        cost_vs_full_mw=round(p.get("diff", float("nan")), 2),
                        cost_sig=p.get("significant", ""),
                        fit_seconds=round(time.perf_counter() - t0, 1),
                    )
                    writer.write(row)
                except Exception:
                    print(f"    FAILED {ab.label} {shape} gamma {gamma}", flush=True)
                    traceback.print_exc()
            print(f"  ladder {shape:<9} gamma {gamma} done", flush=True)


def phase_proxy(train_cfg, cohorts, writer: Writer) -> None:
    print(f"\n=== PROXY QUALITY: {len(PROXY_CORRS)} x {len(GAMMAS)} ===", flush=True)
    for corr in PROXY_CORRS:
        for gamma in GAMMAS:
            t0 = time.perf_counter()
            cfg = SyntheticConfig(censoring_rate=0.20, gamma=gamma, r_shape="logistic",
                                  seed=42, weather_target_corr=corr)
            try:
                for row in score_cell(cfg, train_cfg, cohorts):
                    row["proxy_target_corr"] = corr
                    writer.write(row)
                print(f"  proxy corr {corr} gamma {gamma}  "
                      f"{time.perf_counter() - t0:6.1f}s", flush=True)
            except Exception:
                traceback.print_exc()


def phase_hetero(train_cfg, cohorts, writer: Writer) -> None:
    """Cohort-specific r*, so A3 (one cohort) has something to detect.

    Offsets are spread across the cohorts in capacity order and are deliberately
    large enough to matter: with a shared r* the single-cohort ablation reproduces
    the truth exactly, which is why the earlier ladder found no cost for A3.
    """
    n = len(cohorts)
    offsets = tuple(np.linspace(-0.25, 0.25, n))
    print(f"\n=== HETEROGENEOUS r*: offsets {np.round(offsets, 3).tolist()} ===",
          flush=True)
    for gamma in GAMMAS:
        cfg = SyntheticConfig(censoring_rate=0.20, gamma=gamma, r_shape="logistic",
                              seed=42, r_cohort_offsets=offsets)
        data = generate(cfg, cohorts=cohorts)
        r_true = true_response_curve(cfg, DEPTH_GRID)
        full_err = None
        for ab in (FULL_LADDER[0], *(a for a in FULL_LADDER if a.label in ("A3", "A2b"))):
            t0 = time.perf_counter()
            try:
                fit = fit_m1(data, train_cfg, ablation=ab)
                row = score_method(fit, data, DEPTH_GRID,
                                   m1_response_curve(fit, data, DEPTH_GRID),
                                   r_true, TAUS)
                e = np.abs(fit["a_hat"] - data.a_true_mw)
                if ab.label == "M1":
                    full_err = e
                p = (paired_difference(e, full_err, data.censored, data.berlin_date)
                     if full_err is not None and ab.label != "M1" else {})
                row.update(ablation=ab.label, gamma=gamma, r_shape="logistic",
                           seed=42, heterogeneous_r=True,
                           cost_vs_full_mw=round(p.get("diff", float("nan")), 2),
                           cost_sig=p.get("significant", ""),
                           fit_seconds=round(time.perf_counter() - t0, 1))
                writer.write(row)
            except Exception:
                traceback.print_exc()
        print(f"  hetero gamma {gamma} done", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", choices=("grid", "ladder", "proxy", "hetero"),
                    default=None)
    ap.add_argument("--max-epochs", type=int, default=2000)
    ap.add_argument("--merge-cohorts", action="store_true",
                    help="merge indistinguishable cohorts before generating "
                         "(docs/12 step C). Writes to a SEPARATE artifact dir and "
                         "suffixes the result CSVs, so the unmerged run is kept.")
    args = ap.parse_args()

    global _artifact_dir
    train_cfg = TrainConfig(max_epochs=args.max_epochs)
    cohorts = mastr_cohort_set("DE")
    suffix = ""
    if args.merge_cohorts:
        from src.censoring.identification import (
            format_merge_map, identification_diagnostics, merge_cohorts,
        )
        from src.censoring.synthetic import generate as _gen

        # The merge key is the realised (s, depth) block, which is cell-dependent in
        # principle. Verify the map is the SAME on several cells rather than trusting
        # one probe; the theta = 0 pair is structural and the AW = 66 pair comes from
        # constant thetas, so it should be, but an assumption here would silently
        # change the design between cells.
        probes = [SyntheticConfig(censoring_rate=r, gamma=g, r_shape=sh, seed=sd)
                  for r, g, sh, sd in ((0.10, 0.0, "step", 42),
                                       (0.20, 0.5, "logistic", 43),
                                       (0.40, 1.0, "half", 44))]
        maps = []
        for pc in probes:
            d = _gen(pc, cohorts)
            _, _, gmap = merge_cohorts(cohorts, np.hstack([d.s, d.depth]), d.theta,
                                      rule="exposure")
            maps.append(tuple(sorted(tuple(sorted(g.members)) for g in gmap)))
        if len(set(maps)) != 1:
            raise SystemExit(
                "the merge map is not stable across cells; refusing to generate a "
                f"grid whose cohort design varies by cell. maps = {maps}")
        d0 = _gen(probes[1], cohorts)
        merged, _, gmap = merge_cohorts(cohorts, np.hstack([d0.s, d0.depth]), d0.theta,
                                      rule="exposure")
        print(f"\n--merge-cohorts: K {len(cohorts)} -> {len(merged)}, "
              f"map verified identical on {len(probes)} cells")
        print(format_merge_map(gmap))
        before = identification_diagnostics(d0.s, cohorts.ids,
                                            list(cohorts.shares), d0.depth,
                                            label="before merge")
        dm = _gen(probes[1], merged)
        after = identification_diagnostics(dm.s, merged.ids, list(merged.shares),
                                           dm.depth, label="after merge")
        print(f"  rank {before.exposure.rank}/{before.exposure.k} -> "
              f"{after.exposure.rank}/{after.exposure.k}   "
              f"collinear capacity {100 * before.collinear_capacity_share:.1f}% -> "
              f"{100 * after.collinear_capacity_share:.1f}%")
        cohorts = merged
        _artifact_dir = MERGED_ARTIFACT_DIR
        suffix = "_merged"
        print(f"  artifacts -> {_artifact_dir.relative_to(REPO_ROOT)}")

    print(f"\ncohort shares, {len(cohorts)} cohorts:")
    for c in cohorts:
        print(f"  {c.cohort_id:<48}{c.capacity_share:7.2%}  {c.clock}")

    phases = {
        "grid": (phase_grid, f"12_reduced_grid{suffix}.csv", PAIRED_FIELDS),
        "ladder": (phase_ladder, f"12_ladder{suffix}.csv", ()),
        "proxy": (phase_proxy, f"12_proxy_quality{suffix}.csv", PAIRED_FIELDS),
        "hetero": (phase_hetero, f"12_hetero_r{suffix}.csv", ()),
    }
    chosen = [args.only] if args.only else list(phases)
    wall0 = time.perf_counter()
    for name in chosen:
        fn, out, extras = phases[name]
        w = Writer(RESULTS_DIR / out, extra_fieldnames=extras)
        try:
            fn(train_cfg, cohorts, w)
        finally:
            w.close()
        print(f"wrote results/{out}", flush=True)
    print(f"\nTotal wall clock: {(time.perf_counter() - wall0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
