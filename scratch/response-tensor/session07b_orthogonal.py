"""
SESSION 07B — task-orthogonal dream walks for ensemble diversity

Idea: standard dream walk degrades task because it walks randomly including
in task-critical directions. Instead, compute task gradient on a batch, and
project the dream step to be ORTHOGONAL to it. Weights drift; task loss
should stay near-constant by construction.

This should give diverse copies that are NOT degraded. If it works, we have
a cheap ensemble method that beats the anchor.

Compare:
  anchor alone
  standard dream ensemble (baseline from 7A)
  task-orthogonal walk ensemble (this experiment)
  standard dream + brief fine-tune (a second remedy to try)
  independent ensemble (gold standard)
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
    def compute_grads(self, X, Y):
        """Return gradients as a flat vector in the same order as params_vec."""
        Yp, H = self.forward(X); err = Yp - Y; N = X.shape[0]
        gWo = err.T @ H / N; gbo = err.mean(0)
        dH = err @ self.Wo; dZ1 = dH * (1 - H**2)
        gW1 = dZ1.T @ X / N; gb1 = dZ1.mean(0)
        return np.concatenate([gW1.ravel(), gb1, gWo.ravel(), gbo])
    def apply_grad(self, g_flat, lr):
        i = 0
        n = self.W1.size; self.W1 -= lr * g_flat[i:i+n].reshape(self.W1.shape); i += n
        n = self.b1.size; self.b1 -= lr * g_flat[i:i+n]; i += n
        n = self.Wo.size; self.Wo -= lr * g_flat[i:i+n].reshape(self.Wo.shape); i += n
        n = self.bo.size; self.bo -= lr * g_flat[i:i+n]; i += n
    def train_step(self, X, Y, lr):
        g = self.compute_grads(X, Y)
        self.apply_grad(g, lr)
        Yp, _ = self.forward(X)
        return ((Yp - Y)**2).mean()
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
    _, _, Vt = np.linalg.svd(B_embed, full_matrices=True)
    off_basis = Vt[d_latent:].T
    on = lambda N, rng: rng.normal(0, 1, (N, d_latent)) @ B_embed
    X_tr = on(N_train, r); Y_tr = teacher(X_tr) + 0.02*r.normal(0,1,(N_train,d_out))
    X_te = on(N_test, r); Y_te = teacher(X_te)
    X_off = r.normal(0, 1, (N_test, off_basis.shape[1])) @ off_basis.T * 3.0
    Y_off = teacher(X_off)
    return dict(X_tr=X_tr, Y_tr=Y_tr, X_te=X_te, Y_te=Y_te,
                X_off=X_off, Y_off=Y_off, d_in=d_in, d_out=d_out)

def train(net, task, steps=2500, lr=0.05):
    for _ in range(steps):
        net.train_step(task['X_tr'], task['Y_tr'], lr)
    return net

def mse(Yp, Y): return float(((Yp - Y)**2).mean())

def dream_step_grad(net, rng, eps=0.1, batch=64):
    """Compute dream-step gradient as a flat vector (don't apply yet)."""
    N = rng.normal(0, 1, (batch, net.d_in))
    Y, _ = net.forward(N)
    Y_target = Y + eps * rng.normal(0, 1, Y.shape)
    return net.compute_grads(N, Y_target)

def walk_standard(net, steps, rng, lr=0.01):
    for _ in range(steps):
        g = dream_step_grad(net, rng)
        net.apply_grad(g, lr)

def walk_orthogonal(net, steps, task, rng, lr=0.01):
    """At each step, project dream gradient orthogonal to task gradient,
    then apply. Weights drift but task loss should stay constant."""
    for _ in range(steps):
        g_task = net.compute_grads(task['X_tr'], task['Y_tr'])
        g_task_norm = norm(g_task)
        if g_task_norm < 1e-10:
            g_proj = dream_step_grad(net, rng)
        else:
            g_task_hat = g_task / g_task_norm
            g_dream = dream_step_grad(net, rng)
            g_proj = g_dream - np.dot(g_dream, g_task_hat) * g_task_hat
        net.apply_grad(g_proj, lr)

def ensemble_predict(nets, X):
    return np.mean([n.forward(X)[0] for n in nets], axis=0)

# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------
task = make_task()
print("Training anchor ...")
anchor = train(MLP(task['d_in'], 40, task['d_out'], seed=1), task)
anchor_loss = mse(anchor.forward(task['X_te'])[0], task['Y_te'])
anchor_off  = mse(anchor.forward(task['X_off'])[0], task['Y_off'])
print(f"  anchor test loss: {anchor_loss:.5f}  off-manifold: {anchor_off:.4f}")

# ------------------------------------------------------------------
# Ensemble 1: standard dream walks (from 7A)
# ------------------------------------------------------------------
walk_lengths = [100, 300, 600, 1000, 1500]
print("\n--- Standard dream walks ---")
std_ens = []
for i, steps in enumerate(walk_lengths):
    c = anchor.clone(); walk_standard(c, steps, np.random.default_rng(i + 100))
    std_ens.append(c)
    print(f"  copy {i}: test loss {mse(c.forward(task['X_te'])[0], task['Y_te']):.5f}, "
          f"drift {norm(c.params_vec() - anchor.params_vec()):.3f}")

# ------------------------------------------------------------------
# Ensemble 2: task-orthogonal walks
# ------------------------------------------------------------------
print("\n--- Task-orthogonal walks ---")
orth_ens = []
for i, steps in enumerate(walk_lengths):
    c = anchor.clone(); walk_orthogonal(c, steps, task, np.random.default_rng(i + 200))
    orth_ens.append(c)
    print(f"  copy {i}: test loss {mse(c.forward(task['X_te'])[0], task['Y_te']):.5f}, "
          f"drift {norm(c.params_vec() - anchor.params_vec()):.3f}")

# ------------------------------------------------------------------
# Ensemble 3: standard dream + brief fine-tune (another remedy)
# ------------------------------------------------------------------
print("\n--- Dream walk + brief fine-tune ---")
ft_ens = []
for i, steps in enumerate(walk_lengths):
    c = anchor.clone()
    walk_standard(c, steps, np.random.default_rng(i + 300))
    # brief fine-tune: 100 steps (4% of full training)
    for _ in range(100):
        c.train_step(task['X_tr'], task['Y_tr'], lr=0.02)
    ft_ens.append(c)
    print(f"  copy {i}: test loss {mse(c.forward(task['X_te'])[0], task['Y_te']):.5f}, "
          f"drift {norm(c.params_vec() - anchor.params_vec()):.3f}")

# ------------------------------------------------------------------
# Ensemble 4: independent training (gold standard)
# ------------------------------------------------------------------
print("\n--- Independent training (gold standard) ---")
indep = []
for s in [11, 12, 13, 14, 15]:
    n = train(MLP(task['d_in'], 40, task['d_out'], seed=s), task)
    indep.append(n)
    print(f"  seed {s}: test loss {mse(n.forward(task['X_te'])[0], task['Y_te']):.5f}")

# ------------------------------------------------------------------
# Compare
# ------------------------------------------------------------------
def eval_ens(nets):
    te_pred = ensemble_predict(nets, task['X_te'])
    off_pred = ensemble_predict(nets, task['X_off'])
    ind_te = np.mean([mse(n.forward(task['X_te'])[0], task['Y_te']) for n in nets])
    # error correlation
    preds = [n.forward(task['X_te'])[0] for n in nets]
    errs = [(p - task['Y_te']).ravel() for p in preds]
    corrs = []
    for i in range(len(errs)):
        for j in range(i+1, len(errs)):
            corrs.append(np.corrcoef(errs[i], errs[j])[0,1])
    return mse(te_pred, task['Y_te']), mse(off_pred, task['Y_off']), ind_te, np.mean(corrs)

print("\n" + "="*78)
print(f"{'method':30s}{'ens test':>12s}{'ens off':>12s}{'indiv test':>12s}{'err corr':>12s}")
print("="*78)
print(f"{'anchor alone':30s}{anchor_loss:12.5f}{anchor_off:12.4f}{'---':>12s}{'---':>12s}")
for name, nets in [
    ('standard dream ensemble', std_ens),
    ('task-orthogonal ensemble', orth_ens),
    ('dream + fine-tune ensemble', ft_ens),
    ('independent ensemble',     indep),
]:
    te, off, ind, ec = eval_ens(nets)
    print(f"{name:30s}{te:12.5f}{off:12.4f}{ind:12.5f}{ec:12.3f}")

# ------------------------------------------------------------------
# Training cost accounting
# ------------------------------------------------------------------
print("\n" + "="*78)
print("Training step budget (lower = cheaper)")
print("="*78)
print(f"  anchor alone            : 2500 steps     (baseline)")
print(f"  std dream ensemble      : 2500 + sum(walks)/10x = 2500 + ~350 = ~2850 steps "
      f"(walk steps cheap, batch=64 vs full 600)")
print(f"  orthogonal ensemble     : 2500 + ~350 × 2 = ~3200 steps (orthogonal needs task grad too)")
print(f"  dream + fine-tune       : 2500 + ~350 + 500 = ~3350 steps")
print(f"  independent ensemble    : 5 × 2500 = 12500 steps (5x)")
