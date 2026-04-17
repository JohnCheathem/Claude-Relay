"""
SESSION 08 — inverse training (v2, efficient)

Same idea as v1 but uses evolution-strategy gradient estimation:
  draw random direction δ, evaluate sig loss at θ±ε·δ, estimate gradient.

This costs 2 forward passes per sig update, vs 2*n_params for full FD.
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
    def params(self):
        return [self.W1, self.b1, self.Wo, self.bo]
    def set_params(self, ps):
        self.W1, self.b1, self.Wo, self.bo = ps[0], ps[1], ps[2], ps[3]
    def snapshot(self):
        return [p.copy() for p in self.params()]

# ------------------------------------------------------------------
# Tasks
# ------------------------------------------------------------------
def task_teacher(seed=0, N=600):
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(10), (16, 10)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16), (4, 16)); bt2 = np.zeros(4)
    B = r.normal(0, 1, (3, 10))
    X = r.normal(0, 1, (N, 3)) @ B
    Y = np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2 + 0.02*r.normal(0, 1, (N, 4))
    return X, Y

def task_linear(seed=0, N=600):
    r = np.random.default_rng(seed)
    W = r.normal(0, 0.3, (4, 10))
    X = r.normal(0, 1, (N, 10))
    Y = X @ W.T + 0.05*r.normal(0, 1, (N, 4))
    return X, Y

def task_sparse(seed=0, N=600):
    r = np.random.default_rng(seed)
    W = r.normal(0, 1, (4, 2))
    X = r.normal(0, 1, (N, 10))
    Y = np.tanh(X[:, :2] @ W.T) + 0.02*r.normal(0, 1, (N, 4))
    return X, Y

# ------------------------------------------------------------------
# Signature — 10-dim
# ------------------------------------------------------------------
def signature(net, X):
    Yp, H = net.forward(X)
    sech2 = 1.0 - H**2
    J = np.einsum('oh,nh,hi->noi', net.Wo, sech2, net.W1)
    s_W1 = svd(net.W1, compute_uv=False)
    s_Wo = svd(net.Wo, compute_uv=False)
    p1 = s_W1/s_W1.sum(); p1 = p1[p1>1e-10]
    pO = s_Wo/s_Wo.sum(); pO = pO[pO>1e-10]
    j_frob = np.mean([norm(J[i]) for i in range(J.shape[0])])
    return np.array([
        float(Yp.var(axis=0).mean()),
        float(H.var(axis=0).mean()),
        float((np.abs(H) < 0.1).mean()),
        float(norm(net.W1)),
        float(norm(net.Wo)),
        float(s_W1[0]),
        float(s_Wo[0]),
        float(np.exp(-(p1*np.log(p1)).sum())),
        float(np.exp(-(pO*np.log(pO)).sum())),
        float(j_frob),
    ])

# ------------------------------------------------------------------
# ES-style signature gradient (random directional FD)
# ------------------------------------------------------------------
def sig_grad_es(net, X, target, rng, eps=1e-3, n_dirs=3):
    """Estimate gradient of ||sig(net)-target||^2 using n_dirs random directions.
    Returns list of gradient arrays in same shape as params."""
    base_params = net.snapshot()
    shapes = [p.shape for p in base_params]
    sizes = [p.size for p in base_params]
    total = sum(sizes)
    accum = [np.zeros_like(p) for p in base_params]

    for _ in range(n_dirs):
        # draw random direction (unit norm per param)
        delta_flat = rng.normal(0, 1, total)
        delta_flat /= (np.linalg.norm(delta_flat) + 1e-12)
        # reshape
        deltas = []
        i = 0
        for sh, sz in zip(shapes, sizes):
            deltas.append(delta_flat[i:i+sz].reshape(sh))
            i += sz
        # + direction
        net.set_params([b + eps*d for b, d in zip(base_params, deltas)])
        sig_plus = signature(net, X)
        loss_plus = float(np.sum((sig_plus - target)**2))
        # - direction
        net.set_params([b - eps*d for b, d in zip(base_params, deltas)])
        sig_minus = signature(net, X)
        loss_minus = float(np.sum((sig_minus - target)**2))
        # restore
        net.set_params(base_params)
        # directional grad estimate
        coef = (loss_plus - loss_minus) / (2*eps)
        for k in range(len(accum)):
            accum[k] += coef * deltas[k]
    return [a / n_dirs for a in accum]

def task_grad(net, X, Y):
    Yp, H = net.forward(X); err = Yp - Y; N = X.shape[0]
    gWo = err.T @ H / N; gbo = err.mean(0)
    dH = err @ net.Wo; dZ1 = dH * (1 - H**2)
    gW1 = dZ1.T @ X / N; gb1 = dZ1.mean(0)
    return [gW1, gb1, gWo, gbo]

def apply(net, grads, lr):
    ps = net.params()
    for p, g in zip(ps, grads):
        p -= lr * g

def train_standard(net, X, Y, steps=2000, lr=0.05):
    for _ in range(steps):
        apply(net, task_grad(net, X, Y), lr)
    return net

def train_sig(net, X, Y, target, lam, steps=2000, lr=0.05, sig_lr=0.05, sig_every=3):
    rng = np.random.default_rng(123)
    for t in range(steps):
        apply(net, task_grad(net, X, Y), lr)
        if t % sig_every == 0 and lam > 0:
            sg = sig_grad_es(net, X[:100], target, rng, n_dirs=2)
            apply(net, sg, sig_lr * lam)
    return net

def mse(Yp, Y): return float(((Yp - Y)**2).mean())

# ==================================================================
# Setup: reference networks and reference signatures
# ==================================================================
print("="*72)
print("Setup: train reference networks on three tasks")
print("="*72)
X_T, Y_T = task_teacher()
X_L, Y_L = task_linear()
X_S, Y_S = task_sparse()

A_teacher = train_standard(MLP(10, 20, 4, seed=1), X_T, Y_T)
A_linear  = train_standard(MLP(10, 20, 4, seed=1), X_L, Y_L)
A_sparse  = train_standard(MLP(10, 20, 4, seed=1), X_S, Y_S)

probe_T = X_T[:100]; probe_L = X_L[:100]; probe_S = X_S[:100]
sig_teacher = signature(A_teacher, probe_T)
sig_linear  = signature(A_linear,  probe_L)
sig_sparse  = signature(A_sparse,  probe_S)

print(f"  A_teacher task loss: {mse(A_teacher.forward(X_T)[0], Y_T):.4f}")
print(f"  A_linear  task loss: {mse(A_linear.forward(X_L)[0], Y_L):.4f}")
print(f"  A_sparse  task loss: {mse(A_sparse.forward(X_S)[0], Y_S):.4f}")
print(f"\n  sig(teacher) : {np.round(sig_teacher, 3)}")
print(f"  sig(linear)  : {np.round(sig_linear, 3)}")
print(f"  sig(sparse)  : {np.round(sig_sparse, 3)}")

# ==================================================================
# EXPERIMENT 1: Targeted matching
# Train B on teacher task to match A_teacher's signature.
# Does B functionally resemble A_teacher MORE than independent C does?
# ==================================================================
print("\n" + "="*72)
print("EXPERIMENT 1: Signature-targeted B — functionally closer to A than indep C?")
print("="*72)
C = train_standard(MLP(10, 20, 4, seed=77), X_T, Y_T)
sig_C = signature(C, probe_T)
B = train_sig(MLP(10, 20, 4, seed=55), X_T, Y_T, target=sig_teacher,
              lam=5.0, sig_every=3)
sig_B = signature(B, probe_T)

print(f"  |sig(C) - sig(A)|: {norm(sig_C - sig_teacher):.4f}  (independent baseline)")
print(f"  |sig(B) - sig(A)|: {norm(sig_B - sig_teacher):.4f}  (sig-targeted)")
print(f"  task loss: A={mse(A_teacher.forward(X_T)[0], Y_T):.4f}, "
      f"B={mse(B.forward(X_T)[0], Y_T):.4f}, "
      f"C={mse(C.forward(X_T)[0], Y_T):.4f}")

def func_rms(a, b, X):
    return float(np.sqrt(((a.forward(X)[0] - b.forward(X)[0])**2).mean()))

d_AB = func_rms(A_teacher, B, X_T)
d_AC = func_rms(A_teacher, C, X_T)
d_BC = func_rms(B, C, X_T)
print(f"\n  Function-space distance on teacher task:")
print(f"    ||f_A - f_B|| (sig-matched):  {d_AB:.4f}")
print(f"    ||f_A - f_C|| (independent):  {d_AC:.4f}")
print(f"    ||f_B - f_C||              :  {d_BC:.4f}")
if d_AB < d_AC * 0.95:
    print(f"  → sig-matching brings B functionally CLOSER to A ({100*(1-d_AB/d_AC):.1f}% closer)")
elif d_AB > d_AC * 1.05:
    print(f"  → sig-matching did NOT help; B is further from A")
else:
    print(f"  → sig-matching produces no clear difference from independent training")

# ==================================================================
# EXPERIMENT 2: Signature spoofing
# ==================================================================
print("\n" + "="*72)
print("EXPERIMENT 2: Signature spoofing")
print("  Target: solve teacher task, but have linear-signature")
print("="*72)
spoof = train_sig(MLP(10, 20, 4, seed=33), X_T, Y_T, target=sig_linear,
                  lam=5.0, sig_every=3)
sig_spoof = signature(spoof, probe_T)

print(f"  Spoof net task loss (teacher): {mse(spoof.forward(X_T)[0], Y_T):.4f}  "
      f"(native A_teacher: {mse(A_teacher.forward(X_T)[0], Y_T):.4f})")
print(f"  |sig(spoof) - sig(teacher)|: {norm(sig_spoof - sig_teacher):.4f}")
print(f"  |sig(spoof) - sig(linear)|:  {norm(sig_spoof - sig_linear):.4f}")

# Nearest-class identification
refs = {'teacher': sig_teacher, 'linear': sig_linear, 'sparse': sig_sparse}
def classify(sig):
    return min(refs.keys(), key=lambda k: norm(sig - refs[k]))
print(f"  Fingerprint classification of spoof: {classify(sig_spoof)}")
print(f"    (actual task: teacher)  "
      f"→ fingerprinting {'FOOLED' if classify(sig_spoof) != 'teacher' else 'RESISTS SPOOFING'}")

# ==================================================================
# EXPERIMENT 3: Signature arithmetic
# ==================================================================
print("\n" + "="*72)
print("EXPERIMENT 3: Signature arithmetic — mix two signatures, train net to match")
print("="*72)
sig_mix = 0.5 * sig_teacher + 0.5 * sig_linear
print(f"  sig_mix = 0.5 sig(teacher) + 0.5 sig(linear)")

# Train on MIXED data with target = sig_mix
X_mix = np.vstack([X_T, X_L]); Y_mix = np.vstack([Y_T, Y_L])
perm = np.random.default_rng(0).permutation(X_mix.shape[0])
X_mix, Y_mix = X_mix[perm], Y_mix[perm]

mix_net = train_sig(MLP(10, 20, 4, seed=22), X_mix, Y_mix, target=sig_mix,
                    lam=3.0, sig_every=3)
sig_mix_actual = signature(mix_net, X_mix[:100])
print(f"  Achieved sig: {np.round(sig_mix_actual, 3)}")
print(f"  Target sig:   {np.round(sig_mix, 3)}")
print(f"  Distance to target: {norm(sig_mix_actual - sig_mix):.4f}")

# Also train on mixed data WITHOUT signature constraint (control)
ctrl_mix = train_standard(MLP(10, 20, 4, seed=22), X_mix, Y_mix)
sig_ctrl_mix = signature(ctrl_mix, X_mix[:100])
print(f"  Control (mixed data, no sig): {np.round(sig_ctrl_mix, 3)}")
print(f"  Control |sig - sig_mix|: {norm(sig_ctrl_mix - sig_mix):.4f}")

print(f"\n  Test on individual tasks:")
print(f"  Mix-targeted net loss: teacher={mse(mix_net.forward(X_T)[0], Y_T):.4f}  "
      f"linear={mse(mix_net.forward(X_L)[0], Y_L):.4f}")
print(f"  Control net loss     : teacher={mse(ctrl_mix.forward(X_T)[0], Y_T):.4f}  "
      f"linear={mse(ctrl_mix.forward(X_L)[0], Y_L):.4f}")
