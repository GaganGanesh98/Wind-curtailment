"""Generated blocks for docs/12b_learned_potential_results.md, read from the Experiment 4
artifacts so the number checker holds every figure."""

from __future__ import annotations

import polars as pl

from src.method.learned_potential import config as cfg
from src.method.learned_potential.data import ART

MODELS_ORDER = ("F", "H", "L1", "L2", "N1")
UNITS = (*cfg.AREAS, "pooled area rows", "three-area aggregate")


def _scores() -> pl.DataFrame:
    return pl.read_csv(ART / "lookalike_scores.csv")


def _iv(r: dict | None) -> str:
    if r is None:
        return "—"
    return f"{r['value']:+.4f} [{r['lo']:+.4f}, {r['hi']:+.4f}]".replace("-", "−")


def _iv_pos(r: dict | None, places: int = 4) -> str:
    if r is None:
        return "—"
    return f"{r['value']:.{places}f} [{r['lo']:.{places}f}, {r['hi']:.{places}f}]"


def lookalike_table(subset: str) -> str:
    s = _scores().filter(pl.col("subset") == subset)
    get = lambda m, u, k: next((r for r in s.filter((pl.col("model") == m) & (pl.col("unit") == u)  # noqa: E731
                                                     & pl.col("metric").str.starts_with(k)).iter_rows(named=True)), None)
    out = ["| unit | model | quarter-hours / days | σ of log(G / Â) | mean of log(G / Â) | pinball loss | 0.05–0.95 coverage |",
           "|---|---|---|---|---|---|---|"]
    for u in UNITS:
        for m in MODELS_ORDER:
            sg = get(m, u, "sigma")
            if sg is None:
                continue
            out.append(f"| {u} | {m} | {sg['n_qh']:,} / {sg['n_days']} | {_iv_pos(sg)} | {_iv(get(m, u, 'bias'))} "
                       f"| {_iv_pos(get(m, u, 'pinball'))} | {_iv_pos(get(m, u, 'coverage'), 3)} |")
    return "\n".join(out)


def folds_table() -> str:
    f = pl.read_csv(ART / "gbm_fold_training.csv")
    out = ["| scored month | last training day | training rows (L1 = L2) | sum of weights, L2 | target rows in training | look-alike rows of the scored month in training |",
           "|---|---|---|---|---|---|"]
    for r in f.iter_rows(named=True):
        out.append(f"| {r['month']} | {r['train_last_day']} | {r['n_train_recomputed']:,} | {r['sum_w_L2']:,.0f} "
                   f"| {r['target_rows_in_train']} | {r['rows_on_or_after_month']} |")
    return "\n".join(out)


def selection_table() -> str:
    s = pl.read_csv(ART / "gbm_selection.csv")
    out = ["| model | leaves | trees | median pinball loss, validation month | chosen |", "|---|---|---|---|---|"]
    for r in s.iter_rows(named=True):
        out.append(f"| {r['model']} | {r['num_leaves']} | {r['n_estimators']} | {r['median_pinball']:.4f} "
                   f"| {'yes' if r['chosen'] else ''} |")
    return "\n".join(out)


def selection_note() -> str:
    s = pl.read_csv(ART / "gbm_selection.csv").filter(pl.col("chosen"))
    leaves = sorted({d["num_leaves"] for d in cfg.GBM_GRID})
    trees = sorted({d["n_estimators"] for d in cfg.GBM_GRID})
    parts = []
    for r in s.iter_rows(named=True):
        edge = []
        if r["num_leaves"] in (leaves[0], leaves[-1]):
            edge.append(f"{r['num_leaves']} leaves is the {'lower' if r['num_leaves'] == leaves[0] else 'upper'} edge")
        if r["n_estimators"] in (trees[0], trees[-1]):
            edge.append(f"{r['n_estimators']} trees is the {'lower' if r['n_estimators'] == trees[0] else 'upper'} edge")
        parts.append(f"{r['model']}: {' and '.join(edge)}")
    return ("- **Grid edge.** Both selections sit at the edge of the pre-registered grid ("
            + "; ".join(parts) + "). In a two-by-two grid every point is an edge; the grid is not "
            "changed, and a model outside it might have scored better.")


def _agg(model: str, metric: str, subset: str = "all look-alike") -> dict | None:
    s = _scores().filter((pl.col("subset") == subset) & (pl.col("unit") == "three-area aggregate")
                         & (pl.col("model") == model) & pl.col("metric").str.starts_with(metric))
    return s.row(0, named=True) if s.height else None


def criteria(learned=("L1", "L2")) -> str:
    have = [m for m in learned if _agg(m, "sigma")]
    f = _agg("F", "sigma")
    best = min(have, key=lambda m: _agg(m, "sigma")["value"])
    b = _agg(best, "sigma")
    s1 = b["value"] < f["value"]
    l1 = _agg("L1", "sigma")
    weighted = [m for m in have if m != "L1"]
    s3 = all(_agg(m, "sigma")["value"] <= l1["value"] for m in weighted)
    cand = [m for m in have if m in cfg.CANDIDATES]
    sel = min(cand, key=lambda m: (round(abs(_agg(m, "bias")["value"]), cfg.TIE_DECIMALS), _agg(m, "sigma")["value"]))
    sb = _agg(sel, "bias")
    s2 = (sb["lo"] >= -cfg.S2_HALF_WIDTH) and (sb["hi"] <= cfg.S2_HALF_WIDTH)
    fmt = lambda r: f"{r['value']:.4f} [{r['lo']:.4f}, {r['hi']:.4f}]"  # noqa: E731
    return "\n".join([
        f"- **S1 ({'PASS' if s1 else 'FAIL'}).** Best learned model by aggregate look-alike σ: {best}, "
        f"{fmt(b)}, against F's {fmt(f)}. The two intervals overlap almost entirely.",
        f"- **S3 ({'PASS' if s3 else 'FAIL'}).** "
        + "; ".join(f"{m} σ {fmt(_agg(m, 'sigma'))}" for m in weighted)
        + f", against L1's {fmt(l1)}. Reported as pre-registered; the weighting is not dropped.",
        f"- **S2 (preliminary, {'PASS' if s2 else 'FAIL'}).** Selected so far by the rule (lowest "
        f"aggregate look-alike |bias|, ties by σ): {sel}, bias {fmt(sb)}; the interval must lie within "
        f"±{cfg.S2_HALF_WIDTH:g}. N1 is not fitted yet, so this can still change.",
    ])


def sunny_note() -> str:
    s = _scores().filter(pl.col("subset") == "sunny look-alike days")
    d = {u: s.filter(pl.col("unit") == u)["n_days"].max() for u in UNITS}
    absent = [u for u in UNITS if d[u] is None]
    have = ", ".join(f"{u} {d[u]}" for u in UNITS if d[u] is not None)
    return ("- **Sunny look-alike days** (descriptive only, not a criterion): look-alike days whose clean "
            "quarter-hours have a median solar forecast above the clean set's 75th percentile. Days: "
            + have + ("; none in " + ", ".join(absent) if absent else "")
            + ". So the look-alike check reaches sunny conditions only on a handful of days.")


# ------------------------------------------------- expectation before N1 (doc 44)

EXPECTATION = ART / "expectation_before_n1.csv"


def expectation_rows() -> list[dict]:
    """Descriptive, before N1 is fitted. Assumption: at fixed look-alike days the bias interval's
    half-width scales in proportion to σ of log(G / Â). For each scored model at the aggregate,
    σ* = σ × S2_HALF_WIDTH / half-width is the σ at which an unbiased model's interval would just
    lie within ±S2_HALF_WIDTH."""
    out = []
    for m in ("F", "L1", "L2"):
        b, s = _agg(m, "bias"), _agg(m, "sigma")
        half = (b["hi"] - b["lo"]) / 2.0
        out.append({"kind": "sigma_needed", "model": m, "sigma": s["value"], "bias_half_width": half,
                    "sigma_needed": s["value"] * cfg.S2_HALF_WIDTH / half, "fold": None, "kish_ess": None,
                    "n_train": None})
    return out


def kish_rows() -> list[dict]:
    """Kish effective sample size of L2's training weights per fold: (Σw)² / Σw²."""
    from src.method.learned_potential.data import eval_months, train_mask
    from src.method.learned_potential.models_gbm import rows
    d = rows()
    out = []
    for month in eval_months():
        w = d.filter(train_mask(d, month))["w"].to_numpy()
        out.append({"kind": "kish_ess_L2", "model": "L2", "sigma": None, "bias_half_width": None,
                    "sigma_needed": None, "fold": month, "kish_ess": float(w.sum() ** 2 / (w ** 2).sum()),
                    "n_train": int(w.size)})
    return out


def expectation_note() -> str:
    e = pl.read_csv(EXPECTATION)
    s = e.filter(pl.col("kind") == "sigma_needed")
    k = e.filter(pl.col("kind") == "kish_ess_L2").with_columns((pl.col("kish_ess") / pl.col("n_train")).alias("r"))
    first, last = k.row(0, named=True), k.row(-1, named=True)
    rows_ = "; ".join(f"{r['model']}: σ {r['sigma']:.4f}, half-width {r['bias_half_width']:.4f}, "
                      f"σ needed {r['sigma_needed']:.3f}" for r in s.iter_rows(named=True))
    return "\n".join([
        f"- **σ an unbiased model would need** for its aggregate look-alike bias interval to lie within "
        f"±{cfg.S2_HALF_WIDTH:g}: {rows_}. Assumption: on the same look-alike days the interval's "
        f"half-width scales in proportion to σ, so the needed σ is σ × {cfg.S2_HALF_WIDTH:g} / half-width. "
        f"It ignores any change in how errors cluster within days.",
        f"- **Kish effective sample size of L2's weights**, (Σw)² / Σw², per fold: from "
        f"{first['kish_ess']:,.0f} of {first['n_train']:,} training rows ({first['r']:.1%}) in the "
        f"{first['fold']} fold to {last['kish_ess']:,.0f} of {last['n_train']:,} ({last['r']:.1%}) in the "
        f"{last['fold']} fold (`artifacts/exp4_learned_potential/expectation_before_n1.csv`).",
        "- Descriptive only; no criterion changes.",
    ])


def write_expectation() -> None:
    pl.DataFrame(expectation_rows() + kish_rows(), infer_schema_length=None).write_csv(EXPECTATION)
    print(f"wrote {EXPECTATION}")


if __name__ == "__main__":
    write_expectation()
