#!/usr/bin/env python3
"""Run the E1 grid on the real panel and write only the diagnostics table.

Generation is deterministic given (config, seed), so the 225 per-cell frames are
not stored: the diagnostics table plus the config reproduces any cell. Three
representative frames are written for inspection.

Usage:
  python src/e1_run_grid.py \
      --panel data/processed/panel_qh.parquet \
      --cols 'timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw' \
      --area DE --out-dir data/e1
"""

from __future__ import annotations

import argparse
import os
import time

import pandas as pd

from e1_generator import (E1Config, ResponseSpec, generate, generate_grid,
                          parse_panel_spec)

RATES = (0.05, 0.10, 0.20, 0.30, 0.40)
GAMMAS = (0.0, 0.5, 1.0)
SHAPES = ("step", "logistic", "half")
SEEDS = (0, 1, 2, 3, 4)

# representative frames: the mid rate, all three gammas, at the repo's seed
REP_RATE, REP_SHAPE, REP_SEED = 0.20, "logistic", 42


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--panel", required=True)
    p.add_argument("--cols")
    p.add_argument("--area")
    p.add_argument("--from-date", help="keep berlin_date >= this (study period)")
    p.add_argument("--out-dir", default="data/e1")
    p.add_argument("--tag", default="", help="suffix for the output filenames")
    a = p.parse_args()

    cols = parse_panel_spec(a.cols)
    panel = pd.read_parquet(a.panel)
    if a.area:
        panel = panel.loc[panel[cols.area].astype(str) == a.area].copy()
    if a.from_date:
        panel = panel.loc[panel["berlin_date"] >= a.from_date].copy()
    if panel.empty:
        p.error("no rows left after filtering")
    print(f"panel rows = {len(panel):,}  area={a.area}  from={a.from_date}")

    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.time()
    table = generate_grid(panel, rates=RATES, gammas=GAMMAS, shapes=SHAPES,
                          seeds=SEEDS, cols=cols, out_dir=None, verbose=True)
    wall = time.time() - t0

    diag_path = os.path.join(a.out_dir, f"e1_grid_diagnostics{a.tag}.csv")
    table.to_csv(diag_path, index=False)
    print(f"\ncells = {len(table)}   rate target met = "
          f"{int(table.rate_target_met.sum())}/{len(table)}")
    print(f"wall clock = {wall:.1f} s ({wall/60:.2f} min)")
    print(f"wrote {diag_path}")

    for gam in GAMMAS:
        cfg = E1Config(censoring_rate=REP_RATE, gamma=gam,
                       response=ResponseSpec(shape=REP_SHAPE),  # type: ignore[arg-type]
                       seed=REP_SEED)
        frame, d = generate(panel, cfg, cols)
        name = (f"e1_{(a.area or 'ALL').lower()}_r{int(REP_RATE*100):02d}"
                f"_g{gam}_{REP_SHAPE}_s{REP_SEED}{a.tag}.parquet")
        path = os.path.join(a.out_dir, name)
        frame.to_parquet(path, index=False)
        print(f"wrote {path}  ({len(frame):,} rows, "
              f"realised {d['realised_rate']:.4f}, "
              f"corr {d['confounding_corr_F_vs_c']:+.4f})")


if __name__ == "__main__":
    main()
