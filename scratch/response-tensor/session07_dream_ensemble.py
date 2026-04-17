"""
SESSION 07 — dream-walked ensembles

Test hypothesis: multiple dream-walked copies of a single trained network
produce diverse errors; averaging them recovers (or exceeds) the anchor's
performance. This would give ensemble benefits from one training run.

Comparisons:
  anchor                   : the one trained network
  dream_ensemble           : 5 dream-walked copies averaged
  indep_single             : one independently-trained network (mean)
  indep_ensemble           : 5 independently-trained networks averaged
  noise_ensemble           : 5 copies with random gaussian weight noise,
                             magnitude matched to dream-drift
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
    def params_vec(self):
        return np.concatenate([self.W1.ravel(), self.b1, self.Wo.ravel(), self.bo])

def make_task(seed=0, N_train=600, N_test=400, d_in=10, d_out=4, d_latent=3):
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(d_in), (16, d_in)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16),  (d_out, 16)); bt2 = np.zeros(d_out)
    teacher = lambda X: np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2
    B_embed = r.normal(0, 1, (d_latent, d_in))
    on = lambda N, rng: rng.normal(0, 1, (N, d_latent)) @ B_embed
    _, _, Vt = np.linalg.svd(B_embed, full_matrices=True)
    off_basis = Vt[d_latent:].T
    X_tr = on(N_train, r); Y_tr = teacher(X_tr) + 0.02*r.normal(0,1,(N_train,d_out))
    X_te = on(N_test, r); Y_te = teacher(X_te)
    # off-distribution test
    X_off = r.normal(0, 1, (N_test, off_basis.shape[1])) @ off_basis.T * 3.0
    Y_off = teacher(X_off)
    return dict(X_tr=X_tr, Y_tr=Y_tr, X_te=X_te, Y_te=Y_te,
                X_off=X_off, Y_off=Y_off, d_in=d_in, d_out=d_out)

def train(net, task, steps=2500, lr=0.05):
    for _ in range(steps):
        net.train_step(task['X_tr'], task['Y_tr'], lr)
    return net

def dream_walk(net, steps, eps=0.1, lr=0.01, rng=None):
    if rng is None: rng = np.random.default_rng(0)
    for _ in range(steps):
        N = rng.normal(0, 1, (64, net.d_in))
        Y, _ = net.forward(N)
        Y_target = Y + eps * rng.normal(0, 1, Y.shape)
        net.train_step(N, Y_target, lr)
    return net

def ensemble_predict(nets, X):
    preds = [n.forward(X)[0] for n in nets]
    return np.mean(preds, axis=0), preds

def mse(Yp, Y):
    return float(((Yp - Y)**2).mean())

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------
task = make_task()
print("Training anchor network...")
anchor = train(MLP(task['d_in'], 40, task['d_out'], seed=1), task)
anchor_pred, _ = anchor.forward(task['X_te'])
anchor_loss = mse(anchor_pred, task['Y_te'])
anchor_off = mse(anchor.forward(task['X_off'])[0], task['Y_off'])
print(f"  anchor test loss: {anchor_loss:.5f}  off-manifold: {anchor_off:.4f}")

# ------------------------------------------------------------------
# Dream-walked ensemble
# ------------------------------------------------------------------
print("\nCreating dream-walked copies (5 copies, walk lengths 100..2000)...")
walk_lengths = [100, 300, 600, 1000, 1500]
dream_ensemble = []
for i, steps in enumerate(walk_lengths):
    copy = anchor.clone()
    rng = np.random.default_rng(i + 100)
    dream_walk(copy, steps, rng=rng)
    dream_ensemble.append(copy)
    loss_i = mse(copy.forward(task['X_te'])[0], task['Y_te'])
    drift = norm(copy.params_vec() - anchor.params_vec())
    print(f"  copy {i} (walked {steps} steps): test loss={loss_i:.5f}, drift={drift:.3f}")

de_pred, de_preds = ensemble_predict(dream_ensemble, task['X_te'])
de_loss = mse(de_pred, task['Y_te'])
de_off_pred, _ = ensemble_predict(dream_ensemble, task['X_off'])
de_off = mse(de_off_pred, task['Y_off'])

# ------------------------------------------------------------------
# Independently-trained ensemble
# ------------------------------------------------------------------
print("\nTraining 5 independent networks for comparison...")
indep = []
for s in [11, 12, 13, 14, 15]:
    net = train(MLP(task['d_in'], 40, task['d_out'], seed=s), task)
    indep.append(net)
    print(f"  indep seed {s}: test loss={mse(net.forward(task['X_te'])[0], task['Y_te']):.5f}")
ie_pred, _ = ensemble_predict(indep, task['X_te'])
ie_loss = mse(ie_pred, task['Y_te'])
ie_off_pred, _ = ensemble_predict(indep, task['X_off'])
ie_off = mse(ie_off_pred, task['Y_off'])

indep_single_loss = np.mean([mse(n.forward(task['X_te'])[0], task['Y_te']) for n in indep])
indep_single_off  = np.mean([mse(n.forward(task['X_off'])[0], task['Y_off']) for n in indep])

# ------------------------------------------------------------------
# Noise-perturbation ensemble (matched drift magnitude)
# ------------------------------------------------------------------
# use the mean drift magnitude of dream copies as the perturbation scale
drifts = [norm(c.params_vec() - anchor.params_vec()) for c in dream_ensemble]
mean_drift = np.mean(drifts)
print(f"\nNoise-matched ensemble (perturbation scale = mean drift = {mean_drift:.3f})...")
# Per-weight std for matched drift:
n_params = len(anchor.params_vec())
per_param_sigma = mean_drift / np.sqrt(n_params)
noise_ens = []
for i in range(5):
    rng = np.random.default_rng(i + 999)
    copy = anchor.clone()
    copy.W1 += rng.normal(0, per_param_sigma, copy.W1.shape)
    copy.b1 += rng.normal(0, per_param_sigma, copy.b1.shape)
    copy.Wo += rng.normal(0, per_param_sigma, copy.Wo.shape)
    copy.bo += rng.normal(0, per_param_sigma, copy.bo.shape)
    noise_ens.append(copy)
    li = mse(copy.forward(task['X_te'])[0], task['Y_te'])
    di = norm(copy.params_vec() - anchor.params_vec())
    print(f"  noise copy {i}: test loss={li:.5f}, drift={di:.3f}")
ne_pred, _ = ensemble_predict(noise_ens, task['X_te'])
ne_loss = mse(ne_pred, task['Y_te'])
ne_off_pred, _ = ensemble_predict(noise_ens, task['X_off'])
ne_off = mse(ne_off_pred, task['Y_off'])

# ------------------------------------------------------------------
# Results
# ------------------------------------------------------------------
print("\n" + "="*70)
print(f"{'method':30s}{'test loss':>14s}{'off-mfd':>12s}")
print("="*70)
print(f"{'anchor alone':30s}{anchor_loss:14.5f}{anchor_off:12.4f}")
print(f"{'dream-walked ensemble (5)':30s}{de_loss:14.5f}{de_off:12.4f}")
print(f"{'indep single (mean of 5)':30s}{indep_single_loss:14.5f}{indep_single_off:12.4f}")
print(f"{'independent ensemble (5)':30s}{ie_loss:14.5f}{ie_off:12.4f}")
print(f"{'noise-perturbed ensemble (5)':30s}{ne_loss:14.5f}{ne_off:12.4f}")

# ------------------------------------------------------------------
# Error diversity analysis
# ------------------------------------------------------------------
print("\n" + "="*70)
print("Error diversity analysis")
print("="*70)

def error_correlation(preds_list, Y):
    """Mean pairwise correlation of errors across ensemble members."""
    errs = [p - Y for p in preds_list]          # each [N, d_out]
    errs = [e.ravel() for e in errs]
    n = len(errs)
    corrs = []
    for i in range(n):
        for j in range(i+1, n):
            c = np.corrcoef(errs[i], errs[j])[0, 1]
            corrs.append(c)
    return float(np.mean(corrs))

dream_preds = [n.forward(task['X_te'])[0] for n in dream_ensemble]
indep_preds = [n.forward(task['X_te'])[0] for n in indep]
noise_preds = [n.forward(task['X_te'])[0] for n in noise_ens]

print(f"  dream ensemble  — avg pairwise error correlation: {error_correlation(dream_preds, task['Y_te']):+.4f}")
print(f"  indep ensemble  — avg pairwise error correlation: {error_correlation(indep_preds, task['Y_te']):+.4f}")
print(f"  noise ensemble  — avg pairwise error correlation: {error_correlation(noise_preds, task['Y_te']):+.4f}")

# ratio: how much does ensembling help each method?
print("\n" + "="*70)
print("Ensemble benefit (individual mean loss / ensemble loss, higher=better)")
print("="*70)
dream_individual = np.mean([mse(p, task['Y_te']) for p in dream_preds])
indep_individual = indep_single_loss
noise_individual = np.mean([mse(p, task['Y_te']) for p in noise_preds])
print(f"  dream : individual mean {dream_individual:.5f} → ensemble {de_loss:.5f} (reduction {100*(1-de_loss/dream_individual):.1f}%)")
print(f"  indep : individual mean {indep_individual:.5f} → ensemble {ie_loss:.5f} (reduction {100*(1-ie_loss/indep_individual):.1f}%)")
print(f"  noise : individual mean {noise_individual:.5f} → ensemble {ne_loss:.5f} (reduction {100*(1-ne_loss/noise_individual):.1f}%)")
