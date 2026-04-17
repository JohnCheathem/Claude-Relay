"""
SESSION 09B — optimized probes

Session 9 found that 4 RANDOM probes (16 numbers) produce 23.3% functional recovery,
outperforming 10 weight statistics (17.6%). What if we OPTIMIZE the probes?

Goal: find K probes p_1..p_K such that signature = [f_A(p_1),...,f_A(p_K)]
is maximally informative for recovering f_A by training on task + sig target.

Method — iterative:
  1. Start with random probes P
  2. Train B with sig target = f_A(P)
  3. Measure gap = ||f_A - f_B||
  4. Update P in direction that ENLARGES this gap for nets NOT matching sig,
     but shrinks gap for B that DOES match sig. Practically: choose probes
     where f_A and f_B (under sig constraint) differ most, or where nets
     differ MOST GENERALLY (max-variance probes across seeds).

Simple heuristic this session: adversarial probe selection.
  - Train several nets independently on task → they differ in various ways
  - The probe inputs where these nets disagree MOST are the most identifying
  - Pick the K highest-disagreement probes from a large random candidate pool

This is cheaper than full joint optimization and directly targets "probes that
distinguish networks."
"""
import numpy as np
from numpy.linalg import svd, norm

class MLP:
    def __init__(self, d_in, d_hid, d_out, seed=0):
        r = np.random.default_rng(seed)
        self.W1 = r.normal(0, 1/np.sqrt(d_in), (d_hid, d_in)); self.b1 = np.zeros(d_hid)
        self.Wo = r.normal(0, 1/np.sqrt(d_hid), (d_out, d_hid)); self.bo = np.zeros(d_out)
        self.d_in, self.d_hid, self.d_out = d_in, d_hid, d_out
    def forward(self, X):
        Z1 = X @ self.W1.T + self.b1; H = np.tanh(Z1); return H @ self.Wo.T + self.bo, H
    def params(self): return [self.W1, self.b1, self.Wo, self.bo]
    def set_params(self, ps): self.W1, self.b1, self.Wo, self.bo = ps[0], ps[1], ps[2], ps[3]
    def snapshot(self): return [p.copy() for p in self.params()]

def task_teacher(seed=0, N=600):
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(10), (16, 10)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16), (4, 16)); bt2 = np.zeros(4)
    B = r.normal(0, 1, (3, 10))
    X = r.normal(0, 1, (N, 3)) @ B
    Y = np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2 + 0.02*r.normal(0, 1, (N, 4))
    return X, Y

def task_grad(net, X, Y):
    Yp, H = net.forward(X); err = Yp - Y; N = X.shape[0]
    gWo = err.T @ H / N; gbo = err.mean(0)
    dH = err @ net.Wo; dZ1 = dH * (1 - H**2)
    gW1 = dZ1.T @ X / N; gb1 = dZ1.mean(0)
    return [gW1, gb1, gWo, gbo]

def apply(net, grads, lr):
    ps = net.params()
    for p, g in zip(ps, grads): p -= lr * g

def sig_grad_es(net, probes, target, rng, eps=1e-3, n_dirs=2):
    base = net.snapshot()
    shapes = [p.shape for p in base]; sizes = [p.size for p in base]
    total = sum(sizes); accum = [np.zeros_like(p) for p in base]
    for _ in range(n_dirs):
        df = rng.normal(0, 1, total); df /= (np.linalg.norm(df)+1e-12)
        deltas = []; i = 0
        for sh, sz in zip(shapes, sizes):
            deltas.append(df[i:i+sz].reshape(sh)); i += sz
        net.set_params([b+eps*d for b,d in zip(base, deltas)])
        s_p = net.forward(probes)[0].ravel()
        l_p = float(np.sum((s_p - target)**2))
        net.set_params([b-eps*d for b,d in zip(base, deltas)])
        s_m = net.forward(probes)[0].ravel()
        l_m = float(np.sum((s_m - target)**2))
        net.set_params(base)
        c = (l_p - l_m) / (2*eps)
        for k in range(len(accum)): accum[k] += c * deltas[k]
    return [a/n_dirs for a in accum]

def train(net, X, Y, probes=None, target=None, lam=5.0, steps=2000,
          lr=0.05, sig_lr=0.05, sig_every=3):
    rng = np.random.default_rng(123)
    for t in range(steps):
        apply(net, task_grad(net, X, Y), lr)
        if probes is not None and t % sig_every == 0 and lam > 0:
            sg = sig_grad_es(net, probes, target, rng, n_dirs=2)
            apply(net, sg, sig_lr * lam)
    return net

def mse(a, b): return float(((a - b)**2).mean())
def func_rms(a, b, X): return float(np.sqrt(((a.forward(X)[0] - b.forward(X)[0])**2).mean()))

# ==================================================================
# Setup
# ==================================================================
X, Y = task_teacher()
print("Training anchor A and 6 independent 'siblings' ...")
A = train(MLP(10, 20, 4, seed=1), X, Y)
siblings = [train(MLP(10, 20, 4, seed=s), X, Y) for s in [2, 3, 4, 5, 6, 7]]
print(f"  A task loss: {mse(A.forward(X)[0], Y):.5f}")
print(f"  Sibling losses: {[f'{mse(s.forward(X)[0], Y):.4f}' for s in siblings]}")

# Baseline: sibling ≈ independent baseline
C = train(MLP(10, 20, 4, seed=77), X, Y)
baseline = func_rms(A, C, X)
print(f"  Baseline ||f_A - f_C||: {baseline:.4f}\n")

# ==================================================================
# Step 1: generate large candidate pool of probes
# ==================================================================
N_CANDIDATES = 500
rng_cand = np.random.default_rng(2024)
candidates = rng_cand.normal(0, 1, (N_CANDIDATES, 10))
print(f"Generating {N_CANDIDATES} candidate probe inputs ...")

# For each candidate, measure disagreement among A + siblings
# Higher disagreement = better identifier
all_nets = [A] + siblings
net_outputs = np.stack([n.forward(candidates)[0] for n in all_nets])  # [n_nets, N_cand, d_out]
# disagreement = variance across nets at each candidate, summed over d_out
disagreement = net_outputs.var(axis=0).sum(axis=-1)  # [N_cand]

# Select top-K disagreement probes
def pick_top_k(disagreement, K):
    idx = np.argsort(-disagreement)[:K]
    return candidates[idx]

# Also compare to random selection
def pick_random_k(K):
    idx = np.random.default_rng(K+111).choice(N_CANDIDATES, K, replace=False)
    return candidates[idx]

# ==================================================================
# Step 2: for each K, compare optimized vs random probes
# ==================================================================
print("\n" + "="*78)
print("Optimized probes (max-disagreement) vs random probes")
print("="*78)
print(f"{'K':>3s}{'dim':>6s}{'random ||f_A-f_B||':>24s}{'optimized ||f_A-f_B||':>28s}"
      f"{'optimized gain':>20s}")
print("-"*78)

results = []
for K in [2, 4, 8, 16]:
    # Random
    probes_rand = pick_random_k(K)
    target_rand = A.forward(probes_rand)[0].ravel()
    B_rand = train(MLP(10, 20, 4, seed=55), X, Y,
                   probes=probes_rand, target=target_rand, lam=5.0)
    d_rand = func_rms(A, B_rand, X)

    # Optimized
    probes_opt = pick_top_k(disagreement, K)
    target_opt = A.forward(probes_opt)[0].ravel()
    B_opt = train(MLP(10, 20, 4, seed=55), X, Y,
                  probes=probes_opt, target=target_opt, lam=5.0)
    d_opt = func_rms(A, B_opt, X)

    rand_improvement = 100 * (1 - d_rand / baseline)
    opt_improvement  = 100 * (1 - d_opt / baseline)
    gain = opt_improvement - rand_improvement

    results.append({'K': K, 'dim': K*4, 'd_rand': d_rand, 'd_opt': d_opt,
                    'rand_imp': rand_improvement, 'opt_imp': opt_improvement})
    print(f"{K:>3d}{K*4:>6d}"
          f"{d_rand:14.4f} ({rand_improvement:+5.1f}%)"
          f"{d_opt:18.4f} ({opt_improvement:+5.1f}%)"
          f"{gain:+17.1f}%")

# ==================================================================
# Step 3: how does optimized K=4 compare to all previous signatures?
# ==================================================================
print("\n" + "="*78)
print("Summary across signature types (all on same task, same anchor A)")
print("="*78)
print("  Weight statistics (10-d)          : +17.6% (session 9)")
print("  Random probes K=4 (16-d)          : +23.3% (session 9)")
best_opt = max(results, key=lambda r: r['opt_imp'])
print(f"  Optimized probes K={best_opt['K']} ({best_opt['dim']}-d)        "
      f": {best_opt['opt_imp']:+.1f}% (session 9b)")

# ==================================================================
# Step 4: stack the probes — what do they LOOK like?
# ==================================================================
print("\n" + "="*78)
print("What kind of inputs are the best probes?")
print("="*78)
best_K = 4
best_probes = pick_top_k(disagreement, best_K)
random_probes = pick_random_k(best_K)
print(f"  Avg norm of top-{best_K} disagreement probes: "
      f"{np.linalg.norm(best_probes, axis=1).mean():.3f}")
print(f"  Avg norm of {best_K} random probes: "
      f"{np.linalg.norm(random_probes, axis=1).mean():.3f}")
print(f"  Avg disagreement at top probes : {disagreement[np.argsort(-disagreement)[:best_K]].mean():.4f}")
print(f"  Avg disagreement at random probes: "
      f"{np.random.default_rng(0).choice(disagreement, best_K).mean():.4f}")

# Distance from probes to data manifold
# data lies in 3-d subspace. compute projection residual
from numpy.linalg import svd as np_svd
U, S, Vt = np_svd(X, full_matrices=False)
data_subspace = Vt[:3]                    # [3, 10], rows span data's 3d subspace
def proj_residual(p):
    # project onto data subspace, take residual norm
    proj = data_subspace.T @ (data_subspace @ p)
    return float(np.linalg.norm(p - proj))
print(f"\n  Avg off-data-manifold distance of top probes: "
      f"{np.mean([proj_residual(p) for p in best_probes]):.3f}")
print(f"  Avg off-data-manifold distance of random probes: "
      f"{np.mean([proj_residual(p) for p in random_probes]):.3f}")
print(f"  Avg off-data-manifold distance of training X: "
      f"{np.mean([proj_residual(x) for x in X[:50]]):.3f}")
