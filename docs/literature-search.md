# Literature search log (related work, Section III of the paper)

Date of search: 13 October 2026. Purpose: to check whether a measurement of per-object ML-KEM
(or Kyber) key establishment in an S3-compatible object store under concurrent load has been
published.

## Scope and limits

- Searched: arXiv, dblp and Semantic Scholar through a web search engine restricted to those
  three sites, plus two unrestricted open-web queries.
- **Not searched: IEEE Xplore and the ACM Digital Library.** These need subscription access and
  must be searched by the authors before submission. The paper words its novelty statement "to
  our knowledge" for this reason.
- This is a keyword search, not a systematic review: there was no second screener and no
  citation chasing beyond the works already cited.

## Inclusion criterion

A work is relevant if it measures post-quantum key establishment in a storage data path, or
measures S3 / object-store performance with client-side encryption.

## Queries and outcome

| # | Restriction | Query | Relevant hits |
|---|---|---|---|
| 1 | open web | ML-KEM OR Kyber "object storage" OR S3 client-side encryption benchmark concurrency per-object post-quantum | None. Vendor tutorials and primitive benchmarks only. |
| 2 | open web | post-quantum envelope encryption cloud storage performance evaluation MinIO ML-KEM-768 throughput | arXiv 2608.13138 (already cited as `prikutse2026`). No MinIO or S3 measurement. |
| 3 | arXiv, dblp, Semantic Scholar | ML-KEM object storage S3 client-side encryption performance concurrency | arXiv 2608.26777 (new, added as `junaid2026`); arXiv 2508.01694 (already cited as `rodriguez2025`). |
| 4 | arXiv, dblp, Semantic Scholar | Kyber envelope encryption cloud storage benchmark per-object key encapsulation throughput | arXiv 2503.12952 and 2508.01694 (both already cited). Primitive benchmarks only. |
| 5 | arXiv, dblp, Semantic Scholar | post-quantum cryptography MinIO OR Ceph OR "object store" evaluation KEM data at rest | arXiv 2608.13138 (already cited). Otherwise patents and general surveys. |
| 6 | arXiv, dblp, Semantic Scholar | post-quantum hybrid KEM X-Wing performance storage encryption measurement | None for storage. Hybrid-KEM measurements found were for TLS and the Noise protocol. |

## Result

No work found measures per-object ML-KEM in an S3-compatible store under concurrent clients.
The closest are two 2026 preprints on hybrid post-quantum cloud-storage designs:

- arXiv 2608.13138 (Prikutse et al.): signature amortization over file batches.
- arXiv 2608.26777 (Junaid): a client-side hybrid encryption architecture with self-hosted key
  management; per its abstract it reports per-operation latency on a microcontroller and a
  server, not an object-store workload, concurrent clients or queueing.

Both are described in the paper from their abstracts only.
