"""
SESSION 07D — task fingerprinting via macro-invariants

Hypothesis: a network's macro-invariants (the set of quantities preserved by
dream dynamics) depend on the task, not just the architecture. Different tasks
leave different signatures. Given a trained network, you should be able to
identify the task from macro-invariants alone.

Procedure:
  1. Define 4 different tasks (same architecture).
  2. Train 5 networks per task (5 seeds × 4 tasks = 20 networks).
  3. For each network, compute a full macro-signature (vector of 10 values).
  4. Can we classify task from signature? Use nearest-neighbor in signature space.
  5. Bonus: what's the structure of the signature-space? PCA shows clusters?
"""
import numpy as np
from numpy.linalg import norm, svd

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
    def jacobian(self, X):
        _, H = self.forward(X); sech2 = 1.0 - H**2
        return np.einsum('oh,nh,hi->noi', self.Wo, sech2, self.W1)

# ------------------------------------------------------------------
# Tasks — same architecture, different functions/data distributions
# ------------------------------------------------------------------
def make_teacher_task(seed=0, latent_dim=3, d_in=10, d_out=4, N=600):
    """Standard teacher regression, data on latent-dim subspace."""
    r = np.random.default_rng(seed)
    Wt1 = r.normal(0, 1/np.sqrt(d_in), (16, d_in)); bt1 = np.zeros(16)
    Wt2 = r.normal(0, 1/np.sqrt(16),  (d_out, 16)); bt2 = np.zeros(d_out)
    B_embed = r.normal(0, 1, (latent_dim, d_in))
    X = (r.normal(0, 1, (N, latent_dim)) @ B_embed)
    Y = np.tanh(X @ Wt1.T + bt1) @ Wt2.T + bt2 + 0.02*r.normal(0, 1, (N, d_out))
    return X, Y

def make_linear_task(seed=0, d_in=10, d_out=4, N=600):
    """Linear regression with additive noise."""
    r = np.random.default_rng(seed)
    W = r.normal(0, 0.3, (d_out, d_in))
    X = r.normal(0, 1, (N, d_in))
    Y = X @ W.T + 0.05*r.normal(0, 1, (N, d_out))
    return X, Y

def make_high_freq_task(seed=0, d_in=10, d_out=4, N=600):
    """Sinusoidal, high-frequency target — should be hard, require sharp Jacobians."""
    r = np.random.default_rng(seed)
    Wf = r.normal(0, 1, (d_out, d_in))
    X = r.normal(0, 0.5, (N, d_in))
    Y = np.sin(3.0 * X @ Wf.T) + 0.02*r.normal(0, 1, (N, d_out))
    return X, Y

def make_sparse_target_task(seed=0, d_in=10, d_out=4, N=600):
    """Target depends on only 2 input dimensions — network should learn sparsity."""
    r = np.random.default_rng(seed)
    W = r.normal(0, 1, (d_out, 2))
    X = r.normal(0, 1, (N, d_in))
    Y = np.tanh(X[:, :2] @ W.T) + 0.02*r.normal(0, 1, (N, d_out))
    return X, Y

TASKS = {
    'teacher': make_teacher_task,
    'linear': make_linear_task,
    'high_freq': make_high_freq_task,
    'sparse': make_sparse_target_task,
}

# ------------------------------------------------------------------
# Compute macro-signature
# ------------------------------------------------------------------
def macro_signature(net, X):
    Yp, H = net.forward(X)
    J = net.jacobian(X)
    J_flat = J.reshape(X.shape[0], -1)
    s_J = svd(J_flat, compute_uv=False)
    p = s_J/s_J.sum(); p = p[p>1e-12]
    J_eff_rank = np.exp(-(p*np.log(p)).sum())
    J_opnorms = np.array([svd(J[i], compute_uv=False).max() for i in range(J.shape[0])])
    # weight-matrix spectrum
    s_W1 = svd(net.W1, compute_uv=False)
    s_Wo = svd(net.Wo, compute_uv=False)
    return np.array([
        float(Yp.var(axis=0).mean()),                 # 0: output variance
        float(s_J[0]),                                # 1: top J singular value
        float(norm(s_J)),                             # 2: J Frobenius
        float(J_eff_rank),                            # 3: J effective rank
        float(s_J[0] / (s_J[-1] + 1e-8)),             # 4: J condition number
        float(H.var(axis=0).mean()),                  # 5: hidden var
        float((np.abs(H) < 0.1).mean()),              # 6: hidden sparsity
        float(J_opnorms.max()),                       # 7: Lipschitz
        float(s_W1[0]),                               # 8: top W1 singular
        float(s_Wo[0]),                               # 9: top Wo singular
    ])

SIG_NAMES = ['out_var', 'J_top', 'J_frob', 'J_eff_rank', 'J_cond',
             'H_var', 'H_sparsity', 'Lipschitz', 'W1_top', 'Wo_top']

# ------------------------------------------------------------------
# Train all networks, compute signatures
# ------------------------------------------------------------------
SEEDS = [1, 2, 3, 4, 5]
D_HID = 40
signatures = []
labels = []
nets_by_task = {}
print("Training 4 tasks × 5 seeds = 20 networks ...")
for task_name, task_fn in TASKS.items():
    nets_by_task[task_name] = []
    for s in SEEDS:
        X, Y = task_fn(seed=s)
        # handle varying d_in
        d_in = X.shape[1]; d_out = Y.shape[1]
        net = MLP(d_in, D_HID, d_out, seed=s+100)
        for _ in range(2500):
            net.train_step(X, Y, 0.05)
        loss = ((net.forward(X)[0] - Y)**2).mean()
        sig = macro_signature(net, X[:200])   # signature on a probe batch
        signatures.append(sig)
        labels.append(task_name)
        nets_by_task[task_name].append((net, X, Y))
        print(f"  {task_name:12s} seed {s}: train loss {loss:.4f}  sig top-5: "
              f"{np.round(sig[:5], 3)}")

signatures = np.array(signatures)
labels = np.array(labels)

# ------------------------------------------------------------------
# Nearest-neighbor classification in signature space (leave-one-out)
# ------------------------------------------------------------------
print("\n" + "="*70)
print("Leave-one-out nearest-neighbor classification (task from signature)")
print("="*70)

# normalize signatures per dimension (so ranges don't dominate)
sig_norm = (signatures - signatures.mean(axis=0)) / (signatures.std(axis=0) + 1e-8)

correct = 0
conf_matrix = {t: {t2: 0 for t2 in TASKS} for t in TASKS}
for i in range(len(sig_norm)):
    # distances to all other samples
    others_idx = [j for j in range(len(sig_norm)) if j != i]
    d = np.array([norm(sig_norm[i] - sig_norm[j]) for j in others_idx])
    nearest = others_idx[int(np.argmin(d))]
    pred = labels[nearest]
    true = labels[i]
    conf_matrix[true][pred] += 1
    if pred == true:
        correct += 1

print(f"Accuracy: {correct}/{len(sig_norm)} = {100*correct/len(sig_norm):.1f}%")
print("  (random chance: 25%)")
print("\nConfusion matrix (rows=true, cols=predicted):")
row_w = 14
print(f"{'':>{row_w}s}" + "".join(f"{t:>12s}" for t in TASKS))
for t in TASKS:
    print(f"{t:>{row_w}s}" + "".join(f"{conf_matrix[t][t2]:>12d}" for t2 in TASKS))

# ------------------------------------------------------------------
# Which signature dimensions are most discriminative?
# ------------------------------------------------------------------
print("\n" + "="*70)
print("Per-dimension discrimination: F-statistic of each signature feature")
print("="*70)
from scipy import stats as scistats
f_stats = []
for dim in range(signatures.shape[1]):
    groups = [signatures[labels == t, dim] for t in TASKS]
    f, _ = scistats.f_oneway(*groups)
    f_stats.append((SIG_NAMES[dim], f))
f_stats.sort(key=lambda x: -x[1])
for name, f in f_stats:
    print(f"  {name:15s}: F = {f:.2f}")

# ------------------------------------------------------------------
# 2D visualization via PCA
# ------------------------------------------------------------------
print("\n" + "="*70)
print("PCA of signature space (top 2 components)")
print("="*70)
from numpy.linalg import svd as np_svd
mean_sig = sig_norm.mean(axis=0)
centered = sig_norm - mean_sig
U, S, Vt = np_svd(centered, full_matrices=False)
proj = centered @ Vt[:2].T    # [20, 2]
total_var = (S**2).sum()
print(f"  PC1 explains {100*S[0]**2/total_var:.1f}%")
print(f"  PC2 explains {100*S[1]**2/total_var:.1f}%")
print("\n  Task centroids in PC1-PC2 space:")
for t in TASKS:
    mask = (labels == t)
    cx, cy = proj[mask, 0].mean(), proj[mask, 1].mean()
    sx, sy = proj[mask, 0].std(),  proj[mask, 1].std()
    print(f"    {t:12s}: center=({cx:+.2f}, {cy:+.2f})  spread=({sx:.2f}, {sy:.2f})")

# mean pairwise distance between task centroids vs within-task spread
print("\n  Signal-to-noise: inter-cluster distance / intra-cluster spread")
centroids = {t: proj[labels == t].mean(axis=0) for t in TASKS}
inter = []
for t1 in TASKS:
    for t2 in TASKS:
        if t1 != t2:
            inter.append(norm(centroids[t1] - centroids[t2]))
intra = []
for t in TASKS:
    mask = labels == t
    center = proj[mask].mean(axis=0)
    for p in proj[mask]:
        intra.append(norm(p - center))
print(f"    inter-cluster mean dist: {np.mean(inter):.3f}")
print(f"    intra-cluster mean dist: {np.mean(intra):.3f}")
print(f"    ratio: {np.mean(inter)/max(np.mean(intra), 1e-6):.2f}  (higher = more separable)")
