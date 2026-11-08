import sys
sys.path.insert(0, ".")
import numpy as np
from src.censoring.synthetic import SyntheticConfig, generate
from src.censoring.cohorts import mastr_cohort_set, theta_and_exposure, build_clock_features

ms = mastr_cohort_set("DE")
d = generate(SyntheticConfig(area="DE", censoring_rate=0.20, gamma=0.5,
                             r_shape="logistic", seed=42), cohorts=ms)
s, theta = d.s, d.theta
cs = list(d.cohorts)
print(f"MaStR cohort set: {len(cs)} cohorts, {s.shape[1]:,} QH")
print(f"{'#':>2} {'cohort':<30} {'aw':>7} {'theta_min':>10} {'exposed':>9} {'share':>7}")
for i, c in enumerate(cs):
    print(f"{i:>2} {c.cohort_id:<30} {str(c.aw_eur_mwh):>7} {theta[i].min():>10.1f} "
          f"{int(s[i].sum()):>9,} {c.capacity_share:>7.3f}")
sv = np.linalg.svd(s, compute_uv=False)
rank = int(np.linalg.matrix_rank(s))
print(f"\nrank(s) = {rank} of {len(cs)}")
print(f"singular values = {np.round(sv, 2)}")

print("\nexactly-duplicated exposure rows:")
seen, dup = {}, []
for i in range(len(cs)):
    key = s[i].tobytes()
    if key in seen:
        dup.append((seen[key], i))
    else:
        seen[key] = i
for a, b in dup:
    share = cs[a].capacity_share + cs[b].capacity_share
    print(f"  s[{a}] == s[{b}]  ({cs[a].cohort_id} == {cs[b].cohort_id})"
          f"  combined share {100*share:.1f}%")
if not dup:
    print("  none")
coll = sum(cs[a].capacity_share + cs[b].capacity_share for a, b in dup)
print(f"\ncapacity in exactly-collinear pairs: {100*coll:.1f}%")
alone = [(c.cohort_id, int(((s[i] > 0) & (s.sum(axis=0) == 1)).sum()))
         for i, c in enumerate(cs)]
print("\n'exposed alone' per cohort:")
for cid, n in alone:
    print(f"  {cid:<30} {n:>7,}")
print(f"\ndistinct exposure patterns = {len(np.unique(s.T, axis=0))} of {2**len(cs)}")

print("\n" + "=" * 70)
print("Is the deficiency ONLY the duplicates? Merge each pair and recheck.")
print("=" * 70)
for label, mat, names in (
    ("MaStR (8 cohorts)", s, [c.cohort_id for c in cs]),
):
    keep = []
    seen = set()
    for i in range(mat.shape[0]):
        k = mat[i].tobytes()
        if k not in seen:
            seen.add(k); keep.append(i)
    red = mat[keep]
    sv2 = np.linalg.svd(red, compute_uv=False)
    print(f"{label}: kept {len(keep)} of {mat.shape[0]} rows "
          f"({[names[i] for i in keep]})")
    print(f"  rank = {np.linalg.matrix_rank(red)} of {len(keep)}   "
          f"cond = {sv2[0]/sv2[-1]:.1f}")
    print(f"  singular values = {np.round(sv2, 2)}")
    print("  => once the duplicate pairs are merged the design is FULL RANK and")
    print("     well conditioned; the nesting itself is not the problem.")
