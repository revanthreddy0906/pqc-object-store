# pqc-object-store

Code, configurations, results and paper for **"Benchmarking Post-Quantum Key Encapsulation in
S3-Compatible Object Storage under Client Concurrency"** (Department of Information Technology,
Chaitanya Bharathi Institute of Technology, Hyderabad).

The project measures what it costs to protect every object in an S3-compatible object store with
post-quantum key encapsulation. Objects are encrypted on the client with **ML-KEM-768**
(FIPS 203), **HKDF-SHA256** and chunked **AES-256-GCM**, and stored in a single-node **MinIO**
server. The same data path is measured with X25519, RSA-4096, a symmetric-only baseline, two
X25519 + ML-KEM hybrids (including X-Wing) and bounded ML-KEM sessions, from 1 to 500 concurrent
workers.

> Research prototype. liboqs is intended for prototyping and evaluation, and this code is not a
> production cryptographic service. A new design should use HPKE (RFC 9180), not this envelope
> format.

## Main results

| Finding | Value |
|---|---|
| Where ML-KEM lowered throughput | only where the client was at or near CPU saturation (one unexplained exception in the native reader) |
| Python client, saturated cell, ML-KEM vs X25519 | 4.0 % slower (x86), 4.9 % slower (ARM) |
| Cause on x86 (two pre-registered controls) | mainly the liboqs-python binding (four foreign calls per decapsulation); 17 % from the larger manifest |
| ML-KEM through one foreign call | equivalent to X25519 within ±2 % |
| Native Go reader saturated on one core | 9.5 % slower with ML-KEM, 17.4 % with X-Wing |
| Storage cost | 1,056 more bytes of ciphertext per object than X25519 |

Scope: two clients (Python on x86 and ARM, a GET-only Go reader), one single-node MinIO store, one
cloud provider (AWS). See Section 6 of the paper for the threats to validity and the experiments
not yet run.

## Experiments

| Campaign | Runs | Notes |
|---|---|---|
| Exploratory (batches A to D) | 1,970 | full matrix, five repetitions; verdicts are exploratory |
| Confirmatory (E, EK, F, G, H, P, I, IK, I1) | 1,495 (97.6 M requests, 0 failures) | pre-registered; paired TOST at ±5 %, Holm-corrected; x86 and ARM clients |
| Follow-up controls (J, K, L, M, MT) | 480 | pre-registered manifest, power, binding and allocator controls |
| Native reader (N) | 90 | Go reader, GET only, pre-registered |

The paper uses purpose labels (for example `Primary-x86`, `Control-Binding`); its Table 5 maps
them to these batch identifiers. Pre-registrations were pushed to this repository before the
runs they cover; the push times and deviations are documented in
[`docs/preregistration-timestamps.md`](docs/preregistration-timestamps.md) and
[`docs/github-activity-log.json`](docs/github-activity-log.json). The full protocol, design
decisions and version history are in [`docs/source-of-truth.pdf`](docs/source-of-truth.pdf).

## Repository layout

```
src/pqcstore/
  crypto/          key-establishment modes (B0, B1, R1, B2, P1, P2, P3/X-Wing, N1 and the
                   C2/H1/G1 controls), HKDF, chunked AES-GCM, manifest, envelope, sessions
  storage/         MinIO adapter; encrypted store with manifest-as-commit protocol
  benchmark/       runner (closed and open loop), samplers, record validator, payload pool
  cli.py           doctor, s3-smoke, keygen, put, get, soak, stream-check, bench, validate, gc
native/            Go reader (GET path of B2, P1, P3), its tests and single-thread micro-timer
analysis/          per-run summaries, statistics and the generators of every paper number
config/            experiment configurations (final-a ... final-mt, pilot, development)
results/           per-run summaries and analysis outputs used by the paper
scripts/           liboqs build, VM setup, native-reader fixture and benchmark scripts
infra/aws/         testbed automation (create, provision, run, fetch, tear down)
docker/            MinIO source-build Dockerfile
docs/              source of truth, AWS runbook, literature-search log, pre-registration timestamps
paper/             LaTeX source of the paper (IEEE), supplement, Elsevier version, submission files
tests/             unit, tamper, binding and MinIO integration tests
experiments/       raw request records (git-ignored, about 11 GB compressed)
```

## Requirements

- Python 3.12, Git, CMake 3.18 or later and a C compiler
- Docker with Compose v2 (local MinIO)
- Go 1.26 (native reader only)
- [tectonic](https://tectonic-typesetting.github.io/) (paper only)
- About 10 GB of free disk for the MinIO and liboqs builds

Pinned versions used in the paper: liboqs 0.16.0, liboqs-python 0.16.0.1,
pyca/cryptography 50.0.1, MinIO Python SDK 7.2.20, Python 3.12.3, MinIO
RELEASE.2025-10-15T17-29-55Z, Go 1.26.2.

## Quick start

```bash
make setup             # builds liboqs 0.16.0 into .local/, creates .venv and .env
make minio-build       # compiles MinIO from its final community release (slow the first time)
make services-up       # starts MinIO on 127.0.0.1:9000
make doctor            # checks versions, liboqs and S3 reachability
make test              # unit and integration tests (integration tests skip if MinIO is down)
```

Run Python through the Makefile targets, or export `OQS_INSTALL_PATH=$PWD/.local/liboqs` first.
Without it, liboqs-python would download an unpinned liboqs, and `pqcstore` refuses to load.

An encrypted round trip:

```bash
export OQS_INSTALL_PATH=$PWD/.local/liboqs
.venv/bin/pqcstore keygen --public keys/recipient.pub --private keys/recipient.key
.venv/bin/pqcstore put --bucket pqc-bench --key demo/object-1 \
    --input fixtures/1MiB.bin --recipient-public-key keys/recipient.pub
.venv/bin/pqcstore get --bucket pqc-bench --key demo/object-1 \
    --output recovered.bin --recipient-private-key keys/recipient.key
```

Timings from a single CLI call include one-off start-up costs; the benchmark runner measures only
after an in-process warm-up.

## Reproducing the paper

Every number, table and figure in the paper is generated from the per-run summaries in
`results/`; none is typed by hand.

```bash
make paper-assets      # regenerates paper/generated/ from results/
make paper             # builds paper/main.pdf (IEEE version)
cd paper && tectonic -X compile supplement.tex             # supplementary material
.venv/bin/python paper/tools/build_elsevier.py             # Elsevier version in paper/elsevier/
```

Rebuilding the per-run summaries themselves (`analysis/summarize.py`) needs the raw request
records in `experiments/`, which are not in the repository because of their size.

## Running the experiments

The experiments ran on two AWS instances in one cluster placement group (client c7i.4xlarge or
c7g.4xlarge, server i4i.4xlarge with local NVMe). [`docs/aws-runbook.md`](docs/aws-runbook.md)
describes the workflow; in short:

```bash
infra/aws/pqc-aws.sh check && infra/aws/pqc-aws.sh up && infra/aws/pqc-aws.sh provision
infra/aws/pqc-aws.sh run config/final-e.yaml
infra/aws/pqc-aws.sh fetch
infra/aws/pqc-aws.sh destroy
```

Every configuration file records the random seed of its experiment. The native reader is run
with `scripts/native_bench.sh` after `scripts/native_fixture.py` has written its objects.

## Rules

- Private keys, `.env`, cloud credentials and raw experiment data never enter Git.
- Numbers from laptops or Docker Desktop are never reported; all measurements come from the
  cloud testbeds.
- Every reported number is regenerated by a script from retained data.

## Authors

Revanth Reddy Lingala, K. Gangadhara Rao, Padigela Srujan, Saarthak Manocha and Vainavi Venkat,
Department of Information Technology, Chaitanya Bharathi Institute of Technology, Hyderabad,
India. Contact: revanthreddy0906@gmail.com.
