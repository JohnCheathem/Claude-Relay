# Response Tensor Research — Session 07 Findings

## Question

Can we turn the session 6 manifold finding into something useful? Three application categories tested:

1. Ensembling / diversity (7A, 7B)
2. Uncertainty / OOD detection (7C)
3. Model identification / fingerprinting (7D)

## 7A — Dream-walked ensembles: FAIL

Hypothesis: multiple dream-walked copies of one trained network averaged together should outperform the anchor, giving ensemble benefit from single-model training cost.

```
method                          test loss    indiv test    err corr
anchor alone                     0.00073        —             —
dream-walked ensemble            0.00079      0.00118       0.628
noise-perturbed ensemble         0.00074      0.00077       0.963
independent ensemble (5 trains)  0.00038      0.00076       0.381
```

Dream copies have meaningful error diversity (0.63 correlation, 33% ensemble benefit vs 3% for weight noise) but are individually degraded. Ensemble approximately matches anchor, doesn't exceed it.

## 7B — Task-orthogonal walks + fine-tune: FAIL

Tried:
- Projecting dream steps orthogonal to task gradient (should preserve task loss by construction)
- Dream-walk followed by brief fine-tune to restore accuracy

Results:
- Orthogonal projection is only instantaneous; cumulative walks drift into task-relevant directions
- Fine-tune restores accuracy but collapses all copies to same function (error correlation 0.998)

**Trade-off:** cannot have diversity AND accuracy from local weight perturbation of a single trained network. The Fisher-preserved manifold and the good-solution manifold intersect at the trained point but diverge elsewhere — walking one moves you off the other.

## 7C — Dream ensembles for uncertainty + OOD: WEAK

```
                        pearson(var, error)    OOD separation
test (in-dist)           +0.29                  —
mild off-manifold        -0.14                  —
strong off-manifold      -0.06                  70% (baseline pred-norm: 79%)
```

Dream-ensemble variance correlates only weakly with anchor error, and worse than a simpler baseline (prediction norm) for OOD detection.

However: on-manifold functional spread of dream ensembles is **1.3× larger** than independent ensembles (they explore local Fisher-soft directions independent training doesn't visit), while off-manifold spread is **25× smaller**. Dream and independent ensembles capture *different* kinds of variation — dream is local parameter-sensitivity, independent is basin-diversity. Neither replaces the other.

## 7D — Task fingerprinting via macro-invariants: WORKS

This is the session's real positive result.

Setup: 4 tasks × 5 seeds = 20 networks. Compute 10-dim macro-signature per network (weight spectra, Jacobian spectra, hidden statistics, Lipschitz). Leave-one-out nearest-neighbor classification in signature space.

```
Accuracy: 18/20 = 90.0%    (random chance: 25%)

Confusion matrix (rows=true, cols=predicted):
                teacher   linear   high_freq   sparse
    teacher       5         0         0          0
     linear       0         5         0          0
  high_freq       0         0         4          1
     sparse       1         0         0          4
```

Misclassifications cluster between the two most similar tasks (sparse and teacher — both tanh-based regressions).

Per-dimension F-statistic:
```
H_var          F = 99.10      (hidden variance — strongest)
H_sparsity     F = 93.79
J_eff_rank     F = 38.25
Wo_top         F = 11.76
Lipschitz      F =  1.00      (not discriminative)
```

Hidden-layer properties dominate the signature. Makes mechanistic sense: hidden representations are where task-specific internal content lives.

PCA visualization: PC1+PC2 explain 72% variance; inter-cluster distance 2.99, intra-cluster spread 1.07, separability ratio 2.79.

## Why fingerprinting works when ensembling doesn't

The manifold is a **description**, not a **lever**.

As a description: task fingerprinting works because different tasks produce different characteristic signatures, and that characterization is stable across seeds. The manifold's existence is the useful fact.

As a lever: dream dynamics has zero drift (it's a random walk), so it can't move networks anywhere in particular. You can walk within the level set, but you can't purposefully walk toward better performance without external signal — and with external signal (task gradient) you're back to standard training.

## Applications of the fingerprinting result

1. **Model forensics** — identify what task an unknown model was trained on from weights alone
2. **Model verification** — detect mismatch between a deployed model's claimed purpose and its actual signature
3. **Training diagnostics** — track macro-invariants during training; convergence toward task-typical values is a progress signal beyond loss
4. **Transfer learning prediction** — signature-similar tasks may transfer better between each other
5. **Supply chain integrity** — substantial retraining alters signatures while benign modifications preserve them, giving a persistent identity signal
6. **Watermarking** — the macro-signature is intrinsic to a trained network in a way that's hard to preserve while substantively modifying the function

## Confidence

- Fingerprinting at 90% accuracy: **high** at this scale — clean result, understood mechanism, reasonable baselines
- Generalization to larger networks / harder tasks: **unknown** — would need testing
- Dream ensembles fail to beat independent training: **high** — multiple attempts with proper controls (7A, 7B, 7C) all confirm
- Fisher-manifold and good-solution-manifold are different: **high** — confirmed empirically and theoretically

## Scripts

- `scratch/response-tensor/session07_dream_ensemble.py` — dream ensembling (7A)
- `scratch/response-tensor/session07b_orthogonal.py` — task-orthogonal walks + fine-tune (7B)
- `scratch/response-tensor/session07c_uncertainty.py` — uncertainty and OOD detection (7C)
- `scratch/response-tensor/session07d_fingerprint.py` — task fingerprinting (7D)

## What the full 1-7 arc has produced

Starting from your opening question about AI modeling other AI recursively:

1. **Sessions 1-2:** Unified object M(x) is the algebraic common ancestor of weights and activations. Response tensor (stack of per-input Jacobians) is function-invariant on the data manifold, arbitrary off it.
2. **Session 3:** Self-knowledge via current J(x) fails because J(x) is deterministic given (x, θ) — no new information.
3. **Session 4:** Self-knowledge via past M(x; θ_{t-K}) works modestly. Surprise: self-temporal ≈ other-temporal. "Self" is about type, not identity.
4. **Session 5:** Writing to future self requires BPTT-style credit assignment to bootstrap; without it, the mechanism stays dormant.
5. **Session 6:** Dream dynamics is Fisher-metric Brownian motion. Type is a *level set* of preserved macro-invariants, not a shared attractor. Networks in same type occupy different points on shared level set.
6. **Session 7:** Macro-invariants are a task fingerprint. You can identify what task a network was trained on from its weights alone, at 90% accuracy.

Coherent arc, concrete endpoint, genuine if modest novelty in the synthesis and the fingerprinting application.
