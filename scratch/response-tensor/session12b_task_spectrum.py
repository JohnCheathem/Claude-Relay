"""
SESSION 12B — task complexity spectrum

Does signature-compression ratio track task complexity / smoothness?

Tasks (same architecture throughout: d_in=10, d_out=4, hidden=20):
  1. linear         : Y = W X           (minimal complexity)
  2. teacher_smooth : Y = tanh(W1 X) W2 with slow W1 (current baseline)
  3. teacher_sharp  : Y = tanh(5 W1 X) W2  (sharper features)
  4. oscillatory    : Y = sin(3 W X) (periodic, low-dim)
  5. noisy_teacher  : Y = tanh(W1 X) W2 + large_noise
  6. memorization   : Y = random per-sample (maximum task entropy)

For each, use session 12A's best recipe (K=128 on-manifold, output+hidden,
α_h=0.3, λ=12). Measure:
  - A's train loss (proxy for task learnability)
  - A's test loss gap vs train (proxy for overfit / task difficulty)
  - Jacobian effective rank of A at training inputs (function smoothness)
  - Recovery % via signature matching

Hypothesis: smooth structured tasks → high recovery; memorization → low recovery.
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

def out_match_grad(net, P, T_out):
    return task_grad(net, P, T_out)

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
            apply(net, out_match_grad(net, P, T_out), lr * lam)
            if alpha_h > 0:
                apply(net, hidden_match_grad(net, P, T_H), lr * lam * alpha_h)
    return net

def func_rms(a, b, X): return float(np.sqrt(((a.forward(X)[0] - b.forward(X)[0])**2).mean()))
def mse(Yp, Y): return float(((Yp - Y)**2).mean())

# ------------------------------------------------------------------
# Task definitions
# ------------------------------------------------------------------
def make_linear(seed, N=600):
    r = np.random.default_rng(seed)
    W = r.normal(0, 0.3, (4, 10))
    X = r.normal(0, 1, (N, 10))
    Y = X @ W.T + 0.02*r.normal(0, 1, (N, 4))
    return X, Y

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
    Wt1 = r.normal(0, 5/np.sqrt(10), (16, 10))       # sharper activations
    bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16), (4, 16)); bt2 = np.zeros(4)
    B = r.normal(0, 1, (3, 10))
    X = r.normal(0, 1, (N, 3)) @ B
    Y = np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2 + 0.02*r.normal(0, 1, (N, 4))
    return X, Y

def make_oscillatory(seed, N=600):
    r = np.random.default_rng(seed)
    W = r.normal(0, 1, (4, 10))
    X = r.normal(0, 0.5, (N, 10))
    Y = np.sin(3.0 * X @ W.T) + 0.02*r.normal(0, 1, (N, 4))
    return X, Y

def make_noisy_teacher(seed, N=600):
    X, Y = make_teacher_smooth(seed, N)
    r = np.random.default_rng(seed+999)
    Y_noisy = Y + 0.3 * r.normal(0, 1, Y.shape)    # 15× more noise
    return X, Y_noisy

def make_memorization(seed, N=600):
    r = np.random.default_rng(seed)
    X = r.normal(0, 1, (N, 10))
    Y = r.normal(0, 1, (N, 4))                       # random labels
    return X, Y

TASKS = {
    'linear':         make_linear,
    'teacher_smooth': make_teacher_smooth,
    'teacher_sharp':  make_teacher_sharp,
    'oscillatory':    make_oscillatory,
    'noisy_teacher':  make_noisy_teacher,
    'memorization':   make_memorization,
}

# ------------------------------------------------------------------
# Complexity measures
# ------------------------------------------------------------------
def jacobian_effective_rank(net, X):
    J = net.jacobian(X)
    J_flat = J.reshape(X.shape[0], -1)
    s = svd(J_flat, compute_uv=False)
    p = s / s.sum(); p = p[p > 1e-10]
    return float(np.exp(-(p * np.log(p)).sum()))

def task_separability(Y):
    """proxy for task difficulty via output variance structure.
    Low if outputs follow low-dim structure; high if they're random."""
    return float(np.linalg.norm(Y - Y.mean(axis=0)))

# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------
K = 128
B_seeds = [55, 66, 88]

print("="*78)
print(f"{'task':>18s}{'train loss':>12s}{'test loss':>12s}"
      f"{'J_erank':>10s}{'recovery':>12s}")
print("="*78)

results = []
for name, make_task in TASKS.items():
    # Train data + test data (different seeds)
    X_tr, Y_tr = make_task(seed=0)
    X_te, Y_te = make_task(seed=100)
    # Train A
    A = train_standard(MLP(10, 20, 4, seed=1), X_tr, Y_tr, steps=3000)
    C = train_standard(MLP(10, 20, 4, seed=77), X_tr, Y_tr, steps=3000)
    train_loss = mse(A.forward(X_tr)[0], Y_tr)
    test_loss  = mse(A.forward(X_te)[0], Y_te)
    J_erank = jacobian_effective_rank(A, X_tr[:200])
    BASELINE = func_rms(A, C, X_tr)

    # Signature matching with best recipe
    dists = []
    for ps in range(2):
        rng_p = np.random.default_rng(3000 + ps)
        idx = rng_p.choice(X_tr.shape[0], K, replace=False)
        P = X_tr[idx]
        T_out, T_H = A.forward(P)
        for s in B_seeds:
            B = train_with_sig(MLP(10, 20, 4, seed=s), X_tr, Y_tr,
                               P, T_out, T_H, lam=12.0, alpha_h=0.3)
            dists.append(func_rms(A, B, X_tr))
    mean_d = np.mean(dists)
    recovery = 100 * (1 - mean_d / BASELINE)
    results.append({
        'task': name, 'train_loss': train_loss, 'test_loss': test_loss,
        'J_erank': J_erank, 'recovery': recovery, 'baseline': BASELINE,
    })
    print(f"{name:>18s}{train_loss:>12.4f}{test_loss:>12.4f}"
          f"{J_erank:>10.2f}{recovery:>+10.1f}%")

# ------------------------------------------------------------------
# Look for correlation between complexity measures and recovery
# ------------------------------------------------------------------
print("\n" + "="*78)
print("Correlation analysis")
print("="*78)

train_losses = np.array([r['train_loss'] for r in results])
test_losses  = np.array([r['test_loss'] for r in results])
erank        = np.array([r['J_erank'] for r in results])
recoveries   = np.array([r['recovery'] for r in results])
names        = [r['task'] for r in results]

def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])

print(f"  recovery vs train_loss:     pearson = {corr(recoveries, train_losses):+.3f}")
print(f"  recovery vs test_loss:      pearson = {corr(recoveries, test_losses):+.3f}")
print(f"  recovery vs J_erank:        pearson = {corr(recoveries, erank):+.3f}")
print(f"  recovery vs test/train gap: pearson = {corr(recoveries, test_losses - train_losses):+.3f}")

# Ranking
print("\n  Tasks ranked by recovery (highest first):")
order = np.argsort(-recoveries)
for i in order:
    print(f"    {names[i]:>18s}: {recoveries[i]:+6.1f}%  "
          f"(train={train_losses[i]:.3f}, test={test_losses[i]:.3f}, J_erank={erank[i]:.2f})")
