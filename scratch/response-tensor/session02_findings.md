# Response Tensor Research — Session 02 Findings

**Question entering session:** Session 1 found that two networks agree on mean Jacobian (cosine 0.9997) but disagree in residual subspaces. Is the disagreement due to weight-space symmetries (permutations, sign flips), or something deeper? And what is the "true" unified object that weights and activations both project from?

## Algebraic framing

For a 2-layer tanh MLP `y = W2 tanh(W1 x + b1) + b2`, define

```
M(x) = W2 · diag(σ'(W1 x + b1))        shape [d_out, d_hid]
```

Then both Jacobians factor through M:

```
dy/dx         = M(x) · W1                     (input Jacobian)
dy/dW1[i,j,k] = M(x)[i,j] · x[k]             (weight Jacobian, outer product)
dy/dW2[i,j,k] = δ_ij · h[k]                  (depends only on activations)
```

**M(x) is the algebraic common ancestor.** Both `dy/dx` and `dy/dW` are contractions of M. This made M the first-guess unified object.

## T5 — Hungarian hidden-unit alignment

Aligned B's hidden units to A's using best bipartite matching on activation correlations, with sign flips allowed (tanh odd-function symmetry).

```
mean |correlation| before alignment: 0.2125
mean |correlation| after  alignment: 0.6279

weight-space distance drops:
  ||W1_a - W1_b||     = 10.66  →  6.47  after alignment
  ||W2_a - W2_b||     =  2.45  →  1.83  after alignment

Jacobian invariance under alignment:
  ||J_b - J_b_aligned||² / ||J_b||² = 9.57e-32   (exact, as expected)
```

**Result:** J is exactly permutation-invariant (to machine precision). The disagreement in Session 1 residuals therefore cannot be explained by weight-space symmetry. This kills the "it's just a permutation" hypothesis.

## T6 — Jacobian covariance

First moment (mean J) agreed with cosine 0.9997 between nets. Second moment:

```
||Σ_a - Σ_b||_F / ||Σ_a||_F = 0.5253
top-5 eigvals Σ_a: [0.070, 0.039, 0.019, 0.013, 0.010]
top-5 eigvals Σ_b: [0.061, 0.026, 0.025, 0.015, 0.011]
Bures distance     : 0.2893      (vs scale sqrt(tr Σ_a) = 0.4797)
```

**Result:** Networks agreeing in first moment do *not* agree in second moment. So the disagreement is real, distributional, and not washed out by averaging. A moment-based invariant won't trivially hold.

## T7 — On-manifold vs off-manifold decomposition *(the headline result)*

Re-ran with data embedded on a 4-dim subspace of 12-dim ambient input. Input PCs:

```
PC eigenvalues: [14.73, 10.80, 7.88, 1.16, 0, 0, 0, 0, 0, 0, 0, 0]
→ first 4 PCs = on-manifold   |   last 8 PCs = off-manifold
```

Projected residual Jacobian onto each sub-space:

```
                      on-manifold      off-manifold
residual energy A  :  88.90            263.53
residual energy B  :  92.21            260.23
cosine(res_A, res_B):  0.9326           0.1411
subspace cos k=10  :  0.9080           0.3500
```

**Result:** Two independently-trained networks have **nearly-identical Jacobians along data directions** (cosine 0.93, subspace overlap 0.91) and **essentially unrelated Jacobians in directions orthogonal to the data** (cosine 0.14, subspace overlap 0.35).

This completely explains Session 1's mixed result:

- Mean Jacobian agreement (0.9997) was dominated by on-manifold structure.
- Residual disagreement came from off-manifold projections where training provides no constraint.

Each network invents its own off-manifold extrapolation. **R is function-invariant on the data manifold and arbitrary off it.**

## T8 — M(x) as candidate is too parameterization-bound

Even after Hungarian alignment:

```
||M_a - M_b||_F / ||M_a||         = 1.4280  (raw)
||M_a - M_b_aligned||_F / ||M_a|| = 1.1245  (aligned)
per-hidden-unit mean |cos| raw     : 0.3372
per-hidden-unit mean |cos| aligned : 0.3975
```

**Result:** M carries richer parameterization dependence than just permutation/sign. Rescaling, non-integer mode mixing, redundancy (64 hidden units vs ~20 effective rank), all contribute. M is *the algebraic ancestor* but not *the invariant object*.

## Synthesis — what the unified object actually is

Three levels refine:

1. **M(x)** — algebraic common factor of `dy/dx` and `dy/dθ`. Clean mathematically but parameterization-bound.
2. **J(x) = M(x)·W1** — already invariant under hidden-symmetry. But carries off-manifold garbage that differs across networks.
3. **J(x) restricted to data-manifold directions** (or equivalently, the pushforward measure `x → J(x)` with x drawn from data distribution, projected onto the data's tangent space) — function-invariant across networks solving the same task.

The "Maxwell object" hypothesized in the conversation is level 3. It is:
- Basis-free (it's a distribution, not a tensor with an arbitrary axis)
- Parameterization-free (different weight configs give the same object)
- Tightly concentrated (energy lives in a subspace of dim ≤ intrinsic data dim)
- **Smaller than weights by orders of magnitude** (≈ d_out × d_manifold coordinates)

## Implication for the self-modeling design question

The original question was: what should a model be fed to give it self-knowledge?

- Raw weights: parameterization-specific; much of the info is irrelevant symmetry-equivalent duplication.
- Raw activations + raw J: includes off-manifold garbage; different for two nets computing the same function.
- **J restricted to data-manifold directions**: function-invariant, much smaller, captures what the network actually *does* (as opposed to how it's wired).

This is a concrete answer to "what is the right object to feed in for introspection" — at least for this toy setting. It also matches an intuition that showed up earlier in the conversation: the model's *dispositions* (how it responds where it encounters data) are real; its *off-distribution weights* are arbitrary bookkeeping.

## Confidence levels

- T5 alignment + J permutation invariance: **very high** (algebraically exact, confirmed to machine precision)
- T6 second-moment disagreement: **high** (clean quantitative finding)
- T7 on/off-manifold split: **high for this setting**, **medium** for generalization to deep nets and real data — needs replication at scale
- T8 M-as-unified-object refuted as-stated: **high**
- Synthesis (pushforward measure as the invariant): **medium-high** — the evidence points here strongly, but a formal statement requires more care about what "data manifold" means when data doesn't lie on a clean subspace

## Session 03 — plan

Two converging threads:

1. **Confirm at depth + realism.** Run T7-style on/off manifold check on a 3-layer MLP trained on MNIST or a small Shakespeare char-level LM. Key test: does on-manifold agreement survive? If yes, the story generalizes. If no, either the manifold concept needs refining or the invariance is a toy-setting artifact.

2. **Formalize the NTK connection.** NTK theory says `df/dθ df/dθ^T` (function-space kernel) is a function-invariant quantity at infinite width. Our finding says `df/dx` restricted on-manifold is a finite-width analog. Working out the exact map between these two quantities for the 2-layer MLP should tell us whether our object is "the NTK in disguise" or something genuinely new.

If I had to bet: it'll turn out our on-manifold J is the *input-side* dual of the NTK's *parameter-side* description, and the two together capture all the information a feature-learning network has about a task. That would be a clean Maxwell moment — electric and magnetic, finally the same field.
