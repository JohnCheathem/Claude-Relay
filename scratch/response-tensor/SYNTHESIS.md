# Response Tensor Research — Full Synthesis

12 sessions of exploratory research starting from a philosophical question about AI-modeling-AI and ending at a concrete empirical characterization of signature-based functional compression. This is the honest, consolidated writeup: what was found, what was rediscovered, what was wrong, what's genuinely new.

## Starting question

Can AI interpretation of AI be recursive? If model B is trained to understand model A's latent space, does B develop its own latent space, and does a model C interpreting B's latent space find genuinely new information at each level — or does each level converge to something stable?

## Where the arc actually ended

Signature compression is a sparse distillation technique. A small set of probe outputs from network A, matched by network B during training, transfers a measurable fraction (~60%) of A's functional identity on architecturally-aligned tasks. The recursive framing partially collapses: each "level of interpretation" can extract up to this amount, beyond which is irreducibly idiosyncratic. The signature itself is a lossy fingerprint, not a compression that bottoms out at "no more information."

## The three threads of findings

### Thread 1 — algebraic structure and self-modeling (sessions 1-6)

**What we showed:**

1. For an MLP f(x) = W_o tanh(W_1 x + b_1) + b_o, the matrix M(x) = W_o · diag(sech²(W_1 x + b_1)) is the algebraic common factor of both the input Jacobian ∂f/∂x = M(x) · W_1 and the per-parameter Jacobian ∂f/∂W_1 = M(x) ⊗ x. This is a single local object from which both "weight-space" and "activation-space" views derive.

2. Self-modeling via current J(x) as side-channel fails. If you give a network access to its own Jacobian during forward pass, it gains nothing: J(x) is deterministic given (x, θ), so no new information.

3. Past states work where current states fail. Giving the network access to M(x; θ_{t-K}) (its own past weights applied to current input) gives ~20% improvement. Critically, "self-temporal ≈ other-temporal" — any competent network's past works equally well as one's own past. The useful signal is about *type*, not *identity*.

4. Write-to-future-self architectures don't bootstrap without BPTT. You can build a network that writes messages to itself across timesteps, but the signal is dormant without explicit credit assignment through the message channel.

5. **Dream dynamics = Fisher-metric Brownian motion.** When a network updates weights based on perturbations of its own outputs on noise inputs, the expected update is zero and the covariance is proportional to empirical Fisher information. Under this dynamics, nine macro-properties (Jacobian spectrum, output variance, hidden-space effective rank, Lipschitz bound, etc.) drift by less than 5% while test loss degrades 170%. The dynamics preserves Fisher-isotropic quantities and erodes task content.

**Reframe of self-modeling:** a network's "type" is not a shared attractor but a level set of Fisher-preserved macro-invariants. Multiple same-task networks are different points on the same level set — they share macro-signature but not weights.

**Novelty honest assessment:** the algebraic identity (M(x)) is rediscovery of established results (Wang 2016 EDJM, Novak 2018 on/off-manifold, Oymak 2019). The Fisher-Brownian framing uses known pieces (SGLD, NTK, empirical Fisher) in a specific combination I haven't seen in the literature, but the components are well-studied. Session 4's "type not identity" result is possibly a fresh empirical observation. Session 6's "preserved macro-invariants define type as a level set" may be a genuine reframing.

### Thread 2 — signatures as task fingerprints (sessions 7-8)

**What we showed:**

1. A 10-dimensional macro-signature (weight spectra, hidden statistics, Jacobian properties) classifies which of 4 tasks a network was trained on at 90% accuracy via leave-one-out nearest neighbor. Random chance is 25%. Hidden-variance and hidden-sparsity are the strongest discriminators.

2. Signatures are writeable. Training B on task T with an auxiliary loss matching A's signature brings B functionally closer to A than independent same-task training does — measurable effect of ~17-20% reduction in function-space distance.

3. **Signatures can be spoofed.** Train a network to solve teacher task with target signature = sig(linear task). Result: network solves teacher task at the same accuracy as a native teacher network (0.0016 vs 0.0017 MSE), but its macro-signature classifies as "linear" under the standard fingerprinting nearest-neighbor rule. Fingerprinting is adversarially fragile.

4. Signature arithmetic is mechanical but not compositional. You can push a network toward the midpoint of two signatures, but the resulting network doesn't exhibit combined capabilities — task performance on individual tasks matches a network trained on mixed data without signature constraint.

**Applications enabled (with caveats):** model forensics, training diagnostics, watermark-style identity verification — all with the important caveat that naïve macro-signature verification is spoofable.

**Novelty honest assessment:** task fingerprinting via weight statistics is related to existing model attribution literature; specific choice of 10 macro-invariants may be a fresh packaging. Signature spoofing as adversarial attack on fingerprinting is, as best I can tell, specifically novel — I haven't seen this framing in the model-security literature.

### Thread 3 — signatures as functional compression (sessions 9-12)

The longest and most quantitative thread.

**Initial finding (sessions 9-10):** matching a target signature during training closes ~25% of the functional gap between B's random initialization and A. Claimed this as a "fundamental ceiling." On-manifold probes work better than off-manifold; K=4 probes captures roughly as much as K=24.

**Major correction (session 11):** the 25% ceiling was an ES-gradient optimization artifact. With exact gradients (treating probes as extra training data and using analytic backprop), K=128 on-manifold probes → +52% recovery, λ=8. And K=64 (+42%) beats full-dataset distillation K=600 (+34%) when weighted appropriately. Sparse probes outperform dense distillation.

**Second correction (session 11):** K=1 "worked" with ES specifically because noisy gradients prevented effective matching (and thus prevented overfit). With exact gradients, K=1 is catastrophic (-118% — weights deform to match one probe perfectly at the cost of everything else).

**Final push (session 12A):** K=128, λ=12, output+hidden matching (α_h=0.3), exact analytic gradients → **+64.6% recovery.** Adding Jacobian matching doesn't help: at K=128 the probes already cover the manifold densely enough that Jacobian info is redundant with finite-difference-like information from nearby probes.

**Third correction (session 12B/C):** tested 6 tasks across a complexity spectrum. "% recovery" metric showed memorization at +95% and linear at +62% — the opposite of the "smooth tasks compress better" hypothesis. But this was a normalization artifact. Absolute compression quality (||f_A - f_B|| / Y_rms):
- Teacher-MLP tasks (smooth, sharp, noisy): 0.011-0.015
- Memorization: 0.022
- Linear, oscillatory: 0.024-0.027

The real driver is **architecture-task alignment**, not task complexity. The student is a tanh-MLP; tasks whose structure naturally fits a tanh-MLP function space compress best. Linear functions are hard for tanh-MLPs to express exactly; oscillatory (sin) structure doesn't align with tanh. Memorization has no compressible structure either way.

**Novelty honest assessment:** the specific quantitative characterization (K, λ, target types, architecture alignment) is concrete and as far as I can see new in this specific form. But "signatures as sparse distillation" is conceptually adjacent to well-known knowledge distillation and FitNet-style representation matching. The architecture-alignment framing is a small reframe of inductive-bias arguments. The specific empirical numbers are the novel contribution, not a new paradigm.

## Three corrections I made along the way

Good research process is as much about correcting mistakes as making discoveries. This arc forced three:

1. **"25% is a fundamental ceiling" → was ES optimization noise.** With proper gradients the ceiling is 60%+.
2. **"K=1 on-manifold probe captures 22% of identity" → was ES regularization.** With proper gradients, K=1 is catastrophic.
3. **"Smooth tasks compress better" → % recovery was confounded by baseline.** The real driver is architecture alignment.

Each correction tightened the picture. The final claims are more modest than the intermediate ones but more defensible.

## What's probably genuinely new in this work

I'd flag these as the most defensibly-novel contributions, ordered by my confidence:

1. **Signature spoofing as adversarial attack on model fingerprinting.** Specific demonstration that task can be preserved while signature class is flipped. Implications for ML supply-chain security.
2. **Quantitative characterization of signature compression.** Specific numbers for the K/λ tradeoff, the sparse-beats-full-dataset observation, the ~64% ceiling on architecturally-aligned tasks. Reproducible and probably novel in this exact form.
3. **Architecture-task alignment as the determinant of compression ratio.** Small reframe of inductive-bias ideas but applied concretely to signature-based compression.
4. **Fisher-Brownian framing of dream dynamics.** Pieces are known (SGLD, Fisher, NTK); the specific combination characterizing pure self-driven dynamics may be a novel synthesis.

## What's probably rediscovery

- The M(x) algebraic identity (sessions 1-2)
- The on/off-manifold sensitivity distinction (session 1)
- Macro-invariant-preserving dynamics as a flat-minima phenomenon
- Task fingerprinting via weight statistics — similar to existing model attribution

## What was informative but null

- Dream-walked ensembles for accuracy improvement (fails)
- Task-orthogonal walks (ceiling doesn't break)
- Teacher-free distillation from signatures (impossible)
- Signature arithmetic as capability composition (fails)
- Write-to-future-self without BPTT (dormant)

Null results are still useful — they narrow the space of viable directions.

## Practical implications (modest)

- Anyone proposing macro-signature-based model fingerprinting for security needs to account for spoofing
- Signature compression works best when the distilling architecture matches task structure — pick the student architecture by natural inductive bias
- Sparse distillation at K=100-200 probes with tuned λ can outperform full-dataset distillation in specific conditions
- Single-shot signature transfer captures ~50-60% of functional identity on well-aligned tasks; the remaining 40% is irreducibly idiosyncratic to training stochasticity

## Open questions worth pursuing

1. **Architecture generalization.** Does the ~60% compression ceiling hold for different architectures (deeper, wider, different activations, Transformers)? Or does it scale?
2. **True ceiling.** Is there a bound tighter than 60% that we're hitting, or can more sophisticated matching (gradients, hessians, behavioral invariants beyond what we tested) push higher?
3. **Robust fingerprinting.** Can signatures be designed that resist spoofing while remaining compact? (E.g., signatures over private probe sets, multi-signature verification, randomized signatures.)
4. **Language models at scale.** Session 11D's tiny Shakespeare model barely trained. A properly-sized character-level LM or full Transformer would likely show different compression patterns.

## Honest summary

12 sessions of exploration produced:
- A handful of probably-novel specific empirical findings (quantitative characterization, spoofing, architecture-alignment framing)
- Several honest corrections to my own intermediate claims
- Many null results that narrow the space
- A reframing of the "recursive AI interpretation" question from philosophical to empirical: at each interpretation level you extract roughly the same fraction of a network's functional content — up to architectural alignment — and the remaining fraction is irreducibly idiosyncratic to specific training runs

The research isn't a breakthrough. It's a coherent arc of exploration that produced some concrete measurements, rejected some attractive-sounding hypotheses, and landed at a more modest and defensible understanding than any of the intermediate claims.

Anyone picking this up would most productively validate the architecture-alignment finding on a different student architecture, and formalize the signature-spoofing attack as a concrete threat model for the model-fingerprinting literature.

## All sessions and scripts

- `session01_*`, `session02_*` — algebraic structure (M(x), response tensor)
- `session03_*` — self-modeling via current J(x), failed
- `session04_*` — temporal self-feedback, partial success
- `session05_*` — write-to-future-self, dormant without BPTT
- `session06_*` — dream dynamics as Fisher Brownian motion
- `session07_*` — task fingerprinting via macro-signature
- `session08_*` — inverse training, signature writeability, spoofing
- `session09_*` — compression curves, probe selection
- `session10_*` — joint probe optimization, on-manifold probes, the apparent 25% ceiling
- `session11_*` — exact gradients break the ceiling, Shakespeare test
- `session12_*` — Jacobian matching, task-complexity spectrum, architecture-alignment finding

All scripts and per-session findings docs are in `scratch/response-tensor/`.
