"""
SESSION 07B — Task-orthogonal dream dynamics

7A showed dream ensembles match single networks but don't beat them, because
isotropic dream diffusion erodes task accuracy along with everything else.

The theory predicts: if we project dream updates ORTHOGONAL to the task
gradient direction, we diffuse on the manifold without eroding task signal.
Individuals should preserve accuracy while still diverging.

Mechanism:
  1. compute task gradient g = ∇_θ L(f(X_tr), Y_tr)   on a real training batch
  2. compute dream update δ_dream (as before)
  3. project orthogonal: δ = δ_dream - (δ_dream · ĝ) · ĝ     where ĝ = g/||g||
  4. apply δ

Compare:
  - single base
  - indep ensemble (5 independently-trained)
  - dream ensemble (isotropic)         [from 7A]
  - dream ensemble (task-orthogonal)   [new]
"""
import numpy as np
from numpy.linalg import norm

class MLP:
    def __init__(self, d_in, d_hid, d_out, seed=0):
        r = np.random.default_rng(seed)
        self.W1 = r.normal(0, 1/np.sqrt(d_in), (d_hid, d_in)); self.b1 = np.zeros(d_hid)
        self.Wo = r.normal(0, 1/np.sqrt(d_hid), (d_out, d_hid)); self.bo = np.zeros(d_out)
        self.d_in, self.d_hid, self.d_out = d_in, d_hid, d_out

    def forward(self, X):
        Z1 = X @ self.W1.T + self.b1; H = np.tanh(Z1); Y = H @ self.Wo.T + self.bo
        return Y, H

    def compute_grads(self, X, Y):
        """Return gradients as a flat dict that can be projected and applied."""
        Yp, H = self.forward(X); err = Yp - Y; N = X.shape[0]
        gWo = err.T @ H / N; gbo = err.mean(0)
        dH = err @ self.Wo; dZ1 = dH * (1 - H**2)
        gW1 = dZ1.T @ X / N; gb1 = dZ1.mean(0)
        return dict(W1=gW1, b1=gb1, Wo=gWo, bo=gbo)

    def apply_update(self, grads, lr):
        self.W1 -= lr * grads['W1']; self.b1 -= lr * grads['b1']
        self.Wo -= lr * grads['Wo']; self.bo -= lr * grads['bo']

    def train_step(self, X, Y, lr):
        g = self.compute_grads(X, Y); self.apply_update(g, lr)
        return ((self.forward(X)[0] - Y)**2).mean()

    def clone(self):
        n = MLP.__new__(MLP)
        n.W1 = self.W1.copy(); n.b1 = self.b1.copy()
        n.Wo = self.Wo.copy(); n.bo = self.bo.copy()
        n.d_in, n.d_hid, n.d_out = self.d_in, self.d_hid, self.d_out
        return n

def flatten(grads):
    return np.concatenate([grads[k].ravel() for k in ['W1','b1','Wo','bo']])
def unflatten(vec, template):
    out = {}; i = 0
    for k in ['W1','b1','Wo','bo']:
        sz = template[k].size
        out[k] = vec[i:i+sz].reshape(template[k].shape); i += sz
    return out

def make_task(seed=0, N_train=600, N_test=400, d_in=10, d_out=4, d_latent=3):
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(d_in), (16, d_in)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16),  (d_out, 16)); bt2 = np.zeros(d_out)
    teacher = lambda X: np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2
    B_embed = r.normal(0, 1, (d_latent, d_in))
    on = lambda N: r.normal(0, 1, (N, d_latent)) @ B_embed
    X_tr = on(N_train); Y_tr = teacher(X_tr) + 0.02*r.normal(0,1,(N_train,d_out))
    X_te = on(N_test); Y_te = teacher(X_te)
    return dict(X_tr=X_tr, Y_tr=Y_tr, X_te=X_te, Y_te=Y_te, d_in=d_in, d_out=d_out)

def dream_step_basic(net, eps, lr, batch, rng):
    N = rng.normal(0, 1, (batch, net.d_in))
    Y, _ = net.forward(N)
    target = Y + eps * rng.normal(0, 1, Y.shape)
    g = net.compute_grads(N, target)
    net.apply_update(g, lr)

def dream_step_task_orthogonal(net, eps, lr, batch, rng, X_tr, Y_tr, task_batch=128):
    """Same as basic dream, but project the update orthogonal to task gradient."""
    # sample noise for dream
    N = rng.normal(0, 1, (batch, net.d_in))
    Y_n, _ = net.forward(N)
    target = Y_n + eps * rng.normal(0, 1, Y_n.shape)
    g_dream = net.compute_grads(N, target)
    # task gradient on a training sub-batch
    idx = rng.integers(0, X_tr.shape[0], task_batch)
    g_task = net.compute_grads(X_tr[idx], Y_tr[idx])
    # project: g = g_dream - (g_dream · ĝ_task) · ĝ_task
    v_dream = flatten(g_dream); v_task = flatten(g_task)
    nt = norm(v_task)
    if nt > 1e-12:
        u = v_task / nt
        v_ortho = v_dream - (v_dream @ u) * u
    else:
        v_ortho = v_dream
    g_ortho = unflatten(v_ortho, g_dream)
    net.apply_update(g_ortho, lr)

def eval_ensemble(nets, X, Y):
    preds = np.stack([n.forward(X)[0] for n in nets])
    mean_pred = preds.mean(0)
    ens_loss = ((mean_pred - Y)**2).mean()
    indiv = [((p - Y)**2).mean() for p in preds]
    disagree = preds.std(0).mean(1)
    err = ((mean_pred - Y)**2).mean(1)
    cal = float(np.corrcoef(disagree, err)[0, 1]) if disagree.std() > 1e-12 else float('nan')
    return dict(ens_loss=ens_loss, indiv_mean=float(np.mean(indiv)),
                indiv_std=float(np.std(indiv)),
                mean_disagree=float(disagree.mean()), cal=cal)

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
task = make_task()

print("Base network:")
base = MLP(task['d_in'], 40, task['d_out'], seed=0)
for _ in range(2500): base.train_step(task['X_tr'], task['Y_tr'], lr=0.05)
base_loss = ((base.forward(task['X_te'])[0] - task['Y_te'])**2).mean()
print(f"  test loss: {base_loss:.4f}\n")

print("Independent ensemble (5 nets, 5× training cost):")
indep = []
for s in range(5):
    n = MLP(task['d_in'], 40, task['d_out'], seed=200 + s)
    for _ in range(2500): n.train_step(task['X_tr'], task['Y_tr'], lr=0.05)
    indep.append(n)
r_indep = eval_ensemble(indep, task['X_te'], task['Y_te'])
print(f"  indiv: {r_indep['indiv_mean']:.4f} ± {r_indep['indiv_std']:.4f}")
print(f"  ensemble: {r_indep['ens_loss']:.4f}")
print(f"  disagreement: {r_indep['mean_disagree']:.4f}")
print(f"  calibration: {r_indep['cal']:.3f}\n")

# Compare isotropic vs task-orthogonal dream at several budgets
print("Dream ensembles at various K:")
print(f"{'method':>25s}{'K':>6s}{'indiv':>10s}{'ens':>10s}{'disagr':>10s}{'cal':>8s}")
print("-"*75)
for K in [500, 1000, 2000, 5000]:
    # isotropic dream
    copies_iso = []
    for s in range(5):
        c = base.clone()
        rng = np.random.default_rng(s + 7777 + K)
        for _ in range(K):
            dream_step_basic(c, eps=0.1, lr=0.01, batch=64, rng=rng)
        copies_iso.append(c)
    r_iso = eval_ensemble(copies_iso, task['X_te'], task['Y_te'])
    print(f"{'isotropic dream':>25s}{K:>6d}{r_iso['indiv_mean']:10.4f}"
          f"{r_iso['ens_loss']:10.4f}{r_iso['mean_disagree']:10.4f}{r_iso['cal']:8.3f}")
    # task-orthogonal dream
    copies_ort = []
    for s in range(5):
        c = base.clone()
        rng = np.random.default_rng(s + 8888 + K)
        for _ in range(K):
            dream_step_task_orthogonal(c, eps=0.1, lr=0.01, batch=64, rng=rng,
                                       X_tr=task['X_tr'], Y_tr=task['Y_tr'])
        copies_ort.append(c)
    r_ort = eval_ensemble(copies_ort, task['X_te'], task['Y_te'])
    print(f"{'task-orthogonal dream':>25s}{K:>6d}{r_ort['indiv_mean']:10.4f}"
          f"{r_ort['ens_loss']:10.4f}{r_ort['mean_disagree']:10.4f}{r_ort['cal']:8.3f}")
    print()

# Summary
print("="*70)
print("SUMMARY")
print("="*70)
print(f"  single network            : {base_loss:.4f}")
print(f"  independent ensemble (5×) : {r_indep['ens_loss']:.4f}  [cost: 5× train]")
print(f"  best isotropic dream      : see table")
print(f"  best task-orthogonal dream: see table  [cost: ~0.5× train for all 5 copies]")
