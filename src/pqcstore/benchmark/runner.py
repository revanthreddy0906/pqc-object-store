"""Benchmark runner (SoT §9, §10; decision D10).

One *run* executes one cell (mode, object size, concurrency, operation, loop)
with freshly started worker processes; a run is the unit of replication.
Concurrency N is realised as P = min(N, cores) processes with exactly N worker
threads spread across them. Workers warm up, then start together at a common
wall-clock instant. Every request, including failures and warm-up requests,
produces one JSONL record; analysis filters on `phase`.

Closed loop: each worker thread issues requests back to back.
Open loop: each process draws Poisson arrivals at its share of the target
rate; requests wait in a queue for a free thread (`queue_wait_ns`), and any
request not started by the end of the drain window is recorded as failed
(`error_class = "NotStarted"`), never dropped silently.
"""

from __future__ import annotations

import dataclasses
import gc
import hashlib
import itertools
import json
import multiprocessing as mp
import os
import platform
import queue
import random
import socket
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import psutil
import yaml

from pqcstore.benchmark.records import RAW, compress_raw, sha256_file
from pqcstore.crypto.modes import MODES, RecipientPrivate, RecipientPublic, generate_recipient

STAGE_FIELDS = ("ke_ns", "kdf_ns", "aead_ns", "ser_ns", "s3_ns", "total_ns")
DRAIN_GRACE_S = 30.0
CLIENT_BOUND_CPU_PCT = 90.0


@dataclass(frozen=True)
class Cell:
    mode: str
    size: int
    concurrency: int
    operation: str            # "put", "get" or "mix"
    loop: str = "closed"      # "closed" or "open"
    rate: float = 0.0         # open loop: total offered requests per second
    get_fraction: float = 0.7  # mix: share of GETs
    session_bmax: int = 0      # N1 only: hard object bound per session root
    session_tmax_s: float = 0.0  # N1 only: hard lifetime of a session root
    queue_aware: bool = False  # N1 only: adapt the bound to utilization within [bmin, bmax]
    session_bmin: int = 1

    def label(self) -> str:
        load = f"c{self.concurrency}" if self.loop == "closed" else f"r{self.rate:g}"
        mode = self.mode
        if mode == "N1":
            mode += f"{'q' if self.queue_aware else 'b'}{self.session_bmax}"
        return f"{mode}-{self.operation}-{self.size}-{load}"

    def session_policy(self):
        from pqcstore.crypto.session import SessionPolicy

        return SessionPolicy(self.session_bmax, self.session_tmax_s, self.queue_aware,
                             min(self.session_bmin, self.session_bmax))


@dataclass(frozen=True)
class RunPlan:
    experiment_id: str
    run_id: str
    block_id: str
    repetition: int
    cell: Cell
    bucket: str
    chunk_size: int
    part_size: int
    warmup_s: float
    duration_s: float
    min_measured_ops: int
    pool_bytes: int
    seed: int
    git_commit: str
    config_hash: str
    machine_id: str
    get_objects: tuple[tuple[str, str], ...] = ()
    put_prefix: str = ""


@dataclass
class RunOutcome:
    run_id: str
    exit_codes: list[int]
    records: int
    failures: int
    valid: bool
    note: str = ""
    client_bound: bool = False   # mean client host CPU > 90%: kept, but flagged (SoT §9.3)
    mean_client_host_cpu: float = 0.0


# --------------------------------------------------------------------------- workers

def _thread_counts(concurrency: int, processes: int) -> list[int]:
    base, extra = divmod(concurrency, processes)
    return [base + (1 if i < extra else 0) for i in range(processes)]


def _worker(plan: RunPlan, public: RecipientPublic, private: RecipientPrivate, worker_id: int,
            threads: int, rate_share: float, ready: Any, go: Any, start_at: Any,
            out_path: str) -> None:
    from pqcstore.benchmark.payload import HashingSink, PayloadPool
    from pqcstore.crypto import envelope
    from pqcstore.crypto.chunked_aead import IntegrityError
    from pqcstore.settings import Settings
    from pqcstore.storage import minio_store
    from pqcstore.storage.encrypted_store import EncryptedObjectStore

    cell = plan.cell
    store = minio_store.MinioStore(Settings.from_env(),
                                   minio_store.benchmark_http_client(threads + 2))
    estore = EncryptedObjectStore(store, part_size=plan.part_size)
    envelope.warm_up(cell.mode, public, private)
    busy = [0]  # in-flight requests in this process: the queue-aware policy's utilization
    busy_lock = threading.Lock()
    session = cache = None
    if cell.mode == "N1":
        from pqcstore.crypto.session import ReceiverSessionCache, SenderSession

        session = SenderSession(public.mlkem, cell.session_policy(),
                                utilization=lambda: busy[0] / max(1, threads))
        cache = ReceiverSessionCache(cell.session_policy())
    pool = PayloadPool(plan.pool_bytes)
    # Garbage-collection pauses would land inside random stage timers; collect now and
    # keep the collector off for the timed window (records hold no reference cycles).
    gc.collect()
    gc.freeze()
    gc.disable()
    ready.put(worker_id)
    go.wait()
    t0 = start_at.value
    warmup_end = t0 + plan.warmup_s
    end = warmup_end + plan.duration_s
    quota = -(-plan.min_measured_ops // max(1, cell.concurrency))  # per-thread share

    records: list[dict] = []
    written: list[tuple[str, str]] = []
    lock = threading.Lock()
    static = {
        "experiment_id": plan.experiment_id, "run_id": plan.run_id, "block_id": plan.block_id,
        "repetition": plan.repetition, "git_commit": plan.git_commit,
        "config_hash": plan.config_hash, "machine_id": plan.machine_id, "worker_id": worker_id,
        "pid": os.getpid(), "mode": cell.mode, "object_size_bytes": cell.size,
        "concurrency": cell.concurrency, "loop_type": cell.loop, "target_rate": cell.rate,
        "chunk_size": plan.chunk_size,
        "session_bmax": cell.session_bmax or None, "session_queue_aware": cell.queue_aware,
    }
    no_session = {"session_id": None, "session_seq": None, "session_bound": None,
                  "session_rotated": None}

    def one(rng: random.Random, thread_id: int, seq: int, operation: str,
            scheduled_ns: int | None) -> dict:
        record = {**static, "request_id": f"{worker_id}-{thread_id}-{seq}",
                  "thread_id": thread_id, "operation": operation}
        start_ns = time.time_ns()
        record["ts_start_utc_ns"] = start_ns
        record["queue_wait_ns"] = 0 if scheduled_ns is None else max(0, start_ns - scheduled_ns)
        record["phase"] = "warmup" if start_ns / 1e9 < warmup_end else "measure"
        record.update(no_session)
        cpu_start = time.thread_time_ns()
        wall_start = time.perf_counter_ns()
        with busy_lock:
            busy[0] += 1
        try:
            if operation == "put":
                key = f"{plan.put_prefix}w{worker_id}-t{thread_id}-{seq}"
                result = estore.put(plan.bucket, key, pool.reader(cell.size,
                                                                  rng.randrange(len(pool))),
                                    cell.size, public, plan.chunk_size, cell.mode, session)
                if result.details:
                    record.update(session_id=result.details["session_id"],
                                  session_seq=result.details["session_seq"],
                                  session_bound=result.details["session_bound"],
                                  session_rotated=result.details["session_rotated"])
                with lock:
                    written.append((key, result.identity.object_version))
                record["bytes_sent"] = result.stored_bytes + result.metadata_bytes
                record["bytes_received"] = 0
            else:
                key, version = rng.choice(plan.get_objects)
                sink = HashingSink()
                result = estore.get(plan.bucket, key, private, sink, version, mode=cell.mode,
                                    session_cache=cache)
                if sink.bytes_written != cell.size:
                    raise IntegrityError("short read")
                record["bytes_sent"] = 0
                record["bytes_received"] = result.stored_bytes + result.metadata_bytes
            record.update(result.stages.as_dict())
            record["metadata_bytes"] = result.metadata_bytes
            record["success"] = True
            record["error_class"] = ""
        except Exception as exc:  # noqa: BLE001 - every failure is a data point
            record.update(dict.fromkeys(STAGE_FIELDS, 0))
            record["total_ns"] = time.perf_counter_ns() - wall_start
            record.update(bytes_sent=0, bytes_received=0, metadata_bytes=0, success=False,
                          error_class=type(exc).__name__)
        with busy_lock:
            busy[0] -= 1
        record["cpu_thread_ns"] = time.thread_time_ns() - cpu_start
        return record

    def choose(rng: random.Random) -> str:
        if cell.operation != "mix":
            return cell.operation
        return "get" if rng.random() < cell.get_fraction else "put"

    def closed_thread(thread_id: int) -> None:
        rng = random.Random(f"{plan.seed}-{plan.run_id}-{worker_id}-{thread_id}")
        local, measured = [], 0
        time.sleep(max(0.0, t0 - time.time()))
        for seq in itertools.count():
            if time.time() >= end and measured >= quota:
                break
            record = one(rng, thread_id, seq, choose(rng), None)
            measured += record["phase"] == "measure"
            local.append(record)
        with lock:
            records.extend(local)

    def open_loop() -> None:
        work: queue.Queue = queue.Queue()
        stop_after = end + DRAIN_GRACE_S

        def consumer(thread_id: int) -> None:
            rng = random.Random(f"{plan.seed}-{plan.run_id}-{worker_id}-{thread_id}")
            local = []
            while (item := work.get()) is not None:
                seq, scheduled_ns = item
                if time.time() > stop_after:
                    local.append({**static, "request_id": f"{worker_id}-{thread_id}-{seq}",
                                  "thread_id": thread_id, "operation": choose(rng),
                                  "ts_start_utc_ns": scheduled_ns, "queue_wait_ns": 0,
                                  "phase": "measure" if scheduled_ns / 1e9 >= warmup_end
                                  else "warmup", **dict.fromkeys(STAGE_FIELDS, 0),
                                  "bytes_sent": 0, "bytes_received": 0, "metadata_bytes": 0,
                                  "cpu_thread_ns": 0, "success": False,
                                  "error_class": "NotStarted", **no_session})
                    continue
                local.append(one(rng, thread_id, seq, choose(rng), scheduled_ns))
            with lock:
                records.extend(local)

        pool_threads = [threading.Thread(target=consumer, args=(i,)) for i in range(threads)]
        for thread in pool_threads:
            thread.start()
        rng = random.Random(f"{plan.seed}-{plan.run_id}-{worker_id}-arrivals")
        next_arrival = t0
        for seq in itertools.count():
            next_arrival += rng.expovariate(rate_share)
            if next_arrival >= end:
                break
            time.sleep(max(0.0, next_arrival - time.time()))
            work.put((seq, int(next_arrival * 1e9)))
        for _ in pool_threads:
            work.put(None)
        for thread in pool_threads:
            thread.join()

    if cell.loop == "open":
        open_loop()
    else:
        workers = [threading.Thread(target=closed_thread, args=(i,)) for i in range(threads)]
        for thread in workers:
            thread.start()
        for thread in workers:
            thread.join()

    gc.enable()
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(record, separators=(",", ":")) + "\n" for record in records)
    for key, version in written:  # untimed cleanup of this run's PUT objects
        try:
            estore.delete_version(plan.bucket, key, version)
        except Exception:  # noqa: BLE001, S110 - leftovers are reported by `pqcstore gc`
            pass


# --------------------------------------------------------------------------- orchestration

def run_cell(plan: RunPlan, public: RecipientPublic, private: RecipientPrivate, run_dir: Path,
             metrics_url: str | None, max_processes: int | None = None) -> RunOutcome:
    from pqcstore.benchmark.samplers import ClientSampler, ServerSampler

    cell = plan.cell
    processes = max(1, min(cell.concurrency, max_processes or os.cpu_count() or 1))
    counts = _thread_counts(cell.concurrency, processes)
    ctx = mp.get_context("spawn")
    ready, go, start_at = ctx.Queue(), ctx.Event(), ctx.Value("d", 0.0)
    parts_dir = run_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    part_paths = [parts_dir / f"{plan.run_id}-w{i}.jsonl" for i in range(processes)]
    procs = [ctx.Process(target=_worker, args=(plan, public, private, i, counts[i],
                                               cell.rate / processes, ready, go, start_at,
                                               str(part_paths[i])))
             for i in range(processes)]
    for proc in procs:
        proc.start()
    note = ""
    try:
        for _ in procs:
            ready.get(timeout=120)
    except queue.Empty:
        note = "workers did not become ready"
    samplers = [ClientSampler(run_dir / "client-samples.csv", [p.pid for p in procs])]
    if metrics_url:
        samplers.append(ServerSampler(run_dir / "server-samples.csv", metrics_url))
    for sampler in samplers:
        sampler.run_id = plan.run_id
        sampler.start()
    start_at.value = time.time() + 0.5
    go.set()
    deadline = time.time() + plan.warmup_s + plan.duration_s + DRAIN_GRACE_S + 600
    for proc in procs:
        proc.join(timeout=max(1.0, deadline - time.time()))
        if proc.is_alive():
            proc.terminate()
            note = note or "worker timed out"
    for sampler in samplers:
        sampler.stop()

    records = failures = 0
    with (run_dir / "requests.jsonl").open("a", encoding="utf-8") as merged:
        for path in part_paths:
            if not path.exists():
                continue
            for line in path.open(encoding="utf-8"):
                merged.write(line)
                records += 1
                failures += '"success":false' in line
            path.unlink()
    exit_codes = [proc.exitcode if proc.exitcode is not None else -1 for proc in procs]
    valid = not note and all(code == 0 for code in exit_codes) and records > 0
    host_cpu = samplers[0].host_cpu
    mean_cpu = round(sum(host_cpu) / len(host_cpu), 1) if host_cpu else 0.0
    return RunOutcome(plan.run_id, exit_codes, records, failures, valid, note,
                      client_bound=mean_cpu > CLIENT_BOUND_CPU_PCT,
                      mean_client_host_cpu=mean_cpu)


def prepare_get_objects(plan_bucket: str, cell: Cell, public: RecipientPublic, count: int,
                        chunk_size: int, prefix: str) -> list[tuple[str, str]]:
    """Untimed setup for GET cells: write `count` objects of the cell's mode and size."""
    from pqcstore.benchmark.payload import PayloadPool
    from pqcstore.settings import Settings
    from pqcstore.storage.encrypted_store import EncryptedObjectStore
    from pqcstore.storage.minio_store import MinioStore

    estore = EncryptedObjectStore(MinioStore(Settings.from_env()))
    pool = PayloadPool(min(cell.size + 1, 64 * 1024 * 1024) if cell.size else 1024)
    session = None
    if cell.mode == "N1":
        from pqcstore.crypto.session import SenderSession

        session = SenderSession(public.mlkem, cell.session_policy())
    objects = []
    for i in range(count):
        result = estore.put(plan_bucket, f"{prefix}get-{i}", pool.reader(cell.size, i * 7919),
                            cell.size, public, chunk_size, cell.mode, session)
        objects.append((result.identity.object_key, result.identity.object_version))
    return objects


def delete_objects(bucket: str, objects: list[tuple[str, str]]) -> None:
    from pqcstore.settings import Settings
    from pqcstore.storage.encrypted_store import EncryptedObjectStore
    from pqcstore.storage.minio_store import MinioStore

    estore = EncryptedObjectStore(MinioStore(Settings.from_env()))
    for key, version in objects:
        estore.delete_version(bucket, key, version)


# --------------------------------------------------------------------------- experiments

@dataclass
class ExperimentConfig:
    experiment_id: str
    blocks: list[dict]
    bucket: str = "pqc-bench"
    chunk_size: int = 4 * 1024 * 1024
    part_size: int = 8 * 1024 * 1024
    repetitions: int = 1
    warmup_s: float = 10.0
    duration_s: float = 30.0
    min_measured_ops: int = 0
    get_objects: int = 8
    pool_bytes: int = 64 * 1024 * 1024
    seed: int = 1
    max_processes: int | None = None
    min_free_bytes: int = 5 * 2**30  # disk guard for client and server (checked per run)
    # After each run, wait (up to this long) until MinIO stops writing to disk, so that purging
    # the previous run's deleted objects does not overlap the next run (pilot finding).
    settle_max_s: float = 0.0
    server_metrics_url: str | None = "http://127.0.0.1:9000/minio/v2/metrics/node"
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> ExperimentConfig:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        # On the AWS testbed the storage server is remote: the setup script exports its
        # metrics URL so the same configs run locally and on the VMs.
        if os.environ.get("PQC_METRICS_URL"):
            known["server_metrics_url"] = os.environ["PQC_METRICS_URL"]
        return cls(**known, raw=raw)

    def cells(self) -> list[list[Cell]]:
        """Blocks of cells: one block per (size, load, operation); modes vary within."""
        blocks = []
        for block in self.blocks:
            loop = block.get("loop", "closed")
            loads = block["rates"] if loop == "open" else block["concurrency"]
            for size, load, operation in itertools.product(block["sizes"], loads,
                                                           block["operations"]):
                cells = []
                for mode in block["modes"]:
                    base = Cell(mode, size,
                                load if loop == "closed" else block.get("threads", 64),
                                operation, loop, float(load) if loop == "open" else 0.0,
                                block.get("get_fraction", 0.7))
                    if mode != "N1":
                        cells.append(base)
                        continue
                    for bmax, aware in itertools.product(block.get("session_bmax", [100]),
                                                         block.get("queue_aware", [False])):
                        cells.append(dataclasses.replace(
                            base, session_bmax=bmax,
                            session_tmax_s=float(block.get("session_tmax_s", 60)),
                            queue_aware=bool(aware), session_bmin=block.get("session_bmin", 1)))
                blocks.append(cells)
        for block in blocks:
            for cell in block:
                if cell.mode not in MODES:
                    raise ValueError(f"unknown mode {cell.mode}")
        return blocks


def _git_commit() -> str:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, check=True).stdout.strip()
        return commit + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        # Deployed from `git archive` (no .git): the provisioning step records the commit.
        return os.environ.get("PQC_GIT_COMMIT", "unknown")


def environment_info() -> dict[str, Any]:
    import cryptography
    import minio

    from pqcstore.crypto import oqs_runtime

    cpu_model = platform.processor()
    try:
        if platform.system() == "Darwin":
            cpu_model = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                       capture_output=True, text=True, check=False).stdout.strip()
        elif Path("/proc/cpuinfo").exists():
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    cpu_model = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "cpu_model": cpu_model,
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(),
        "ram_bytes": psutil.virtual_memory().total,
        "python": platform.python_version(),
        "cryptography": cryptography.__version__,
        "minio_py": minio.__version__,
        **oqs_runtime.build_info(),
    }


def run_experiment(config_path: Path, out_root: Path = Path("experiments"),
                   progress=print) -> tuple[Path, list[RunOutcome]]:
    from pqcstore.crypto import envelope

    config = ExperimentConfig.load(config_path)
    config_bytes = config_path.read_bytes()
    config_hash = hashlib.sha256(config_bytes).hexdigest()[:16]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = out_root / config.experiment_id / stamp
    run_dir.mkdir(parents=True)
    (run_dir / "config.yaml").write_bytes(config_bytes)

    envelope.warm_up()
    public, private = generate_recipient()  # untimed; RSA-4096 generation is slow
    ensure_bucket(config.bucket)  # a fresh or instance-store server starts empty
    commit = _git_commit()
    machine_id = hashlib.sha256(socket.gethostname().encode()).hexdigest()[:12]
    blocks = config.cells()
    manifest: dict[str, Any] = {
        "experiment_id": config.experiment_id, "started_utc": stamp, "git_commit": commit,
        "config_hash": config_hash, "machine_id": machine_id, "environment": environment_info(),
        "server_metrics_url": config.server_metrics_url, "seed": config.seed, "runs": [],
    }
    outcomes = []
    total = config.repetitions * sum(len(b) for b in blocks)
    def save_manifest() -> None:  # after every run, so an interruption loses nothing
        (run_dir / "run-manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                                   encoding="utf-8")

    stopped = None
    for repetition in range(1, config.repetitions + 1):
        order_rng = random.Random(f"{config.seed}-{repetition}")
        for block_index, block in enumerate(blocks):
            cells = block[:]
            order_rng.shuffle(cells)  # randomized mode order within the block (SoT §9.3)
            for cell in cells:
                if stopped is None:
                    stopped = disk_guard(run_dir, config.server_metrics_url,
                                         config.min_free_bytes)
                if stopped is not None:
                    break
                run_id = f"rep{repetition:02d}-b{block_index:03d}-{cell.label()}"
                prefix = f"bench/{config.experiment_id}/{stamp}/{run_id}/"
                get_objects: list[tuple[str, str]] = []
                started = time.time()
                try:
                    if cell.operation in ("get", "mix"):
                        get_objects = prepare_get_objects(config.bucket, cell, public,
                                                          config.get_objects, config.chunk_size,
                                                          prefix)
                    plan = RunPlan(config.experiment_id, run_id, f"b{block_index:03d}",
                                   repetition, cell, config.bucket, config.chunk_size,
                                   config.part_size, config.warmup_s, config.duration_s,
                                   config.min_measured_ops, config.pool_bytes, config.seed,
                                   commit, config_hash, machine_id, tuple(get_objects), prefix)
                    outcome = run_cell(plan, public, private, run_dir,
                                       config.server_metrics_url, config.max_processes)
                except Exception as exc:  # noqa: BLE001 - one broken run must not end the experiment
                    outcome = RunOutcome(run_id, [], 0, 0, False,
                                         f"setup/run error: {type(exc).__name__}: {exc}"[:300])
                finally:
                    try:
                        delete_objects(config.bucket, get_objects)
                    except Exception:  # noqa: BLE001, S110 - reported later by `pqcstore gc`
                        pass
                settled = settle(config.server_metrics_url, config.settle_max_s)
                outcomes.append(outcome)
                manifest["runs"].append({**asdict(outcome), "cell": asdict(cell),
                                         "started_unix": started,
                                         "seconds": round(time.time() - started, 2),
                                         "settle_s": settled})
                save_manifest()
                progress(f"[{len(outcomes)}/{total}] {run_id}: {outcome.records} requests, "
                         f"{outcome.failures} failed{'' if outcome.valid else ' INVALID'}"
                         f"{' (' + outcome.note + ')' if outcome.note else ''}"
                         f"{' [client-bound]' if outcome.client_bound else ''}")
    if stopped is not None:
        manifest["stopped_early"] = stopped
        progress(f"STOPPED EARLY: {stopped}")
    manifest["finished_utc"] = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    save_manifest()
    if (run_dir / RAW).exists():
        progress(f"compressing {RAW} ...")
        compress_raw(run_dir)
    write_checksums(run_dir)
    return run_dir, outcomes


def ensure_bucket(bucket: str) -> None:
    from pqcstore.settings import Settings
    from pqcstore.storage.minio_store import MinioStore

    MinioStore(Settings.from_env()).ensure_bucket(bucket)


def settle(metrics_url: str | None, max_s: float, quiet_bytes_per_s: float = 5 * 2**20,
           quiet_seconds: int = 2) -> float:
    """Wait until MinIO's disk writes stay below `quiet_bytes_per_s` for `quiet_seconds`
    consecutive seconds (or `max_s` passes). Returns the seconds waited."""
    if not metrics_url or max_s <= 0:
        return 0.0
    from pqcstore.benchmark.samplers import scrape_minio

    start = time.monotonic()
    quiet, last = 0, None
    while time.monotonic() - start < max_s:
        try:
            written = scrape_minio(metrics_url).get("io_write_bytes")
        except OSError:
            written = None
        if written is None:  # metric unavailable: fall back to a short fixed pause
            time.sleep(min(5.0, max_s))
            break
        if last is not None:
            quiet = quiet + 1 if written - last < quiet_bytes_per_s else 0
            if quiet >= quiet_seconds:
                break
        last = written
        time.sleep(1.0)
    return round(time.monotonic() - start, 1)


def plan_experiment(config_path: Path, hourly_usd: float, overhead_s: float = 5.0,
                    settle_s: float = 3.0) -> dict:
    """Runs, time and cost of an experiment before launching it. Overhead per run (setup,
    fixtures, cleanup) is calibrated on the pilot: 45 s wall time per 40 s timed run."""
    config = ExperimentConfig.load(config_path)
    cells = sum(len(block) for block in config.cells())
    runs = cells * config.repetitions
    per_run = config.warmup_s + config.duration_s + overhead_s + \
        (settle_s if config.settle_max_s > 0 else 0.0)
    hours = runs * per_run / 3600
    return {"cells": cells, "runs": runs, "seconds_per_run": per_run, "hours": round(hours, 1),
            "usd": round(hours * hourly_usd, 1)}


def disk_guard(run_dir: Path, metrics_url: str | None, min_free: int) -> str | None:
    """Return a reason to stop if the client disk or the server drive is nearly full.
    Under Docker Desktop the client-disk check is the one that matters: the server's
    drive metric reports the VM's disk, not the host's."""
    import shutil

    free = shutil.disk_usage(run_dir).free
    if free < min_free:
        return f"client disk has {free / 2**30:.1f} GiB free (< {min_free / 2**30:.1f} GiB)"
    if metrics_url:
        from pqcstore.benchmark.samplers import scrape_minio

        try:
            server_free = scrape_minio(metrics_url).get("drive_free_bytes")
        except OSError:
            server_free = None
        if server_free is not None and server_free < min_free:
            return (f"server drive has {server_free / 2**30:.1f} GiB free "
                    f"(< {min_free / 2**30:.1f} GiB)")
    return None


def write_checksums(run_dir: Path) -> None:
    lines = []
    for path in sorted(p for p in run_dir.iterdir() if p.is_file() and p.name != "checksums.sha256"):
        lines.append(f"{sha256_file(path)}  {path.name}")  # streamed: files reach tens of GB
    (run_dir / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
