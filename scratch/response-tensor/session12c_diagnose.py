"""
SESSION 12C — diagnose the task-complexity results

The 12B result has memorization at +95% and linear at +62%, backwards from the
hypothesis. Likely cause: "% recovery" is normalized by baseline ||f_A - f_C||,
which varies a lot across tasks.

For memorization, both A and C fail to learn (produce near-mean), so
||f_A - f_C|| is small → any matching looks like high % recovery.

For linear, both A and C learn well (produce near-identical functions),
so ||f_A - f_C|| is also small but the absolute distances are close to zero.

Show ABSOLUTE distances, not just %, and several normalizations to see what's
actually happening.
"""
import numpy as np
from numpy.linalg import svd, norm

# --- reuse everything from 12B
class MLP:
    def __init__(self, d_in, d_hid, d_out, seed=0):
        r = np.random.default_rng(seed)
        self.W1 = r.normal(0, 1/np.sqrt(d_in), (d_hid, d_in)); self.b1 = np.zeros(d_hid)
        self.Wo = r.normal(0, 1/np.sqrt(d_hid), (d_out, d_hid)); self.bo = np.zeros(d_out)
        self.d_in, self.d_hid, self.d_out = d_in, d_hid, d_out
    def forward(self, X):
        Z1 = X @ self.W1.T + self.b1; H = np.tanh(Z1); return H @ self.Wo.T + self.bo, H
    def jacobian(self, X):
        _, H = self.forward(X); S = 1.0 - H**2
        return np.einsum('oh,nh,hi->noi', self.Wo, S, self.W1)
    def params(self): return [self.W1, self.b1, self.Wo, self.bo]

def task_grad(net, X, Y):
    Yp, H = net.forward(X); err = Yp - Y; N = X.shape[0]
    gWo = err.T @ H / N; gbo = err.mean(0)
    dH = err @ net.Wo; dZ1 = dH * (1 - H**2)
    gW1 = dZ1.T @ X / N; gb1 = dZ1.mean(0)
    return [gW1, gb1, gWo, gbo]

def hidden_match_grad(net, P, T_H):
    _, H = net.forward(P); err = (H - T_H) / P.shape[0]
    sech2 = 1.0 - H**2; dZ1 = err * sech2
    gW1 = dZ1.T @ P; gb1 = dZ1.sum(0)
    return [gW1, gb1, np.zeros_like(net.Wo), np.zeros_like(net.bo)]

def apply(net, grads, lr):
    for p, g in zip(net.params(), grads): p -= lr * g

def train_standard(net, X, Y, steps=3000, lr=0.05):
    for _ in range(steps):
        apply(net, task_grad(net, X, Y), lr)
    return net

def train_with_sig(net, X, Y, P, T_out, T_H, lam=12.0, alpha_h=0.3,
                    steps=3000, lr=0.05, sig_every=3):
    for t in range(steps):
        apply(net, task_grad(net, X, Y), lr)
        if t % sig_every == 0 and lam > 0:
            apply(net, task_grad(net, P, T_out), lr * lam)
            if alpha_h > 0:
                apply(net, hidden_match_grad(net, P, T_H), lr * lam * alpha_h)
    return net

def func_rms(a, b, X): return float(np.sqrt(((a.forward(X)[0] - b.forward(X)[0])**2).mean()))
def mse(Yp, Y): return float(((Yp - Y)**2).mean())

# Task definitions
def make_linear(seed, N=600):
    r = np.random.default_rng(seed)
    W = r.normal(0, 0.3, (4, 10)); X = r.normal(0, 1, (N, 10))
    Y = X @ W.T + 0.02*r.normal(0, 1, (N, 4)); return X, Y

def make_teacher_smooth(seed, N=600):
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(10), (16, 10)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16), (4, 16)); bt2 = np.zeros(4)
    B = r.normal(0, 1, (3, 10))
    X = r.normal(0, 1, (N, 3)) @ B
    Y = np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2 + 0.02*r.normal(0, 1, (N, 4))
    return X, Y

def make_teacher_sharp(seed, N=600):
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 5/np.sqrt(10), (16, 10)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16), (4, 16)); bt2 = np.zeros(4)
    B = r.normal(0, 1, (3, 10))
    X = r.normal(0, 1, (N, 3)) @ B
    Y = np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2 + 0.02*r.normal(0, 1, (N, 4))
    return X, Y

def make_oscillatory(seed, N=600):
    r = np.random.default_rng(seed)
    W = r.normal(0, 1, (4, 10)); X = r.normal(0, 0.5, (N, 10))
    Y = np.sin(3.0 * X @ W.T) + 0.02*r.normal(0, 1, (N, 4)); return X, Y

def make_noisy_teacher(seed, N=600):
    X, Y = make_teacher_smooth(seed, N)
    r = np.random.default_rng(seed+999)
    return X, Y + 0.3 * r.normal(0, 1, Y.shape)

def make_memorization(seed, N=600):
    r = np.random.default_rng(seed)
    return r.normal(0, 1, (N, 10)), r.normal(0, 1, (N, 4))

TASKS = [
    ('linear', make_linear),
    ('teacher_smooth', make_teacher_smooth),
    ('teacher_sharp', make_teacher_sharp),
    ('oscillatory', make_oscillatory),
    ('noisy_teacher', make_noisy_teacher),
    ('memorization', make_memorization),
]

K = 128
B_seeds = [55, 66, 88]

print("="*110)
print(f"{'task':>18s}{'Y_var':>10s}{'||f_A-f_C||':>13s}"
      f"{'||f_A-f_B||':>13s}{'%rec':>8s}"
      f"{'d/Y_rms':>10s}{'d_B/d_C':>10s}{'d_B/Y_rms':>11s}")
print(f"{'':>18s}{'(task)':>10s}{'(baseline)':>13s}"
      f"{'(sig match)':>13s}{'':>8s}"
      f"{'(absolute)':>10s}{'(ratio)':>10s}{'(normalized)':>11s}")
print("="*110)

# Additionally: measure ||f_A - 0|| as a "null baseline" (how much does A output?)
# And ||Y||_rms = target scale of the task

all_results = []
for name, make in TASKS:
    X_tr, Y_tr = make(seed=0)
    A = train_standard(MLP(10, 20, 4, seed=1), X_tr, Y_tr, steps=3000)
    C = train_standard(MLP(10, 20, 4, seed=77), X_tr, Y_tr, steps=3000)
    d_C = func_rms(A, C, X_tr)

    Y_rms = float(np.sqrt((Y_tr**2).mean()))
    Y_var = float(Y_tr.var())

    dists = []
    for ps in range(2):
        rng_p = np.random.default_rng(3000 + ps)
        idx = rng_p.choice(X_tr.shape[0], K, replace=False)
        P = X_tr[idx]; T_out, T_H = A.forward(P)
        for s in B_seeds:
            B = train_with_sig(MLP(10, 20, 4, seed=s), X_tr, Y_tr,
                               P, T_out, T_H, lam=12.0, alpha_h=0.3)
            dists.append(func_rms(A, B, X_tr))
    d_B = np.mean(dists)
    recovery = 100 * (1 - d_B / d_C)

    # Relative measures
    d_B_over_Y = d_B / Y_rms
    d_C_over_Y = d_C / Y_rms
    d_B_over_d_C = d_B / d_C

    all_results.append({
        'name': name, 'Y_var': Y_var, 'Y_rms': Y_rms,
        'd_C': d_C, 'd_B': d_B, 'recovery': recovery,
        'd_B_over_Y': d_B_over_Y, 'd_B_over_d_C': d_B_over_d_C,
    })
    print(f"{name:>18s}{Y_var:>10.3f}{d_C:>13.4f}{d_B:>13.4f}{recovery:>+6.1f}%"
          f"{d_B_over_Y:>10.4f}{d_B_over_d_C:>10.3f}{d_B_over_Y:>11.4f}")

# ==================================================================
# What's the real story?
# ==================================================================
print("\n" + "="*78)
print("Interpretation")
print("="*78)

# Absolute ||f_A - f_B|| ranked ascending (lower = better signature compression)
print("\n  Absolute ||f_A - f_B|| (ascending — lower means signature compression worked better):")
order = sorted(all_results, key=lambda r: r['d_B'])
for r in order:
    print(f"    {r['name']:>18s}: d_B = {r['d_B']:.4f}  "
          f"(Y_rms = {r['Y_rms']:.3f}, "
          f"relative d_B/Y_rms = {r['d_B_over_Y']:.4f})")

# Normalized by Y_rms:
print("\n  Absolute d_B normalized by Y_rms (ascending — best compression):")
order = sorted(all_results, key=lambda r: r['d_B_over_Y'])
for r in order:
    print(f"    {r['name']:>18s}: d_B/Y_rms = {r['d_B_over_Y']:.4f}")

# Check: do both nets just learn "mean Y" on memorization?
# Compute f_A mean on memorization vs overall mean
print("\n  Sanity check on memorization: is A collapsing to mean?")
X_m, Y_m = make_memorization(seed=0)
A_m = train_standard(MLP(10, 20, 4, seed=1), X_m, Y_m, steps=3000)
Y_pred = A_m.forward(X_m)[0]
print(f"    A's output variance: {Y_pred.var():.4f}  (Y's variance: {Y_m.var():.4f})")
print(f"    ||A's output - mean(Y)|| / ||Y - mean(Y)||: "
      f"{np.linalg.norm(Y_pred - Y_m.mean(0))/np.linalg.norm(Y_m - Y_m.mean(0)):.3f}")
