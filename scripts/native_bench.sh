#!/usr/bin/env bash
# Batch N (SoT v1.14): randomized complete blocks of the native reader on 64 KiB GET.
#   native_bench.sh BINARY FIXTURE OUT_JSONL REPETITIONS SEED
# Cells: 1 core / 128 workers (client saturated by construction), 16 cores / 128 workers and
# 16 cores / 500 workers. Each repetition runs every cell once, in shuffled order, and within a
# cell every mode once, in shuffled order. One JSON line per run.
set -euo pipefail
BIN=${1:?binary}; FIXTURE=${2:?fixture}; OUT=${3:?output}; REPS=${4:-10}; SEED=${5:-20261022}
set -a; source .env; set +a
: > "$OUT"
total=$((REPS * 9)); n=0
for rep in $(seq 1 "$REPS"); do
  for cell in $(printf '1:128\n16:128\n16:500\n' | shuf --random-source=<(openssl enc -aes-256-ctr -pass pass:"$SEED-$rep" -nosalt </dev/zero 2>/dev/null)); do
    cores=${cell%%:*}; workers=${cell##*:}
    for mode in $(printf 'B2\nP1\nP3\n' | shuf --random-source=<(openssl enc -aes-256-ctr -pass pass:"$SEED-$rep-$cell" -nosalt </dev/zero 2>/dev/null)); do
      n=$((n + 1))
      if [[ "$cores" == 1 ]]; then pin=(taskset -c 2); else pin=(); fi
      line=$(GOMAXPROCS="$cores" "${pin[@]}" "$BIN" -fixture "$FIXTURE" -mode "$mode" -workers "$workers" \
             -label "rep=$rep,cores=$cores")
      echo "$line" >> "$OUT"
      echo "[$n/$total] rep$rep cores=$cores workers=$workers $mode: $(echo "$line" | grep -o '"ops_per_s":[0-9.]*') $(echo "$line" | grep -o '"failures":[0-9]*') $(echo "$line" | grep -o '"client_cores":[0-9.]*')"
      sleep 5
    done
  done
done
sha256sum "$OUT" > "$OUT.sha256"
echo "wrote $OUT ($n runs)"
