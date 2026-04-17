"""
SESSION 07C — dream ensembles for uncertainty + other use cases

Dream walks can't beat independent training for accuracy. But they produce
diverse predictions. What CAN that diversity be used for?

Tests:
  1. Uncertainty estimation: does ensemble_variance(x) correlate with
     anchor_error(x)? If so, dream copies give free uncertainty from one
     training run.
  2. Out-of-distribution detection: does ensemble_variance spike on
     off-manifold inputs vs test inputs?
  3. Functional sampling: can we use dream walks to sample "plausible
     alternative networks" for research purposes? Measure how much of
     function-space the walks actually cover.
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
        Z1 = X @ self.W1.T + self.b1; H = np.tanh(Z1); return H @ self.Wo.T + self.bo, H
    def train_step(self, X, Y, lr):
        Yp, H = self.forward(X); err = Yp - Y; N = X.shape[0]
        gWo = err.T @ H / N; gbo = err.mean(0)
        dH = err @ self.Wo; dZ1 = dH * (1 - H**2)
        gW1 = dZ1.T @ X / N; gb1 = dZ1.mean(0)
        self.W1 -= lr*gW1; self.b1 -= lr*gb1
        self.Wo -= lr*gWo; self.bo -= lr*gbo
        return (err**2).mean()
    def clone(self):
        new = MLP.__new__(MLP)
        new.W1 = self.W1.copy(); new.b1 = self.b1.copy()
        new.Wo = self.Wo.copy(); new.bo = self.bo.copy()
        new.d_in = self.d_in; new.d_hid = self.d_hid; new.d_out = self.d_out
        return new

def make_task(seed=0, N_train=600, N_test=400, d_in=10, d_out=4, d_latent=3):
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(d_in), (16, d_in)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16),  (d_out, 16)); bt2 = np.zeros(d_out)
    teacher = lambda X: np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2
    B_embed = r.normal(0, 1, (d_latent, d_in))
    _, _, Vt = np.linalg.svd(B_embed, full_matrices=True)
    off_basis = Vt[d_latent:].T
    on = lambda N, rng: rng.normal(0, 1, (N, d_latent)) @ B_embed
    X_tr = on(N_train, r); Y_tr = teacher(X_tr) + 0.02*r.normal(0,1,(N_train,d_out))
    X_te = on(N_test, r); Y_te = teacher(X_te)
    # Generate inputs at varying off-manifold distance
    X_off_mild = on(200, r) + 0.3 * r.normal(0, 1, (200, d_in))      # mild off-manifold
    Y_off_mild = teacher(X_off_mild)
    X_off_strong = r.normal(0, 1, (200, off_basis.shape[1])) @ off_basis.T * 3.0
    Y_off_strong = teacher(X_off_strong)
    return dict(X_tr=X_tr, Y_tr=Y_tr, X_te=X_te, Y_te=Y_te,
                X_off_mild=X_off_mild, Y_off_mild=Y_off_mild,
                X_off_strong=X_off_strong, Y_off_strong=Y_off_strong,
                d_in=d_in, d_out=d_out)

def train(net, task, steps=2500, lr=0.05):
    for _ in range(steps):
        net.train_step(task['X_tr'], task['Y_tr'], lr)
    return net

def dream_walk(net, steps, rng, eps=0.1, lr=0.01):
    for _ in range(steps):
        N = rng.normal(0, 1, (64, net.d_in))
        Y, _ = net.forward(N)
        net.train_step(N, Y + eps * rng.normal(0, 1, Y.shape), lr)

def mse(Yp, Y): return float(((Yp - Y)**2).mean())

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------
task = make_task()
anchor = train(MLP(task['d_in'], 40, task['d_out'], seed=1), task)

# make dream ensemble
walk_lengths = [200, 500, 1000, 1500, 2000]
dream_ens = []
for i, s in enumerate(walk_lengths):
    c = anchor.clone(); dream_walk(c, s, np.random.default_rng(i + 1000))
    dream_ens.append(c)

# ------------------------------------------------------------------
# Experiment 1: ensemble variance as uncertainty signal
# ------------------------------------------------------------------
print("="*70)
print("EXPERIMENT 1: Does ensemble variance predict anchor error?")
print("="*70)

def per_sample_variance(nets, X):
    """For each sample, variance of predictions across ensemble members. [N, d_out]."""
    preds = np.stack([n.forward(X)[0] for n in nets])   # [K, N, d_out]
    return preds.var(axis=0).mean(axis=-1)              # [N] per-sample scalar variance

def per_sample_anchor_error(anchor, X, Y):
    pred, _ = anchor.forward(X)
    return ((pred - Y)**2).mean(axis=-1)                # [N]

for name, X, Y in [('test',       task['X_te'], task['Y_te']),
                   ('mild off',   task['X_off_mild'], task['Y_off_mild']),
                   ('strong off', task['X_off_strong'], task['Y_off_strong'])]:
    var = per_sample_variance(dream_ens, X)
    err = per_sample_anchor_error(anchor, X, Y)
    corr = float(np.corrcoef(var, err)[0, 1])
    # rank correlation (Spearman)
    from scipy.stats import spearmanr
    rank_corr, _ = spearmanr(var, err)
    print(f"  {name:12s}: var mean={var.mean():.6f}, err mean={err.mean():.4f}, "
          f"pearson={corr:+.3f}, spearman={rank_corr:+.3f}")

# ------------------------------------------------------------------
# Experiment 2: OOD detection via ensemble variance (vs anchor-alone features)
# ------------------------------------------------------------------
print("\n" + "="*70)
print("EXPERIMENT 2: OOD detection — does variance separate in vs out of distribution?")
print("="*70)
var_id   = per_sample_variance(dream_ens, task['X_te'])
var_ood  = per_sample_variance(dream_ens, task['X_off_strong'])
# AUC-like separability: what fraction of OOD points have higher variance than median ID?
median_id = np.median(var_id)
frac_ood_above = (var_ood > median_id).mean()
frac_id_above  = (var_id  > median_id).mean()  # ~0.5
print(f"  var (in-dist)   : mean={var_id.mean():.6f}, median={median_id:.6f}")
print(f"  var (OOD)       : mean={var_ood.mean():.6f}")
print(f"  fraction OOD above in-dist median: {frac_ood_above:.3f}  "
      f"(0.5=no separation, 1.0=perfect)")
# also by ratio
print(f"  variance ratio (OOD/ID): {var_ood.mean()/var_id.mean():.2f}x")

# baseline: anchor's own prediction norm as OOD signal
def pred_norm(net, X):
    p, _ = net.forward(X); return np.linalg.norm(p, axis=-1)
pn_id = pred_norm(anchor, task['X_te'])
pn_ood = pred_norm(anchor, task['X_off_strong'])
median_pn_id = np.median(pn_id)
frac_pn_ood_above = (pn_ood > median_pn_id).mean()
print(f"\n  baseline (anchor pred norm):")
print(f"    pred_norm ID: {pn_id.mean():.3f},  OOD: {pn_ood.mean():.3f}")
print(f"    fraction OOD above ID median: {frac_pn_ood_above:.3f}")

# ------------------------------------------------------------------
# Experiment 3: how much of function-space do dream walks cover?
# ------------------------------------------------------------------
print("\n" + "="*70)
print("EXPERIMENT 3: Function-space coverage of dream walks")
print("="*70)
# Compare spread of predictions within dream ensemble vs within independent ensemble
# If dream spread is comparable to indep spread, walks cover real function-space variety
indep_ens = [train(MLP(task['d_in'], 40, task['d_out'], seed=s), task)
             for s in [11, 12, 13, 14, 15]]

def pairwise_pred_dist(nets, X):
    preds = np.stack([n.forward(X)[0] for n in nets])  # [K, N, d_out]
    K = len(nets)
    dists = []
    for i in range(K):
        for j in range(i+1, K):
            dists.append(np.sqrt(((preds[i] - preds[j])**2).mean()))
    return float(np.mean(dists))

for name, X in [('on-manifold test', task['X_te']),
                ('off-manifold',     task['X_off_strong'])]:
    d_dream = pairwise_pred_dist(dream_ens, X)
    d_indep = pairwise_pred_dist(indep_ens, X)
    print(f"  {name:18s}  dream-ens spread: {d_dream:.4f}   indep-ens spread: {d_indep:.4f}   "
          f"ratio: {d_dream/d_indep:.2f}")

# ------------------------------------------------------------------
# Experiment 4: correlation of dream-var with indep-var
# If both ensemble methods measure "model uncertainty," they should agree
# on WHICH inputs are uncertain.
# ------------------------------------------------------------------
print("\n" + "="*70)
print("EXPERIMENT 4: Does dream-var track indep-var (both measure same uncertainty)?")
print("="*70)
for name, X in [('test',       task['X_te']),
                ('off-mild',   task['X_off_mild']),
                ('off-strong', task['X_off_strong'])]:
    var_dream = per_sample_variance(dream_ens, X)
    var_indep = per_sample_variance(indep_ens, X)
    corr = float(np.corrcoef(var_dream, var_indep)[0, 1])
    from scipy.stats import spearmanr
    rc, _ = spearmanr(var_dream, var_indep)
    print(f"  {name:12s}: pearson={corr:+.3f}, spearman={rc:+.3f}")
