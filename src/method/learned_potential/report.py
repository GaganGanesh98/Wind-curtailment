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
        (f"- **S2 (preliminary, {'PASS' if s2 else 'FAIL'}).** Selected so far by the rule (lowest "
         f"aggregate look-alike |bias|, ties by σ): {sel}, bias {fmt(sb)}; the interval must lie within "
         f"±{cfg.S2_HALF_WIDTH:g}. N1 is not fitted yet, so this can still change.")
        if "N1" not in have else
        (f"- **S2 ({'PASS' if s2 else 'FAIL'}).** All three learned models are fitted. The rule (lowest "
         f"aggregate look-alike |bias|, ties by σ) selects {sel}, bias {fmt(sb)}; the interval must lie "
         f"within ±{cfg.S2_HALF_WIDTH:g}. "
         + ("B̂ can be computed in step 4." if s2 else
            "As pre-registered, B̂ is reported as not estimable with public inputs, and the readings are "
            "not compared against it.")),
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


# ------------------------------------------------------------- N1 loss trace (doc 46)

TRACE = ART / "cnn_loss_trace.csv"
TRACE_SUMMARY = ART / "cnn_trace_summary.csv"
FLAT_BAND = 0.02          # every epoch within 2% of the best validation loss
DROP_TOL = 0.005          # after the best, no epoch-to-epoch drop larger than 0.5% of the best
RISE_END = 0.02           # and the last epoch at least 2% above the best


def trace_pattern(val: list[float], best_epoch: int) -> str:
    vb = val[best_epoch - 1]
    rel = [(v - vb) / vb for v in val]
    if max(abs(r) for r in rel) < FLAT_BAND:
        return "flat"
    post = val[best_epoch - 1:]
    steps_ok = all(b - a >= -DROP_TOL * vb for a, b in zip(post, post[1:]))
    if steps_ok and rel[-1] >= RISE_END:
        return "rising after the best epoch"
    return "unstable"


def trace_summary() -> pl.DataFrame:
    t = pl.read_csv(TRACE)
    out = []
    for (fit, layers, channels), g in t.group_by(["fit", "layers", "channels"], maintain_order=True):
        g = g.sort("epoch")
        be = int(g["best_epoch"][0])
        val, tr = g["val_loss_weighted"].to_list(), g["train_loss_weighted"].to_list()
        out.append({"fit": fit, "layers": layers, "channels": channels, "epochs": g.height,
                    "best_epoch": be, "train_epoch1": tr[0], "train_best": tr[be - 1], "train_last": tr[-1],
                    "val_epoch1": val[0], "val_best": val[be - 1], "val_last": val[-1],
                    "val_max_rel_to_best": max((v - val[be - 1]) / val[be - 1] for v in val),
                    "pattern": trace_pattern(val, be),
                    "val_first_day": g["val_first_day"][0], "val_last_day": g["val_last_day"][0]})
    return pl.DataFrame(out)


def trace_table() -> str:
    s = pl.read_csv(TRACE_SUMMARY)
    out = ["| fit | config | epochs | best epoch | train loss: epoch 1 / best / last | validation loss: epoch 1 / best / last | max above best | pattern |",
           "|---|---|---|---|---|---|---|---|"]
    for r in s.iter_rows(named=True):
        out.append(f"| {r['fit']} | {r['layers']} × {r['channels']} | {r['epochs']} | {r['best_epoch']} "
                   f"| {r['train_epoch1']:.4f} / {r['train_best']:.4f} / {r['train_last']:.4f} "
                   f"| {r['val_epoch1']:.4f} / {r['val_best']:.4f} / {r['val_last']:.4f} "
                   f"| {r['val_max_rel_to_best']:.1%} | {r['pattern']} |")
    return "\n".join(out)


def trace_note() -> str:
    s = pl.read_csv(TRACE_SUMMARY)
    counts = s.group_by("pattern").len().sort("pattern")
    c = ", ".join(f"{r['pattern']} {r['len']}" for r in counts.iter_rows(named=True))
    folds = s.filter(pl.col("fit") != "selection")
    return "\n".join([
        f"- **Rule.** With rel = (validation loss − best) / best: flat if every epoch is within "
        f"{FLAT_BAND:.0%} of the best; rising after the best epoch if, from the best epoch on, no "
        f"epoch-to-epoch fall exceeds {DROP_TOL:.1%} of the best and the last epoch is at least "
        f"{RISE_END:.0%} above it; unstable otherwise. Descriptive only.",
        f"- **Counts over the {s.height} fits:** {c}. Training loss falls in every fit (epoch 1 to last: "
        f"{s['train_epoch1'].min():.4f}–{s['train_epoch1'].max():.4f} to "
        f"{s['train_last'].min():.4f}–{s['train_last'].max():.4f}); the folds' best epochs run from "
        f"{folds['best_epoch'].min()} to {folds['best_epoch'].max()}.",
        "- The validation windows are the last 28 days of each training span, so their level moves with "
        "the season of that window; compare curves within a fit, not across fits.",
    ])


def cnn_selection_table() -> str:
    s = pl.read_csv(ART / "cnn_selection.csv")
    out = ["| layers | channels | weighted median pinball loss, validation month | best epoch | chosen |",
           "|---|---|---|---|---|"]
    for r in s.iter_rows(named=True):
        out.append(f"| {r['layers']} | {r['channels']} | {r['median_pinball_weighted']:.4f} | {r['best_epoch']} "
                   f"| {'yes' if r['chosen'] else ''} |")
    return "\n".join(out)


def cnn_selection_note() -> str:
    r = pl.read_csv(ART / "cnn_selection.csv").filter(pl.col("chosen")).row(0, named=True)
    lay = sorted({g["layers"] for g in cfg.CNN_GRID})
    ch = sorted({g["channels"] for g in cfg.CNN_GRID})
    e = lambda v, s: "lower" if v == s[0] else ("upper" if v == s[-1] else "inner")    # noqa: E731
    return (f"- **Grid edge.** The selection chose {r['layers']} layers and {r['channels']} channels: the "
            f"{e(r['layers'], lay)} edge of the layers axis and the {e(r['channels'], ch)} edge of the "
            f"channels axis, the smallest configuration in the pre-registered grid. The grid is not changed "
            f"and nothing was retuned; a smaller network outside it might have scored better.")


def selected_model() -> str:
    have = [m for m in cfg.CANDIDATES if _agg(m, "bias")]
    return min(have, key=lambda m: (round(abs(_agg(m, "bias")["value"]), cfg.TIE_DECIMALS), _agg(m, "sigma")["value"]))


# ------------------------------------------------------------------ step 4 (reduced)

def _m(x: float, p: int = 4) -> str:
    return f"{x:+.{p}f}".replace("-", "−")


def bias_table() -> str:
    b = pl.read_csv(ART / "bias_budget.csv")
    out = ["| unit | arm | target quarter-hours (share kept) | b̂_H, mean log(H / Â) | L2 look-alike bias, mean log(G / Â) | corrected, mean log(H / A) | status |",
           "|---|---|---|---|---|---|---|"]
    for r in b.iter_rows(named=True):
        out.append(f"| {r['unit']} | {r['arm']} | {r['n_target_qh']:,} ({r['share_of_target_kept']:.1%}) "
                   f"| {_m(r['b_hat_H'])} [{_m(r['b_hat_H_lo'])}, {_m(r['b_hat_H_hi'])}] "
                   f"| {_m(r['beta_A_lookalike'])} [{_m(r['beta_lo'])}, {_m(r['beta_hi'])}] "
                   f"| {_m(r['corrected'])} [{_m(r['corrected_lo'])}, {_m(r['corrected_hi'])}] | {r['status']} |")
    return "\n".join(out)


def arm_table() -> str:
    a = pl.read_csv(ART / "exp3_arm_readings.csv", infer_schema_length=0)
    sym = {"L1": "λ₁", "L2": "λ₂", "L3": "λ₃", "L6": "λ₆"}
    out = ["| reading | under H: interval at B = 0, holds, breakdown | under Â (L2): interval at B = 0, holds, breakdown | agrees |",
           "|---|---|---|---|"]
    for r in a.iter_rows(named=True):
        f = lambda lo, hi: f"[{float(lo):.3f}, {float(hi):.3f}]".replace("-", "−")   # noqa: E731
        yn = lambda v: "yes" if v == "true" else "no"                                  # noqa: E731
        hb = r["H_breakdown"] if r["H_breakdown"].startswith(">") else f"{float(r['H_breakdown']):.2f}"
        ab = r["A_breakdown"] if r["A_breakdown"].startswith(">") else f"{float(r['A_breakdown']):.2f}"
        out.append(f"| {sym[r['lam']]} {r['reading']} | {f(r['H_lo_B0'], r['H_hi_B0'])}, {yn(r['H_holds_B0'])}, {hb} "
                   f"| {f(r['A_lo_B0'], r['A_hi_B0'])}, {yn(r['A_holds_B0'])}, {ab} | {yn(r['agree'])} |")
    return "\n".join(out)


def arm_note() -> str:
    a = pl.read_csv(ART / "exp3_arm_readings.csv", infer_schema_length=0)
    c = pl.read_csv(ART / "exp3_with_learned_potential.csv", infer_schema_length=0).filter(pl.col("b") == "0.0").row(0, named=True)
    h = pl.read_csv(ART.parent / "exp3_german_application" / "bias_robust_full_window_cells.csv",
                    infer_schema_length=0).filter(pl.col("b") == "0.0").row(0, named=True)
    n_agree = int((a["agree"] == "true").sum())
    agg = pl.read_csv(ART / "bias_budget.csv").filter(pl.col("unit") == "three-area aggregate")
    prim = agg.filter(pl.col("arm").str.starts_with("trimmed")).row(0, named=True)
    return "\n".join([
        f"- **Agreement:** {n_agree} of {a.height} readings agree with the headline. Under Â the data-fit "
        f"tolerance ε at B = 0 is {float(c['eps']):.3f}, against {float(h['eps']):.3f} under H, on the same "
        f"{int(c['n_qh_period']):,} quarter-hours: Â follows output much less closely than H, so every "
        f"identified set widens. As fixed before step 4, this disagreement is not resolved by public "
        f"data and is not evidence that H is wrong.",
        f"- **b̂_H** at the aggregate, trimmed (primary): corrected mean log(H / A) "
        f"{_m(prim['corrected'])} [{_m(prim['corrected_lo'])}, {_m(prim['corrected_hi'])}]. Descriptive "
        f"only: L2 failed S2, no B̂ is defined and no reading is classified against it. It cannot tell "
        f"H adding back more than was curtailed apart from Â, which never saw negative-price hours, "
        f"falling short there.",
    ])


# ------------------------------------------------------------------ step 5 summaries

def _gap() -> tuple[float, float, str]:
    e = pl.read_csv(EXPECTATION).filter(pl.col("kind") == "sigma_needed")
    need = float(e.filter(pl.col("model") != "F")["sigma_needed"].min())
    have = [m for m in cfg.CANDIDATES if _agg(m, "sigma")]
    best = min(have, key=lambda m: _agg(m, "sigma")["value"])
    return need, _agg(best, "sigma")["value"], best


def summary_text() -> str:
    need, got, best = _gap()
    sel = selected_model()
    b = _agg(sel, "bias")
    return "\n".join([
        f"- **S2 failed.** The selected model, {sel}, has an aggregate look-alike bias of "
        f"{b['value']:.4f} [{b['lo']:.4f}, {b['hi']:.4f}], not within ±{cfg.S2_HALF_WIDTH:g}. B̂ is "
        f"therefore not estimable with public inputs, and no reading is classified against a budget.",
        f"- **The σ gap.** For an unbiased model's interval to fit within ±{cfg.S2_HALF_WIDTH:g}, its "
        f"aggregate look-alike σ would need to be about {need:.3f} (expectation section above); the best "
        f"learned model, {best}, reached {got:.3f}. Neither the shift correction nor the temporal model "
        f"closed that gap.",
    ])


def subquestion_answer() -> str:
    need, got, _ = _gap()
    o = {r["unit"]: r for r in pl.read_csv(ART / "domain_overlap.csv").iter_rows(named=True)}
    return ("**Answer to sub-question 4 (negative result).** Not with these public inputs. The best "
            f"price-blind learned model's error on negative-price look-alike quarter-hours (σ {got:.3f}) is "
            f"far above the roughly {need:.3f} needed to pin its own bias within ±{cfg.S2_HALF_WIDTH:g}, so "
            "the projection's bias at negative prices could not be bounded (S2 failed, "
            "`docs/12b_learned_potential_results.md`). In 50Hertz "
            f"{o['50Hertz']['share_no_overlap']:.1%} of the negative-price quarter-hours have no clean "
            "look-alike at all.")


def limitations_text() -> str:
    d = {r["area"]: r for r in pl.read_csv(ART / "overlap_diagnosis.csv").iter_rows(named=True)}
    s = _scores().filter((pl.col("subset") == "sunny look-alike days") & (pl.col("unit") == "three-area aggregate"))
    sunny_days = int(s["n_days"].max())
    t = pl.read_csv(TRACE_SUMMARY)
    n_unst = int((t["pattern"] == "unstable").sum())
    return "\n".join([
        "- **Experiment 4 rests on assumption A1:** conditional on the price-free inputs, available power "
        "does not depend on the price. It cannot be proven from data; the look-alike check and the overlap "
        "report are the only evidence offered.",
        f"- **Overlap is incomplete in 50Hertz:** only {d['50Hertz']['share_target_with_overlap']:.1%} of its "
        "negative-price quarter-hours have a clean look-alike, because the clean-set rule (no renewable "
        "redispatch) removes sunny middays there.",
        f"- **The sunny-day look-alike set is thin:** {sunny_days} days at the three-area aggregate, so the "
        "learned potential is barely checked under the conditions where negative prices occur.",
        f"- **N1's validation curves are unstable** in all {n_unst} fits, so its early-stopping epoch is "
        "driven largely by noise in the validation loss.",
    ])


def future_work_text() -> str:
    need, got, _ = _gap()
    return (f"- Finer price-free weather inputs (for example station wind or numerical weather fields) for "
            f"the learned potential, judged against the σ target: its aggregate look-alike σ would need to "
            f"fall from about {got:.3f} to about {need:.3f} before H's bias at negative prices can be bounded.")
