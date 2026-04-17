"""
SESSION 02 — the unified object candidate M(x), and why Jacobian residuals differ

Algebraic finding (2-layer tanh MLP):
    Define M(x) = W2 @ diag(sech^2(W1 x + b1))     shape [d_out, d_hid]
    Then:
        dy/dx         = M(x) @ W1              shape [d_out, d_in]
        dy/dW1[i,j,k] = M(x)[i,j] * x[k]        (M ⊗ x)
        dy/dW2[i,j,k] = δ_ij * h[k]             (depends only on hidden activation)

    M(x) is the per-input "sensitivity-to-hidden-layer" matrix. Both the input
    Jacobian and the W1 weight Jacobian are contractions of M.  This is our
    cleanest Maxwell-object candidate: weights and activations (via J and dy/dθ)
    are BOTH projections of M.

Tests this session:
    T5. Hungarian hidden-unit alignment on weights.
        Prediction: weight-space distance should drop sharply; J residual agreement
        should not improve, because J is already permutation-invariant.
    T6. Jacobian covariance comparison Σ_A vs Σ_B (moments, not subspaces).
    T7. On-manifold vs off-manifold split of residual J.
        Prediction: on-manifold agreement >> off-manifold agreement.
    T8. Compare M(x) directly between nets, not J(x).  If M is the right object,
        aligned hidden units should make M_A(x) ≈ M_B(x) under the alignment.
"""

import numpy as np
from numpy.linalg import svd, norm
from scipy.optimize import linear_sum_assignment

rng = np.random.default_rng(0)

# -----------------------------------------------------------------
# MLP (reused)
# -----------------------------------------------------------------
class TinyMLP:
    def __init__(self, d_in, d_hid, d_out, seed=0):
        r = np.random.default_rng(seed)
        self.W1 = r.normal(0, 1/np.sqrt(d_in),  (d_hid, d_in))
        self.b1 = np.zeros(d_hid)
        self.W2 = r.normal(0, 1/np.sqrt(d_hid), (d_out, d_hid))
        self.b2 = np.zeros(d_out)
    def forward(self, X):
        Z1 = X @ self.W1.T + self.b1
        H  = np.tanh(Z1)
        Y  = H @ self.W2.T + self.b2
        return Y, H, Z1
    def M_batch(self, X):
        """M(x) = W2 @ diag(sech^2(W1 x + b1)). Returns [N, d_out, d_hid]."""
        _, H, _ = self.forward(X)
        sech2 = 1.0 - H**2                      # [N, d_hid]
        # M[n, o, h] = W2[o, h] * sech2[n, h]
        return self.W2[None, :, :] * sech2[:, None, :]
    def jacobian_batch(self, X):
        M = self.M_batch(X)
        return np.einsum('noh,hi->noi', M, self.W1)
    def train(self, X, Y, lr=0.05, steps=2000):
        for t in range(steps):
            Yp, H, _ = self.forward(X)
            err = Yp - Y
            N = X.shape[0]
            gW2 = err.T @ H / N; gb2 = err.mean(0)
            dH = err @ self.W2; dZ1 = dH * (1 - H**2)
            gW1 = dZ1.T @ X / N; gb1 = dZ1.mean(0)
            self.W1 -= lr*gW1; self.b1 -= lr*gb1
            self.W2 -= lr*gW2; self.b2 -= lr*gb2

# -----------------------------------------------------------------
# Task
# -----------------------------------------------------------------
D_IN, D_HID, D_OUT, N = 12, 64, 6, 800
X = rng.normal(0, 1, (N, D_IN))
teacher = TinyMLP(D_IN, 24, D_OUT, seed=7)
Y = teacher.forward(X)[0] + 0.02 * rng.normal(0, 1, (N, D_OUT))

net_a = TinyMLP(D_IN, D_HID, D_OUT, seed=11); net_a.train(X, Y)
net_b = TinyMLP(D_IN, D_HID, D_OUT, seed=42); net_b.train(X, Y)

print(f"Final loss:  A={((net_a.forward(X)[0]-Y)**2).mean():.5f}"
      f"   B={((net_b.forward(X)[0]-Y)**2).mean():.5f}")

# -----------------------------------------------------------------
# T5. Hungarian hidden-unit alignment on weights
# -----------------------------------------------------------------
# Use hidden activations on data as "signatures" for each unit.
Ha = net_a.forward(X)[1]         # [N, d_hid]
Hb = net_b.forward(X)[1]

# Correlation matrix between A's hidden units and B's hidden units.
# Allow sign flips: align on |correlation|, then apply sign.
def standardize(M):
    m = M.mean(0, keepdims=True); s = M.std(0, keepdims=True) + 1e-9
    return (M - m) / s
Ha_s = standardize(Ha); Hb_s = standardize(Hb)
Corr = (Ha_s.T @ Hb_s) / N                      # [d_hid, d_hid]

# maximize sum |corr| -> linear assignment on -|Corr|
row_ind, col_ind = linear_sum_assignment(-np.abs(Corr))
# record chosen sign per pair
signs = np.sign(Corr[row_ind, col_ind])
signs[signs == 0] = 1

print(f"\n[T5] Hungarian hidden alignment:")
print(f"  mean |correlation| before alignment (diagonal of raw corr): "
      f"{np.abs(np.diag(Corr)).mean():.4f}")
print(f"  mean |correlation| AFTER alignment (best-match pairs):      "
      f"{np.abs(Corr[row_ind, col_ind]).mean():.4f}")

# Permute + sign-flip B to align with A
P = np.zeros((D_HID, D_HID))
for r, c, s in zip(row_ind, col_ind, signs):
    P[r, c] = s                                 # P @ v_b ≈ v_a
# Apply: W1_b' = P @ W1_b, W2_b' = W2_b @ P^T, b1_b' = P @ b1_b
W1_b_aligned = P @ net_b.W1
W2_b_aligned = net_b.W2 @ P.T
b1_b_aligned = P @ net_b.b1

print(f"\n[T5 cont.] Weight-space distances before vs after alignment:")
print(f"  ||W1_a - W1_b||     = {norm(net_a.W1 - net_b.W1):.4f}")
print(f"  ||W1_a - W1_b_aln|| = {norm(net_a.W1 - W1_b_aligned):.4f}")
print(f"  ||W2_a - W2_b||     = {norm(net_a.W2 - net_b.W2):.4f}")
print(f"  ||W2_a - W2_b_aln|| = {norm(net_a.W2 - W2_b_aligned):.4f}")

# Jacobians ARE already perm-invariant; alignment should not change J
Jb_before = net_b.jacobian_batch(X)
# Build aligned net_b by substituting weights
class NetFromWeights(TinyMLP):
    def __init__(self, W1, b1, W2, b2):
        self.W1, self.b1, self.W2, self.b2 = W1, b1, W2, b2
net_b_aln = NetFromWeights(W1_b_aligned, b1_b_aligned, W2_b_aligned, net_b.b2)
Jb_after  = net_b_aln.jacobian_batch(X)
print(f"  ||J_b - J_b_aligned||^2 / ||J_b||^2 = "
      f"{(norm(Jb_before - Jb_after)**2 / norm(Jb_before)**2):.2e}"
      f"   (should be ~0: J is permutation-invariant by construction)")

# -----------------------------------------------------------------
# T6. Jacobian covariance Σ_A vs Σ_B
# -----------------------------------------------------------------
Ra = net_a.jacobian_batch(X)              # [N, d_out, d_in]
Rb = net_b.jacobian_batch(X)
Ra_flat = Ra.reshape(N, -1); Rb_flat = Rb.reshape(N, -1)
mu_a = Ra_flat.mean(0); mu_b = Rb_flat.mean(0)
Xa = Ra_flat - mu_a; Xb = Rb_flat - mu_b
Sigma_a = (Xa.T @ Xa) / (N - 1)           # [72, 72]
Sigma_b = (Xb.T @ Xb) / (N - 1)

# Compare covariances: symmetric KL-like measure, spectrum overlap, Frobenius diff
def symm_bures(A, B, eps=1e-8):
    """Bures/Wasserstein^2 between centered Gaussians with these covariances."""
    # 2-Wasserstein^2 between N(0, A) and N(0, B) = tr(A+B - 2*(A^{1/2} B A^{1/2})^{1/2})
    # stable computation via eigendecomp of A
    wa, Va = np.linalg.eigh(A)
    wa = np.clip(wa, 0, None)
    A_half = Va @ np.diag(np.sqrt(wa)) @ Va.T
    inner = A_half @ B @ A_half
    wi, _ = np.linalg.eigh(inner)
    wi = np.clip(wi, 0, None)
    return float(np.trace(A) + np.trace(B) - 2*np.sum(np.sqrt(wi)))

print(f"\n[T6] Jacobian covariance comparison:")
print(f"  ||Σ_a - Σ_b||_F / ||Σ_a||_F = {norm(Sigma_a-Sigma_b) / norm(Sigma_a):.4f}")
# spectrum
ea = np.linalg.eigvalsh(Sigma_a)[::-1]
eb = np.linalg.eigvalsh(Sigma_b)[::-1]
print(f"  top-5 eigvals of Σ_a: {np.round(ea[:5],3)}")
print(f"  top-5 eigvals of Σ_b: {np.round(eb[:5],3)}")
# Bures distance
print(f"  Bures distance      : {np.sqrt(symm_bures(Sigma_a, Sigma_b)):.4f}")
print(f"  sqrt(tr Σ_a)        : {np.sqrt(np.trace(Sigma_a)):.4f}  (scale reference)")

# -----------------------------------------------------------------
# T7. On-manifold vs off-manifold residual decomposition
# -----------------------------------------------------------------
# Data PCs: eigenvectors of X^T X
Cov_X = X.T @ X / N
wx, Ux = np.linalg.eigh(Cov_X)
order = np.argsort(wx)[::-1]
wx = wx[order]; Ux = Ux[:, order]
# For a random N(0,I) input, all D_IN directions have ~unit variance (no manifold
# structure beyond isotropy). To actually test manifold vs off-manifold, we need
# a lower-dim task. Let's create one: embed 4-dim structure into 12-dim input.
print(f"\n[T7] Data PC eigenvalues (current task): {np.round(wx, 3)}")
print("  Input data is isotropic (all eigenvalues ~1). Creating a low-rank variant...")

# --- variant: same teacher, but data lives on 4-d subspace in 12-d ambient ---
D_LATENT = 4
Z = rng.normal(0, 1, (N, D_LATENT))
B_embed = rng.normal(0, 1, (D_LATENT, D_IN))
X2 = Z @ B_embed                                        # lies on 4-d subspace
Y2 = teacher.forward(X2)[0] + 0.02*rng.normal(0, 1, (N, D_OUT))
net_a2 = TinyMLP(D_IN, D_HID, D_OUT, seed=11); net_a2.train(X2, Y2)
net_b2 = TinyMLP(D_IN, D_HID, D_OUT, seed=42); net_b2.train(X2, Y2)

# Compute data PCs of X2
Cov_X2 = X2.T @ X2 / N
wx2, Ux2 = np.linalg.eigh(Cov_X2)
order = np.argsort(wx2)[::-1]; wx2 = wx2[order]; Ux2 = Ux2[:, order]
print(f"  Variant PC eigenvalues: {np.round(wx2, 4)}")
on_manifold_dirs  = Ux2[:, :D_LATENT]                    # [d_in, 4]
off_manifold_dirs = Ux2[:, D_LATENT:]                    # [d_in, 8]

Ra2 = net_a2.jacobian_batch(X2)                          # [N, d_out, d_in]
Rb2 = net_b2.jacobian_batch(X2)
Ja_mean = Ra2.mean(0); Jb_mean = Rb2.mean(0)
res_a = Ra2 - Ja_mean; res_b = Rb2 - Jb_mean              # [N, d_out, d_in]

def project_J(J_tensor, basis):
    """Project J onto input-side basis. Returns J restricted to those input dirs."""
    # J_tensor [N, d_out, d_in]; basis [d_in, k]
    return np.einsum('noi,ik->nok', J_tensor, basis)

res_a_on  = project_J(res_a, on_manifold_dirs)
res_b_on  = project_J(res_b, on_manifold_dirs)
res_a_off = project_J(res_a, off_manifold_dirs)
res_b_off = project_J(res_b, off_manifold_dirs)

def agreement(A, B):
    """Cosine between flattened tensors."""
    a = A.ravel(); b = B.ravel()
    if norm(a) < 1e-12 or norm(b) < 1e-12: return float('nan')
    return float(a @ b / (norm(a) * norm(b)))

def energy(A): return float((A**2).sum())

print(f"\n[T7] Residual J: on-manifold (4 dirs) vs off-manifold (8 dirs):")
print(f"  on-manifold energy  A={energy(res_a_on):7.2f}   B={energy(res_b_on):7.2f}")
print(f"  off-manifold energy A={energy(res_a_off):7.2f}   B={energy(res_b_off):7.2f}")
print(f"  cosine(res_a_on , res_b_on ) = {agreement(res_a_on, res_b_on):.4f}")
print(f"  cosine(res_a_off, res_b_off) = {agreement(res_a_off, res_b_off):.4f}")

# Also check subspace alignment per-block
def subspace_overlap(Aflat, Bflat, k):
    _, _, Va = svd(Aflat, full_matrices=False)
    _, _, Vb = svd(Bflat, full_matrices=False)
    k = min(k, Va.shape[0], Vb.shape[0])
    return svd(Va[:k] @ Vb[:k].T, compute_uv=False).mean()

print(f"  subspace cos k=10 (on ): "
      f"{subspace_overlap(res_a_on.reshape(N,-1), res_b_on.reshape(N,-1), 10):.4f}")
print(f"  subspace cos k=10 (off): "
      f"{subspace_overlap(res_a_off.reshape(N,-1), res_b_off.reshape(N,-1), 10):.4f}")

# -----------------------------------------------------------------
# T8. Compare M(x) directly between nets (after alignment)
# -----------------------------------------------------------------
# M_a(x) and M_b(x) both have shape [N, d_out, d_hid]. Compare columns after
# aligning hidden units.
Ma = net_a.M_batch(X)                       # [N, d_out, d_hid]
Mb = net_b.M_batch(X)

# align B's hidden units to A's (reuse Corr from T5)
row_ind, col_ind = linear_sum_assignment(-np.abs(Corr))
signs = np.sign(Corr[row_ind, col_ind])
signs[signs == 0] = 1

# Mb_aligned: column j of Mb_aligned = signs[k] * Mb[:,:,col_ind[k]] where row_ind[k]=j
# build an aligned permutation on hidden axis
Mb_aln = np.zeros_like(Mb)
for k in range(D_HID):
    j = row_ind[k]; c = col_ind[k]; s = signs[k]
    Mb_aln[:, :, j] = s * Mb[:, :, c]

print(f"\n[T8] M(x) comparison (unified-object candidate):")
print(f"  ||M_a||_F            = {norm(Ma):.2f}")
print(f"  ||M_b||_F            = {norm(Mb):.2f}")
print(f"  ||M_a - M_b||_F / ||M_a||         = {norm(Ma-Mb)/norm(Ma):.4f}  (no alignment)")
print(f"  ||M_a - M_b_aln||_F / ||M_a||     = {norm(Ma-Mb_aln)/norm(Ma):.4f}  (hidden-aligned)")
# column-wise cosine similarity averaged
cos_raw = np.sum(Ma.reshape(N*D_OUT, D_HID) * Mb.reshape(N*D_OUT, D_HID), axis=0)
cos_aln = np.sum(Ma.reshape(N*D_OUT, D_HID) * Mb_aln.reshape(N*D_OUT, D_HID), axis=0)
na = norm(Ma.reshape(N*D_OUT, D_HID), axis=0); nbr = norm(Mb.reshape(N*D_OUT, D_HID), axis=0)
nbal = norm(Mb_aln.reshape(N*D_OUT, D_HID), axis=0)
cos_raw /= (na*nbr + 1e-12); cos_aln /= (na*nbal + 1e-12)
print(f"  per-hidden-unit mean |cos| (raw)     : {np.abs(cos_raw).mean():.4f}")
print(f"  per-hidden-unit mean |cos| (aligned) : {np.abs(cos_aln).mean():.4f}")

# -----------------------------------------------------------------
# Summary of session 2 findings
# -----------------------------------------------------------------
print("\n" + "="*60)
print("Session 2 summary:")
print("="*60)
