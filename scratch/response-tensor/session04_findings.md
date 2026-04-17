# Response Tensor Research — Session 04 Findings

## Setup

Combined three elements per user request: (1) temporal trajectory of the self, (2) the unified object M(x), (3) active feedback via gating. Architecture:

```
h_x   = tanh(W1 x + b1)                           main hidden
past  = flatten(M(x; θ_{t-K}))                    past-self feature (non-redundant)
g     = 1 + tanh(W_g · past + b_g)                gate (identity at init)
h_mod = h_x · g                                   multiplicative modulation
y     = W_out · h_mod + b_out
```

The crucial design point: `past` uses θ from K=200 steps ago, not current θ. That information is NOT reconstructible from current state (many trajectories can reach the same θ), unlike session 3's J(x; θ_t) which was fully determined by current x and θ.

Five conditions × 5 seeds on teacher-regression with data on 3-dim subspace of 8-dim input.

## Results

```
                      train     test   off_mfd   gate_dev
no_feedback         0.0024   0.0027     1.368     0.000
self_temporal       0.0020   0.0022     1.350     0.069
other_temporal      0.0021   0.0023     1.355     0.068
shuffled_temporal   0.0023   0.0026     1.356     0.069
random_history      0.0024   0.0026     1.355     0.063
```

## Three findings

### 1. Self-temporal feedback helps — modestly

Test loss drops from 0.0027 (no_feedback) to 0.0022 (self_temporal), ~20% improvement. With ±0.0008 standard deviation, that's about one sigma. Directional effect is consistent across all 5 seeds but needs more seeds to reach statistical significance.

### 2. Other_temporal matches self_temporal. "Self" is about type, not identity.

This is the surprising part. When the past-self feature comes from a *different seed's* past snapshots (net B's θ_{t-200} used while training net A), performance matches self_temporal. Mean test losses are 0.0022 (self) vs 0.0023 (other) — indistinguishable.

Implication: the useful information in "past-self" isn't this specific network's trajectory. It's a coherent answer to "what does a network solving this task look like at input x at this point in training?" Any plausible past solver provides the same signal. The "self" in self-modeling here is equivalence-class, not instance.

### 3. Structural coherence matters; literal content doesn't

Shuffled_temporal (real past-M but applied to wrong x-sample) and random_history both fail to improve over no_feedback (0.0026 and 0.0026 vs 0.0027). The gate still modulates (gate_dev ~0.07) but gets no traction.

So the signal needs to be a real M(x; θ_past) coherently paired with x. Once that coherence is there, it doesn't much matter whose θ_past it was.

## Why this is different from session 3

| | Session 3 | Session 4 |
|---|---|---|
| Signal | J(x; θ_t) | M(x; θ_{t-K}) |
| Redundant given x, θ_t? | Yes (deterministic) | No (need θ_{t-K}) |
| Architecture | Passive side channel | Active multiplicative gate |
| Network uses signal? | Barely (0.03 side-use) | Yes (0.07 gate_dev) |
| Does content matter? | No | Yes (structural coherence) |
| Off-manifold stability? | Yes (any side channel) | No |

The session 3 negative result was because the signal was formally redundant. Session 4 uses a signal that isn't redundant AND an architecture where the signal can actually affect the main computation. Both moves were necessary.

## The philosophical observation

The user's original question (turn 1, this conversation): "when you train an AI to understand latent space thinking and vector space etc of another model, do they then have their own latent space that differs from what they learned, that another AI could learn to understand? and repeat etc?"

Session 4's finding suggests a specific answer: if "self-knowledge" is about the local response structure M(x) of a competent solver, then recursive AI-interprets-AI would share its *type*, not its *instances*. B learning about A's latent space would acquire something equivalent to A's past-self information, which A could use interchangeably with its own. C learning about B would be in the same equivalence class, etc. The recursion doesn't generate new information at each level — it finds the same functional type at each level. This would predict that interpretation chains collapse to a fixed point, not diverge into genuinely novel objects.

This is speculative but testable. The test is: does arbitrary-depth recursive interpretation produce distinct information at each level, or does it converge? Session 4 data alone doesn't answer this but points at the question sharply.

## Confidence

- Self_temporal ≈ other_temporal > shuffled/random: **medium** — direction is clear, magnitude is 1 sigma
- Active gating architecture matters (session 3 vs session 4 contrast): **high** — both the architecture change and the temporal signal are necessary
- Philosophical claim about "self as type not identity": **low-medium** — warranted by this data but toy-scale; could be artifact of small networks solving simple shared task

## What session 5 could test

1. **Cross-task past-self.** Take net trained on task P, use its past snapshots as temporal signal for net on task Q. If this still matches self_temporal → equivalence class is very broad. If it fails → equivalence class is task-bounded.
2. **More seeds + real task.** 20 seeds on MNIST or char-LM. Confirm or reject the effect at scale.
3. **Recursion direct test.** Train net A, use A's trajectory as signal for B, use B's trajectory as signal for C. Ask: does C's learned behavior differ from A's, or do they converge?

Option 3 is the direct form of the original question from turn 1 of this conversation.
