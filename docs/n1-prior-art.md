# N1 (bounded ML-KEM session amortization): prior art and claim scope

Status: search performed 24 Sep 2026 with public web sources only. Before the paper states any
novelty claim, the analysis lead must repeat it in IEEE Xplore, ACM DL and Google Scholar
(SoT §15 "Definition of done"). This note records what was found and the wording that follows.

## The mechanism

One ML-KEM-768 encapsulation establishes a session root `S_r`. Each object gets
`K_i = HKDF-SHA256(S_r, salt_i, "pqc-s3-session-v1" || 0x00 || context_i)`, where `context_i`
authenticates the object identity, session id, sequence number and bound. A root protects at
most `B` objects and lives at most `T_max` seconds. `B` is either fixed (`B_max`) or queue-aware,
`B_t = clip(B_min, B_max, round(B_min + (B_max - B_min) * rho_hat))`, fixed per session at its
creation. The receiver enforces its own `B_max` and caches decapsulated roots under the same
caps. Implementation: `src/pqcstore/crypto/session.py`.

## Closest prior art

| Work | What it does | Same as N1 | Different from N1 |
|---|---|---|---|
| Amazon S3 Bucket Keys | A time-limited bucket-level key from KMS derives a unique data key per object; up to 99% fewer KMS requests | Reuse of a parent key for a limited time, per-object derived keys, motivated by cost of the expensive key operation | Server-side and KMS-based (no public-key KEM); time bound only; not post-quantum; no measurement of the trade-off |
| AWS Encryption SDK caching CMM | Caches data keys, bounded by `max_age`, `max_messages_encrypted`, `max_bytes_encrypted` | Count and age bounds on reuse | Data keys come from a keyring (commonly KMS), not a per-session KEM; bounds are static; no object-store evaluation |
| TLS 1.3 PSK resumption (RFC 8446) | Session tickets let later connections skip the full (possibly hybrid PQ) key exchange, with a ticket lifetime | Amortizing an expensive key exchange across uses, lifetime-bounded | Transport-layer connections, not per-object storage keys |
| Usage-limit key rotation (e.g. US patent 9,882,720) | Rotate when usage of a key exceeds a threshold | Count-triggered rotation | No KEM, no adaptive bound |
| Prikutse et al., arXiv:2608.13138 | Batch commitment cuts PQ signing from n to 1 for multi-file cloud storage | Amortizing a PQ operation across many files | Amortizes signatures, not KEM key establishment; client-only, no concurrency or bound trade-off |

## What the searches did not find

- A **load- or queue-adaptive** bound on key reuse, where the reuse limit follows measured
  utilization while hard caps stay in force.
- Published **measurements of the performance versus compromise-scope trade-off** for
  post-quantum KEM key establishment in an S3-compatible object store under concurrency.

Absence from a web search is not evidence of absence; this must be re-checked in the
academic databases.

## Claim wording for the paper

Do **not** claim bounded key reuse as new. Suggested wording:

> Bounded reuse of a key-establishment result with per-object key derivation is established
> practice (e.g. Amazon S3 Bucket Keys, the AWS Encryption SDK's data-key cache). We apply it to
> ML-KEM-768-established roots in client-side object encryption, quantify the latency and CPU
> saved as a function of the bound B against the compromise scope B, and evaluate a
> queue-aware variant that adapts B to client utilization within fixed caps.

The queue-aware policy is the candidate novelty; the evaluation (Sweep E) is the contribution
either way.

## Security scope (must appear in the paper)

- **Per-object keys stay independent.** Contexts differ in object identity and sequence number,
  so under the usual HKDF-as-PRF assumption learning one `K_i` reveals nothing about other
  object keys or `S_r`.
- **What N1 changes.** A leaked session root exposes at most `B_max` objects (in-memory
  compromise of sender or receiver). This is the only exposure N1 adds over P1.
- **What N1 does not change.** Compromise of the recipient's ML-KEM decapsulation key exposes
  every object in both P1 and N1. Neither mode has forward secrecy against that.
- **Queue-aware worst case.** An adversary who drives load up can push `B` to `B_max`, but
  never past it. The security guarantee is that of fixed `B_max`; the adaptive policy only
  lowers expected exposure when load is light.
- **Receiver-side enforcement.** Readers reject objects whose authenticated sequence number or
  bound exceeds the reader's own `B_max`.

## Sources

- Amazon S3 User Guide, "Reducing the cost of SSE-KMS with Amazon S3 Bucket Keys":
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-key.html
- AWS Encryption SDK Developer Guide, "Data key caching details":
  https://docs.aws.amazon.com/encryption-sdk/latest/developer-guide/data-caching-details.html
- E. Rescorla, RFC 8446, The Transport Layer Security (TLS) Protocol Version 1.3, §2.2, §4.6.1.
- "Data loss prevention with key usage limit enforcement", US patent 9,882,720:
  https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9882720
- L. F. Prikutse et al., "A Commitment-Based Hybrid Post-Quantum Cryptographic Model for
  Multi-File Cloud Storage", arXiv:2608.13138, Aug 2026.
