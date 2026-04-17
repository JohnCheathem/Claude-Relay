# Response Tensor Research — Session 12 Findings

## Two-part session

1. **12A** — push the ceiling further using Jacobian matching and tuned hyperparameters
2. **12B/C** — characterize signature-compression across a spectrum of tasks, discovering the "% recovery" metric was misleading

## 12A — Ceiling push to +64.6%

Added analytic Jacobian-matching gradient (verified against finite differences, error 4.2e-12). Swept α_h (hidden weight), α_j (Jacobian weight), K, λ.

**Result: K=128, λ=12, α_h=0.3, α_j=0 → +64.6% recovery.**

```
Session 9-10 (ES gradient):                 +25%  ← supposed ceiling
Session 11 (exact, output only, K=128):     +52%
Session 12A (exact, output+hidden, tuned):  +64.6%
```

More than doubled the "fundamental" ceiling from sessions 9-10.

**Jacobian matching doesn't help.** Any α_j > 0 slightly or substantially hurts. Probable reason: at K=128 the probes cover the data manifold densely enough that Jacobian info at each probe is redundant with having nearby probes for finite-difference-like Jacobian information. And Jacobian has 10× more dims per probe than output, creating competing objective pressure.

Scaling K with best α_h: K=128 stays optimal, K=200 slightly worse, K=300+ drops. The sweet spot for this architecture appears to be K≈128 regardless of other target types.

## 12B/C — Task complexity spectrum, and why my hypothesis was wrong

Tested 6 tasks with the best recipe (K=128, λ=12, α_h=0.3, output+hidden):

```
Task              % recovery    ||f_A - f_B||    ||f_A - f_B|| / Y_rms
memorization      +95.0%        0.0227           0.0223
oscillatory       +85.0%        0.0186           0.0266
noisy_teacher     +74.2%        0.0111           0.0125
teacher_sharp     +71.5%        0.0127           0.0113
teacher_smooth    +65.4%        0.0127           0.0150
linear            +62.0%        0.0175           0.0239
```

**The % recovery column is misleading.** It normalizes against baseline ||f_A - f_C||, which varies by 10× across tasks (memorization baseline is huge because independent nets can't learn random labels → very different; linear baseline is small because independent nets converge to nearly the same linear map → already similar).

**The absolute normalized distance ||f_A - f_B|| / Y_rms tells the real story:**

- Teacher-type tasks (sharp, noisy, smooth) compress *best* (0.011-0.015)
- Memorization sits in the middle (0.022)
- Linear and oscillatory compress *worst* (0.024-0.027)

## The actual finding: architecture-task alignment determines compression

My original hypothesis: smooth tasks compress better, high-entropy tasks compress worse. **Wrong.**

The actual pattern: **the student architecture is a tanh-MLP, and tasks that naturally fit a tanh-MLP function space compress best.**

- Teacher-MLP tasks: student's inductive bias matches task structure → signature transfers cleanly
- Linear tasks: tanh-MLP can approximate linear functions but it's not the natural form; signature captures tanh-MLP-style structure that doesn't efficiently encode linear maps
- Oscillatory (sin) tasks: periodic structure doesn't align with tanh activation function
- Memorization: no compressible structure either way

This is not about task complexity or smoothness. It's about **architectural alignment**: the signature compresses what matters for the specific function class both networks inhabit.

## Implications

- Signature compression isn't a universal property of trained networks. It's an interaction between architecture, task structure, and the inductive bias they share.
- A Transformer signature could compress Transformer-learnable tasks well but MLP-learnable tasks poorly, and vice versa.
- The ~50-60% recovery rates from sessions 11-12 are specific to "architecture optimally matched to task" conditions.
- On genuinely misaligned tasks, signature compression is much weaker in absolute terms.

This connects to well-established themes (inductive bias, no-free-lunch) but applies them concretely to the signature-as-lossy-compression question: compression is only as good as the shared inductive bias.

## What was wrong in my earlier claims

1. **The "25% ceiling" (sessions 9-10)** was ES-gradient noise. Exact gradients go well past it.
2. **The "K=1 captures identity" claim (session 10)** was ES regularization masking inability to match. Exact gradient at K=1 is catastrophic.
3. **The "task complexity determines compression" hypothesis (start of 12B)** was confused by a normalization artifact. The actual determinant is architecture-task alignment.

Each correction tightened the picture.

## Confidence

- K=128, λ=12, α_h=0.3, α_j=0 gives +64.6% on teacher: **high** (multiple seeds, reproducible)
- Jacobian matching redundant at dense K: **medium-high** (tested multiple α_j, consistently unhelpful; possible different configuration could change this)
- "% recovery" is misleading across tasks: **high** (clean decomposition into baseline + absolute distance)
- Teacher-MLP tasks compress best because of architecture alignment: **medium-high** (consistent pattern across 6 tasks, but single architecture family tested)
- Compression depends on architecture-task alignment, not complexity: **medium-high** (clean pattern but would want to test with different architectures to confirm the architecture-dependence)

## What's novel in this session

- The ~64% recovery achieved with correct hyperparameters (substantially better than sessions 9-11)
- The identification that the student architecture's inductive bias determines what signatures can compress (not "task complexity")
- The analytic Jacobian-matching gradient for MLPs (verified to match FD)
- The demonstration that "% recovery" is a misleading metric when comparing across tasks
- Honest correction of three prior claims

## Scripts

- `scratch/response-tensor/session12a_push_ceiling.py` — Jacobian gradient + hyperparameter sweep
- `scratch/response-tensor/session12b_task_spectrum.py` — 6-task comparison
- `scratch/response-tensor/session12c_diagnose.py` — absolute measures and the "% recovery" diagnosis

## Where this could go

1. **Test with different architecture** — train students with different activation functions (ReLU, SiLU, tanh) and see if compression ratio for each task varies with student architecture match
2. **Build a "complexity index"** that captures architecture-task alignment explicitly
3. **Shakespeare with bigger student** — session 11D's tiny Shakespeare MLP barely trained; a properly-sized student might show Transformer-like compression patterns
4. **Stop and synthesize** — 12 sessions, the arc is becoming clear; a proper synthesis might be more valuable than session 13

## Final synthesis of sessions 1-12

Starting question: does AI-modeling-AI generate genuinely new information, recursively?

The arc resolved in a specific way:
- Sessions 1-2: unified object M(x) is the shared structure under weights and activations (known)
- Sessions 3-5: self-modeling requires information beyond the current state; past states work; type not identity
- Session 6: dream dynamics is Fisher Brownian motion; "type" is a level set, not a point
- Session 7: macro-signatures task-fingerprint at 90%
- Session 8: signatures are writeable; lossy functional compression (17.6%); spoofable
- Session 9-10: ES gradient optimization apparent ceiling at 25% (seed variance + ES noise)
- Session 11-12: with exact gradients, combined targets, tuned λ → +64.6% on teacher-MLP tasks, but
  task-dependent — compression works best when student architecture matches task structure

The "recursive AI interpretation" question: each interpretation level can extract up to ~60% of a compatible-architecture network's functional identity with 128 well-placed probes. Beyond that is irreducibly idiosyncratic to specific training runs. For architecture-mismatched tasks, even this capacity drops substantially.
