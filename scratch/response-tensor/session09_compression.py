"""
SESSION 09 — pushing the compression further

Three experiments:

  A. COMPARE SIGNATURE TYPES (all ~10 dims)
     - weight_stat sig  : 10 hand-picked weight/Jacobian statistics (session 7/8)
     - probe sig        : concatenated outputs on 3 fixed probe inputs (3*4=12 dims)
     - hybrid sig       : both concatenated (~22 dims, slightly larger but compare)
     Which encoding makes matching-B functionally closest to A?

  B. COMPRESSION CURVE (for best signature type)
     Train B with K = 4, 8, 16, 32, 64 signature dims. Plot ||f_B - f_A|| vs K.
     Find where the curve elbows / saturates.

  C. TEACHER-FREE DISTILLATION
     Can B be trained with ONLY sig(A) as target, NO task data?
     Radical test of signature sufficiency as a functional description.
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
    def set_params(self, ps):
        self.W1, self.b1, self.Wo, self.bo = ps[0], ps[1], ps[2], ps[3]
    def snapshot(self): return [p.copy() for p in self.params()]

def task_teacher(seed=0, N=600):
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(10), (16, 10)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16), (4, 16)); bt2 = np.zeros(4)
    B = r.normal(0, 1, (3, 10))
    X = r.normal(0, 1, (N, 3)) @ B
    Y = np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2 + 0.02*r.normal(0, 1, (N, 4))
    return X, Y

# ------------------------------------------------------------------
# Signature types
# ------------------------------------------------------------------
def sig_weight_stat(net, X):
    """10-dim weight/Jacobian statistics signature."""
    Yp, H = net.forward(X)
    sech2 = 1.0 - H**2
    J = np.einsum('oh,nh,hi->noi', net.Wo, sech2, net.W1)
    s_W1 = svd(net.W1, compute_uv=False); s_Wo = svd(net.Wo, compute_uv=False)
    p1 = s_W1/s_W1.sum(); p1 = p1[p1>1e-10]
    pO = s_Wo/s_Wo.sum(); pO = pO[pO>1e-10]
    j_frob = np.mean([norm(J[i]) for i in range(J.shape[0])])
    return np.array([
        float(Yp.var(axis=0).mean()), float(H.var(axis=0).mean()),
        float((np.abs(H) < 0.1).mean()), float(norm(net.W1)), float(norm(net.Wo)),
        float(s_W1[0]), float(s_Wo[0]),
        float(np.exp(-(p1*np.log(p1)).sum())), float(np.exp(-(pO*np.log(pO)).sum())),
        float(j_frob)])

# fixed probe inputs for probe_sig (used by ALL networks for comparability)
_PROBE_RNG = np.random.default_rng(42)
PROBE_VECS = _PROBE_RNG.normal(0, 1, (3, 10))     # 3 probe inputs

def sig_probe(net, X=None, K=3):
    """K-probe behavioral signature: output on K fixed probe inputs.
    K * d_out numbers. Default K=3 gives 12 dims."""
    probes = PROBE_VECS[:K]
    Yp, _ = net.forward(probes)
    return Yp.ravel()

def sig_probe_variable(net, K):
    """For compression curves: use first K probe rows, extend if needed."""
    if K <= PROBE_VECS.shape[0]:
        probes = PROBE_VECS[:K]
    else:
        # generate additional probes deterministically
        extra = np.random.default_rng(99).normal(0, 1, (K - PROBE_VECS.shape[0], 10))
        probes = np.vstack([PROBE_VECS, extra])
    Yp, _ = net.forward(probes)
    return Yp.ravel()                             # K * d_out numbers

def sig_hybrid(net, X):
    return np.concatenate([sig_weight_stat(net, X), sig_probe(net, X)])

SIG_FNS = {
    'weight_stat': sig_weight_stat,
    'probe':       sig_probe,
    'hybrid':      sig_hybrid,
}

# ------------------------------------------------------------------
# Training machinery (ES sig grad as session 8)
# ------------------------------------------------------------------
def task_grad(net, X, Y):
    Yp, H = net.forward(X); err = Yp - Y; N = X.shape[0]
    gWo = err.T @ H / N; gbo = err.mean(0)
    dH = err @ net.Wo; dZ1 = dH * (1 - H**2)
    gW1 = dZ1.T @ X / N; gb1 = dZ1.mean(0)
    return [gW1, gb1, gWo, gbo]

def apply(net, grads, lr):
    ps = net.params()
    for p, g in zip(ps, grads): p -= lr * g

def sig_grad_es(net, X, target, sig_fn, rng, eps=1e-3, n_dirs=2):
    base = net.snapshot()
    shapes = [p.shape for p in base]; sizes = [p.size for p in base]
    total = sum(sizes)
    accum = [np.zeros_like(p) for p in base]
    for _ in range(n_dirs):
        dflat = rng.normal(0, 1, total); dflat /= (np.linalg.norm(dflat) + 1e-12)
        deltas = []; i = 0
        for sh, sz in zip(shapes, sizes):
            deltas.append(dflat[i:i+sz].reshape(sh)); i += sz
        net.set_params([b + eps*d for b, d in zip(base, deltas)])
        s_plus = sig_fn(net, X); l_plus = float(np.sum((s_plus - target)**2))
        net.set_params([b - eps*d for b, d in zip(base, deltas)])
        s_minus = sig_fn(net, X); l_minus = float(np.sum((s_minus - target)**2))
        net.set_params(base)
        coef = (l_plus - l_minus) / (2*eps)
        for k in range(len(accum)): accum[k] += coef * deltas[k]
    return [a/n_dirs for a in accum]

def train(net, X, Y, sig_target=None, sig_fn=None, lam=0.0, steps=2000,
          lr=0.05, sig_lr=0.05, sig_every=3, task_weight=1.0):
    rng = np.random.default_rng(123)
    for t in range(steps):
        if task_weight > 0:
            g = task_grad(net, X, Y)
            apply(net, [gi * task_weight for gi in g], lr)
        if sig_target is not None and t % sig_every == 0 and lam > 0:
            sg = sig_grad_es(net, X[:100], sig_target, sig_fn, rng, n_dirs=2)
            apply(net, sg, sig_lr * lam)
    return net

def mse(Yp, Y): return float(((Yp - Y)**2).mean())
def func_rms(a, b, X): return float(np.sqrt(((a.forward(X)[0] - b.forward(X)[0])**2).mean()))

# ------------------------------------------------------------------
# Reference anchor network
# ------------------------------------------------------------------
X, Y = task_teacher()
probe_X = X[:100]
A = train(MLP(10, 20, 4, seed=1), X, Y)
print(f"Anchor A trained. Task loss: {mse(A.forward(X)[0], Y):.5f}")

# ==================================================================
# EXPERIMENT A — compare signature types
# ==================================================================
print("\n" + "="*74)
print("EXPERIMENT A: Compare signature types")
print("  For each type: train B with sig target = sig(A), measure ||f_A - f_B||")
print("  Also compare to C (independent baseline, no sig target)")
print("="*74)

C = train(MLP(10, 20, 4, seed=77), X, Y)
baseline_dist = func_rms(A, C, X)
print(f"  Baseline C (independent): ||f_A - f_C|| = {baseline_dist:.4f}")

results = {}
for name, sig_fn in SIG_FNS.items():
    sig_A = sig_fn(A, probe_X)
    dim = len(sig_A)
    # Train B with sig target
    B = train(MLP(10, 20, 4, seed=55), X, Y,
              sig_target=sig_A, sig_fn=sig_fn, lam=5.0, steps=2000)
    sig_B = sig_fn(B, probe_X)
    d_AB = func_rms(A, B, X)
    task_B = mse(B.forward(X)[0], Y)
    sig_err = norm(sig_B - sig_A)
    improvement = 100 * (1 - d_AB / baseline_dist)
    results[name] = {
        'dim': dim, 'sig_err': sig_err, 'd_AB': d_AB,
        'task_B': task_B, 'improvement_pct': improvement
    }
    print(f"  {name:12s} (dim={dim:2d}): |sig_B - sig_A|={sig_err:.4f}  "
          f"||f_A - f_B||={d_AB:.4f}  task_loss={task_B:.5f}  "
          f"→ {improvement:+.1f}% closer to A than C")

# ==================================================================
# EXPERIMENT B — compression curve
# Use probe signature (most easily scalable).
# ==================================================================
print("\n" + "="*74)
print("EXPERIMENT B: Compression curve — f_B → f_A recovery vs signature dim")
print("  Using probe-signature (K probes × 4 outputs)")
print("="*74)
print(f"  Baseline ||f_A - f_C||: {baseline_dist:.4f}")

compression_curve = []
for K in [1, 2, 4, 8, 16, 32]:
    sig_fn = lambda net, X, K=K: sig_probe_variable(net, K)
    sig_A_K = sig_fn(A, probe_X)
    dim = len(sig_A_K)
    B = train(MLP(10, 20, 4, seed=55), X, Y,
              sig_target=sig_A_K, sig_fn=sig_fn, lam=5.0, steps=2000)
    d_AB = func_rms(A, B, X)
    compression_curve.append((K, dim, d_AB))
    improvement = 100 * (1 - d_AB / baseline_dist)
    print(f"  K={K:3d} probes (dim={dim:3d}): ||f_A - f_B||={d_AB:.4f}  "
          f"→ {improvement:+.1f}% closer")

# ==================================================================
# EXPERIMENT C — teacher-free distillation
# Train B using ONLY sig(A) as target, NO raw (X, Y) data.
# Signatures so far: weight_stat (doesn't use data), probe (uses PROBE_VECS — data
# in the sense that it has some inputs, but not the task data).
# Using probe sig: B learns from A's outputs on PROBE_VECS only.
# Plus: use weight_stat sig (no data at all - purely weight statistics).
# ==================================================================
print("\n" + "="*74)
print("EXPERIMENT C: Teacher-free distillation")
print("  Train B using ONLY signature of A as target. No task data.")
print("  Measure: does B function anywhere like A? Or useless noise?")
print("="*74)

# Version 1: only weight_stat signature (no data at all)
sig_A_ws = sig_weight_stat(A, probe_X)
B_only_sig_ws = train(MLP(10, 20, 4, seed=555),
                      X, Y,                         # X passed but task_weight=0
                      sig_target=sig_A_ws, sig_fn=sig_weight_stat,
                      lam=10.0, steps=2500, task_weight=0.0)
d_only_sig_ws = func_rms(A, B_only_sig_ws, X)
task_only_sig_ws = mse(B_only_sig_ws.forward(X)[0], Y)

# Version 2: only probe signature (sees A's outputs on 3 specific points, no task)
sig_A_p = sig_probe(A, probe_X)
B_only_sig_p = train(MLP(10, 20, 4, seed=555),
                     X, Y, sig_target=sig_A_p, sig_fn=sig_probe,
                     lam=10.0, steps=2500, task_weight=0.0)
d_only_sig_p = func_rms(A, B_only_sig_p, X)
task_only_sig_p = mse(B_only_sig_p.forward(X)[0], Y)

# Version 3: large probe signature (K=16) - 64 numbers
sig_fn_k16 = lambda net, X: sig_probe_variable(net, 16)
sig_A_k16 = sig_fn_k16(A, probe_X)
B_only_sig_k16 = train(MLP(10, 20, 4, seed=555),
                       X, Y, sig_target=sig_A_k16, sig_fn=sig_fn_k16,
                       lam=10.0, steps=2500, task_weight=0.0)
d_only_sig_k16 = func_rms(A, B_only_sig_k16, X)
task_only_sig_k16 = mse(B_only_sig_k16.forward(X)[0], Y)

# Baselines for context
random_net = MLP(10, 20, 4, seed=555)
d_random = func_rms(A, random_net, X)
task_random = mse(random_net.forward(X)[0], Y)

print(f"  Context — distances/task loss vs A:")
print(f"    random untrained           : ||f_A - f_B||={d_random:.4f}  task={task_random:.3f}")
print(f"    C (indep full training)    : ||f_A - f_C||={baseline_dist:.4f}  task={mse(C.forward(X)[0],Y):.5f}")
print(f"  With task data + weight-stat sig (Exp A result):")
print(f"    ||f_A - f_B||={results['weight_stat']['d_AB']:.4f}  task={results['weight_stat']['task_B']:.5f}")
print()
print(f"  TEACHER-FREE (no task data):")
print(f"    sig only (weight_stat, 10d): ||f_A - f_B||={d_only_sig_ws:.4f}  task={task_only_sig_ws:.3f}")
print(f"    sig only (probe, 12d)      : ||f_A - f_B||={d_only_sig_p:.4f}  task={task_only_sig_p:.3f}")
print(f"    sig only (probe K=16, 64d) : ||f_A - f_B||={d_only_sig_k16:.4f}  task={task_only_sig_k16:.3f}")

# How much of A's function is recoverable from signature alone?
for name, d in [('weight_stat', d_only_sig_ws), ('probe', d_only_sig_p),
                ('probe K=16', d_only_sig_k16)]:
    # 0% = random; 100% = as good as independent full training
    recovery = 100 * (d_random - d) / (d_random - baseline_dist)
    print(f"    → {name:12s}: {recovery:.1f}% of (random→indep) functional gap closed")
