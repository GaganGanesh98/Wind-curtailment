"""Is the rank deficiency universal, and does it survive r_cohort_offsets?"""
import sys
sys.path.insert(0, ".")
import numpy as np
from src.censoring.synthetic import SyntheticConfig, generate
from src.censoring.cohorts import placeholder_cohort_set, mastr_cohort_set

print("placeholder_cohort_set, DE, logistic -- rank of s across the grid")
print(f"{'rate':>5} {'gamma':>6} {'seed':>5} {'rank':>5} {'s0==s4':>7} "
      f"{'alone_any':>10} {'patterns':>9} {'cond':>10}")
bad = 0
for rate in (0.05, 0.20, 0.40):
    for gam in (0.0, 1.0):
        for seed in (42, 43):
            d = generate(SyntheticConfig(area="DE", censoring_rate=rate, gamma=gam,
                                         r_shape="logistic", seed=seed))
            s = d.s
            sv = np.linalg.svd(s, compute_uv=False)
            rank = int(np.linalg.matrix_rank(s))
            same = bool(np.array_equal(s[0], s[4]))
            alone = int(((s.sum(axis=0) == 1)).sum())
            npat = len(np.unique(s.T, axis=0))
            bad += rank < len(d.cohorts)
            print(f"{rate:>5.2f} {gam:>6.1f} {seed:>5} {rank:>5} {str(same):>7} "
                  f"{alone:>10,} {npat:>9} {sv[0]/max(sv[-1],1e-12):>10.1e}")
print(f"\nrank-deficient cells: {bad}/12")

print("\n-- is it the cohort definitions, independent of the data? --")
cs = placeholder_cohort_set()
for c in cs:
    print(f"  {c.cohort_id:<30} clock={c.clock:<12} s51={c.subject_to_s51!s:<5} "
          f"in_support={c.in_support!s:<5} aw={c.aw_eur_mwh}")
print("\n  cohort 0 (out of support): theta = 0 always -> exposed iff price_qh < 0")
print("  cohort 4 (qh clock, s51):  trigger = price_qh < 0 -> theta = 0 there,")
print("                             -29 elsewhere -> exposed iff price_qh < 0")
print("  => identical exposure for ANY price series. Structural, not sampling.")

print("\n-- does it persist with per-cohort offsets (the arm that needs rank 5)? --")
d2 = generate(SyntheticConfig(area="DE", censoring_rate=0.20, gamma=0.5,
                              r_shape="logistic", seed=42,
                              r_cohort_offsets=(0.0, -0.1, 0.05, 0.1, -0.05)))
s2, r2 = d2.s, d2.r_true
print(f"  rank(s) = {np.linalg.matrix_rank(s2)} of {len(d2.cohorts)}  "
      f"s0==s4: {np.array_equal(s2[0], s2[4])}")
w = np.array([c.capacity_share for c in d2.cohorts])
on = s2[0] > 0
print(f"  r*_0 and r*_4 differ on exposed QH: "
      f"{float(np.abs(r2[0][on]-r2[4][on]).mean()):.4f} mean abs")
print(f"  but only w0*r0 + w4*r4 enters c, and s0==s4, so the split is unidentified.")
print(f"  w0={w[0]:.2f} w4={w[4]:.2f} -> {100*(w[0]+w[4]):.0f}% of fleet capacity "
      f"with no separable response.")

print("\n-- the MaStR cohort set (Phase 3), if available --")
try:
    ms = mastr_cohort_set("DE")
    print(f"  {len(ms)} cohorts")
    for c in ms:
        print(f"    {c.cohort_id:<30} clock={c.clock:<12} s51={c.subject_to_s51!s:<5} "
              f"in_support={c.in_support!s:<5} share={c.capacity_share:.3f}")
except Exception as e:
    print(f"  unavailable: {type(e).__name__}: {e}")
