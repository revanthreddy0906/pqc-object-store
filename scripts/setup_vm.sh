#!/usr/bin/env bash
# Per-VM setup and run steps for the AWS testbed (called by infra/aws/pqc-aws.sh).
# Runs as the 'ubuntu' user inside ~/pqc on Ubuntu 24.04.
#
#   setup_vm.sh server              data disk, MinIO (source build), iperf3 server, idle watchdog
#   setup_vm.sh client              liboqs, venv, .env pointing at the server, full test suite
#   setup_vm.sh fio                 disk baseline on the server's MinIO data disk
#   setup_vm.sh baseline SERVER_IP  network baseline from the client
#   setup_vm.sh run SERVER_IP CONFIG...  run experiments in order, validate each, then stop this VM
#   setup_vm.sh profile CYCLES [SECONDS]  server: profile MinIO and the disk (perf, bio latency, strace)
#   setup_vm.sh watchdog server|client  (re)install the idle auto-stop
set -euo pipefail
cd "$(dirname "$0")/.."
ROLE=${1:?role}
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
export DEBIAN_FRONTEND=noninteractive

apt_install() {
  # `sudo` drops exported variables, so the non-interactive settings go on the command line.
  # iperf3 asks whether to start a daemon; answer no (setup_server runs its own unit).
  echo "iperf3 iperf3/start_daemon boolean false" | sudo debconf-set-selections
  sudo DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get install -y -qq \
    -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold "$@" </dev/null >/dev/null
}

setup_server() {
  : "${MINIO_ROOT_PASSWORD:?}"
  echo "[server] installing packages..."
  apt_install docker.io fio iperf3 jq curl
  sudo usermod -aG docker ubuntu

  install_data_disk_service   # format (if blank) and mount /data now and at every boot
  sudo systemctl start pqc-data-disk

  local tag image
  tag="$(grep -m1 '^ARG MINIO_TAG=' docker/minio.Dockerfile | cut -d= -f2)"
  image="pqc-minio:$tag"
  echo "[server] building MinIO $tag from source (5-10 minutes)..."
  sudo docker build -q -f docker/minio.Dockerfile -t "$image" . >/dev/null
  local uid; uid="$(sudo docker run --rm --entrypoint id "$image" -u)"
  echo "$uid" | sudo tee /etc/pqc-minio-uid >/dev/null
  sudo chown -R "$uid" /data
  sudo docker rm -f pqc-minio >/dev/null 2>&1 || true
  # Host networking: no Docker NAT between the benchmark and the store.
  sudo docker run -d --name pqc-minio --restart unless-stopped --network host \
    -v /data:/data \
    -e MINIO_ROOT_USER=pqcadmin -e MINIO_ROOT_PASSWORD="$MINIO_ROOT_PASSWORD" \
    -e MINIO_PROMETHEUS_AUTH_TYPE=public -e MINIO_API_DELETE_CLEANUP_INTERVAL=5s \
    "$image" >/dev/null
  for _ in $(seq 60); do curl -fsS http://127.0.0.1:9000/minio/health/live && break; sleep 1; done
  echo "MinIO $(sudo docker exec pqc-minio minio --version | head -1)"

  # Kernel counters of this host (dirty/write-back memory, disk I/O) for the client's sampler
  # and for the pause between runs. Reachable only from the client (security group).
  sudo docker rm -f pqc-node-exporter >/dev/null 2>&1 || true
  sudo docker run -d --name pqc-node-exporter --restart unless-stopped --network host --pid host \
    -v /:/host:ro,rslave quay.io/prometheus/node-exporter:v1.8.2 --path.rootfs=/host >/dev/null
  for _ in $(seq 30); do curl -fsS http://127.0.0.1:9100/metrics 2>/dev/null | grep -q '^node_memory_Dirty_bytes' && break; sleep 1; done
  curl -fsS http://127.0.0.1:9100/metrics | grep -c '^node_disk_written_bytes_total' \
    | xargs -I{} echo "node_exporter up ({} disks reported)"
  # Profiling tools for the storage-path attribution (best effort: not needed for normal runs).
  apt_install strace sysstat bpfcc-tools "linux-tools-$(uname -r)" 2>/dev/null \
    || echo "warning: some profiling tools could not be installed"

  # iperf3 server for the network baseline (reachable only from the client: security group).
  sudo tee /etc/systemd/system/iperf3-server.service >/dev/null <<'EOF'
[Unit]
Description=iperf3 server for the benchmark network baseline
After=network-online.target
[Service]
ExecStart=/usr/bin/iperf3 -s
Restart=always
[Install]
WantedBy=multi-user.target
EOF
  install_idle_watchdog server
  sudo systemctl daemon-reload
  sudo systemctl enable --now iperf3-server >/dev/null 2>&1
  echo "server ready"
}

# MinIO's data disk. An instance-store NVMe comes back blank after every stop/start, so this runs
# at each boot before Docker: format the disk if it has no filesystem, mount it on /data and give
# it to the MinIO user. An EBS data disk keeps its filesystem and is only mounted.
install_data_disk_service() {
  sudo tee /usr/local/bin/pqc-data-disk >/dev/null <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
mountpoint -q /data && exit 0
dev=""
for d in $(lsblk -dpno NAME,TYPE | awk '$2=="disk"{print $1}'); do
  # The root disk has mounted partitions; the data disk has none.
  [[ -z "$(lsblk -no MOUNTPOINT "$d" | tr -d '[:space:]')" ]] && dev=$d && break
done
[[ -n "$dev" ]] || { echo "pqc-data-disk: no unmounted data disk found" >&2; exit 1; }
blkid "$dev" >/dev/null 2>&1 || mkfs.xfs -q -f "$dev"
mkdir -p /data
mount -o noatime "$dev" /data
[[ -f /etc/pqc-minio-uid ]] && chown "$(cat /etc/pqc-minio-uid)" /data
echo "pqc-data-disk: $dev mounted on /data"
SCRIPT
  sudo chmod 755 /usr/local/bin/pqc-data-disk
  sudo tee /etc/systemd/system/pqc-data-disk.service >/dev/null <<'UNIT'
[Unit]
Description=Prepare and mount MinIO's data disk (instance store is blank after stop/start)
DefaultDependencies=no
After=local-fs.target
Before=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/pqc-data-disk
[Install]
WantedBy=multi-user.target
UNIT
  sudo systemctl daemon-reload
  sudo systemctl enable pqc-data-disk >/dev/null 2>&1
}

# Cost guard: stop the VM after 60 minutes without benchmark activity.
install_idle_watchdog() {
  local role=$1
  sudo tee /usr/local/bin/pqc-idle-check >/dev/null <<EOF
#!/usr/bin/env bash
# Stops this VM when nothing has happened for 60 minutes (role: $role).
state=/var/lib/pqc-idle; mkdir -p \$state
now=\$(date +%s)
busy=0
if [[ "$role" == server ]]; then
  # Real benchmark traffic moves far more than the ~KB this check itself adds to the counter
  # (the metrics request is itself network traffic, so "any change" never looks idle).
  bytes=\$(curl -fsS http://127.0.0.1:9000/minio/v2/metrics/node 2>/dev/null \
    | awk '/^minio_process_network_receive_bytes_total/{printf "%d", \$2}')
  last=\$(cat \$state/bytes 2>/dev/null || echo 0)
  echo "\${bytes:-0}" > \$state/bytes
  (( \${bytes:-0} - last > 10 * 1024 * 1024 )) && busy=1
else
  pgrep -f "pqcstore.cli bench" >/dev/null && busy=1
fi
if (( busy )) || [[ ! -f \$state/changed ]]; then
  echo "\$now" > \$state/changed
fi
changed=\$(cat \$state/changed 2>/dev/null || echo "\$now")
up=\$(cut -d. -f1 /proc/uptime)
if (( now - changed > 3600 && up > 3600 )); then
  logger "pqc-idle-check: idle for 60 minutes, stopping"
  shutdown -h now
fi
EOF
  sudo chmod 755 /usr/local/bin/pqc-idle-check
  sudo tee /etc/systemd/system/pqc-idle.service >/dev/null <<'EOF'
[Unit]
Description=Stop the VM when the benchmark has been idle for 60 minutes
[Service]
Type=oneshot
ExecStart=/usr/local/bin/pqc-idle-check
EOF
  sudo tee /etc/systemd/system/pqc-idle.timer >/dev/null <<'EOF'
[Unit]
Description=Idle check every 5 minutes
[Timer]
OnBootSec=10min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now pqc-idle.timer >/dev/null 2>&1
}

setup_client() {
  : "${MINIO_ROOT_PASSWORD:?}" "${SERVER_IP:?}"
  echo "[client] installing packages..."
  apt_install build-essential cmake git python3.12-venv python3.12-dev tmux iperf3 jq curl rsync
  echo "[client] building liboqs and the Python environment..."
  make liboqs venv
  umask 077
  cat > .env <<EOF
MINIO_ROOT_USER=pqcadmin
MINIO_ROOT_PASSWORD=$MINIO_ROOT_PASSWORD
PQC_S3_ENDPOINT=$SERVER_IP:9000
PQC_S3_SECURE=false
PQC_BUCKET=pqc-bench
EOF
  umask 022
  install_idle_watchdog client
  make doctor
  echo "Running the full test suite against the MinIO VM..."
  PQC_REQUIRE_MINIO=1 make test
  echo "client ready"
}

run_fio() {
  mkdir -p experiments/baselines
  sudo fio --name=minio-disk --directory=/data --size=4G --rw=randrw --rwmixread=70 --bs=1M \
    --ioengine=libaio --direct=1 --iodepth=16 --numjobs=4 --runtime=60 --time_based \
    --group_reporting --output-format=json > "experiments/baselines/fio-$STAMP.json"
  sudo rm -f /data/minio-disk.*
  jq -r '.jobs[0] | "fio: read \(.read.bw/1024|floor) MiB/s, write \(.write.bw/1024|floor) MiB/s"' \
    "experiments/baselines/fio-$STAMP.json"
}

run_baseline() {
  local server=${1:?server ip}
  mkdir -p experiments/baselines
  iperf3 -c "$server" -t 20 -P 4 -J > "experiments/baselines/iperf3-$STAMP.json"
  jq -r '"iperf3: \(.end.sum_received.bits_per_second/1e9*100|floor/100) Gbit/s"' \
    "experiments/baselines/iperf3-$STAMP.json"
  ping -c 20 -q "$server" | tail -1 | tee "experiments/baselines/ping-$STAMP.txt"
}

# Profile the storage path on the server while a workload runs. Each cycle is one window with
# sampling tools (low overhead) followed by one window with strace (high overhead: the runs
# that overlap an strace window are for attribution only, never for performance numbers).
run_profile() {
  local cycles=${1:?cycles} secs=${2:-45}
  local pid out; pid="$(sudo docker inspect -f '{{.State.Pid}}' pqc-minio)"
  out="experiments/profiles/$STAMP"; mkdir -p "$out"
  echo "profiling MinIO pid $pid: $cycles cycles of 2 x $secs s -> $out"
  for i in $(seq "$cycles"); do
    local tag; tag="$(printf '%02d' "$i")"
    echo "$(date -u +%s.%N) cycle $tag sampling start" >> "$out/windows.log"
    cp /proc/vmstat "$out/$tag-vmstat-before.txt"; sudo cat "/proc/$pid/io" > "$out/$tag-io-before.txt"
    cat /sys/fs/xfs/stats/stats > "$out/$tag-xfs-before.txt" 2>/dev/null || true
    iostat -x -t 1 "$secs" > "$out/$tag-iostat.txt" 2>&1 &
    sudo biolatency-bpfcc -D "$secs" 1 > "$out/$tag-biolatency.txt" 2>&1 &
    sudo perf record -F 99 -g -p "$pid" -o "/tmp/perf-$tag.data" -- sleep "$secs" >/dev/null 2>&1 || true
    wait
    sudo perf report -i "/tmp/perf-$tag.data" --stdio --no-children --sort symbol 2>/dev/null \
      | grep -v '^$' | head -120 > "$out/$tag-perf.txt" || true
    sudo rm -f "/tmp/perf-$tag.data"
    cp /proc/vmstat "$out/$tag-vmstat-after.txt"; sudo cat "/proc/$pid/io" > "$out/$tag-io-after.txt"
    cat /sys/fs/xfs/stats/stats > "$out/$tag-xfs-after.txt" 2>/dev/null || true
    echo "$(date -u +%s.%N) cycle $tag sampling end; strace start" >> "$out/windows.log"
    sudo timeout -s INT "$secs" strace -c -f -p "$pid" -o "$out/$tag-strace.txt" >/dev/null 2>&1 || true
    echo "$(date -u +%s.%N) cycle $tag strace end" >> "$out/windows.log"
  done
  sudo chown -R ubuntu "$out"
  echo "profiles written to $out"
}

run_experiment() {
  local config=${1:?config} server=${2:?server ip}
  export PQC_METRICS_URL="http://$server:9000/minio/v2/metrics/node"
  export PQC_NODE_URL="http://$server:9100/metrics"
  export PQC_GIT_COMMIT="$(cat GIT_COMMIT 2>/dev/null || echo unknown)"
  export OQS_INSTALL_PATH="$PWD/.local/liboqs"   # the Makefile sets this; direct calls must too
  # A previous run's pending auto-stop must not shut this run down.
  if [[ -f /tmp/pqc-autostop.pid ]]; then
    kill "$(cat /tmp/pqc-autostop.pid)" 2>/dev/null && echo "=== cancelled the previous run's auto-stop"
    rm -f /tmp/pqc-autostop.pid
  fi
  local stamp; stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  echo "=== $stamp starting $config (commit $PQC_GIT_COMMIT)"
  local status=0 out="$HOME/pqc-bench-$stamp.out"
  set +e   # capture the benchmark's own exit code (with `|| true` it would be lost)
  .venv/bin/python -u -m pqcstore.cli bench --config "$config" 2>&1 \
    | grep -v --line-buffered "faulthandler is disabled" | tee "$out"
  status=${PIPESTATUS[0]}
  set -e
  local run_dir; run_dir="$(sed -n 's/^wrote \(experiments\/[^ ]*\) (.*/\1/p' "$out" | tail -1)"
  if [[ -n "$run_dir" ]]; then
    .venv/bin/python -m pqcstore.cli validate "$run_dir" 2>&1 | grep -v "faulthandler" || true
  fi
  (( status == 0 )) || echo "=== bench FAILED with exit code $status (see the lines above)"
}

# Run several experiments back to back (unattended overnight batches), then stop the VM once.
run_experiments() {
  local server=${1:?server ip}; shift
  (( $# )) || { echo "usage: setup_vm.sh run SERVER_IP CONFIG..."; exit 1; }
  local config
  for config in "$@"; do
    [[ -f "$config" ]] || { echo "=== no such config: $config"; exit 1; }
  done
  for config in "$@"; do run_experiment "$config" "$server"; done
  echo "=== all $# experiment(s) finished"
  if [[ "${NO_AUTOSTOP:-0}" != 1 ]]; then
    # A scheduled `shutdown +N` blocks new logins at once; wait in the background instead so
    # the log can still be read during the grace period. A new run cancels this.
    echo "=== done; stopping this VM in 10 minutes (set NO_AUTOSTOP=1 to keep it running)"
    nohup bash -c 'sleep 600; sudo shutdown -h now' >/dev/null 2>&1 &
    echo $! > /tmp/pqc-autostop.pid
  fi
}

case "$ROLE" in
  watchdog) install_idle_watchdog "${2:?server|client}" ;;
  server) setup_server ;;
  client) setup_client ;;
  fio) run_fio ;;
  baseline) run_baseline "${2:-}" ;;
  run) shift; run_experiments "$@" ;;
  profile) run_profile "${2:-}" "${3:-45}" ;;
  *) echo "unknown role $ROLE"; exit 1 ;;
esac
