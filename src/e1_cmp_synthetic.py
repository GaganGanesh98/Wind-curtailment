"""Does src/censoring/synthetic.py have the same thin-direction problem?"""
import sys
sys.path.insert(0, ".")
import numpy as np
from src.censoring.synthetic import SyntheticConfig, generate
from src.censoring.cohorts import (build_clock_features, exposure_differs_by_day,
                                   placeholder_cohort_set, QH_CLOCK, HOUR_CLOCK)

cfg = SyntheticConfig(area="DE", censoring_rate=0.20, gamma=0.5,
                      r_shape="logistic", seed=42)
d = generate(cfg)
s, price, theta = d.s, d.price_eur_mwh, d.theta
cohorts = list(d.cohorts)
T = price.size
print(f"rows = {T:,}   cohorts = {len(cohorts)}")
print(f"{'cohort':<30} {'clock':>6} {'run_h':>6} {'s51':>5} {'supp':>5} "
      f"{'share':>6} {'theta_min':>10} {'exposed':>9}")
for i, c in enumerate(cohorts):
    print(f"{c.cohort_id:<30} {c.clock:>6} {str(c.run_length_h):>6} "
          f"{str(c.subject_to_s51):>5} {str(c.in_support):>5} "
          f"{c.capacity_share:>6.2f} {theta[i].min():>10.1f} {int(s[i].sum()):>9,}")

clock = build_clock_features(d.ts_utc_ns, price)
hour_neg = clock.hour_mean_price < 0.0
qh_neg = price < 0.0

print("\n" + "=" * 78)
print("1. THE STRICT THIN DIRECTION (the e1_generator failure mode)")
print("   QH price >= 0  AND  hourly mean < 0  AND  an hour-clock cohort exposed")
print("=" * 78)
hour_idx = [i for i, c in enumerate(cohorts) if c.clock == HOUR_CLOCK]
qh_idx = [i for i, c in enumerate(cohorts) if c.clock == QH_CLOCK]
thin = (price >= 0) & hour_neg & (s[hour_idx].max(axis=0) > 0)
print(f"   thin rows = {int(thin.sum())}")
print(f"   QH with price >= 0 inside a negative hour = {int(((price>=0)&hour_neg).sum()):,}"
      "   <- the raw opportunity")
print(f"   any cohort exposed at a QH with price >= 0 = {int(((price>=0)&(s.max(axis=0)>0)).sum())}")
print(f"   max theta over all cohorts/QH = {theta.max():.3f}  "
      f"(exposure needs price < theta, so theta <= 0 => price must be < 0)")

print("\n" + "=" * 78)
print("2. WHERE SYNTHETIC.PY'S IDENTIFICATION ACTUALLY COMES FROM")
print("=" * 78)
print("   'exposed alone' = this cohort exposed, every other cohort not:")
for i, c in enumerate(cohorts):
    alone = (s[i] > 0) & (s.sum(axis=0) == 1)
    print(f"     {c.cohort_id:<30} alone on {int(alone.sum()):>7,} QH "
          f"({100*alone.sum()/T:>6.3f}%)")
print("\n   distinct exposure patterns across cohorts (columns of s):")
pats, cnts = np.unique(s.T, axis=0, return_counts=True)
order = np.argsort(-cnts)
for j in order[:12]:
    print(f"     {pats[j].astype(int)}  x {cnts[j]:>7,}")
print(f"   total distinct patterns = {len(cnts)}  (2^{len(cohorts)} = {2**len(cohorts)} possible)")

print("\n   rank / conditioning of the exposure matrix s (K x T):")
sv = np.linalg.svd(s, compute_uv=False)
print(f"     singular values = {np.round(sv, 2)}")
print(f"     rank = {np.linalg.matrix_rank(s)} of {len(cohorts)}   "
      f"cond = {sv[0]/sv[-1]:.1f}")

print("\n   pairwise: QH where cohort i exposed and j not (row i, col j):")
hdr = "".join(f"{j:>9}" for j in range(len(cohorts)))
print(f"     {'':<4}{hdr}")
for i in range(len(cohorts)):
    row = "".join(f"{int(((s[i]>0)&(s[j]==0)).sum()):>9,}" for j in range(len(cohorts)))
    print(f"     {i:<4}{row}")

n_days, _ = exposure_differs_by_day(s, d.berlin_date)
print(f"\n   exposure_differs_by_day = {n_days} days (pre-registered threshold 10)")
print(f"   realised censoring rate = {d.diagnostics.get('realised_negative_rate', float('nan')):.4f}")
print(f"   censored QH = {int(d.censored.sum()):,}   exposed any = {int(d.exposed_any.sum()):,}")
print(f"   episodes: hourly={d.diagnostics.get('episodes_hourly')} "
      f"subhour={d.diagnostics.get('episodes_subhour')} "
      f"shoulder_qh={d.diagnostics.get('shoulder_qh_placed')}")
