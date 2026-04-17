"""
SESSION 12A — push the ceiling: output + hidden + Jacobian matching

Session 11 got +52% with output+hidden at K=64 and output-only at K=128.
This session:
  1. Implement analytic Jacobian-matching gradient (exact backprop through J)
  2. Verify against finite differences
  3. Test (output + hidden + Jacobian) combined at K=64, K=128
  4. Tune per-target weights and lambda
"""
import numpy as np
from numpy.linalg import norm

class MLP:
    def __init__(self, d_in, d_hid, d_out, seed=0):
        r = np.random.default_rng(seed)
        self.W1 = r.normal(0, 1/np.sqrt(d_in), (d_hid, d_in))
        self.b1 = np.zeros(d_hid)
        self.Wo = r.normal(0, 1/np.sqrt(d_hid), (d_out, d_hid))
        self.bo = np.zeros(d_out)
        self.d_in, self.d_hid, self.d_out = d_in, d_hid, d_out
    def forward(self, X):
        Z1 = X @ self.W1.T + self.b1
        H = np.tanh(Z1)
        return H @ self.Wo.T + self.bo, H
    def jacobian(self, X):
        _, H = self.forward(X); S = 1.0 - H**2
        return np.einsum('oh,nh,hi->noi', self.Wo, S, self.W1)
    def params(self): return [self.W1, self.b1, self.Wo, self.bo]

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

def out_match_grad(net, P, T_out):
    """Gradient of 0.5 ||f(P) - T_out||^2 / N"""
    return task_grad(net, P, T_out)

def hidden_match_grad(net, P, T_H):
    """Gradient of 0.5 ||H(P) - T_H||^2 / N  (only affects W1, b1)"""
    _, H = net.forward(P); err = (H - T_H) / P.shape[0]
    sech2 = 1.0 - H**2
    dZ1 = err * sech2
    gW1 = dZ1.T @ P; gb1 = dZ1.sum(0)
    return [gW1, gb1, np.zeros_like(net.Wo), np.zeros_like(net.bo)]

def jacobian_match_grad(net, P, T_J):
    """Analytic gradient of 0.5 ||J(P) - T_J||_F^2 / N_probes / (d_out*d_in)
    where J[n,o,i] = sum_h Wo[o,h] * S[n,h] * W1[h,i] with S = sech^2(W1 P + b1).

    Returns [gW1, gb1, gWo, gbo] with gbo = 0 (bo doesn't affect J).
    """
    Z1 = P @ net.W1.T + net.b1
    H = np.tanh(Z1); S = 1.0 - H**2
    J = np.einsum('oh,nh,hi->noi', net.Wo, S, net.W1)
    # normalize by N and by total dims to have comparable gradient magnitude
    N = P.shape[0]; d = net.d_out * net.d_in
    E = (J - T_J) / (N * d)     # [N, d_out, d_in]

    # gWo[o,h] = sum_{n,i} E[n,o,i] * S[n,h] * W1[h,i]
    gWo = np.einsum('noi,nh,hi->oh', E, S, net.W1)
    # direct contribution to W1: dJ[n,o,i]/dW1[h,i'] has direct term Wo[o,h] S[n,h] δ_{ii'}
    gW1_direct = np.einsum('noi,oh,nh->hi', E, net.Wo, S)
    # indirect through S[n,h]: dS[n,h]/dZ1[n,h] = -2 H[n,h] S[n,h]
    # dJ[n,o,i]/dS[n,h] = Wo[o,h] W1[h,i]
    # → dL/dZ1[n,h] = -2 H[n,h] S[n,h] * sum_{o,i} E[n,o,i] Wo[o,h] W1[h,i]
    inner = np.einsum('noi,oh,hi->nh', E, net.Wo, net.W1)
    dZ1 = -2.0 * H * S * inner
    gW1_indirect = dZ1.T @ P
    gW1 = gW1_direct + gW1_indirect
    gb1 = dZ1.sum(axis=0)
    gbo = np.zeros_like(net.bo)
    return [gW1, gb1, gWo, gbo]

# ------------------------------------------------------------------
# Verify Jacobian gradient against finite differences
# ------------------------------------------------------------------
print("Verifying jacobian_match_grad against finite differences ...")
X_test, Y_test = task_teacher(N=100)
test_net = MLP(10, 8, 4, seed=11)
A = MLP(10, 8, 4, seed=22)
T_J = A.jacobian(X_test[:8])
P = X_test[:8]

def jmatch_loss(net, P, T_J):
    J = net.jacobian(P)
    return float(0.5 * ((J - T_J)**2).sum() / (P.shape[0] * T_J.shape[1] * T_J.shape[2]))

analytic = jacobian_match_grad(test_net, P, T_J)

# FD check on a few entries
eps = 1e-5
fd_W1 = np.zeros_like(test_net.W1)
for i in [0, 3, 5]:
    for j in [0, 2, 6]:
        test_net.W1[i, j] += eps
        lp = jmatch_loss(test_net, P, T_J)
        test_net.W1[i, j] -= 2*eps
        lm = jmatch_loss(test_net, P, T_J)
        test_net.W1[i, j] += eps
        fd_W1[i, j] = (lp - lm) / (2*eps)

# Compare
max_err = 0
for i in [0, 3, 5]:
    for j in [0, 2, 6]:
        err = abs(analytic[0][i,j] - fd_W1[i,j])
        max_err = max(max_err, err)
        if err > 1e-4:
            print(f"  W1[{i},{j}]: analytic={analytic[0][i,j]:.6f}, fd={fd_W1[i,j]:.6f}, "
                  f"err={err:.6f}")
print(f"  max W1 entry error: {max_err:.2e}  "
      f"{'✓ PASS' if max_err < 1e-4 else '✗ FAIL'}\n")

# ------------------------------------------------------------------
# Main experiment: test combined targets
# ------------------------------------------------------------------
def apply(net, grads, lr):
    for p, g in zip(net.params(), grads): p -= lr * g

def train_all(net, X, Y, P, T_out, T_H, T_J,
              lam_out=5.0, alpha_h=0.0, alpha_j=0.0,
              steps=2000, lr=0.05, sig_every=3):
    for t in range(steps):
        apply(net, task_grad(net, X, Y), lr)
        if t % sig_every == 0:
            if lam_out > 0:
                apply(net, out_match_grad(net, P, T_out), lr * lam_out)
            if alpha_h > 0:
                apply(net, hidden_match_grad(net, P, T_H), lr * lam_out * alpha_h)
            if alpha_j > 0:
                apply(net, jacobian_match_grad(net, P, T_J), lr * lam_out * alpha_j)
    return net

def train_standard(net, X, Y, steps=2000, lr=0.05):
    for _ in range(steps):
        apply(net, task_grad(net, X, Y), lr)
    return net

def func_rms(a, b, X): return float(np.sqrt(((a.forward(X)[0] - b.forward(X)[0])**2).mean()))
def mse(Yp, Y): return float(((Yp - Y)**2).mean())

X, Y = task_teacher()
A = train_standard(MLP(10, 20, 4, seed=1), X, Y)
C = train_standard(MLP(10, 20, 4, seed=77), X, Y)
BASELINE = func_rms(A, C, X)
print(f"Anchor A task loss: {mse(A.forward(X)[0], Y):.5f}")
print(f"Baseline indep C: ||f_A - f_C||={BASELINE:.4f}\n")

B_seeds = [55, 66, 88]

def evaluate(K, lam_out, alpha_h, alpha_j, seed_probe=0):
    rng_p = np.random.default_rng(2000 + seed_probe + K)
    idx = rng_p.choice(X.shape[0], K, replace=False)
    P = X[idx]
    T_out, T_H = A.forward(P)
    T_J = A.jacobian(P)
    dists = []
    for s in B_seeds:
        B = train_all(MLP(10, 20, 4, seed=s), X, Y, P, T_out, T_H, T_J,
                      lam_out=lam_out, alpha_h=alpha_h, alpha_j=alpha_j)
        dists.append(func_rms(A, B, X))
    md = np.mean(dists)
    return md, 100 * (1 - md / BASELINE)

# ==================================================================
# Baseline: output alone at K=128, λ=8 (session 11 best for output-only)
# ==================================================================
print("="*74)
print("Baseline references (from session 11)")
print("="*74)

d_out_k128, imp_out_k128 = evaluate(K=128, lam_out=8.0, alpha_h=0.0, alpha_j=0.0)
print(f"  output-only, K=128, λ=8:                 {imp_out_k128:+.1f}%")

# ==================================================================
# Add Jacobian matching
# ==================================================================
print("\n" + "="*74)
print("Adding Jacobian matching at K=128")
print("="*74)
print(f"{'α_h':>6s}{'α_j':>6s}{'recovery':>14s}")
print("-"*74)

best = (0, 0, imp_out_k128)
for alpha_h in [0.0, 0.3, 1.0]:
    for alpha_j in [0.0, 0.1, 0.3, 1.0]:
        d, imp = evaluate(K=128, lam_out=8.0, alpha_h=alpha_h, alpha_j=alpha_j)
        mark = ""
        if imp > best[2]:
            best = (alpha_h, alpha_j, imp)
            mark = " ← new best"
        print(f"{alpha_h:>6.2f}{alpha_j:>6.2f}{imp:+11.1f}%{mark}")

print(f"\n  Best combination: α_h={best[0]:.2f}, α_j={best[1]:.2f} → {best[2]:+.1f}%")

# ==================================================================
# Fine-tune best combination
# ==================================================================
print("\n" + "="*74)
print("Fine-tuning best combination, sweeping λ")
print("="*74)
for lam in [3.0, 5.0, 8.0, 12.0, 20.0]:
    d, imp = evaluate(K=128, lam_out=lam, alpha_h=best[0], alpha_j=best[1])
    bar = "▓" * max(0, int(imp/2))
    print(f"  λ={lam:>5.1f}: {imp:+6.1f}%  {bar}")

# ==================================================================
# Try even higher K with best α_h, α_j
# ==================================================================
print("\n" + "="*74)
print("Scaling K with best α_h, α_j")
print("="*74)
for K in [64, 128, 200, 300, 400]:
    # adjust lambda by K (following pattern from session 11)
    lam = {64: 5.0, 128: 8.0, 200: 5.0, 300: 3.0, 400: 2.0}.get(K, 5.0)
    d, imp = evaluate(K=K, lam_out=lam, alpha_h=best[0], alpha_j=best[1])
    print(f"  K={K:>4d}, λ={lam:>4.1f}: {imp:+6.1f}%")
