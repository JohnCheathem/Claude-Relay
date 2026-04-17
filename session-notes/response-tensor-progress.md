# Response Tensor Research — Session Progress

**Branch:** `research/response-tensor`
**Started:** April 2026
**Status:** Session 02 complete (2 of up to 10)

## Research Question

Weights and activations are conventionally treated as distinct. Backprop shows they are dual — weight-gradients factor as (incoming activation) ⊗ (backprop error). Is there a single underlying object — call it the *response tensor* R — of which weights and activations are two projections? If so:
- What is R?
- Is it a faithful invariant of the function the network computes?
- What structure (low rank? group symmetry?) does it have?
- Would a model with access to a compressed R have qualitatively richer self-access than one fed raw weights+activations?

## Framing

The candidate R proposed: the collection of input-output Jacobians `{J(x) = dy/dx : x ∈ data}`. This lives between weights (which parameterize J for all x) and activations (which parameterize a single forward trace). Moments/spectra of R, and its symmetry-quotient, are the targets.

## Sessions

### Session 01 — foundational probes on tiny MLP
- Setup: two students trained on same nonlinear teacher, `d_in=12, d_hid=64, d_out=6, N=800`.
- Verified activations-as-gradients duality numerically.
- Spectrum of R is sharply low-rank: top-1 captures 90% energy; effective rank ~19/72.
- **Key finding:** R splits into (mean Jacobian, 89.7% energy, function-invariant with cosine 0.9997 across nets) + (residual, 10.3% energy, network-specific).
- Interpretation: the mean Jacobian is a genuine function-invariant — a weak "Maxwell" candidate but too coarse (it discards nonlinearity). The residual is where parameterization still bleeds through, even between networks solving the same task.
- Full writeup: `scratch/response-tensor/session01_findings.md`
- Scripts: `scratch/response-tensor/session01_response_tensor.py`, `session01_meanVSresidual.py`

### Session 02 — the unified object is on-manifold J
- Worked out algebra: both `dy/dx` and `dy/dθ` contract through `M(x) = W2·diag(σ'(W1 x))`. M was the first-guess unified object.
- T5: Hungarian hidden-unit alignment drops weight-space distance but leaves J unchanged to 10^-32 (J is exactly permutation-invariant by algebra). So Session 1 residual disagreement is NOT a symmetry artifact.
- T6: Networks agreeing in first Jacobian moment (cos 0.9997) disagree in second moment (Bures distance 0.29 vs scale 0.48).
- **T7 headline:** on a task where data lives on a 4-dim subspace of 12-dim input, residual J has cosine agreement **0.93 on-manifold** and **0.14 off-manifold**. Networks agree on Jacobians in directions the data actually explores, disagree in directions orthogonal to data.
- T8: M(x) as a unified object is refuted — even after alignment, M_a vs M_b per-unit cosine only 0.40. M is the algebraic ancestor but is not basis-free.
- **Refined unified-object candidate:** the pushforward measure `x → J(x)` over the data distribution, restricted to on-manifold directions. This is function-invariant, parameterization-free, and much smaller than weights.
- Implication for self-modeling: the right object to feed a model as self-knowledge is on-manifold J, not weights or full J.
- Full writeup: `scratch/response-tensor/session02_findings.md`
- Scripts: `scratch/response-tensor/session02_unified_M.py`

### Session 03 — planned
1. **Scale check.** Reproduce T7 on 3-layer MLP + MNIST (or char-LM on Shakespeare). Does on-manifold agreement survive at depth and with real data? Defines a "data manifold" operationally via local PCA or input statistics.
2. **NTK connection.** NTK kernel `K(x,x') = (df/dθ)(x)(df/dθ)(x')^T` is a known function-invariant at infinite width. Our on-manifold J is the input-side analog. Work out the exact map between the two. Likely finding: they are dual descriptions of the same function-space structure, the long-sought third object.

### Sessions 03+ — tentative
- Scale up (larger model, real task) to see if the mean-vs-residual energy partition survives.
- Formalize the path-integral / action-functional framing raised in the earlier conversation.
- Probe the Kronecker structure of per-layer Fisher info (K-FAC style) and relate to R.
- Prototype a "response-native" architecture that parameterizes J directly and see if it trains.
- Write-up a theoretical note on "R as a function invariant modulo weight-space symmetry."

## Files

- `session-notes/response-tensor-progress.md` — this file (tracker)
- `scratch/response-tensor/session01_response_tensor.py` — baseline experiments
- `scratch/response-tensor/session01_meanVSresidual.py` — mean/residual decomposition
- `scratch/response-tensor/session01_findings.md` — session 01 writeup
- `scratch/response-tensor/session02_unified_M.py` — M(x), Hungarian, on/off-manifold
- `scratch/response-tensor/session02_findings.md` — session 02 writeup

## Open questions carried forward

- Does the on-manifold J invariance survive at depth and on real data? (Session 3 primary)
- What is the formal relationship between on-manifold J and the NTK? Are they dual? (Session 3)
- For data that doesn't lie on a clean low-dim subspace (real images, text), how do we operationalize "on-manifold"? Local PCA? Data-tangent space?
- Given the unified object is the on-manifold Jacobian pushforward, what's the right *architecture* for a network that parameterizes it directly?
- Connection to mechanistic interpretability: features learned by SAEs are roughly "directions the network is sensitive to on data" — is this the same thing we're calling on-manifold J, just computed one layer at a time?
