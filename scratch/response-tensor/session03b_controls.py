"""
SESSION 03B — self-modeling experiment with cleaner controls

Motivation: first run used a random linear projection of x as "random_ctrl,"
which is actually informative about x. This run uses noise signals with
genuinely zero information about x.

Conditions (all with same augmented architecture, 10 seeds each):
  baseline      : no side channel (narrow main pathway only)
  self_access   : side channel = J(x)                         [real self-signal]
  shuffled_J    : side channel = J(x) from OTHER samples      [same dist, wrong content]
  pure_noise    : side channel = fresh random noise each batch [zero info]
  static_noise  : side channel = single random vector, repeated [zero info, constant]
  x_proj        : side channel = random linear projection of x [genuine extra info from x]

Key tests:
  (self_access vs shuffled_J):  does CONTENT of J(x) matter beyond its distribution?
  (self_access vs pure_noise):  does having any signal stabilize off-manifold?
  (self_access vs x_proj):      does J(x) carry info x doesn't already provide?
"""

import numpy as np
rng_task = np.random.default_rng(0)

# ------------------------------------------------------------------
# Task
# ------------------------------------------------------------------
def make_task(seed=0, N_train=600, N_test=200, d_in=10, d_out=4, d_latent=3):
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(d_in), (16, d_in)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16), (d_out, 16));  bt2 = np.zeros(d_out)
    def teacher(X):
        return np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2
    B_embed = r.normal(0, 1, (d_latent, d_in))
    _, _, Vt = np.linalg.svd(B_embed, full_matrices=True)
    null_basis = Vt[d_latent:].T
    def sample_on(N):
        z = r.normal(0, 1, (N, d_latent)); return z @ B_embed
    def sample_off(N):
        z = r.normal(0, 1, (N, null_basis.shape[1])); return z @ null_basis.T
    X_tr = sample_on(N_train); Y_tr = teacher(X_tr) + 0.02*r.normal(0,1,(N_train,d_out))
    X_te = sample_on(N_test);  Y_te = teacher(X_te)
    X_off = sample_off(N_test) * 3.0; Y_off = teacher(X_off)
    return dict(X_tr=X_tr, Y_tr=Y_tr, X_te=X_te, Y_te=Y_te,
                X_off=X_off, Y_off=Y_off, d_in=d_in, d_out=d_out)

# ------------------------------------------------------------------
# Augmented MLP (always used; baseline is just d_hid_s=0)
# ------------------------------------------------------------------
class AugMLP:
    def __init__(self, d_in, d_hid, d_sig, d_hid_s, d_out, seed=0):
        r = np.random.default_rng(seed)
        self.W1 = r.normal(0, 1/np.sqrt(d_in),  (d_hid, d_in))
        self.b1 = np.zeros(d_hid)
        self.d_hid_s = d_hid_s
        if d_hid_s > 0:
            self.Ws = r.normal(0, 1/np.sqrt(d_sig), (d_hid_s, d_sig))
            self.bs = np.zeros(d_hid_s)
        d_hid_total = d_hid + d_hid_s
        self.Wo = r.normal(0, 1/np.sqrt(d_hid_total), (d_out, d_hid_total))
        self.bo = np.zeros(d_out)
        self.d_in, self.d_hid, self.d_sig, self.d_out = d_in, d_hid, d_sig, d_out

    def self_jacobian(self, X):
        Z1 = X @ self.W1.T + self.b1
        H  = np.tanh(Z1)
        sech2 = 1.0 - H**2
        Wo_main = self.Wo[:, :self.d_hid]
        return np.einsum('oh,nh,hi->noi', Wo_main, sech2, self.W1).reshape(X.shape[0], -1)

    def forward(self, X, S=None):
        Z1 = X @ self.W1.T + self.b1
        H  = np.tanh(Z1)
        if self.d_hid_s == 0:
            H_cat = H
            Zs = Hs = None
        else:
            Zs = S @ self.Ws.T + self.bs
            Hs = np.tanh(Zs)
            H_cat = np.concatenate([H, Hs], axis=1)
        Y = H_cat @ self.Wo.T + self.bo
        return Y, (H, Hs, H_cat)

    def train_step(self, X, S, Y, lr):
        Yp, (H, Hs, H_cat) = self.forward(X, S)
        err = Yp - Y; N = X.shape[0]
        gWo = err.T @ H_cat / N; gbo = err.mean(0)
        dH_cat = err @ self.Wo
        dH = dH_cat[:, :self.d_hid]
        dZ1 = dH * (1 - H**2)
        gW1 = dZ1.T @ X / N; gb1 = dZ1.mean(0)
        self.W1 -= lr*gW1; self.b1 -= lr*gb1
        if self.d_hid_s > 0:
            dHs = dH_cat[:, self.d_hid:]
            dZs = dHs * (1 - Hs**2)
            gWs = dZs.T @ S / N; gbs = dZs.mean(0)
            self.Ws -= lr*gWs; self.bs -= lr*gbs
        self.Wo -= lr*gWo; self.bo -= lr*gbo
        return (err**2).mean()

    def n_params(self):
        n = self.W1.size + self.b1.size + self.Wo.size + self.bo.size
        if self.d_hid_s > 0: n += self.Ws.size + self.bs.size
        return n

# ------------------------------------------------------------------
# Signal providers for each condition
# ------------------------------------------------------------------
def build_signal_fn(condition, net, task, seed):
    rng = np.random.default_rng(seed + 99991)
    d_sig = task['d_out'] * task['d_in']
    d_in = task['d_in']

    if condition == 'baseline':
        return None
    if condition == 'self_access':
        return lambda X: net.self_jacobian(X)
    if condition == 'shuffled_J':
        def fn(X):
            S = net.self_jacobian(X)
            perm = rng.permutation(S.shape[0])
            return S[perm]
        return fn
    if condition == 'pure_noise':
        return lambda X: rng.normal(0, 1, (X.shape[0], d_sig))
    if condition == 'static_noise':
        vec = rng.normal(0, 1, (d_sig,))
        return lambda X: np.broadcast_to(vec, (X.shape[0], d_sig)).copy()
    if condition == 'x_proj':
        R = rng.normal(0, 1/np.sqrt(d_in), (d_sig, d_in))
        return lambda X: X @ R.T
    raise ValueError(condition)

# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------
def run(task, condition, seed, steps=2000, lr=0.05):
    d_in, d_out = task['d_in'], task['d_out']
    d_sig = d_out * d_in
    if condition == 'baseline':
        net = AugMLP(d_in, d_hid=40, d_sig=0, d_hid_s=0, d_out=d_out, seed=seed)
    else:
        net = AugMLP(d_in, d_hid=32, d_sig=d_sig, d_hid_s=16, d_out=d_out, seed=seed)
    sig_fn = build_signal_fn(condition, net, task, seed)
    for _ in range(steps):
        S = None if sig_fn is None else sig_fn(task['X_tr'])
        net.train_step(task['X_tr'], S, task['Y_tr'], lr)

    # eval
    def eval_on(X, Y):
        S = None if sig_fn is None else sig_fn(X)
        Yp, _ = net.forward(X, S); return ((Yp - Y)**2).mean(), Yp
    tr, _   = eval_on(task['X_tr'],  task['Y_tr'])
    te, Yp_te  = eval_on(task['X_te'],  task['Y_te'])
    off, _  = eval_on(task['X_off'], task['Y_off'])

    # ablation: zero the signal at test
    abl_te = abl_off = None
    if condition != 'baseline':
        S_te  = np.zeros((task['X_te'].shape[0],  d_sig))
        S_off = np.zeros((task['X_off'].shape[0], d_sig))
        Yp_abl,  _ = net.forward(task['X_te'],  S_te)
        Yp_aoff, _ = net.forward(task['X_off'], S_off)
        abl_te  = ((Yp_abl  - task['Y_te'])**2).mean()
        abl_off = ((Yp_aoff - task['Y_off'])**2).mean()

    # side-channel usage metric: how much of output depends on signal?
    # Compare signal-fed vs signal-zeroed predictions on test
    side_use_te = side_use_off = None
    if condition != 'baseline':
        S_te_live = sig_fn(task['X_te']) if condition != 'baseline' else None
        S_off_live = sig_fn(task['X_off']) if condition != 'baseline' else None
        Yp_live_te,  _ = net.forward(task['X_te'],  S_te_live)
        Yp_live_off, _ = net.forward(task['X_off'], S_off_live)
        Yp_zero_te,  _ = net.forward(task['X_te'],  np.zeros((task['X_te'].shape[0], d_sig)))
        Yp_zero_off, _ = net.forward(task['X_off'], np.zeros((task['X_off'].shape[0], d_sig)))
        side_use_te  = np.sqrt(((Yp_live_te  - Yp_zero_te )**2).mean())
        side_use_off = np.sqrt(((Yp_live_off - Yp_zero_off)**2).mean())

    return dict(condition=condition, seed=seed,
                train_loss=tr, test_loss=te, off_loss=off,
                abl_test=abl_te, abl_off=abl_off,
                side_use_te=side_use_te, side_use_off=side_use_off,
                n_params=net.n_params(), preds_test=Yp_te)

# ------------------------------------------------------------------
# Experiments
# ------------------------------------------------------------------
SEEDS = list(range(1, 7))  # 6 seeds
CONDS = ['baseline', 'self_access', 'shuffled_J', 'pure_noise', 'static_noise', 'x_proj']

task = make_task(seed=0)
print(f"Task: {task['X_tr'].shape[0]} train, d_in={task['d_in']}, d_out={task['d_out']}\n")

results = []
for cond in CONDS:
    for s in SEEDS:
        results.append(run(task, cond, s))

print("="*78)
print(f"{'condition':14s}{'train':>9s}{'test':>9s}{'off_mfd':>10s}  "
      f"{'abl_te':>9s}{'abl_off':>10s}  {'side_use_te':>12s}{'side_use_off':>13s}")
print("="*78)
def agg(cond, key):
    xs = np.array([r[key] for r in results if r['condition']==cond and r[key] is not None])
    return xs.mean() if len(xs) else float('nan'), xs.std() if len(xs) else float('nan')

for cond in CONDS:
    rs = [r for r in results if r['condition'] == cond]
    tr_m, tr_s   = agg(cond, 'train_loss')
    te_m, te_s   = agg(cond, 'test_loss')
    off_m, off_s = agg(cond, 'off_loss')
    abl_te_m,_  = agg(cond, 'abl_test')
    abl_off_m,_ = agg(cond, 'abl_off')
    su_te_m,_   = agg(cond, 'side_use_te')
    su_off_m,_  = agg(cond, 'side_use_off')
    abl_te_str  = f"{abl_te_m:.4f}" if not np.isnan(abl_te_m) else "   —  "
    abl_off_str = f"{abl_off_m:.3f}" if not np.isnan(abl_off_m) else "   —  "
    su_te_str   = f"{su_te_m:.4f}" if not np.isnan(su_te_m) else "   —   "
    su_off_str  = f"{su_off_m:.4f}" if not np.isnan(su_off_m) else "   —   "
    print(f"{cond:14s}{tr_m:9.4f}{te_m:9.4f}{off_m:10.3f}  "
          f"{abl_te_str:>9s}{abl_off_str:>10s}  {su_te_str:>12s}{su_off_str:>13s}")
    print(f"{'  ± std':14s}{tr_s:9.4f}{te_s:9.4f}{off_s:10.3f}")

print("\n" + "="*78)
print("INTERPRETATION SHORTCUTS")
print("="*78)
# 1. Variance of off-manifold loss (how stable each condition is across seeds)
print("\nOff-manifold loss std across seeds (lower = more consistent extrapolation):")
for cond in CONDS:
    xs = [r['off_loss'] for r in results if r['condition'] == cond]
    print(f"  {cond:14s}: std = {np.std(xs):.3f}   mean = {np.mean(xs):.3f}")

# 2. Side-channel usage: how much does the signal actually affect output?
print("\nSide-channel usage (RMS output change when signal is zeroed):")
print("  (Higher = network relies more on the signal)")
for cond in CONDS:
    xs = [r['side_use_te'] for r in results if r['condition']==cond and r['side_use_te'] is not None]
    if xs:
        print(f"  {cond:14s}: on-mfd  = {np.mean(xs):.4f}")
    xs = [r['side_use_off'] for r in results if r['condition']==cond and r['side_use_off'] is not None]
    if xs:
        print(f"  {'':14s}  off-mfd = {np.mean(xs):.4f}")
