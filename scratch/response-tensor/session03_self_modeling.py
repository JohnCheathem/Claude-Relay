"""
SESSION 03 — Self-modeling experiment

Question: Does a network trained with access to its own input-Jacobian J(x)
perform qualitatively differently from a matched baseline? Specifically, does
the CONTENT of the self-signal matter, vs. just the extra pathway?

Three conditions (5 seeds each):
  A) baseline    : y = MLP(x)
  B) self-access : y = MLP_aug(x, s)  where s = stop_grad(flatten(J(x)))
  C) rand-ctrl   : y = MLP_aug(x, s)  where s = random noise of same shape

MLP_aug has two parallel hidden pathways:
  h_x = tanh(W1 x + b1)           [main]
  h_s = tanh(Ws s + bs)            [side]
  y   = W_out [h_x; h_s] + b_out

J(x) is recomputed every forward pass (cheap for 2-layer MLP). Stop-gradient
means gradients don't flow back through its construction — the self-signal
is treated as a feature, not optimized through.

The key control is (C). If (B) ≈ (C), the side channel just adds capacity
regardless of content; the "self-knowledge" is redundant given x. If (B)
outperforms (C), the content matters.
"""

import numpy as np
from numpy.linalg import norm

# ------------------------------------------------------------------
# Task: teacher regression on data embedded in low-dim subspace
# ------------------------------------------------------------------
def make_task(seed=0, N_train=600, N_test=200, d_in=10, d_out=4, d_latent=3):
    r = np.random.default_rng(seed)
    # fixed teacher
    Wt1 = r.normal(0, 1/np.sqrt(d_in), (16, d_in))
    bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16), (d_out, 16))
    bt2 = np.zeros(d_out)
    def teacher(X):
        return np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2

    # on-manifold data: d_latent-dim latent embedded in d_in-dim input
    B_embed = r.normal(0, 1, (d_latent, d_in))
    def sample_on(N):
        z = r.normal(0, 1, (N, d_latent))
        return z @ B_embed
    def sample_off(N):
        # perturbations orthogonal to embedding row-space
        U, _, _ = np.linalg.svd(B_embed, full_matrices=True)  # [d_latent, d_in] — wait wrong shape
        # redo: need null space of B_embed rows in d_in-space
        # B_embed: [d_latent, d_in]. Its row space is the on-manifold subspace.
        _, _, Vt = np.linalg.svd(B_embed, full_matrices=True)   # Vt: [d_in, d_in]
        null_basis = Vt[d_latent:].T       # [d_in, d_in - d_latent]
        z = r.normal(0, 1, (N, null_basis.shape[1]))
        return z @ null_basis.T

    X_tr = sample_on(N_train)
    Y_tr = teacher(X_tr) + 0.02 * r.normal(0, 1, (N_train, d_out))
    X_te = sample_on(N_test)
    Y_te = teacher(X_te)
    X_off = sample_off(N_test) * 3.0            # clearly off-manifold probes
    Y_off = teacher(X_off)
    return dict(X_tr=X_tr, Y_tr=Y_tr, X_te=X_te, Y_te=Y_te,
                X_off=X_off, Y_off=Y_off, d_in=d_in, d_out=d_out)

# ------------------------------------------------------------------
# Baseline MLP
# ------------------------------------------------------------------
class BaselineMLP:
    def __init__(self, d_in, d_hid, d_out, seed=0):
        r = np.random.default_rng(seed)
        self.W1 = r.normal(0, 1/np.sqrt(d_in),  (d_hid, d_in))
        self.b1 = np.zeros(d_hid)
        self.Wo = r.normal(0, 1/np.sqrt(d_hid), (d_out, d_hid))
        self.bo = np.zeros(d_out)
        self.d_in, self.d_hid, self.d_out = d_in, d_hid, d_out
    def forward(self, X):
        Z1 = X @ self.W1.T + self.b1
        H  = np.tanh(Z1)
        Y  = H @ self.Wo.T + self.bo
        return Y, H
    def jacobian(self, X):
        _, H = self.forward(X)
        sech2 = 1.0 - H**2
        return np.einsum('oh,nh,hi->noi', self.Wo, sech2, self.W1)
    def train_step(self, X, Y, lr):
        Yp, H = self.forward(X)
        err = Yp - Y
        N = X.shape[0]
        gWo = err.T @ H / N
        gbo = err.mean(0)
        dH  = err @ self.Wo
        dZ1 = dH * (1 - H**2)
        gW1 = dZ1.T @ X / N
        gb1 = dZ1.mean(0)
        self.W1 -= lr*gW1; self.b1 -= lr*gb1
        self.Wo -= lr*gWo; self.bo -= lr*gbo
        return (err**2).mean()
    def n_params(self):
        return self.W1.size + self.b1.size + self.Wo.size + self.bo.size

# ------------------------------------------------------------------
# Augmented MLP: two hidden pathways, one for x, one for self-signal s
# ------------------------------------------------------------------
class AugmentedMLP:
    def __init__(self, d_in, d_hid, d_sig, d_hid_s, d_out, seed=0):
        r = np.random.default_rng(seed)
        # main pathway
        self.W1 = r.normal(0, 1/np.sqrt(d_in),  (d_hid, d_in))
        self.b1 = np.zeros(d_hid)
        # side pathway (processes self-signal s)
        self.Ws = r.normal(0, 1/np.sqrt(d_sig), (d_hid_s, d_sig))
        self.bs = np.zeros(d_hid_s)
        # output layer on concatenated hidden
        self.Wo = r.normal(0, 1/np.sqrt(d_hid + d_hid_s), (d_out, d_hid + d_hid_s))
        self.bo = np.zeros(d_out)
        self.d_in, self.d_hid, self.d_sig, self.d_hid_s, self.d_out = \
            d_in, d_hid, d_sig, d_hid_s, d_out

    def compute_self_jacobian_flat(self, X):
        """J(x) for the MAIN pathway only, flattened per sample. [N, d_out*d_in].
        Computed from main pathway weights W1, b1, and a 'virtual' output
        W_main = Wo[:, :d_hid] (the chunk of Wo that reads the main hidden).
        We include all of Wo (main part) for this — the net sees the full
        df/dx of its main pathway. Stop-gradient applied externally.
        """
        Z1 = X @ self.W1.T + self.b1
        H  = np.tanh(Z1)
        sech2 = 1.0 - H**2
        Wo_main = self.Wo[:, :self.d_hid]
        # J = Wo_main @ diag(sech2) @ W1
        J = np.einsum('oh,nh,hi->noi', Wo_main, sech2, self.W1)
        return J.reshape(X.shape[0], -1)       # [N, d_out * d_in]

    def forward(self, X, S):
        """X: [N, d_in], S: [N, d_sig]. Returns y and internals for backprop."""
        Z1 = X @ self.W1.T + self.b1
        H  = np.tanh(Z1)                                    # main hidden
        Zs = S @ self.Ws.T + self.bs
        Hs = np.tanh(Zs)                                    # side hidden
        H_cat = np.concatenate([H, Hs], axis=1)
        Y  = H_cat @ self.Wo.T + self.bo
        return Y, (H, Hs, H_cat, Z1, Zs)

    def train_step(self, X, S, Y, lr):
        # S is treated as stop-gradient (not differentiated through)
        Yp, (H, Hs, H_cat, Z1, Zs) = self.forward(X, S)
        err = Yp - Y
        N = X.shape[0]
        gWo = err.T @ H_cat / N
        gbo = err.mean(0)
        dH_cat = err @ self.Wo
        dH  = dH_cat[:, :self.d_hid]
        dHs = dH_cat[:, self.d_hid:]
        # main pathway backprop
        dZ1 = dH * (1 - H**2)
        gW1 = dZ1.T @ X / N
        gb1 = dZ1.mean(0)
        # side pathway backprop (through S as constant)
        dZs = dHs * (1 - Hs**2)
        gWs = dZs.T @ S / N
        gbs = dZs.mean(0)
        self.W1 -= lr*gW1; self.b1 -= lr*gb1
        self.Ws -= lr*gWs; self.bs -= lr*gbs
        self.Wo -= lr*gWo; self.bo -= lr*gbo
        return (err**2).mean()

    def n_params(self):
        return (self.W1.size + self.b1.size + self.Ws.size + self.bs.size
                + self.Wo.size + self.bo.size)

# ------------------------------------------------------------------
# Experiment runner
# ------------------------------------------------------------------
def run_one_seed(task, condition, seed, steps=3000, lr=0.03):
    d_in, d_out = task['d_in'], task['d_out']
    X_tr, Y_tr = task['X_tr'], task['Y_tr']
    d_sig = d_out * d_in

    rng_sig = np.random.default_rng(seed + 10000)  # for random-control signal

    if condition == 'baseline':
        # slightly wider to approximately match params of augmented
        net = BaselineMLP(d_in, d_hid=40, d_out=d_out, seed=seed)
        def get_signal(X): return None
        def fwd_loss(net, X, Y):
            Yp, _ = net.forward(X); return ((Yp - Y)**2).mean(), Yp
        def step(X, Y):
            return net.train_step(X, Y, lr)
    elif condition == 'self_access':
        net = AugmentedMLP(d_in, d_hid=32, d_sig=d_sig, d_hid_s=16,
                           d_out=d_out, seed=seed)
        def get_signal(X):
            # stop-gradient by construction — it's numpy, no autograd
            return net.compute_self_jacobian_flat(X)
        def fwd_loss(net, X, Y):
            S = net.compute_self_jacobian_flat(X)
            Yp, _ = net.forward(X, S); return ((Yp - Y)**2).mean(), Yp
        def step(X, Y):
            S = net.compute_self_jacobian_flat(X)
            return net.train_step(X, S, Y, lr)
    elif condition == 'random_ctrl':
        net = AugmentedMLP(d_in, d_hid=32, d_sig=d_sig, d_hid_s=16,
                           d_out=d_out, seed=seed)
        # fixed random basis: signal = random projection of x.
        # use a FIXED mapping so the noise is a consistent (if random) feature,
        # not pure IID noise that the net can't use at all. This is a stronger
        # control: it has structure, just wrong structure.
        R_proj = rng_sig.normal(0, 1/np.sqrt(d_in), (d_sig, d_in))
        def get_signal(X):
            return X @ R_proj.T
        def fwd_loss(net, X, Y):
            S = X @ R_proj.T
            Yp, _ = net.forward(X, S); return ((Yp - Y)**2).mean(), Yp
        def step(X, Y):
            S = X @ R_proj.T
            return net.train_step(X, S, Y, lr)
    else:
        raise ValueError(condition)

    losses = []
    for t in range(steps):
        l = step(X_tr, Y_tr)
        losses.append(l)

    # evaluate
    tr_loss  = fwd_loss(net, task['X_tr'],  task['Y_tr'])[0]
    te_loss  = fwd_loss(net, task['X_te'],  task['Y_te'])[0]
    off_loss = fwd_loss(net, task['X_off'], task['Y_off'])[0]

    # ablation: if augmented, zero the self-signal at test time
    abl_te = abl_off = None
    if condition in ('self_access', 'random_ctrl'):
        N_te  = task['X_te'].shape[0]
        N_off = task['X_off'].shape[0]
        S_zero_te  = np.zeros((N_te,  d_sig))
        S_zero_off = np.zeros((N_off, d_sig))
        Yp_te,  _ = net.forward(task['X_te'],  S_zero_te)
        Yp_off, _ = net.forward(task['X_off'], S_zero_off)
        abl_te  = ((Yp_te  - task['Y_te'])**2).mean()
        abl_off = ((Yp_off - task['Y_off'])**2).mean()

    # also snapshot predictions for function-space similarity across seeds
    if condition == 'baseline':
        Yp_te, _ = net.forward(task['X_te'])
    else:
        S_te = get_signal(task['X_te'])
        Yp_te, _ = net.forward(task['X_te'], S_te)

    return dict(condition=condition, seed=seed,
                train_loss=tr_loss, test_loss=te_loss, off_loss=off_loss,
                abl_test=abl_te, abl_off=abl_off,
                n_params=net.n_params(),
                preds_test=Yp_te, final_loss_curve=losses[-100:])

# ------------------------------------------------------------------
# Run all
# ------------------------------------------------------------------
print("="*70)
print("SESSION 03 — self-modeling experiment")
print("="*70)

task = make_task(seed=0)
print(f"Task:  {task['X_tr'].shape[0]} train, {task['X_te'].shape[0]} test, "
      f"{task['X_off'].shape[0]} off-manifold probes")
print(f"       d_in={task['d_in']}, d_out={task['d_out']}\n")

SEEDS = [1, 2, 3, 4, 5]
CONDS = ['baseline', 'self_access', 'random_ctrl']

results = []
for cond in CONDS:
    for s in SEEDS:
        r = run_one_seed(task, cond, s)
        results.append(r)
        print(f"  [{cond:12s}] seed {s}: "
              f"train={r['train_loss']:.4f}  "
              f"test={r['test_loss']:.4f}  "
              f"off={r['off_loss']:.3f}  "
              f"params={r['n_params']}")

# ------------------------------------------------------------------
# Aggregate + report
# ------------------------------------------------------------------
print("\n" + "="*70)
print("AGGREGATE  (mean ± std over 5 seeds)")
print("="*70)

def summarize(cond):
    rs = [r for r in results if r['condition'] == cond]
    tr = np.array([r['train_loss'] for r in rs])
    te = np.array([r['test_loss']  for r in rs])
    off= np.array([r['off_loss']   for r in rs])
    return tr, te, off, rs

for cond in CONDS:
    tr, te, off, rs = summarize(cond)
    print(f"\n  [{cond}]   (n={rs[0]['n_params']} params)")
    print(f"    train loss : {tr.mean():.4f} ± {tr.std():.4f}")
    print(f"    test loss  : {te.mean():.4f} ± {te.std():.4f}")
    print(f"    off-mfd    : {off.mean():.3f} ± {off.std():.3f}")
    if rs[0]['abl_test'] is not None:
        abl_te  = np.array([r['abl_test'] for r in rs])
        abl_off = np.array([r['abl_off']  for r in rs])
        print(f"    [ablation: zero self-signal at test]")
        print(f"      test loss  : {abl_te.mean():.4f} ± {abl_te.std():.4f}  "
              f"(delta = {(abl_te-te).mean():+.4f})")
        print(f"      off-mfd    : {abl_off.mean():.3f} ± {abl_off.std():.3f}  "
              f"(delta = {(abl_off-off).mean():+.3f})")

# ------------------------------------------------------------------
# Function-space diversity within each condition
# ------------------------------------------------------------------
print("\n" + "="*70)
print("FUNCTION-SPACE DIVERSITY: RMS prediction diff between seed pairs")
print("  Lower = seeds converge to more similar functions")
print("="*70)
for cond in CONDS:
    rs = [r for r in results if r['condition'] == cond]
    preds = np.stack([r['preds_test'] for r in rs])    # [n_seeds, N_te, d_out]
    pairwise = []
    for i in range(len(rs)):
        for j in range(i+1, len(rs)):
            pairwise.append(np.sqrt(((preds[i] - preds[j])**2).mean()))
    pairwise = np.array(pairwise)
    print(f"  [{cond:12s}]  {pairwise.mean():.4f} ± {pairwise.std():.4f}")
