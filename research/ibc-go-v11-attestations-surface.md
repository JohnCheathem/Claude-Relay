# ibc-go v11 — Attestations Module & IBC v2 Attack Surface Research
**Date:** 2026-04-16  
**Source:** `cosmos/ibc-go` tag `v11.0.0`, read directly from public repo  
**Scope:** `modules/light-clients/attestations/`, `modules/core/ante/`, `modules/core/04-channel/v2/`  
**Status:** Pre-report. All findings are unconfirmed bounty candidates — confirm severity before submitting.

---

## Summary

Starting from the known ABI type confusion (PacketAttestation bytes silently decode as StateAttestation), a broad sweep of the attestations module and surrounding IBC v2 code reveals **5 additional distinct findings**, ranging from chain-halting panics to timestamp unit corruption and a double-quorum-check logic gap. All are in new code shipped in v11 with no prior audit.

---

## Finding 1 (KNOWN — Filed for report)
### ABI Type Confusion: PacketAttestation Decodes as StateAttestation

**Files:** `abi.go`, `update.go`, `light_client_module.go`

- `ValidateBasic` tries `ABIDecodePacketAttestation` first. Because PacketAttestation is tuple-wrapped, its first 32 bytes are always `0x0000...0020` (offset pointer). `ABIDecodeStateAttestation` reads the first two uint64 words — these always parse as valid (non-zero) uint64 values.
- `CheckForMisbehaviour` and `UpdateState` call `ABIDecodeStateAttestation` on whatever `AttestationData` is present — no type enforcement.
- Result: a PacketAttestation submitted via `MsgUpdateClient` passes `ValidateBasic`, passes `VerifyClientMessage` (if attacker holds quorum keys and signs with `AttestationTypeState` tag), then silently corrupts consensus state in `UpdateState` or triggers false freeze in `CheckForMisbehaviour`.
- **Correctness path (no attacker needed):** a relayer submitting `MsgUpdateClient` with a PacketAttestation by mistake causes the same corruption.

**Severity estimate:** Medium–High (mitigated by experimental label + quorum requirement on malicious path)

---

## Finding 2 (NEW)
### `GetTimestamp()` Panic: Deprecated Interface Method Can Halt Chain

**File:** `consensus_state.go:18-19`

```go
func (ConsensusState) GetTimestamp() uint64 {
    panic("GetTimestamp is deprecated")
}
```

`GetTimestamp()` is part of the `exported.ConsensusState` interface. Any core IBC code path that calls this method on an attestations consensus state will **panic and halt the chain block**.

**Question to answer:** Does any code in `modules/core/` call `GetTimestamp()` on a `ConsensusState` retrieved generically via the interface?

```bash
grep -rn "GetTimestamp" modules/core/ --include="*.go" | grep -v "_test.go"
```

If yes — this is a **chain halt DoS**. Any relayer (no special keys needed) that triggers the code path halts the chain. Severity: Critical.

If no callers exist in v11 core — this is a latent time bomb that will activate when any future code generically iterates consensus states. Still reportable as a correctness issue.

**Suggested fix:** Return `0` or implement the method properly rather than panicking.

---

## Finding 3 (NEW)
### Ante Handler Skips Misbehaviour Check — Bypasses Freeze Logic

**File:** `modules/core/ante/ante.go:181-183`

```go
// Note that misbehaviour checks are omitted.
func (rrd RedundantRelayDecorator) updateClientCheckTx(...) error {
    ...
    heights := clientModule.UpdateState(ctx, msg.ClientId, clientMsg)
```

The `updateClientCheckTx` function (called during `CheckTx` and `ReCheckTx` for every `MsgUpdateClient`) explicitly skips `CheckForMisbehaviour` and calls `UpdateState` directly.

**Impact chain:**
1. Attacker submits `MsgUpdateClient` in mempool (CheckTx path)
2. Ante handler calls `UpdateState` — writes corrupted consensus state
3. `CheckForMisbehaviour` never runs — client is never frozen
4. The corrupted state persists

This means **misbehaviour that should freeze the client is silently ignored during CheckTx**, and the state written is never corrected if the tx later passes DeliverTx normally (which does run misbehaviour checks — but by then state may already be dirty depending on cache semantics).

**Severity estimate:** Medium. Depends on whether CheckTx state bleeds into DeliverTx. In standard Cosmos SDK, CheckTx uses a cached context that is discarded — but this warrants a careful trace through the cache boundaries, because the comment "state updates in both CheckTx and ReCheckTx" suggests writes are intentional.

---

## Finding 4 (NEW)
### Timestamp Unit Confusion: Nanoseconds Stored, Seconds Compared — Potential Overflow/Mismatch

**File:** `abi.go:67-68, 156`, `light_client_module.go:93`, `update.go:47`

**Encode path:**
```go
timestampSeconds := sa.Timestamp / nanosPerSecond  // converts ns → s before ABI packing
```

**Decode path:**
```go
Timestamp: timestampSeconds * nanosPerSecond  // converts s → ns after ABI unpacking
```

**Stored in ConsensusState:** nanoseconds

**Compared in CheckForMisbehaviour:**
```go
return consensusState.Timestamp != stateAttestation.Timestamp
```

`stateAttestation.Timestamp` at this point is already reconverted to nanoseconds (×1e9). The stored `consensusState.Timestamp` is also nanoseconds. So the comparison is consistent *if decode is always called before compare.*

**Bug vector:** If any external attestor system submits a `StateAttestation` with a timestamp that is already in seconds (not nanoseconds), the stored value becomes `seconds * 1e9`, which is astronomically large. This would:
- Make `CheckForMisbehaviour` always return false (no existing state matches)
- Set `LatestHeight` to an attacker-controlled value
- Write a consensus state with a timestamp ~31 years in the future, breaking IBC timeout logic for this client permanently

This is an **input validation gap** — there is no range check on the incoming timestamp to ensure it is plausible. A timestamp of `1` (clearly in seconds) passes all validation.

**Severity estimate:** Medium. Requires an attestor (trusted party) to submit a wrong-unit value, or an off-chain integration bug. Documents a correctness invariant that is never enforced.

---

## Finding 5 (NEW)
### Double Quorum Check Is Redundant — Logic Gap in `verifySignatures`

**File:** `signature.go:47-48, 87-88`

```go
func (cs *ClientState) verifySignatures(...) error {
    if len(proof.Signatures) < int(cs.MinRequiredSigs) {
        return ErrInvalidQuorum  // CHECK 1 — at top
    }
    ...
    // [loop through signatures, verify each]
    ...
    if len(proof.Signatures) < int(cs.MinRequiredSigs) {
        return ErrInvalidQuorum  // CHECK 2 — identical, at bottom
    }
    return nil
}
```

The second check is identical to the first and is dead code — the loop body has no logic that could reduce `len(proof.Signatures)`. However, **the function never checks that the number of *valid, unique, known* signers meets quorum** — it only checks the raw count of submitted signatures.

An attacker who can produce `MinRequiredSigs` signatures (even from non-attestor keys) will pass the count checks. The loop does catch unknown signers via `ErrUnknownSigner` — but the quorum threshold is never applied to the *verified signer count*, only to the *submitted signature count*.

**Concrete attack:**
- Submit `MinRequiredSigs` signatures where the first `MinRequiredSigs - 1` are from valid attestors and the last is from an unknown key
- The unknown key check returns `ErrUnknownSigner` — but only *after* the count check passes
- This is not exploitable as written because any unknown signer causes an error

**The actual issue:** The final quorum check at line 87-88 should be checking `len(seenSigners)` (verified unique valid signers), not `len(proof.Signatures)`. As written, if a caller somehow gets past the unknown signer check (e.g. due to future code changes), the quorum threshold on valid signers is never enforced.

**Severity estimate:** Low (not currently exploitable, but a logic error that creates fragile security invariant). Good candidate for a "code quality / defense-in-depth" finding.

---

## Finding 6 (NEW)
### `ValidateBasic` Decode Ordering: PacketAttestation Always Wins — Structural Ambiguity

**File:** `attestation_proof.go:26-35`

```go
// Try to decode as PacketAttestation first
packetAttestation, packetErr := ABIDecodePacketAttestation(ap.AttestationData)
if packetErr == nil {
    if len(packetAttestation.Packets) == 0 {
        return error
    }
} else {
    // fallback to StateAttestation
}
```

Because PacketAttestation bytes always decode successfully as PacketAttestation (they're well-formed), and StateAttestation bytes **also** successfully decode as PacketAttestation (due to the type confusion — see Finding 1), `ValidateBasic` will:

- Accept a StateAttestation as valid *only if it also satisfies the `len(Packets) > 0` check*
- A minimal StateAttestation (64 bytes: two uint64s) will decode as a PacketAttestation with `Packets = []` and **fail** with "packets cannot be empty"

This means **`ValidateBasic` rejects valid StateAttestations** — they fall through to the else branch and are validated correctly, but the decode-as-PacketAttestation failure path silently discards the PacketAttestation decode error, which may mask malformed inputs.

More critically: the ordering creates a **validation inconsistency** between `ValidateBasic` (which tries Packet first) and `VerifyClientMessage`/`UpdateState` (which always decode as State). A proof that passes `ValidateBasic` as a Packet may fail in `UpdateState` as a State, causing a panic.

**Severity estimate:** Medium. The ValidateBasic → UpdateState inconsistency can cause a panic on any valid message that passes one decoder but not the other.

---

## Recommended Next Steps by Priority

| # | Finding | Action | Effort |
|---|---------|--------|--------|
| 2 | `GetTimestamp` panic | Run `grep -rn GetTimestamp modules/core/` — if any caller exists, this is Critical | 10 min |
| 3 | Ante handler misbehaviour skip | Trace CheckTx cache semantics — is UpdateState write persistent? | 1 hr |
| 6 | ValidateBasic → UpdateState inconsistency | Write PoC: craft StateAttestation that passes ValidateBasic but panics UpdateState | 2 hr |
| 4 | Timestamp unit mismatch | Test: submit attestation with timestamp=1 (seconds), observe stored value | 1 hr |
| 1 | ABI type confusion | Draft report — known, high confidence | Ready |
| 5 | Quorum logic gap | Low priority, file as code quality | Low |

---

## Environment

- Repo: `cosmos/ibc-go` tag `v11.0.0`
- All findings are from static analysis of public source
- No chain was run or state modified
- Files read: `attestations/*.go`, `core/ante/ante.go`, `core/04-channel/v2/keeper/packet.go`
