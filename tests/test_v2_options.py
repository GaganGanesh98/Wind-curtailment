"""bias_robust.run_v2's new options (Phase 4, 22 Nov 2026) leave the pre-registered V2 run as it
was: the default grid is the committed one, and the default fit reproduces it bit for bit."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from src.method import bias_robust as br

REPO_ROOT = Path(__file__).resolve().parents[1]
CELLS = REPO_ROOT / "artifacts" / "exp3_german_application" / "bias_robust_full_window_cells.csv"


def test_default_grid_is_the_committed_v2_grid():
    c = pl.read_csv(CELLS, infer_schema_length=0)
    assert br.grid(br.V2_BMAX) == [float(x) for x in c["b"].unique(maintain_order=True)]
    assert [str(b) for b in br.grid(br.V2_BMAX)] == c["b"].unique(maintain_order=True).to_list()


def test_fine_grid_has_49_points_and_never_targets_the_v2_file():
    g = br.grid(0.06, 0.0025)
    assert len(g) == 49 and g[0] == -0.06 and g[-1] == 0.06 and 0.0325 in g
    with pytest.raises(ValueError):
        br.run_v2(step=0.0025, bmax=0.06, out=None)


@pytest.mark.needs_data("data/processed/panel_qh.parquet")
def test_default_v2_fit_at_b0_reproduces_the_committed_cells_bit_for_bit():
    from src.method.real_panel import THREE_AREA, load_panel, run_arm
    panel = load_panel(THREE_AREA, "H")
    rows = run_arm(panel, "main", panel["keep"], "window", False)
    ref = {r["lam"]: r for r in pl.read_csv(CELLS, infer_schema_length=0).filter(
        pl.col("b") == "0.0").iter_rows(named=True)}
    for r in rows:
        for k in ("lo", "hi", "eps", "width"):
            assert str(r[k]) == ref[r["lam"]][k], (r["lam"], k)


def test_masked_run_never_targets_the_v2_file():
    with pytest.raises(ValueError):
        br.run_v2(masks=("M0",))


@pytest.mark.needs_data("data/processed/panel_qh.parquet")
def test_masks_only_remove_quarter_hours_and_m1_keeps_at_least_m0():
    """No mask adds a quarter-hour; M1 (R > 1% of H) drops a subset of what M0 (R > 0) drops."""
    from src.method.real_panel import THREE_AREA, load_panel
    panel = load_panel(THREE_AREA, "H")
    k0 = panel["keep"] & br.redispatch_keep(panel, "M0")
    k1 = panel["keep"] & br.redispatch_keep(panel, "M1")
    assert k0.sum() < panel["keep"].sum() and (k0 <= k1).all() and (k1 <= panel["keep"]).all()


@pytest.mark.needs_data("data/processed/panel_qh.parquet")
def test_run_v2_unmasked_path_reproduces_the_headline_rows(tmp_path):
    """run_v2 without masks, at b = 0 only, writes the committed V2 b = 0 rows (all columns but
    git_head), so the new mask option leaves the headline path bit for bit as it was."""
    out = br.run_v2(bmax=0.0, out=tmp_path / "v2_b0.csv")
    got = pl.read_csv(out, infer_schema_length=0).drop("git_head")
    ref = pl.read_csv(CELLS, infer_schema_length=0).filter(pl.col("b") == "0.0").drop("git_head")
    assert got.columns == ref.columns
    assert got.equals(ref)
