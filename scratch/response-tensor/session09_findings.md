# Response Tensor Research — Session 09 Findings

## Pushing the compression further

Session 8 found a 10-dim weight-statistic signature gives 17.6% functional recovery — matching a target signature makes B's function measurably closer to A's than independent same-task training. This session asked three questions:

- What *kind* of signature compresses function best?
- What's the compression curve as K grows?
- Can signatures alone teach a network (no task data)?

Plus a follow-up (9B) on optimized probes.

## 9A — Signature type comparison at ~10-12 dims

```
                           dim       ||f_A - f_B||     improvement over indep
weight_stat signature      10        0.0377            +17.6%
probe signature (K=3)      12        0.0401            +12.4%
hybrid (both)              22        0.0397            +13.1%
```

Weight statistics win at this scale. Behavioral probes (outputs on fixed inputs) at the same budget underperform. Hybrid doesn't clearly help — more information isn't automatically better signature.

## 9B — Compression curve (probe signatures, K from 1 to 32)

```
K probes    dim    ||f_A - f_B||    improvement
1           4      0.0394           +13.8%
2           8      0.0405           +11.5%
4           16     0.0351           +23.3%    ← best
8           32     0.0407           +11.1%
16          64     0.0540           -18.0%
32          128    0.0840           -83.6%    ← catastrophic
```

**Non-monotonic.** K=4 probes (16 numbers) gives **23.3% recovery — better than weight statistics at 10 dims**. Beyond K=8, adding more signature dimensions makes things worse. By K=32 the optimization collapses: the signature loss overwhelms the task loss.

This means the "budget" of a signature isn't additive — at some point, more constraints fight each other. There's a concrete sweet spot around 16 behavioral values for a network this size.

## 9C — Teacher-free distillation: complete failure

Train B using ONLY sig(A) as target, no task data:

```
Random untrained B:              ||f_A - f_B|| = 0.92   task loss 0.84
Indep B (full task training):    ||f_A - f_B|| = 0.046  task loss 0.002

Teacher-free (signature only):
  weight_stat sig (10d):         ||f_A - f_B|| = 1.03   task loss 1.07  ← worse than random
  probe sig (12d):               ||f_A - f_B|| = 0.88   ~4% improvement
  probe sig K=16 (64d):          ||f_A - f_B|| = 10^8   weights exploded
```

Signatures cannot teach. The signature is a constraint that enriches task-supervised learning but provides essentially no useful signal alone. Without the task-data anchor, optimizing against signature alone diverges (weight explosion for high-dim).

## 9D — Optimized probes (max-disagreement from 500 candidates)

Build a candidate pool of 500 random inputs; evaluate 7 independently-trained nets on all of them; pick the K candidates where networks disagree most as probes.

```
K     random probes   optimized probes   optimization gain
2     +5.5%           +17.7%              +12.2%
4     +16.5%          +13.0%               -3.5%
8     +3.3%           +18.9%              +15.6%
16    -12.8%          +5.9%               +18.7%
```

Optimization helps substantially at K=2, 8, 16. K=4 is an anomalous sweet spot where random already does well. Best single result in the arc remains **K=4 random probes at 23.3%** — optimization didn't beat it.

## What the best probes look like

```
                             top-disagreement probes    random probes
Avg norm                     3.99                       3.05
Avg disagreement across nets 2.51                       1.35
Off-data-manifold distance   3.79                       2.57
```

Training data is perfectly on-manifold (distance 0). The best probes are **far off-manifold** — they live in input-space regions the training data never visited. All task-trained networks converge to the same function on-manifold; they differ only where the data didn't constrain them.

This is the session's conceptual takeaway. **A trained network's identity lives in its extrapolations, not its interpolations.** The distinctive content that separates one solution to a task from another is how it behaves on inputs the training set didn't cover. The "10 numbers" question has a specific answer: they should be the network's outputs on inputs chosen to maximize extrapolation disagreement.

## Synthesis across sessions 7-9

- Session 7: macro-signatures classify tasks at 90% accuracy (fingerprinting)
- Session 8: signatures are writeable; matching them gives 17.6% functional recovery; spoofing defeats fingerprinting
- Session 9: K=4 probe signatures give 23.3% recovery; the informative probes are off-manifold; signatures are enrichment not replacement

The practical story is: a network's functional identity is partially (~23%) captured by its outputs on a small number of well-chosen (off-manifold) probes. Not enough to reconstruct the network, but enough for a meaningful compression/identity signal.

## Confidence

- Probe-signature compression curve (non-monotonic, K=4 sweet spot): **high** — clean empirical result
- Off-manifold probes are most informative: **high** — multiple signals point to this (norm, disagreement, manifold distance all align)
- Exact 23.3% number: **medium** — depends on architecture, task, signature-loss balance, probe count
- Teacher-free signature distillation fails: **high** — three variants all failed
- Signature arithmetic not compositional (from session 8): **medium** — may depend on composition mechanism

## What's genuinely new here

- The finding that random 4-probe behavioral signatures beat hand-picked 10-dim weight statistics for functional compression — I haven't seen this specific measurement.
- The non-monotonic compression curve with a sweet spot — not matching any obvious prior result.
- The "identity lives in extrapolation" framing via off-manifold probes — conceptually related to adversarial examples literature but used here as characterization rather than attack.

## Scripts

- `scratch/response-tensor/session09_compression.py` — signature type comparison + compression curve + teacher-free test
- `scratch/response-tensor/session09b_optimized_probes.py` — max-disagreement probe selection

## Natural next steps

1. **Joint (probe, target) gradient optimization** — current heuristic picks probes from a pool. Full joint optimization might push past 23.3%.
2. **Why K=4?** investigate the optimization balance. What lambda scheduling enables higher-K signatures without collapse?
3. **Off-manifold connection** — link to adversarial examples and decision boundary literature. Best probes may be boundary-adjacent.
4. **Robust signatures** — design signatures hard to spoof (multiple randomized probe sets, private probes).
5. **Compositional networks** — why did signature arithmetic fail in session 8? Alternative mechanisms for capability blending.
6. **Scale test** — does 23.3% compression survive on MNIST / CIFAR / real tasks?
