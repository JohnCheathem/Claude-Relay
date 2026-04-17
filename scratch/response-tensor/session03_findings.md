# Response Tensor Research — Session 03 Findings

## Pivot

After a literature survey showed sessions 1-2 rediscovered established work (Wang 2016 EDJM, Novak 2018 on-manifold Jacobian, Oymak 2019 information/nuisance split, Srinivas 2018 Jacobian matching, empirical NTK literature), we pivoted. The one angle not clearly covered was *building* self-knowledge into a network rather than computing it externally. This session tests whether giving a network access to its own on-manifold Jacobian as an input signal produces qualitatively different behavior.

## Experimental setup

Three-way comparison became a six-way comparison with proper controls. All "augmented" conditions share the same architecture:

```
x → [W1, b1] → h_x = tanh(...)
s → [Ws, bs] → h_s = tanh(...)                [stop-gradient on s]
y = W_out · [h_x ; h_s] + b_out
```

Six conditions, 6 seeds each, 2-layer MLP on teacher-regression task with data on a 3-dim subspace of 10-dim input:

- **baseline**: no side channel
- **self_access**: side channel s = flatten(J(x))
- **shuffled_J**: side channel s = J(x) from *other* samples in batch (same distribution, wrong content)
- **pure_noise**: s = fresh random noise each batch (zero information)
- **static_noise**: s = one fixed random vector (zero information, constant)
- **x_proj**: s = random linear projection of x (genuine extra features from x)

## Results

```
                    off-mfd     off-mfd    side-channel
                    mean        std        usage
baseline  (no side) 1.232       0.440      —
self_access  (J(x)) 0.928       0.128      0.030
shuffled_J          0.931       0.133      0.017
pure_noise          0.929       0.132      0.001
static_noise        0.930       0.132      0.030
x_proj (info of x)  1.177       0.178      0.520
```

## Three findings, in priority order

### 1. The content of the self-signal does not matter

Self_access, shuffled_J, pure_noise, and static_noise are statistically indistinguishable on every metric (train, test, off-manifold, stability). The network treats a meaningful self-signal and pure random noise identically. **J(x) as a self-modeling input provides no benefit over random noise of the same shape.**

### 2. Any side pathway stabilizes off-manifold behavior

All augmented conditions show dramatically tighter off-manifold variance across seeds (std 0.13 vs baseline 0.44) and lower mean off-manifold loss. This is an architectural effect (extra tanh nonlinearity + extra pathway acting as regularization), not a self-knowledge effect. The network uses the side path as a regularizer rather than a signal carrier when the signal has no new information.

### 3. The network barely uses the self-signal

Zeroing the self_access signal at test time changes predictions by RMS 0.03 — near zero. Compare to x_proj, where zeroing changes predictions by RMS 0.52 (20x higher) because that signal genuinely carries information about x.

## Why the network ignores J(x) — the underlying reason

J(x) is a deterministic function of x and θ. The network already has:
- x (in its main input pathway)
- θ (as its own weights)

Therefore J(x) contains **zero information the network doesn't already have internal access to**. It is formally redundant. The gradient descent dynamics correctly learn to ignore it.

This is not a failure of self-modeling in general — it's a failure of *this particular choice* of self-signal. The framing that drove sessions 1-2 (on-manifold Jacobian as the unified object) pointed at something that is real as a function-space invariant but *trivially redundant as an input feature*.

## The sharpened research question

For self-knowledge to be useful, the signal must carry information the network cannot already compute from its current inputs. Candidates:

1. **Temporal self-knowledge** — past activations/weights from earlier training steps. Genuinely not in the current forward pass. Closest to "watch yourself evolve."
2. **Perturbation responses** — outputs at θ + ε for random ε. Requires evaluating at configurations the network is not actually in. Fisher information sits here.
3. **External analysis** — another network's output about this network. Not internally computable by construction. Connects to the recursion question from the initial conversation.
4. **Held-out behavioral signals** — network's own performance on data not in the current forward pass.

Each of these carries real information beyond what x + θ alone provide. Each is a different notion of "self."

## Confidence

- Negative result (J(x) doesn't help): **high** — clean separation between conditions, consistent across 6 seeds, causal mechanism (redundancy) is understood
- Side-pathway-as-regularizer story: **high** — all four null-content conditions converge on the same off-manifold behavior
- The specific claim that useful self-knowledge needs non-internal information: **medium-high** — follows from the finding, but hasn't been tested directly

## Methodological note

Session 3's first run had a broken control: I used a random linear projection of x as the "random" control, which is actually informative about x. This produced misleading results (random-ctrl "beat" self-access on test loss). Catching this required running the experiment twice. A good reminder that "null" controls need to be genuinely null; "random" is not automatically "informative-less."

## What changes for session 4

The research program has a new shape. The "unified object" framing was useful but led to a redundant signal. The real question is now much closer to your original one ("as its latent space evolves it can see that and learn more"): **give the network access to information about itself that it cannot already compute from its current state.** The simplest version: past states. The most mathematically interesting: perturbation responses / Fisher structure.
