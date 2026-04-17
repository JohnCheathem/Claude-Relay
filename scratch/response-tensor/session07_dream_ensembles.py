"""
SESSION 07 — Dream Ensembles

Hypothesis: train one network, dream-walk copies along the manifold, use as ensemble.
If ensemble accuracy is preserved while individuals degrade, we have a cheap ensemble
method that exploits the session 6 finding.

Conditions:
  single              : one trained net (baseline)
  indep_ensemble      : 5 nets trained independently (expensive gold standard)
  dream_ensemble@K    : 1 trained net, 5 dream-walked copies, K dream steps each
  noise_ensemble      : 1 trained net, 5 copies with gaussian weight perturbation (control)

Metrics:
  - Individual test loss (mean over members)
  - Ensemble test loss (test loss of averaged predictions)
  - Prediction disagreement (std of predictions across members)
  - Calibration: correlation between (per-sample) disagreement and (per-sample) error
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
    def train_step(self, X, Y, lr):
        Yp, H = self.forward(X); err = Yp - Y; N = X.shape[0]
        gWo = err.T @ H / N; gbo = err.mean(0)
        dH = err @ self.Wo; dZ1 = dH * (1 - H**2)
        gW1 = dZ1.T @ X / N; gb1 = dZ1.mean(0)
        self.W1 -= lr*gW1; self.b1 -= lr*gb1
        self.Wo -= lr*gWo; self.bo -= lr*gbo
        return (err**2).mean()
    def clone(self):
        n = MLP.__new__(MLP)
        n.W1 = self.W1.copy(); n.b1 = self.b1.copy()
        n.Wo = self.Wo.copy(); n.bo = self.bo.copy()
        n.d_in, n.d_hid, n.d_out = self.d_in, self.d_hid, self.d_out
        return n

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

def dream(net, steps, eps=0.1, lr=0.01, batch=64, rng=None):
    if rng is None: rng = np.random.default_rng()
    for _ in range(steps):
        N = rng.normal(0, 1, (batch, net.d_in))
        Y, _ = net.forward(N)
        net.train_step(N, Y + eps*rng.normal(0, 1, Y.shape), lr)

def perturb(net, sigma, rng):
    net.W1 += sigma * rng.normal(0, 1, net.W1.shape)
    net.Wo += sigma * rng.normal(0, 1, net.Wo.shape)
    net.b1 += sigma * rng.normal(0, 1, net.b1.shape)
    net.bo += sigma * rng.normal(0, 1, net.bo.shape)

def eval_ensemble(nets, X, Y):
    preds = np.stack([n.forward(X)[0] for n in nets])        # [M, N, d_out]
    mean_pred = preds.mean(axis=0)                            # ensemble prediction
    ens_loss = ((mean_pred - Y)**2).mean()
    # individual losses
    indiv = [(( p - Y)**2).mean() for p in preds]
    # per-sample disagreement (std over members, averaged over outputs)
    disagree = preds.std(axis=0).mean(axis=1)                 # [N]
    # per-sample error of the ensemble
    err = ((mean_pred - Y)**2).mean(axis=1)                   # [N]
    # calibration: correlation between disagreement and error
    cal = float(np.corrcoef(disagree, err)[0, 1])
    return dict(ens_loss=ens_loss, indiv_mean=float(np.mean(indiv)),
                indiv_std=float(np.std(indiv)),
                mean_disagree=float(disagree.mean()), cal=cal)

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
task = make_task()

# train base
print("Train base network:")
base = MLP(task['d_in'], 40, task['d_out'], seed=0)
for _ in range(2500):
    base.train_step(task['X_tr'], task['Y_tr'], lr=0.05)
base_loss = ((base.forward(task['X_te'])[0] - task['Y_te'])**2).mean()
print(f"  base test loss: {base_loss:.4f}\n")

# independent ensemble (gold standard)
print("Train independent ensemble (5 nets):")
indep = []
for s in range(5):
    n = MLP(task['d_in'], 40, task['d_out'], seed=100 + s)
    for _ in range(2500):
        n.train_step(task['X_tr'], task['Y_tr'], lr=0.05)
    indep.append(n)
indep_res = eval_ensemble(indep, task['X_te'], task['Y_te'])
print(f"  ensemble loss: {indep_res['ens_loss']:.4f}   "
      f"indiv: {indep_res['indiv_mean']:.4f} ± {indep_res['indiv_std']:.4f}")
print(f"  calibration (disagree↔error): {indep_res['cal']:.3f}\n")

# dream ensembles at various K
print("Dream ensembles (base cloned + dreamed K steps):")
print(f"{'K':>8s}{'indiv mean':>14s}{'ens loss':>11s}{'disagree':>11s}{'calib':>8s}")
print("-"*60)
for K in [0, 100, 500, 1000, 2000, 5000]:
    copies = []
    for s in range(5):
        c = base.clone()
        rng = np.random.default_rng(s + 7777 + K)
        dream(c, K, rng=rng)
        copies.append(c)
    r = eval_ensemble(copies, task['X_te'], task['Y_te'])
    print(f"{K:>8d}{r['indiv_mean']:14.4f}{r['ens_loss']:11.4f}"
          f"{r['mean_disagree']:11.4f}{r['cal']:8.3f}")

# noise ensembles (control)
print("\nNoise ensembles (base cloned + Gaussian weight perturbation):")
print(f"{'σ':>8s}{'indiv mean':>14s}{'ens loss':>11s}{'disagree':>11s}{'calib':>8s}")
print("-"*60)
for sigma in [0.001, 0.01, 0.03, 0.1, 0.3]:
    copies = []
    for s in range(5):
        c = base.clone()
        perturb(c, sigma, np.random.default_rng(s + 12345 + int(sigma*1e6)))
        copies.append(c)
    r = eval_ensemble(copies, task['X_te'], task['Y_te'])
    print(f"{sigma:>8.3f}{r['indiv_mean']:14.4f}{r['ens_loss']:11.4f}"
          f"{r['mean_disagree']:11.4f}{r['cal']:8.3f}")

# single baseline
print("\nSingle net (no ensembling):")
singleton = eval_ensemble([base], task['X_te'], task['Y_te'])
print(f"  test loss: {singleton['ens_loss']:.4f}")

print("\n" + "="*70)
print("COMPARISON:")
print("="*70)
print(f"  single network               : {singleton['ens_loss']:.4f}")
print(f"  independent ensemble (5)     : {indep_res['ens_loss']:.4f}")
print(f"  best dream ensemble          : depends on K — see table above")
print(f"  noise ensemble               : see table above")
