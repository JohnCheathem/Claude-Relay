"""
SESSION 07C — Dream-regularized training

Test: interleave dream steps between training steps. Hypothesis: walking the
manifold during training acts as regularization, improving generalization.

Conditions:
  standard_train   : normal gradient descent
  dream_reg_train  : alternating (train step, dream step)  — dream has small lr
  noise_reg_train  : alternating (train step, gaussian weight noise)  [control]
  sgd_noise_train  : SGLD-like (train with gradient + gaussian noise)  [another control]

All run for same total number of parameter updates.

Measure:
  - Training loss
  - Test loss
  - Off-manifold loss (generalization probe)
  - Multiple seeds
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
    def dream_step(self, eps, lr, batch, rng):
        N = rng.normal(0, 1, (batch, self.d_in))
        Y, _ = self.forward(N)
        target = Y + eps * rng.normal(0, 1, Y.shape)
        self.train_step(N, target, lr)
    def perturb_weights(self, sigma, rng):
        self.W1 += sigma * rng.normal(0, 1, self.W1.shape)
        self.Wo += sigma * rng.normal(0, 1, self.Wo.shape)
        self.b1 += sigma * rng.normal(0, 1, self.b1.shape)
        self.bo += sigma * rng.normal(0, 1, self.bo.shape)
    def train_step_sgld(self, X, Y, lr, sigma, rng):
        """Gradient step plus Gaussian noise on weights (SGLD-like)."""
        loss = self.train_step(X, Y, lr)
        self.perturb_weights(sigma, rng)
        return loss

def make_task(seed=0, N_train=400, N_test=400, d_in=10, d_out=4, d_latent=3,
              noise_level=0.1):
    """Task with MORE noise so there's room for regularization to help."""
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(d_in), (16, d_in)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16),  (d_out, 16)); bt2 = np.zeros(d_out)
    teacher = lambda X: np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2
    B_embed = r.normal(0, 1, (d_latent, d_in))
    _, _, Vt = np.linalg.svd(B_embed, full_matrices=True)
    null_basis = Vt[d_latent:].T
    on  = lambda N: r.normal(0, 1, (N, d_latent)) @ B_embed
    off = lambda N: r.normal(0, 1, (N, null_basis.shape[1])) @ null_basis.T
    # noise-corrupted training set, clean test set
    X_tr = on(N_train)
    Y_tr = teacher(X_tr) + noise_level * r.normal(0, 1, (N_train, d_out))
    X_te = on(N_test); Y_te = teacher(X_te)
    X_off = off(N_test)*3.0; Y_off = teacher(X_off)
    return dict(X_tr=X_tr, Y_tr=Y_tr, X_te=X_te, Y_te=Y_te,
                X_off=X_off, Y_off=Y_off, d_in=d_in, d_out=d_out)

def eval_net(net, task):
    tr_loss   = ((net.forward(task['X_tr'])[0]  - task['Y_tr'])**2).mean()
    te_loss   = ((net.forward(task['X_te'])[0]  - task['Y_te'])**2).mean()
    off_loss  = ((net.forward(task['X_off'])[0] - task['Y_off'])**2).mean()
    return float(tr_loss), float(te_loss), float(off_loss)

def run_condition(condition, seed, task, steps=2500, train_lr=0.05, dream_lr=0.003,
                  dream_eps=0.1, sgld_sigma=0.001, reg_sigma=0.003):
    net = MLP(task['d_in'], 40, task['d_out'], seed=seed)
    rng = np.random.default_rng(seed + 54321)
    for t in range(steps):
        if condition == 'standard':
            net.train_step(task['X_tr'], task['Y_tr'], train_lr)
        elif condition == 'dream_reg':
            net.train_step(task['X_tr'], task['Y_tr'], train_lr)
            net.dream_step(dream_eps, dream_lr, 64, rng)
        elif condition == 'noise_reg':
            net.train_step(task['X_tr'], task['Y_tr'], train_lr)
            net.perturb_weights(reg_sigma, rng)
        elif condition == 'sgld':
            net.train_step_sgld(task['X_tr'], task['Y_tr'], train_lr, sgld_sigma, rng)
        else:
            raise ValueError(condition)
    return eval_net(net, task)

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
SEEDS = list(range(1, 8))
print("Running 4 conditions × 7 seeds on a noisy regression task\n")
tasks = [make_task(seed=t) for t in range(3)]  # 3 different tasks for robustness

all_results = {c: [] for c in ['standard', 'dream_reg', 'noise_reg', 'sgld']}
for task_i, task in enumerate(tasks):
    for cond in ['standard', 'dream_reg', 'noise_reg', 'sgld']:
        for s in SEEDS:
            tr, te, off = run_condition(cond, s, task)
            all_results[cond].append((tr, te, off))

# Aggregate
print("="*74)
print(f"{'condition':15s}{'train loss':>14s}{'test loss':>14s}{'off-mfd':>14s}")
print(f"{'':15s}{'(mean±std)':>14s}{'(mean±std)':>14s}{'(mean±std)':>14s}")
print("="*74)
for cond in ['standard', 'dream_reg', 'noise_reg', 'sgld']:
    res = np.array(all_results[cond])
    tr_m, tr_s = res[:,0].mean(), res[:,0].std()
    te_m, te_s = res[:,1].mean(), res[:,1].std()
    off_m, off_s = res[:,2].mean(), res[:,2].std()
    print(f"{cond:15s}{tr_m:8.4f}±{tr_s:.4f}  {te_m:8.4f}±{te_s:.4f}  {off_m:7.3f}±{off_s:.3f}")

# Key comparison: test loss of dream_reg vs standard
print("\n" + "="*74)
print("Per-task test loss (does dream regularization help consistently?)")
print("="*74)
N_per_task = len(SEEDS)
for task_i in range(len(tasks)):
    start = task_i * N_per_task; end = start + N_per_task
    te_standard = np.mean([all_results['standard'][i][1] for i in range(start, end)])
    te_dream    = np.mean([all_results['dream_reg'][i][1] for i in range(start, end)])
    te_noise    = np.mean([all_results['noise_reg'][i][1] for i in range(start, end)])
    te_sgld     = np.mean([all_results['sgld'][i][1]      for i in range(start, end)])
    print(f"  task {task_i}: standard={te_standard:.4f}  dream={te_dream:.4f}  "
          f"noise={te_noise:.4f}  sgld={te_sgld:.4f}")

# Statistical test: is dream_reg consistently better than standard?
print("\nPaired comparison across all (task, seed) pairs:")
wins_dream, losses_dream, ties_dream = 0, 0, 0
for i in range(len(all_results['standard'])):
    s = all_results['standard'][i][1]; d = all_results['dream_reg'][i][1]
    if d < s * 0.98: wins_dream += 1
    elif d > s * 1.02: losses_dream += 1
    else: ties_dream += 1
print(f"  dream_reg vs standard: {wins_dream} wins, {losses_dream} losses, "
      f"{ties_dream} ties  (out of {len(all_results['standard'])})")
