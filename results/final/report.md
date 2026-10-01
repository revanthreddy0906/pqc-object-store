# Final results (batches A, B, C)

1710 runs, 83,318,994 measured requests, 0 failed requests. Link capacity (iperf3) 1,479 MiB/s. 95% CIs are Student-t over 5 repetitions; mode ratios are paired by repetition within one batch.

Run-to-run noise: 43 of 342 cells exceed 5% throughput CV (38 of them small-object PUT cells). 17 runs are flagged as server stalls (server CPU and throughput both well below their own cell's median); by mode: B0 0, B1 3, R1 2, B2 0, P1 3, P2 0, N1 9.

## Metric 1 — key-establishment (handshake) time per request, one worker

Batch B, closed loop, 1 worker; per repetition averaged over the six object sizes.

| Mode | Op | Key establishment (µs), mean [95% CI] |
|---|---|---|
| B1 AES only (pre-shared key) | put | 1.6 [1.6, 1.7] |
| B1 AES only (pre-shared key) | get | 1.1 [1.1, 1.2] |
| R1 RSA-OAEP-4096 | put | 108.1 [107.3, 109.0] |
| R1 RSA-OAEP-4096 | get | 1493.9 [1491.2, 1496.6] |
| B2 X25519 | put | 100.8 [100.1, 101.5] |
| B2 X25519 | get | 49.0 [48.5, 49.6] |
| P1 ML-KEM-768 | put | 58.0 [56.7, 59.3] |
| P1 ML-KEM-768 | get | 46.5 [45.9, 47.1] |

## Metric 2 — throughput (batch A, closed loop)

Requests/s, mean ± 95% CI half-width; MiB/s in parentheses; limiting resource from the client/server/network samples.

**PUT 64 KiB**

| Workers | B0 | B1 | R1 | B2 | P1 | P2 | Limit (B1) |
|---|---|---|---|---|---|---|---|
| 1 | 263 ±5 (16) | 253 ±11 (16) | 250 ±8 (16) | 247 ±12 (15) | 248 ±8 (16) | – | none (latency-bound) |
| 8 | 1,702 ±7 (106) | 1,743 ±77 (109) | 1,676 ±51 (105) | 1,657 ±8 (104) | 1,680 ±53 (105) | – | none (latency-bound) |
| 32 | 3,793 ±415 (237) | 3,640 ±270 (228) | 3,858 ±268 (241) | 3,645 ±135 (228) | 3,809 ±446 (238) | – | none (latency-bound) |
| 128 | 4,547 ±87 (284) | 4,207 ±570 (263) | 4,619 ±216 (289) | 4,668 ±180 (292) | 4,368 ±635 (273) | – | none (latency-bound) |
| 256 | 4,460 ±101 (279) | 4,481 ±79 (280) | 4,255 ±618 (266) | 4,549 ±241 (284) | 4,522 ±210 (283) | – | server write path |
| 500 | 4,513 ±199 (282) | 4,528 ±360 (283) | 4,274 ±370 (267) | 4,407 ±144 (275) | 4,467 ±104 (279) | – | server write path |

**PUT 1 MiB**

| Workers | B0 | B1 | R1 | B2 | P1 | P2 | Limit (B1) |
|---|---|---|---|---|---|---|---|
| 1 | 117 ±2 (117) | 108 ±2 (108) | 113 ±3 (113) | 113 ±2 (113) | 113 ±2 (113) | 105 ±2 (105) | none (latency-bound) |
| 8 | 702 ±3 (702) | 674 ±15 (674) | 691 ±16 (691) | 686 ±11 (686) | 682 ±5 (682) | 660 ±5 (660) | none (latency-bound) |
| 32 | 1,342 ±9 (1,342) | 1,363 ±16 (1,363) | 1,347 ±27 (1,347) | 1,330 ±25 (1,330) | 1,349 ±15 (1,349) | 1,368 ±17 (1,368) | network |
| 128 | 1,314 ±5 (1,314) | 1,318 ±11 (1,318) | 1,306 ±16 (1,306) | 1,318 ±15 (1,318) | 1,317 ±25 (1,317) | 1,327 ±10 (1,327) | network |
| 256 | 1,311 ±16 (1,311) | 1,309 ±12 (1,309) | 1,305 ±14 (1,305) | 1,315 ±12 (1,315) | 1,313 ±16 (1,313) | – | network |
| 500 | 1,316 ±15 (1,316) | 1,317 ±19 (1,317) | 1,310 ±18 (1,310) | 1,321 ±16 (1,321) | 1,328 ±23 (1,328) | 1,329 ±14 (1,329) | network |

**PUT 16 MiB**

| Workers | B0 | B1 | R1 | B2 | P1 | P2 | Limit (B1) |
|---|---|---|---|---|---|---|---|
| 1 | 17 ±0 (276) | 16 ±0 (254) | 16 ±0 (253) | 16 ±0 (254) | 16 ±1 (252) | – | none (latency-bound) |
| 8 | 73 ±4 (1,161) | 73 ±2 (1,171) | 75 ±3 (1,203) | 72 ±2 (1,158) | 72 ±3 (1,147) | – | none (latency-bound) |
| 32 | 90 ±1 (1,443) | 91 ±0 (1,458) | 90 ±1 (1,448) | 91 ±1 (1,450) | 90 ±0 (1,443) | – | network |
| 128 | 89 ±0 (1,419) | 89 ±0 (1,422) | 89 ±1 (1,423) | 89 ±0 (1,424) | 89 ±0 (1,421) | – | network |

**GET 64 KiB**

| Workers | B0 | B1 | R1 | B2 | P1 | P2 | Limit (B1) |
|---|---|---|---|---|---|---|---|
| 1 | 459 ±12 (29) | 456 ±21 (29) | 261 ±4 (16) | 454 ±14 (28) | 449 ±19 (28) | – | none (latency-bound) |
| 8 | 3,513 ±48 (220) | 3,417 ±55 (214) | 1,974 ±15 (123) | 3,381 ±20 (211) | 3,344 ±41 (209) | – | none (latency-bound) |
| 32 | 9,995 ±152 (625) | 9,394 ±118 (587) | 3,597 ±4 (225) | 9,053 ±117 (566) | 8,978 ±93 (561) | – | server write path |
| 128 | 10,386 ±344 (649) | 9,639 ±134 (602) | 3,577 ±4 (224) | 9,345 ±127 (584) | 9,446 ±132 (590) | – | client CPU |
| 256 | 9,270 ±74 (579) | 8,599 ±88 (537) | 3,466 ±7 (217) | 8,253 ±95 (516) | 8,010 ±136 (501) | – | client CPU |
| 500 | 9,248 ±35 (578) | 8,564 ±34 (535) | 3,400 ±32 (213) | 8,265 ±32 (517) | 7,946 ±26 (497) | – | client CPU |

**GET 1 MiB**

| Workers | B0 | B1 | R1 | B2 | P1 | P2 | Limit (B1) |
|---|---|---|---|---|---|---|---|
| 1 | 291 ±3 (291) | 247 ±2 (247) | 181 ±3 (181) | 244 ±2 (244) | 245 ±1 (245) | 242 ±2 (242) | none (latency-bound) |
| 8 | 1,471 ±6 (1,471) | 1,474 ±2 (1,474) | 1,354 ±26 (1,354) | 1,474 ±1 (1,474) | 1,472 ±2 (1,472) | 1,472 ±1 (1,472) | network |
| 32 | 1,472 ±6 (1,472) | 1,475 ±2 (1,475) | 1,469 ±9 (1,469) | 1,473 ±4 (1,473) | 1,472 ±4 (1,472) | 1,470 ±8 (1,470) | network |
| 128 | 1,463 ±2 (1,463) | 1,464 ±6 (1,464) | 1,463 ±4 (1,463) | 1,462 ±2 (1,462) | 1,461 ±3 (1,461) | 1,459 ±2 (1,459) | network |
| 256 | 1,461 ±3 (1,461) | 1,461 ±1 (1,461) | 1,460 ±1 (1,460) | 1,461 ±2 (1,461) | 1,460 ±1 (1,460) | – | network |
| 500 | 1,434 ±13 (1,434) | 1,442 ±9 (1,442) | 1,434 ±27 (1,434) | 1,419 ±34 (1,419) | 1,401 ±55 (1,401) | 1,434 ±22 (1,434) | network |

**GET 16 MiB**

| Workers | B0 | B1 | R1 | B2 | P1 | P2 | Limit (B1) |
|---|---|---|---|---|---|---|---|
| 1 | 59 ±1 (947) | 44 ±1 (706) | 41 ±1 (655) | 43 ±1 (691) | 42 ±1 (678) | – | none (latency-bound) |
| 8 | 92 ±0 (1,477) | 92 ±0 (1,476) | 92 ±0 (1,475) | 92 ±0 (1,476) | 92 ±0 (1,476) | – | network |
| 32 | 92 ±0 (1,467) | 92 ±0 (1,466) | 92 ±0 (1,466) | 92 ±0 (1,468) | 92 ±0 (1,466) | – | network |
| 128 | 89 ±0 (1,430) | 89 ±0 (1,429) | 89 ±0 (1,430) | 89 ±0 (1,427) | 89 ±0 (1,429) | – | network |

## Metric 3 — CPU (batch A)

Cores in use during the measured window (client: benchmark processes; server: MinIO), and client thread CPU per request (ms).

| Op | Size | Workers | Mode | Client cores | Server cores | Client CPU ms/request |
|---|---|---|---|---|---|---|
| put | 64 KiB | 1 | B1 | 0.31 [0.30, 0.33] | 0.50 [0.46, 0.54] | 1.230 [1.222, 1.237] |
| put | 64 KiB | 1 | R1 | 0.33 [0.32, 0.34] | 0.49 [0.45, 0.53] | 1.317 [1.298, 1.337] |
| put | 64 KiB | 1 | B2 | 0.33 [0.31, 0.35] | 0.49 [0.45, 0.52] | 1.322 [1.310, 1.334] |
| put | 64 KiB | 1 | P1 | 0.32 [0.31, 0.34] | 0.49 [0.45, 0.52] | 1.289 [1.276, 1.303] |
| put | 64 KiB | 32 | B1 | 5.33 [4.85, 5.82] | 8.18 [6.84, 9.52] | 1.454 [1.428, 1.479] |
| put | 64 KiB | 32 | R1 | 6.20 [5.68, 6.71] | 8.78 [7.87, 9.70] | 1.596 [1.576, 1.616] |
| put | 64 KiB | 32 | B2 | 5.77 [5.50, 6.05] | 8.26 [7.61, 8.90] | 1.574 [1.552, 1.595] |
| put | 64 KiB | 32 | P1 | 5.95 [5.13, 6.77] | 8.56 [7.41, 9.71] | 1.553 [1.523, 1.582] |
| put | 64 KiB | 128 | B1 | 6.46 [5.28, 7.64] | 9.84 [7.61, 12.07] | 1.526 [1.461, 1.592] |
| put | 64 KiB | 128 | R1 | 8.02 [7.63, 8.42] | 11.22 [11.06, 11.38] | 1.726 [1.719, 1.733] |
| put | 64 KiB | 128 | B2 | 8.01 [7.67, 8.35] | 11.24 [10.94, 11.54] | 1.706 [1.699, 1.713] |
| put | 64 KiB | 128 | P1 | 7.31 [5.95, 8.67] | 10.35 [8.22, 12.49] | 1.658 [1.577, 1.740] |
| put | 1 MiB | 1 | B1 | 0.36 [0.36, 0.37] | 0.57 [0.56, 0.58] | 3.360 [3.318, 3.402] |
| put | 1 MiB | 1 | R1 | 0.34 [0.33, 0.35] | 0.59 [0.57, 0.61] | 3.003 [2.973, 3.033] |
| put | 1 MiB | 1 | B2 | 0.33 [0.32, 0.33] | 0.59 [0.58, 0.60] | 2.901 [2.850, 2.952] |
| put | 1 MiB | 1 | P1 | 0.33 [0.32, 0.33] | 0.59 [0.58, 0.60] | 2.873 [2.855, 2.890] |
| put | 1 MiB | 32 | B1 | 5.08 [4.99, 5.17] | 8.85 [8.47, 9.24] | 3.706 [3.668, 3.744] |
| put | 1 MiB | 32 | R1 | 5.73 [5.47, 6.00] | 8.90 [8.51, 9.30] | 4.231 [4.096, 4.365] |
| put | 1 MiB | 32 | B2 | 5.12 [5.02, 5.21] | 8.50 [8.22, 8.78] | 3.824 [3.798, 3.850] |
| put | 1 MiB | 32 | P1 | 5.20 [5.13, 5.28] | 8.81 [8.56, 9.05] | 3.840 [3.806, 3.874] |
| put | 1 MiB | 128 | B1 | 5.19 [5.13, 5.26] | 8.42 [8.14, 8.69] | 3.915 [3.898, 3.932] |
| put | 1 MiB | 128 | R1 | 6.53 [6.33, 6.73] | 8.20 [7.92, 8.47] | 4.967 [4.854, 5.081] |
| put | 1 MiB | 128 | B2 | 5.39 [5.31, 5.48] | 8.26 [8.16, 8.36] | 4.065 [4.004, 4.126] |
| put | 1 MiB | 128 | P1 | 5.40 [5.30, 5.51] | 8.18 [8.05, 8.32] | 4.073 [4.060, 4.086] |
| get | 64 KiB | 1 | B1 | 0.49 [0.46, 0.52] | 0.49 [0.46, 0.53] | 1.068 [1.043, 1.093] |
| get | 64 KiB | 1 | R1 | 0.70 [0.69, 0.71] | 0.29 [0.28, 0.30] | 2.666 [2.655, 2.676] |
| get | 64 KiB | 1 | B2 | 0.51 [0.49, 0.53] | 0.49 [0.48, 0.50] | 1.110 [1.100, 1.121] |
| get | 64 KiB | 1 | P1 | 0.51 [0.49, 0.54] | 0.49 [0.48, 0.51] | 1.124 [1.112, 1.136] |
| get | 64 KiB | 32 | B1 | 12.95 [12.80, 13.09] | 10.96 [10.56, 11.35] | 1.365 [1.362, 1.369] |
| get | 64 KiB | 32 | R1 | 15.52 [15.51, 15.53] | 3.64 [3.44, 3.83] | 4.299 [4.295, 4.303] |
| get | 64 KiB | 32 | B2 | 13.00 [12.85, 13.14] | 10.56 [10.00, 11.12] | 1.423 [1.418, 1.427] |
| get | 64 KiB | 32 | P1 | 13.15 [13.05, 13.26] | 10.47 [10.09, 10.85] | 1.452 [1.448, 1.456] |
| get | 64 KiB | 128 | B1 | 14.47 [14.32, 14.62] | 11.41 [11.11, 11.71] | 1.487 [1.477, 1.498] |
| get | 64 KiB | 128 | R1 | 15.66 [15.65, 15.68] | 3.67 [3.36, 3.97] | 4.360 [4.353, 4.368] |
| get | 64 KiB | 128 | B2 | 14.51 [14.39, 14.63] | 10.99 [10.72, 11.27] | 1.539 [1.528, 1.549] |
| get | 64 KiB | 128 | P1 | 14.83 [14.69, 14.96] | 11.18 [10.91, 11.45] | 1.555 [1.546, 1.565] |
| get | 1 MiB | 1 | B1 | 0.61 [0.60, 0.63] | 0.49 [0.46, 0.52] | 2.472 [2.433, 2.512] |
| get | 1 MiB | 1 | R1 | 0.73 [0.71, 0.75] | 0.36 [0.34, 0.39] | 4.033 [3.997, 4.068] |
| get | 1 MiB | 1 | B2 | 0.62 [0.60, 0.64] | 0.48 [0.45, 0.51] | 2.523 [2.465, 2.580] |
| get | 1 MiB | 1 | P1 | 0.64 [0.62, 0.65] | 0.49 [0.45, 0.52] | 2.587 [2.521, 2.654] |
| get | 1 MiB | 32 | B1 | 6.24 [6.04, 6.43] | 2.99 [2.88, 3.11] | 4.205 [4.072, 4.337] |
| get | 1 MiB | 32 | R1 | 10.34 [10.09, 10.58] | 2.99 [2.73, 3.26] | 6.985 [6.821, 7.150] |
| get | 1 MiB | 32 | B2 | 6.32 [6.15, 6.50] | 2.90 [2.67, 3.12] | 4.265 [4.147, 4.382] |
| get | 1 MiB | 32 | P1 | 6.37 [6.15, 6.60] | 2.82 [2.54, 3.10] | 4.302 [4.149, 4.455] |
| get | 1 MiB | 128 | B1 | 6.95 [6.74, 7.15] | 3.05 [2.96, 3.14] | 4.685 [4.548, 4.821] |
| get | 1 MiB | 128 | R1 | 11.21 [11.02, 11.39] | 2.87 [2.60, 3.14] | 7.573 [7.450, 7.696] |
| get | 1 MiB | 128 | B2 | 7.10 [6.89, 7.30] | 2.98 [2.78, 3.18] | 4.788 [4.651, 4.925] |
| get | 1 MiB | 128 | P1 | 7.17 [7.02, 7.33] | 2.88 [2.68, 3.08] | 4.845 [4.740, 4.950] |

## Metric 4 — memory (client RSS summed over worker processes; MinIO RSS)

Peak RSS over the whole run and growth from the first sample (before warm-up). Every run starts fresh worker processes, so nothing accumulates across runs.

| Op | Size | Workers | Mode | Client peak MiB | Client growth MiB | Server growth MiB |
|---|---|---|---|---|---|---|
| put | 64 KiB | 500 | B1 | 2,080 [2,064, 2,095] | 181 [162, 199] | 640 [420, 860] |
| put | 64 KiB | 500 | R1 | 2,064 [2,050, 2,078] | 163 [156, 169] | 400 [84, 716] |
| put | 64 KiB | 500 | B2 | 2,061 [2,048, 2,074] | 161 [157, 165] | 641 [194, 1,088] |
| put | 64 KiB | 500 | P1 | 2,077 [2,057, 2,097] | 178 [170, 186] | 448 [108, 788] |
| get | 64 KiB | 500 | B1 | 2,212 [2,196, 2,227] | 338 [335, 340] | 15 [-26, 56] |
| get | 64 KiB | 500 | R1 | 2,017 [2,003, 2,032] | 142 [129, 155] | 1 [-1, 3] |
| get | 64 KiB | 500 | B2 | 2,199 [2,184, 2,213] | 314 [311, 316] | 0 [-0, 0] |
| get | 64 KiB | 500 | P1 | 2,168 [2,153, 2,183] | 286 [285, 287] | 0 [-0, 1] |
| put | 16 MiB | 128 | B1 | 6,610 [6,573, 6,646] | 540 [431, 650] | 8 [-5, 20] |
| put | 16 MiB | 128 | R1 | 6,667 [6,643, 6,691] | 644 [501, 787] | 14 [-2, 31] |
| put | 16 MiB | 128 | B2 | 6,614 [6,592, 6,637] | 691 [247, 1,135] | 40 [22, 59] |
| put | 16 MiB | 128 | P1 | 6,537 [6,501, 6,573] | 489 [399, 578] | 5 [-4, 15] |
| get | 16 MiB | 128 | B1 | 3,543 [3,515, 3,571] | 692 [656, 729] | 122 [-174, 419] |
| get | 16 MiB | 128 | R1 | 3,553 [3,494, 3,611] | 751 [677, 825] | 175 [-280, 630] |
| get | 16 MiB | 128 | B2 | 3,581 [3,557, 3,606] | 738 [719, 757] | 168 [-288, 624] |
| get | 16 MiB | 128 | P1 | 3,483 [3,457, 3,508] | 659 [609, 710] | 8 [-8, 24] |
| put | 500 MiB | 1 | B1 | 175 [170, 180] | 16 [11, 21] | 48 [-38, 134] |
| put | 500 MiB | 1 | R1 | 180 [180, 180] | 20 [20, 20] | 22 [-30, 73] |
| put | 500 MiB | 1 | B2 | 180 [176, 183] | 19 [13, 24] | 10 [-7, 27] |
| put | 500 MiB | 1 | P1 | 174 [171, 176] | 15 [12, 17] | 23 [-15, 61] |
| get | 500 MiB | 1 | B1 | 125 [123, 127] | 3 [-1, 8] | 49 [12, 85] |
| get | 500 MiB | 1 | R1 | 128 [126, 130] | 0 [0, 0] | 57 [14, 101] |
| get | 500 MiB | 1 | B2 | 125 [124, 127] | 1 [-1, 4] | 89 [-15, 193] |
| get | 500 MiB | 1 | P1 | 125 [124, 126] | 2 [-2, 6] | 53 [8, 97] |
| put | 500 MiB | 16 | B1 | 2,698 [2,679, 2,718] | 174 [157, 190] | 70 [-11, 150] |
| put | 500 MiB | 16 | R1 | 2,719 [2,696, 2,742] | 188 [160, 217] | 27 [-36, 90] |
| put | 500 MiB | 16 | P1 | 2,729 [2,708, 2,750] | 202 [189, 215] | 18 [-14, 49] |
| get | 500 MiB | 16 | B1 | 2,011 [2,002, 2,021] | 12 [1, 23] | 90 [16, 163] |
| get | 500 MiB | 16 | R1 | 2,025 [2,020, 2,031] | 28 [10, 46] | 144 [77, 210] |
| get | 500 MiB | 16 | P1 | 2,011 [2,001, 2,022] | 33 [11, 54] | 67 [-27, 161] |

## H1 — ML-KEM-768 (P1) vs X25519 (B2): throughput and median latency

Paired ratio P1/B2 [95% CI] and verdict (equivalent = CI inside ±5%).

| Batch | Op | Size | Workers | Throughput ratio | p50 ratio | Throughput verdict w/o stalls |
|---|---|---|---|---|---|---|
| final-a | get | 1 MiB | 1 | 1.005 [0.999, 1.010] equivalent | 0.991 [0.978, 1.003] equivalent | equivalent |
| final-a | get | 1 MiB | 128 | 0.999 [0.997, 1.002] equivalent | 1.015 [0.998, 1.033] equivalent | equivalent |
| final-a | get | 1 MiB | 256 | 0.999 [0.997, 1.001] equivalent | 1.001 [0.989, 1.013] equivalent | equivalent |
| final-a | get | 1 MiB | 32 | 0.999 [0.994, 1.004] equivalent | 1.068 [0.998, 1.143] inconclusive | equivalent |
| final-a | get | 1 MiB | 500 | 0.987 [0.967, 1.007] equivalent | 1.004 [0.995, 1.013] equivalent | equivalent |
| final-a | get | 1 MiB | 8 | 0.998 [0.997, 0.999] equivalent | 0.993 [0.974, 1.013] equivalent | equivalent |
| final-a | get | 16 MiB | 1 | 0.981 [0.935, 1.029] inconclusive | 1.026 [0.982, 1.072] inconclusive | inconclusive |
| final-a | get | 16 MiB | 128 | 1.001 [0.999, 1.003] equivalent | 1.034 [0.950, 1.127] inconclusive | equivalent |
| final-a | get | 16 MiB | 32 | 0.999 [0.997, 1.000] equivalent | 1.071 [1.013, 1.132] inconclusive | equivalent |
| final-a | get | 16 MiB | 8 | 1.000 [0.999, 1.001] equivalent | 1.139 [1.038, 1.249] inconclusive | equivalent |
| final-a | get | 64 KiB | 1 | 0.990 [0.957, 1.024] equivalent | 1.015 [0.992, 1.038] equivalent | equivalent |
| final-a | get | 64 KiB | 128 | 1.011 [0.993, 1.029] equivalent | 0.988 [0.963, 1.013] equivalent | equivalent |
| final-a | get | 64 KiB | 256 | 0.971 [0.962, 0.980] equivalent | 1.040 [1.029, 1.050] equivalent | equivalent |
| final-a | get | 64 KiB | 32 | 0.992 [0.987, 0.997] equivalent | 1.013 [1.009, 1.017] equivalent | equivalent |
| final-a | get | 64 KiB | 500 | 0.961 [0.959, 0.964] equivalent | 1.049 [1.047, 1.051] inconclusive | equivalent |
| final-a | get | 64 KiB | 8 | 0.989 [0.980, 0.998] equivalent | 1.011 [1.002, 1.021] equivalent | equivalent |
| final-a | put | 1 MiB | 1 | 1.002 [0.992, 1.011] equivalent | 0.998 [0.989, 1.008] equivalent | equivalent |
| final-a | put | 1 MiB | 128 | 0.999 [0.972, 1.026] equivalent | 1.004 [0.972, 1.036] equivalent | equivalent |
| final-a | put | 1 MiB | 256 | 0.999 [0.979, 1.018] equivalent | 0.999 [0.976, 1.022] equivalent | equivalent |
| final-a | put | 1 MiB | 32 | 1.014 [0.985, 1.044] equivalent | 0.981 [0.949, 1.015] inconclusive | equivalent |
| final-a | put | 1 MiB | 500 | 1.005 [0.999, 1.011] equivalent | 0.998 [0.975, 1.022] equivalent | equivalent |
| final-a | put | 1 MiB | 8 | 0.995 [0.976, 1.013] equivalent | 1.005 [0.988, 1.023] equivalent | equivalent |
| final-a | put | 16 MiB | 1 | 0.992 [0.964, 1.022] equivalent | 1.010 [0.975, 1.045] equivalent | equivalent |
| final-a | put | 16 MiB | 128 | 0.998 [0.996, 0.999] equivalent | 0.952 [0.929, 0.975] inconclusive | equivalent |
| final-a | put | 16 MiB | 32 | 0.995 [0.988, 1.003] equivalent | 1.010 [0.963, 1.061] inconclusive | equivalent |
| final-a | put | 16 MiB | 8 | 0.990 [0.931, 1.054] inconclusive | 1.023 [0.896, 1.169] inconclusive | inconclusive |
| final-a | put | 64 KiB | 1 | 1.006 [0.974, 1.038] equivalent | 0.991 [0.960, 1.023] equivalent | equivalent |
| final-a | put | 64 KiB | 128 | 0.931 [0.769, 1.127] inconclusive | 1.051 [0.914, 1.209] inconclusive | inconclusive |
| final-a | put | 64 KiB | 256 | 0.994 [0.934, 1.059] inconclusive | 1.018 [0.964, 1.076] inconclusive | inconclusive |
| final-a | put | 64 KiB | 32 | 1.042 [0.933, 1.164] inconclusive | 0.963 [0.867, 1.070] inconclusive | inconclusive |
| final-a | put | 64 KiB | 500 | 1.014 [0.967, 1.062] inconclusive | 0.998 [0.974, 1.023] equivalent | inconclusive |
| final-a | put | 64 KiB | 8 | 1.014 [0.983, 1.045] equivalent | 0.986 [0.956, 1.018] equivalent | equivalent |
| final-b | get | 1 KiB | 1 | 0.991 [0.963, 1.019] equivalent | 1.003 [0.946, 1.064] inconclusive | equivalent |
| final-b | get | 1 MiB | 1 | 1.011 [0.978, 1.045] equivalent | 0.990 [0.969, 1.012] equivalent | equivalent |
| final-b | get | 128 MiB | 1 | 0.921 [0.845, 1.005] inconclusive | 1.081 [0.982, 1.191] inconclusive | inconclusive |
| final-b | get | 16 MiB | 1 | 1.002 [0.982, 1.023] equivalent | 0.988 [0.959, 1.017] equivalent | equivalent |
| final-b | get | 500 MiB | 1 | 1.011 [0.982, 1.041] equivalent | 0.990 [0.965, 1.016] equivalent | equivalent |
| final-b | get | 64 KiB | 1 | 1.000 [0.961, 1.041] equivalent | 1.000 [0.971, 1.030] equivalent | equivalent |
| final-b | put | 1 KiB | 1 | 1.014 [0.962, 1.070] inconclusive | 0.983 [0.925, 1.044] inconclusive | inconclusive |
| final-b | put | 1 MiB | 1 | 1.005 [0.997, 1.013] equivalent | 0.993 [0.985, 1.001] equivalent | equivalent |
| final-b | put | 128 MiB | 1 | 1.039 [1.034, 1.044] equivalent | 0.961 [0.956, 0.966] equivalent | equivalent |
| final-b | put | 16 MiB | 1 | 1.000 [0.992, 1.008] equivalent | 1.000 [0.995, 1.005] equivalent | equivalent |
| final-b | put | 500 MiB | 1 | 1.005 [0.997, 1.014] equivalent | 0.993 [0.981, 1.006] equivalent | equivalent |
| final-b | put | 64 KiB | 1 | 1.033 [0.986, 1.083] inconclusive | 0.966 [0.921, 1.013] inconclusive | inconclusive |

Throughput verdicts: equivalent 35, inconclusive 9

## H2 — share of request time spent in ML-KEM (P1, one worker, batch B)

| Op | Size | ML-KEM µs | Share of request time | p50 ms |
|---|---|---|---|---|
| put | 1 KiB | 44.6 | 1.411% [1.339, 1.484] | 3.18 [3.04, 3.32] |
| put | 64 KiB | 44.9 | 1.258% [1.199, 1.318] | 3.59 [3.44, 3.73] |
| put | 1 MiB | 45.3 | 0.543% [0.531, 0.555] | 8.35 [8.25, 8.46] |
| put | 16 MiB | 46.4 | 0.077% [0.072, 0.083] | 59.74 [59.27, 60.20] |
| put | 128 MiB | 82.1 | 0.040% [0.037, 0.043] | 204.59 [202.89, 206.28] |
| put | 500 MiB | 84.5 | 0.012% [0.012, 0.012] | 706.13 [698.64, 713.61] |
| get | 1 KiB | 45.7 | 2.193% [2.140, 2.246] | 2.14 [2.06, 2.21] |
| get | 64 KiB | 46.3 | 2.252% [2.169, 2.336] | 2.11 [2.08, 2.14] |
| get | 1 MiB | 47.4 | 1.245% [1.198, 1.292] | 3.87 [3.79, 3.95] |
| get | 16 MiB | 46.7 | 0.207% [0.201, 0.212] | 22.10 [21.89, 22.31] |
| get | 128 MiB | 46.7 | 0.036% [0.033, 0.039] | 130.25 [117.37, 143.12] |
| get | 500 MiB | 46.2 | 0.010% [0.009, 0.011] | 465.31 [417.78, 512.83] |

## H3 — RSA-OAEP-4096 (R1) vs ML-KEM-768 (P1) on GET

Paired ratio R1/P1 [95% CI].

| Batch | Size | Workers | Throughput ratio | p50 ratio |
|---|---|---|---|---|
| final-a | 1 MiB | 1 | 0.736 [0.723, 0.749] different | 1.366 [1.343, 1.389] different |
| final-a | 1 MiB | 128 | 1.001 [0.998, 1.005] equivalent | 0.996 [0.983, 1.010] equivalent |
| final-a | 1 MiB | 256 | 1.000 [0.999, 1.001] equivalent | 1.002 [0.987, 1.017] equivalent |
| final-a | 1 MiB | 32 | 0.998 [0.993, 1.004] equivalent | 1.046 [0.987, 1.108] inconclusive |
| final-a | 1 MiB | 500 | 1.024 [0.999, 1.049] equivalent | 1.004 [0.994, 1.014] equivalent |
| final-a | 1 MiB | 8 | 0.920 [0.902, 0.938] different | 1.102 [1.077, 1.127] different |
| final-a | 16 MiB | 1 | 0.966 [0.926, 1.008] inconclusive | 1.049 [0.994, 1.108] inconclusive |
| final-a | 16 MiB | 128 | 1.001 [0.998, 1.003] equivalent | 1.009 [0.961, 1.059] inconclusive |
| final-a | 16 MiB | 32 | 1.000 [0.999, 1.001] equivalent | 0.994 [0.954, 1.034] equivalent |
| final-a | 16 MiB | 8 | 0.999 [0.999, 1.000] equivalent | 0.932 [0.887, 0.980] inconclusive |
| final-a | 64 KiB | 1 | 0.580 [0.557, 0.605] different | 1.696 [1.643, 1.750] different |
| final-a | 64 KiB | 128 | 0.379 [0.373, 0.384] different | 2.627 [2.569, 2.685] different |
| final-a | 64 KiB | 256 | 0.433 [0.425, 0.441] different | 2.250 [2.217, 2.283] different |
| final-a | 64 KiB | 32 | 0.401 [0.397, 0.405] different | 2.526 [2.507, 2.546] different |
| final-a | 64 KiB | 500 | 0.428 [0.425, 0.431] different | 2.307 [2.288, 2.326] different |
| final-a | 64 KiB | 8 | 0.590 [0.584, 0.597] different | 1.682 [1.665, 1.699] different |
| final-b | 1 KiB | 1 | 0.626 [0.594, 0.660] different | 1.600 [1.484, 1.725] different |
| final-b | 1 MiB | 1 | 0.740 [0.716, 0.765] different | 1.341 [1.311, 1.371] different |
| final-b | 128 MiB | 1 | 1.062 [0.960, 1.175] inconclusive | 0.945 [0.844, 1.057] inconclusive |
| final-b | 128 MiB | 32 | 1.005 [0.989, 1.022] equivalent | 0.980 [0.834, 1.150] inconclusive |
| final-b | 16 MiB | 1 | 0.935 [0.908, 0.963] inconclusive | 1.080 [1.044, 1.117] inconclusive |
| final-b | 500 MiB | 1 | 0.918 [0.835, 1.009] inconclusive | 1.077 [0.972, 1.193] inconclusive |
| final-b | 500 MiB | 16 | 0.987 [0.959, 1.016] equivalent | 1.109 [0.904, 1.359] inconclusive |
| final-b | 64 KiB | 1 | 0.573 [0.552, 0.595] different | 1.731 [1.673, 1.792] different |

## H4 — client CPU per request, paired difference (ms)

Thread CPU time (excludes GIL waiting), one worker.

| Batch | Op | Size | Comparison | Δ CPU ms/request [95% CI] |
|---|---|---|---|---|
| final-a | get | 1 MiB | P1-B1 | +0.115 [+0.020, +0.210] |
| final-a | get | 1 MiB | P1-B2 | +0.065 [+0.032, +0.097] |
| final-a | get | 1 MiB | P1-R1 | -1.445 [-1.507, -1.383] |
| final-a | get | 16 MiB | P1-B1 | +1.404 [+0.288, +2.519] |
| final-a | get | 16 MiB | P1-B2 | +0.648 [-0.912, +2.209] |
| final-a | get | 16 MiB | P1-R1 | -0.504 [-1.971, +0.962] |
| final-a | get | 64 KiB | P1-B1 | +0.056 [+0.023, +0.089] |
| final-a | get | 64 KiB | P1-B2 | +0.013 [+0.005, +0.022] |
| final-a | get | 64 KiB | P1-R1 | -1.542 [-1.559, -1.525] |
| final-a | put | 1 MiB | P1-B1 | -0.487 [-0.536, -0.438] |
| final-a | put | 1 MiB | P1-B2 | -0.028 [-0.083, +0.026] |
| final-a | put | 1 MiB | P1-R1 | -0.130 [-0.173, -0.088] |
| final-a | put | 16 MiB | P1-B1 | +0.697 [-1.269, +2.663] |
| final-a | put | 16 MiB | P1-B2 | +0.560 [-1.366, +2.485] |
| final-a | put | 16 MiB | P1-R1 | +0.695 [-1.566, +2.955] |
| final-a | put | 64 KiB | P1-B1 | +0.060 [+0.040, +0.080] |
| final-a | put | 64 KiB | P1-B2 | -0.033 [-0.056, -0.009] |
| final-a | put | 64 KiB | P1-R1 | -0.028 [-0.061, +0.005] |
| final-b | get | 1 KiB | P1-B1 | +0.042 [+0.019, +0.066] |
| final-b | get | 1 KiB | P1-B2 | +0.011 [-0.013, +0.036] |
| final-b | get | 1 KiB | P1-R1 | -1.394 [-1.432, -1.355] |
| final-b | get | 1 MiB | P1-B1 | +0.082 [+0.063, +0.101] |
| final-b | get | 1 MiB | P1-B2 | +0.048 [-0.002, +0.098] |
| final-b | get | 1 MiB | P1-R1 | -1.375 [-1.392, -1.358] |
| final-b | get | 128 MiB | P1-B1 | +3.795 [-8.606, +16.196] |
| final-b | get | 128 MiB | P1-B2 | +10.941 [-0.739, +22.621] |
| final-b | get | 128 MiB | P1-R1 | +8.236 [-5.429, +21.901] |
| final-b | get | 16 MiB | P1-B1 | +0.378 [-0.437, +1.193] |
| final-b | get | 16 MiB | P1-B2 | -0.045 [-0.743, +0.654] |
| final-b | get | 16 MiB | P1-R1 | -1.634 [-2.679, -0.589] |
| final-b | get | 500 MiB | P1-B1 | -0.603 [-19.519, +18.314] |
| final-b | get | 500 MiB | P1-B2 | -5.648 [-20.592, +9.296] |
| final-b | get | 500 MiB | P1-R1 | -41.000 [-85.673, +3.673] |
| final-b | get | 64 KiB | P1-B1 | +0.030 [+0.023, +0.036] |
| final-b | get | 64 KiB | P1-B2 | +0.005 [-0.002, +0.012] |
| final-b | get | 64 KiB | P1-R1 | -1.462 [-1.473, -1.451] |
| final-b | put | 1 KiB | P1-B1 | +0.049 [+0.034, +0.064] |
| final-b | put | 1 KiB | P1-B2 | -0.022 [-0.036, -0.009] |
| final-b | put | 1 KiB | P1-R1 | -0.041 [-0.058, -0.024] |
| final-b | put | 1 MiB | P1-B1 | -0.465 [-0.517, -0.412] |
| final-b | put | 1 MiB | P1-B2 | +0.027 [+0.001, +0.052] |
| final-b | put | 1 MiB | P1-R1 | -0.112 [-0.156, -0.069] |
| final-b | put | 128 MiB | P1-B1 | +1.593 [-1.881, +5.068] |
| final-b | put | 128 MiB | P1-B2 | -13.128 [-17.734, -8.523] |
| final-b | put | 128 MiB | P1-R1 | -9.125 [-19.154, +0.904] |
| final-b | put | 16 MiB | P1-B1 | -0.005 [-0.405, +0.395] |
| final-b | put | 16 MiB | P1-B2 | +0.033 [-0.372, +0.438] |
| final-b | put | 16 MiB | P1-R1 | -0.090 [-0.294, +0.113] |
| final-b | put | 500 MiB | P1-B1 | +6.447 [-7.549, +20.442] |
| final-b | put | 500 MiB | P1-B2 | -14.906 [-24.123, -5.689] |
| final-b | put | 500 MiB | P1-R1 | -13.478 [-26.269, -0.687] |
| final-b | put | 64 KiB | P1-B1 | +0.044 [+0.035, +0.052] |
| final-b | put | 64 KiB | P1-B2 | -0.035 [-0.048, -0.022] |
| final-b | put | 64 KiB | P1-R1 | -0.035 [-0.049, -0.021] |
| final-c | get | 1 KiB | P1-B1 | +0.066 [+0.045, +0.086] |
| final-c | get | 64 KiB | P1-B1 | +0.042 [+0.028, +0.055] |
| final-c | put | 1 KiB | P1-B1 | +0.062 [+0.020, +0.103] |
| final-c | put | 64 KiB | P1-B1 | +0.040 [+0.014, +0.066] |

## Hybrid P2 vs P1 (batch A, 1 MiB)

| Op | Workers | Throughput ratio P2/P1 | p50 ratio |
|---|---|---|---|
| get | 1 | 0.988 [0.981, 0.995] equivalent | 1.013 [1.000, 1.026] equivalent |
| get | 128 | 0.999 [0.995, 1.002] equivalent | 0.980 [0.961, 1.000] equivalent |
| get | 32 | 0.999 [0.992, 1.006] equivalent | 0.988 [0.888, 1.100] inconclusive |
| get | 500 | 1.024 [0.977, 1.072] inconclusive | 0.999 [0.994, 1.005] equivalent |
| get | 8 | 1.000 [0.999, 1.002] equivalent | 1.007 [0.997, 1.018] equivalent |
| put | 1 | 0.927 [0.913, 0.940] different | 1.080 [1.065, 1.095] different |
| put | 128 | 1.008 [0.990, 1.026] equivalent | 0.993 [0.974, 1.012] equivalent |
| put | 32 | 1.014 [1.000, 1.029] equivalent | 0.990 [0.978, 1.002] equivalent |
| put | 500 | 1.001 [0.976, 1.026] equivalent | 0.985 [0.959, 1.012] equivalent |
| put | 8 | 0.967 [0.963, 0.972] equivalent | 1.036 [1.029, 1.042] equivalent |

## N1 — bounded ML-KEM session amortisation (batch C, Sweep E)

ML-KEM operations per request, key-establishment time, and throughput/CPU paired against P1 in the same batch.

| Op | Size | Workers | B_max | KEM/request | KE µs N1 vs P1 | Throughput N1/P1 | Δ CPU ms/request |
|---|---|---|---|---|---|---|---|
| put | 1 KiB | 1 | 10 | 0.1000 | 10.6 vs 44.3 | 0.978 [0.926, 1.033] inconclusive | -0.022 [-0.050, +0.006] |
| put | 1 KiB | 1 | 100 | 0.0100 | 6.2 vs 44.3 | 0.842 [0.653, 1.084] inconclusive | -0.017 [-0.040, +0.006] |
| put | 1 KiB | 1 | 1000 | 0.0009 | 5.6 vs 44.3 | 0.885 [0.656, 1.193] inconclusive | -0.019 [-0.059, +0.021] |
| put | 1 KiB | 32 | 10 | 0.1000 | 21.9 vs 130.8 | 0.984 [0.779, 1.243] inconclusive | -0.045 [-0.087, -0.003] |
| put | 1 KiB | 32 | 100 | 0.0100 | 8.1 vs 130.8 | 0.876 [0.768, 1.000] inconclusive | -0.072 [-0.095, -0.048] |
| put | 1 KiB | 32 | 1000 | 0.0010 | 6.9 vs 130.8 | 0.957 [0.915, 1.001] inconclusive | -0.055 [-0.063, -0.046] |
| put | 1 KiB | 128 | 10 | 0.1000 | 40.4 vs 312.9 | 0.889 [0.685, 1.154] inconclusive | -0.092 [-0.191, +0.007] |
| put | 1 KiB | 128 | 100 | 0.0100 | 10.8 vs 312.9 | 0.953 [0.814, 1.115] inconclusive | -0.085 [-0.142, -0.028] |
| put | 1 KiB | 128 | 1000 | 0.0010 | 7.3 vs 312.9 | 0.966 [0.740, 1.262] inconclusive | -0.079 [-0.170, +0.011] |
| put | 64 KiB | 1 | 10 | 0.0999 | 10.8 vs 44.6 | 0.978 [0.921, 1.038] inconclusive | -0.014 [-0.058, +0.030] |
| put | 64 KiB | 1 | 100 | 0.0100 | 6.1 vs 44.6 | 0.983 [0.961, 1.005] equivalent | -0.032 [-0.049, -0.016] |
| put | 64 KiB | 1 | 1000 | 0.0009 | 5.6 vs 44.6 | 0.981 [0.946, 1.016] inconclusive | -0.018 [-0.042, +0.005] |
| put | 64 KiB | 32 | 10 | 0.1000 | 21.0 vs 124.5 | 0.955 [0.895, 1.018] inconclusive | -0.050 [-0.063, -0.037] |
| put | 64 KiB | 32 | 100 | 0.0100 | 8.4 vs 124.5 | 0.932 [0.825, 1.051] inconclusive | -0.067 [-0.090, -0.043] |
| put | 64 KiB | 32 | 1000 | 0.0009 | 7.0 vs 124.5 | 0.993 [0.887, 1.113] inconclusive | -0.051 [-0.070, -0.032] |
| put | 64 KiB | 128 | 10 | 0.1000 | 47.8 vs 273.6 | 1.025 [0.816, 1.289] inconclusive | -0.050 [-0.146, +0.045] |
| put | 64 KiB | 128 | 100 | 0.0100 | 11.7 vs 273.6 | 1.012 [0.848, 1.208] inconclusive | -0.055 [-0.140, +0.030] |
| put | 64 KiB | 128 | 1000 | 0.0010 | 7.3 vs 273.6 | 0.974 [0.879, 1.081] inconclusive | -0.071 [-0.117, -0.025] |
| get | 1 KiB | 1 | 10 | – | 9.6 vs 46.4 | 1.025 [0.968, 1.085] inconclusive | -0.053 [-0.080, -0.026] |
| get | 1 KiB | 1 | 100 | – | 5.4 vs 46.4 | 1.013 [0.966, 1.062] inconclusive | -0.054 [-0.080, -0.029] |
| get | 1 KiB | 1 | 1000 | – | 4.9 vs 46.4 | 1.013 [0.963, 1.065] inconclusive | -0.066 [-0.083, -0.049] |
| get | 1 KiB | 32 | 10 | – | 25.5 vs 185.7 | 1.037 [1.034, 1.040] equivalent | -0.063 [-0.066, -0.060] |
| get | 1 KiB | 32 | 100 | – | 8.1 vs 185.7 | 1.042 [1.041, 1.044] equivalent | -0.070 [-0.072, -0.068] |
| get | 1 KiB | 32 | 1000 | – | 6.2 vs 185.7 | 1.042 [1.039, 1.045] equivalent | -0.070 [-0.073, -0.067] |
| get | 1 KiB | 128 | 10 | – | 241.5 vs 1651.8 | 1.044 [1.041, 1.048] equivalent | -0.071 [-0.074, -0.067] |
| get | 1 KiB | 128 | 100 | – | 39.1 vs 1651.8 | 1.051 [1.048, 1.054] inconclusive | -0.081 [-0.083, -0.079] |
| get | 1 KiB | 128 | 1000 | – | 9.6 vs 1651.8 | 1.049 [1.047, 1.050] inconclusive | -0.080 [-0.082, -0.078] |
| get | 64 KiB | 1 | 10 | – | 9.7 vs 46.6 | 1.014 [0.961, 1.070] inconclusive | -0.031 [-0.039, -0.023] |
| get | 64 KiB | 1 | 100 | – | 5.3 vs 46.6 | 0.998 [0.935, 1.065] inconclusive | -0.030 [-0.052, -0.008] |
| get | 64 KiB | 1 | 1000 | – | 4.9 vs 46.6 | 0.978 [0.930, 1.028] inconclusive | -0.041 [-0.055, -0.027] |
| get | 64 KiB | 32 | 10 | – | 24.4 vs 168.6 | 1.033 [1.028, 1.038] equivalent | -0.061 [-0.063, -0.059] |
| get | 64 KiB | 32 | 100 | – | 8.1 vs 168.6 | 1.037 [1.034, 1.040] equivalent | -0.067 [-0.068, -0.065] |
| get | 64 KiB | 32 | 1000 | – | 6.4 vs 168.6 | 1.036 [1.031, 1.040] equivalent | -0.068 [-0.069, -0.066] |
| get | 64 KiB | 128 | 10 | – | 231.0 vs 1545.4 | 1.012 [0.999, 1.026] equivalent | -0.043 [-0.058, -0.029] |
| get | 64 KiB | 128 | 100 | – | 40.1 vs 1545.4 | 1.014 [1.005, 1.022] equivalent | -0.049 [-0.060, -0.038] |
| get | 64 KiB | 128 | 1000 | – | 9.7 vs 1545.4 | 1.021 [1.004, 1.037] equivalent | -0.058 [-0.077, -0.039] |

### Queue-aware vs fixed bound (open loop, 1 KiB PUT, 128 threads, B_max = 100)

| Offered req/s | Stable | Mean bound (aware vs fixed) | KEM/request (aware vs fixed) | p99 response ratio aware/fixed |
|---|---|---|---|---|
| 1,500 | yes | 18.4 vs 100 | 0.0557 vs 0.0100 | 1.024 [0.977, 1.073] inconclusive |
| 3,500 | yes | 31.9 vs 100 | 0.0343 vs 0.0100 | 0.942 [0.666, 1.332] inconclusive |
| 4,500 | no | 99.6 vs 100 | 0.0101 vs 0.0100 | overloaded (not compared) |
| 6,000 | no | 100.0 vs 100 | 0.0100 vs 0.0100 | overloaded (not compared) |

## RQ3 — offered load vs response time and the M/M/c model (batch C, Sweep D)

Capacity µ from the two most overloaded rates; c = round(µ·S0). Response time = queue wait + service. Unstable runs (below 97% of offered or mean wait ≥ 10 ms) get no prediction.

| Size | Mode | Offered | ρ | Achieved | Stable runs | Mean response ms | M/M/c ms | p99 ms | c |
|---|---|---|---|---|---|---|---|---|---|
| 1 KiB | B1 | 1,500 | 0.31 | 1,499 | 5/5 | 5.45 | 5.22 | 9.5 | 25 |
| 1 KiB | B1 | 3,000 | 0.63 | 3,007 | 5/5 | 5.43 | 5.24 | 11.4 | 25 |
| 1 KiB | B1 | 4,000 | 0.83 | 4,008 | 3/5 | – | – | – | 25 |
| 1 KiB | B1 | 4,500 | 0.94 | 4,130 | 0/5 | – | – | – | 25 |
| 1 KiB | B1 | 5,000 | 1.04 | 4,587 | 0/5 | – | – | – | 25 |
| 1 KiB | B1 | 6,000 | 1.25 | 4,751 | 0/5 | – | – | – | 25 |
| 1 KiB | B1 | 8,000 | 1.67 | 4,832 | 0/5 | – | – | – | 25 |
| 1 KiB | P1 | 1,500 | 0.31 | 1,506 | 5/5 | 5.46 | 5.24 | 9.6 | 25 |
| 1 KiB | P1 | 3,000 | 0.62 | 3,001 | 5/5 | 5.62 | 5.25 | 11.9 | 25 |
| 1 KiB | P1 | 4,000 | 0.83 | 4,001 | 0/5 | – | – | – | 25 |
| 1 KiB | P1 | 4,500 | 0.93 | 4,141 | 0/5 | – | – | – | 25 |
| 1 KiB | P1 | 5,000 | 1.03 | 4,397 | 0/5 | – | – | – | 25 |
| 1 KiB | P1 | 6,000 | 1.24 | 4,857 | 0/5 | – | – | – | 25 |
| 1 KiB | P1 | 8,000 | 1.65 | 4,814 | 0/5 | – | – | – | 25 |
| 64 KiB | B1 | 1,500 | 0.35 | 1,499 | 5/5 | 5.86 | 5.64 | 9.8 | 24 |
| 64 KiB | B1 | 2,500 | 0.58 | 2,500 | 5/5 | 5.66 | 5.64 | 10.6 | 24 |
| 64 KiB | B1 | 3,500 | 0.81 | 3,500 | 0/5 | – | – | – | 24 |
| 64 KiB | B1 | 4,000 | 0.93 | 3,921 | 0/5 | – | – | – | 24 |
| 64 KiB | B1 | 4,500 | 1.04 | 4,459 | 0/5 | – | – | – | 24 |
| 64 KiB | B1 | 5,000 | 1.16 | 4,378 | 0/5 | – | – | – | 24 |
| 64 KiB | B1 | 6,000 | 1.39 | 4,269 | 0/5 | – | – | – | 24 |
| 64 KiB | P1 | 1,500 | 0.35 | 1,502 | 5/5 | 5.40 | 5.18 | 8.8 | 22 |
| 64 KiB | P1 | 2,500 | 0.58 | 2,505 | 5/5 | 5.73 | 5.18 | 10.9 | 22 |
| 64 KiB | P1 | 3,500 | 0.81 | 3,505 | 3/5 | – | – | – | 22 |
| 64 KiB | P1 | 4,000 | 0.92 | 3,829 | 0/5 | – | – | – | 22 |
| 64 KiB | P1 | 4,500 | 1.04 | 4,443 | 0/5 | – | – | – | 22 |
| 64 KiB | P1 | 5,000 | 1.15 | 4,318 | 0/5 | – | – | – | 22 |
| 64 KiB | P1 | 6,000 | 1.38 | 4,347 | 0/5 | – | – | – | 22 |

