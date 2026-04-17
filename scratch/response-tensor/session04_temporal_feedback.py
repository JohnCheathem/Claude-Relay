"""
SESSION 04 — Temporal self-feedback via active gating

Combines three elements (user request):
  (1) temporal trajectory of the self                — past_M(x), not current J(x)
  (2) the unified object                              — M(x), not its contraction J(x)
  (3) active feedback into computation                — gating of main hidden pathway

Architecture:
    h_x   = tanh(W1 x + b1)                              main hidden
    past  = flatten( M_past(x) )   where past-θ is θ_{t-K}, stop-grad
    g     = 1 + tanh(W_g · past + b_g)                  gate (identity at init)
    h_mod = h_x · g                                      active modulation
    y     = W_out · h_mod + b_out

Why past_M rather than current J(x):
  J(x; θ_t) is deterministic given (x, θ_t). Network already has both. Redundant.
  M(x; θ_{t-K}) requires θ_{t-K}. Network does NOT have past weights. Genuine info.

Conditions (5, each with 5 seeds):
  no_feedback      : baseline, g = 1 (disabled)
  self_temporal    : past_M from THIS net's θ_{t-K}             [real]
  other_temporal   : past_M from a DIFFERENT seed's θ_{t-K}     [control: generic past]
  random_history   : past_M replaced by iid random of same shape [control: architecture]
  shuffled_temporal: past_M of this net, batch-permuted          [control: sample mapping]

Key tests:
  self vs other        : is MY history special, or does any past work?
  self vs random       : does content matter vs just having a gating pathway?
  self vs shuffled     : does the sample-by-sample mapping carry signal?
"""

import numpy as np
import copy

# ------------------------------------------------------------------
# Task: teacher-regression on data in a low-dim subspace of ambient input
# ------------------------------------------------------------------
def make_task(seed=0, N_train=500, N_test=200, d_in=8, d_out=4, d_latent=3):
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(d_in), (16, d_in)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16), (d_out, 16));  bt2 = np.zeros(d_out)
    def teacher(X):
        return np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2
    B_embed = r.normal(0, 1, (d_latent, d_in))
    _, _, Vt = np.linalg.svd(B_embed, full_matrices=True)
    null_basis = Vt[d_latent:].T
    def on(N):
        z = r.normal(0, 1, (N, d_latent)); return z @ B_embed
    def off(N):
        z = r.normal(0, 1, (N, null_basis.shape[1])); return z @ null_basis.T
    X_tr = on(N_train); Y_tr = teacher(X_tr) + 0.02*r.normal(0,1,(N_train,d_out))
    X_te = on(N_test);  Y_te = teacher(X_te)
    X_off = off(N_test)*3.0; Y_off = teacher(X_off)
    return dict(X_tr=X_tr, Y_tr=Y_tr, X_te=X_te, Y_te=Y_te, X_off=X_off, Y_off=Y_off,
                d_in=d_in, d_out=d_out)

# ------------------------------------------------------------------
# Gated MLP with optional past-feedback gate
# ------------------------------------------------------------------
class GatedMLP:
    """Main: y = W_out (h_x ⊙ g) + b_out, where h_x = tanh(W1 x + b1).
    Gate: g = 1 + tanh(W_g · past + b_g) if gated; else g = 1."""
    def __init__(self, d_in, d_hid, d_out, d_past, gated=True, seed=0):
        r = np.random.default_rng(seed)
        self.W1 = r.normal(0, 1/np.sqrt(d_in),  (d_hid, d_in))
        self.b1 = np.zeros(d_hid)
        self.Wo = r.normal(0, 1/np.sqrt(d_hid), (d_out, d_hid))
        self.bo = np.zeros(d_out)
        self.gated = gated
        if gated:
            self.Wg = r.normal(0, 0.01/np.sqrt(max(d_past,1)), (d_hid, d_past))
            self.bg = np.zeros(d_hid)
        self.d_in, self.d_hid, self.d_out, self.d_past = d_in, d_hid, d_out, d_past

    def _main_hidden(self, X):
        Z1 = X @ self.W1.T + self.b1
        H  = np.tanh(Z1)
        return Z1, H

    def compute_M(self, X):
        """M(x) = W_out · diag(sech^2(W1 x + b1)). [N, d_out, d_hid]."""
        _, H = self._main_hidden(X)
        sech2 = 1.0 - H**2
        return self.Wo[None,:,:] * sech2[:,None,:]

    def gate(self, past_flat):
        """past_flat: [N, d_past]. Returns g: [N, d_hid] starting near 1."""
        if not self.gated or past_flat is None:
            return np.ones((past_flat.shape[0] if past_flat is not None else 0, self.d_hid))
        z_g = past_flat @ self.Wg.T + self.bg
        return 1.0 + np.tanh(z_g)                # in [0, 2]; starts at 1

    def forward(self, X, past_flat):
        Z1, H = self._main_hidden(X)
        if self.gated and past_flat is not None:
            z_g = past_flat @ self.Wg.T + self.bg
            g   = 1.0 + np.tanh(z_g)
        else:
            g   = np.ones_like(H)
            z_g = None
        H_mod = H * g
        Y = H_mod @ self.Wo.T + self.bo
        return Y, (Z1, H, z_g, g, H_mod)

    def train_step(self, X, past_flat, Y, lr):
        Yp, (Z1, H, z_g, g, H_mod) = self.forward(X, past_flat)
        err = Yp - Y; N = X.shape[0]
        # grad through output layer
        gWo = err.T @ H_mod / N
        gbo = err.mean(0)
        # backprop into h_mod
        dH_mod = err @ self.Wo                              # [N, d_hid]
        # split across h and g (product rule)
        dH = dH_mod * g                                     # dL/dH (via H_mod = H*g)
        dg = dH_mod * H                                     # dL/dg
        dZ1 = dH * (1 - H**2)
        gW1 = dZ1.T @ X / N
        gb1 = dZ1.mean(0)
        self.W1 -= lr*gW1; self.b1 -= lr*gb1
        self.Wo -= lr*gWo; self.bo -= lr*gbo
        # gate pathway (past_flat is stop-grad)
        if self.gated and past_flat is not None:
            dz_g = dg * (1 - np.tanh(z_g)**2)               # derivative of 1+tanh
            gWg = dz_g.T @ past_flat / N
            gbg = dz_g.mean(0)
            self.Wg -= lr*gWg; self.bg -= lr*gbg
        return (err**2).mean(), g

    def snapshot(self):
        """Detached copy of main-pathway weights. Gate weights NOT snapshotted (we
        only ever need past_M, which depends on main pathway only)."""
        return dict(W1=self.W1.copy(), b1=self.b1.copy(),
                    Wo=self.Wo.copy(), bo=self.bo.copy())

# ------------------------------------------------------------------
# Compute M(x) from a detached snapshot (no object, just arrays)
# ------------------------------------------------------------------
def M_from_snapshot(snap, X):
    Z1 = X @ snap['W1'].T + snap['b1']
    H  = np.tanh(Z1)
    sech2 = 1.0 - H**2
    return snap['Wo'][None,:,:] * sech2[:,None,:]            # [N, d_out, d_hid]

# ------------------------------------------------------------------
# Training loop with temporal feedback
# ------------------------------------------------------------------
def run_condition(condition, seed, task, steps=2500, lr=0.05, K=200,
                  other_snap_provider=None):
    d_in, d_out = task['d_in'], task['d_out']
    d_hid = 16
    d_past = d_out * d_hid
    gated = condition != 'no_feedback'
    net = GatedMLP(d_in, d_hid, d_out, d_past, gated=gated, seed=seed)

    rng = np.random.default_rng(seed + 7777)

    # rolling buffer of past snapshots, indexed by step saved
    snap_history = {}   # step -> snapshot dict (detached)

    def past_snap_for_step(t):
        target = t - K
        if target < 0:
            return None
        # use most recent snapshot at or before target
        avail = [s for s in snap_history if s <= target]
        if not avail: return None
        return snap_history[max(avail)]

    def build_past_flat(X, t):
        """Return past feedback tensor of shape [N, d_past] per condition."""
        N = X.shape[0]
        if condition == 'no_feedback':
            return None
        if condition == 'self_temporal':
            snap = past_snap_for_step(t)
            if snap is None: return np.zeros((N, d_past))
            return M_from_snapshot(snap, X).reshape(N, d_past)
        if condition == 'other_temporal':
            # snapshot of some OTHER seed's past state at the same step
            if other_snap_provider is None: return np.zeros((N, d_past))
            snap = other_snap_provider(t)
            if snap is None: return np.zeros((N, d_past))
            return M_from_snapshot(snap, X).reshape(N, d_past)
        if condition == 'random_history':
            return rng.normal(0, 1, (N, d_past))
        if condition == 'shuffled_temporal':
            snap = past_snap_for_step(t)
            if snap is None: return np.zeros((N, d_past))
            M = M_from_snapshot(snap, X).reshape(N, d_past)
            return M[rng.permutation(N)]
        raise ValueError(condition)

    losses = []
    gate_traces = []
    for t in range(steps):
        past = build_past_flat(task['X_tr'], t)
        loss, g = net.train_step(task['X_tr'], past, task['Y_tr'], lr)
        losses.append(loss)
        if t % 100 == 0:
            gate_traces.append((t, float(np.mean(np.abs(g - 1.0))) if g is not None and g.size else 0.0))
        if t % K == 0 and t > 0:
            snap_history[t] = net.snapshot()

    # eval
    def eval_on(X, Y):
        past = build_past_flat(X, steps-1) if gated else None
        Yp, _ = net.forward(X, past); return ((Yp - Y)**2).mean(), Yp

    tr,  _     = eval_on(task['X_tr'],  task['Y_tr'])
    te,  Yp_te = eval_on(task['X_te'],  task['Y_te'])
    off, _     = eval_on(task['X_off'], task['Y_off'])

    # gate usage: how much does gate deviate from identity at test time?
    if gated:
        past_te = build_past_flat(task['X_te'], steps-1)
        _, (_, _, _, g_te, _) = net.forward(task['X_te'], past_te)
        gate_dev = float(np.mean(np.abs(g_te - 1.0)))
    else:
        gate_dev = 0.0

    # ablation: replace gate with identity
    if gated:
        Yp_abl, _ = net.forward(task['X_te'], np.zeros((task['X_te'].shape[0], d_past)))
        # zero past -> z_g = b_g, g = 1 + tanh(b_g); not quite identity unless b_g=0
        # better ablation: call forward with gated=False effectively. Temporarily:
        saved_gated = net.gated; net.gated = False
        Yp_abl_te,  _ = net.forward(task['X_te'],  None)
        Yp_abl_off, _ = net.forward(task['X_off'], None)
        net.gated = saved_gated
        abl_te  = ((Yp_abl_te  - task['Y_te'])**2).mean()
        abl_off = ((Yp_abl_off - task['Y_off'])**2).mean()
    else:
        abl_te = abl_off = None

    return dict(condition=condition, seed=seed,
                train=tr, test=te, off=off,
                gate_dev=gate_dev, abl_te=abl_te, abl_off=abl_off,
                loss_curve=losses, snap_history=snap_history,
                preds_te=Yp_te)

# ------------------------------------------------------------------
# Staged run: need "other_temporal" to reference another seed's history,
# so we first train self_temporal for all seeds to capture snapshots, then
# use those to drive other_temporal runs.
# ------------------------------------------------------------------
SEEDS = [1, 2, 3, 4, 5]
task = make_task(seed=0)
print(f"Task:  {task['X_tr'].shape[0]} train, d_in={task['d_in']}, d_out={task['d_out']}")
print(f"       (data on {3}-dim subspace)\n")

results = []

# First pass: collect self_temporal snapshots (needed for 'other_temporal')
print("Stage 1: run self_temporal for all seeds (also captures snapshots)")
self_snaps = {}
for s in SEEDS:
    r = run_condition('self_temporal', s, task)
    self_snaps[s] = r['snap_history']
    results.append(r)
    print(f"  seed {s}: train={r['train']:.4f}  test={r['test']:.4f}  off={r['off']:.3f}  gate_dev={r['gate_dev']:.3f}")

print("\nStage 2: other conditions")
for cond in ['no_feedback', 'random_history', 'shuffled_temporal', 'other_temporal']:
    for s in SEEDS:
        if cond == 'other_temporal':
            # use a DIFFERENT seed's snapshot history
            other_seed = SEEDS[(SEEDS.index(s)+1) % len(SEEDS)]
            other_hist = self_snaps[other_seed]
            def provider(t, hist=other_hist):
                target = t - 200
                if target < 0: return None
                avail = [k for k in hist if k <= target]
                return hist[max(avail)] if avail else None
            r = run_condition(cond, s, task, other_snap_provider=provider)
        else:
            r = run_condition(cond, s, task)
        results.append(r)
        print(f"  [{cond:20s}] seed {s}: train={r['train']:.4f}  test={r['test']:.4f}  "
              f"off={r['off']:.3f}  gate_dev={r['gate_dev']:.3f}")

# ------------------------------------------------------------------
# Aggregate
# ------------------------------------------------------------------
print("\n" + "="*78)
print(f"{'condition':22s}{'train':>9s}{'test':>9s}{'off_mfd':>10s}{'gate_dev':>11s}"
      f"{'abl_te':>9s}{'abl_off':>10s}")
print("="*78)
for cond in ['no_feedback', 'self_temporal', 'other_temporal',
             'shuffled_temporal', 'random_history']:
    rs = [r for r in results if r['condition'] == cond]
    if not rs: continue
    tr = np.array([r['train'] for r in rs])
    te = np.array([r['test']  for r in rs])
    off= np.array([r['off']   for r in rs])
    gd = np.array([r['gate_dev'] for r in rs])
    abl_te  = [r['abl_te']  for r in rs if r['abl_te']  is not None]
    abl_off = [r['abl_off'] for r in rs if r['abl_off'] is not None]
    abl_te_m  = np.mean(abl_te)  if abl_te  else float('nan')
    abl_off_m = np.mean(abl_off) if abl_off else float('nan')
    print(f"{cond:22s}{tr.mean():9.4f}{te.mean():9.4f}{off.mean():10.3f}"
          f"{gd.mean():11.3f}"
          f"{(f'{abl_te_m:.4f}' if not np.isnan(abl_te_m) else '   —  '):>9s}"
          f"{(f'{abl_off_m:.3f}' if not np.isnan(abl_off_m) else '   —  '):>10s}")
    print(f"{'  ± std':22s}{tr.std():9.4f}{te.std():9.4f}{off.std():10.3f}"
          f"{gd.std():11.3f}")

print("\n" + "="*78)
print("Key comparisons")
print("="*78)
def mean(cond, key):
    xs = np.array([r[key] for r in results if r['condition']==cond])
    return xs.mean(), xs.std()

for m in ['test', 'off', 'gate_dev']:
    print(f"\n{m}:")
    for cond in ['no_feedback','self_temporal','other_temporal','shuffled_temporal','random_history']:
        mn, sd = mean(cond, m)
        print(f"  {cond:22s}: {mn:.4f} ± {sd:.4f}")
