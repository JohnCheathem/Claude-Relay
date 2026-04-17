# Response Tensor Research — Session 08 Findings

## Pivot

Session 7 found task fingerprinting works. Session 8 asks: is the signature read-only (measurable only), or writeable (can be targeted)? If writeable, three follow-ups become possible:

- **Matching:** train net B to have a target signature; does it become functionally similar to the reference?
- **Spoofing:** can a network solve task T while carrying a signature of task T' ≠ T?
- **Arithmetic:** are signatures composable — do blended signatures produce blended capabilities?

Method: add an auxiliary loss `λ · ||sig(net) − target||²` to standard training. Signature gradient estimated via evolution-strategies (random directional finite-differences) for efficiency.

## Results

### Experiment 1 — signatures are a lossy functional compression

```
                        |sig - sig_A|    ||f - f_A|| on test data
A (reference)            —                —
B (sig-targeted)         0.30             0.0377
C (independent)          0.45             0.0458
```

B is **17.6% functionally closer** to A than the independent baseline C, while achieving similar task loss. The 10-dim signature carries information beyond just "same task" — matching it produces functional resemblance that training alone doesn't.

This is the first evidence that signatures are a **lossy functional compression**: ~30× compression (304 weights → 10 signature numbers) with a measurable but modest functional recovery.

### Experiment 2 — signature spoofing defeats fingerprinting

```
Spoof network: trained on teacher task with target signature = sig(linear)
  teacher task loss:                0.0016  (native: 0.0017)
  distance to sig(teacher):         0.70
  distance to sig(linear):          0.53
  fingerprint classification:       'linear'   ← WRONG
```

A network can be trained to solve teacher task while having a signature that *classifies as linear*. Task performance is essentially unchanged (0.0016 vs native 0.0017). Session 7's fingerprinting is **adversarially fragile**.

This is a model-level steganography result: if an adversary knows the reference signatures (which are publicly derivable from known tasks), they can hide a network's actual training purpose behind a different signature.

### Experiment 3 — signature arithmetic is mechanical, not compositional

Target: `sig_mix = 0.5 · sig(teacher) + 0.5 · sig(linear)`. Trained a net on mixed data with this target.

```
                               distance to sig_mix
mix-targeted (constrained)     0.43
control (mixed data, no sig)   0.62
```

Constrained net is 30% closer to the target mix signature than the control. So signatures are *mechanically* additive — you can push networks toward arbitrary points in signature space.

But task performance on individual sub-tasks was indistinguishable from the control (teacher: 0.0147 vs 0.0143; linear: 0.0340 vs 0.0346). Pushing to a midpoint signature does not produce a "blended capability" network in any obvious sense — the signatures are not a functional interpolation space at this measurement resolution.

## Synthesis

Session 7 showed signatures *are* a task identity. Session 8 shows:

- Signatures can be targeted during training (write operation, not just read)
- They carry real functional information (17.6% matching improvement over task-alone)
- They can be spoofed to defeat fingerprinting
- They don't support clean compositional arithmetic despite being mechanically additive

The most actionable finding is spoofing: anyone proposing macro-signature-based model fingerprinting for security purposes should assume signatures are adversarially modifiable. This is a real limitation of the session 7 application.

The most intellectually interesting finding is the lossy-compression observation: 10 numbers capture enough functional content that matching them brings networks measurably closer. This means there's a meaningful low-dimensional description of what a trained network computes — something beyond task identity but captured by simple weight/activation statistics.

## Confidence

- Signatures as lossy functional compression (exp 1): **high** — 17.6% improvement is solid at this scale, though magnitude may be architecture-dependent
- Spoofing defeats fingerprinting (exp 2): **high** — clean result, task loss genuinely preserved while signature class changes
- Signature arithmetic is not compositional (exp 3): **medium** — negative result; possible that different signature components or a richer architecture would show composition

## Novelty

- The "targeted signature as training objective" approach: I haven't seen this framing. Related to neural architecture search (finds architectures with properties) and hypernetworks (generates weights with properties) but neither explicitly treats a learned macro-signature as an engineering target.
- The spoofing adversarial finding: new to my knowledge. Fingerprinting-as-watermark is discussed; signature-spoofing as attack may not be.
- Functional compression via signatures: the measurement is novel even if the concept connects to related compression literature.

## Scripts

- `scratch/response-tensor/session08_inverse_training.py`

## What's next if this keeps going

1. **Stronger spoofing test:** use richer signatures or multi-target constraints to see how much spoofing capacity exists. Is there a fundamental limit to how misleading a signature can be while preserving task function?
2. **Multi-task composition:** if signature arithmetic doesn't yield compositional nets, what DOES? Maybe training on multi-task data with signature targets derived from mixtures of capabilities is the right framing.
3. **Scale test:** does any of this survive in real models? Most likely spoofing does, arithmetic doesn't, compression stays at roughly this modest level.
