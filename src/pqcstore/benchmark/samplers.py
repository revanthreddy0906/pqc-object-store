"""1 Hz resource samplers for the client (load generator) and the server (SoT §8.3).

Client: CPU and RSS of the benchmark worker processes (psutil) plus host CPU
and network counters. Server: MinIO's own Prometheus node metrics, scraped over
HTTP, so the same sampler works for the dev container and a remote Linux VM.
When a Prometheus node_exporter runs on the server host (the AWS testbed), its
kernel counters are sampled too: dirty and write-back memory, disk writes and
I/O time, and I/O pressure. They attribute storage bottlenecks and drive the
pause between runs (runner.settle).
"""

from __future__ import annotations

import csv
import threading
import time
import urllib.request
from pathlib import Path

import psutil

CLIENT_FIELDS = ["run_id", "ts_utc_ns", "proc_cpu_pct", "host_cpu_pct", "logical_cores",
                 "proc_rss_bytes", "host_mem_used_bytes", "net_tx_bytes", "net_rx_bytes",
                 "load_avg_1m"]
NODE_FIELDS = ["dirty_bytes", "writeback_bytes", "disk_written_bytes", "disk_writes",
               "disk_write_time_s", "disk_io_time_s", "disk_io_now", "io_pressure_s",
               "cpu_iowait_s"]
SERVER_FIELDS = ["run_id", "ts_utc_ns", "proc_cpu_pct", "proc_cpu_seconds", "proc_rss_bytes",
                 "net_rx_bytes", "net_tx_bytes", "drive_free_bytes", "io_write_bytes", "scrape_ok",
                 *NODE_FIELDS, "node_ok"]
SERVER_METRICS = {
    "minio_process_cpu_seconds_total": "proc_cpu_seconds",
    "minio_process_resident_memory_bytes": "proc_rss_bytes",
    "minio_process_network_receive_bytes_total": "net_rx_bytes",
    "minio_process_network_transmit_bytes_total": "net_tx_bytes",
    "minio_node_drive_free_bytes": "drive_free_bytes",
    "minio_node_io_wchar_bytes": "io_write_bytes",
}


# node_exporter metric -> (field, label filter); values are summed over matching series.
_REAL_DISK = ("nvme", "xvd", "sd", "vd")
NODE_METRICS = {
    "node_memory_Dirty_bytes": ("dirty_bytes", None),
    "node_memory_Writeback_bytes": ("writeback_bytes", None),
    "node_disk_written_bytes_total": ("disk_written_bytes", "disk"),
    "node_disk_writes_completed_total": ("disk_writes", "disk"),
    "node_disk_write_time_seconds_total": ("disk_write_time_s", "disk"),
    "node_disk_io_time_seconds_total": ("disk_io_time_s", "disk"),
    "node_disk_io_now": ("disk_io_now", "disk"),
    "node_pressure_io_waiting_seconds_total": ("io_pressure_s", None),
    "node_cpu_seconds_total": ("cpu_iowait_s", "iowait"),
}


def scrape_node(node_url: str, timeout: float = 2.0) -> dict[str, float]:
    """Kernel counters of the server host from a Prometheus node_exporter."""
    with urllib.request.urlopen(node_url, timeout=timeout) as response:
        text = response.read().decode("utf-8", "replace")
    values: dict[str, float] = {}
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        series, _, value = line.rpartition(" ")
        name, _, labels = series.partition("{")
        spec = NODE_METRICS.get(name)
        if spec is None:
            continue
        field, kind = spec
        if kind == "disk":
            device = labels.partition('device="')[2].partition('"')[0]
            if not device.startswith(_REAL_DISK):
                continue
        elif kind == "iowait" and 'mode="iowait"' not in labels:
            continue
        values[field] = values.get(field, 0.0) + float(value)
    return values


def scrape_minio(metrics_url: str, timeout: float = 2.0) -> dict[str, float]:
    with urllib.request.urlopen(metrics_url, timeout=timeout) as response:
        text = response.read().decode("utf-8", "replace")
    values = {}
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        name, _, value = line.rpartition(" ")
        name = name.split("{", 1)[0]  # drop labels, e.g. drive="/data"
        if name in SERVER_METRICS:
            values[SERVER_METRICS[name]] = float(value)
    return values


class _Sampler(threading.Thread):
    def __init__(self, path: Path, fields: list[str], interval: float) -> None:
        super().__init__(daemon=True)
        self._handle = path.open("a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._handle, fieldnames=fields)
        if path.stat().st_size == 0:
            self._writer.writeheader()
        self._interval = interval
        self._stop_event = threading.Event()
        self.run_id = ""

    def run(self) -> None:
        self.prime()
        next_tick = time.monotonic()
        while not self._stop_event.is_set():
            next_tick += self._interval
            self._stop_event.wait(max(0.0, next_tick - time.monotonic()))
            row = self.sample()
            if row is not None:
                self._writer.writerow({"run_id": self.run_id, "ts_utc_ns": time.time_ns(), **row})

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=5)
        self._handle.close()

    def prime(self) -> None: ...

    def sample(self) -> dict | None: ...


class ClientSampler(_Sampler):
    def __init__(self, path: Path, pids: list[int], interval: float = 1.0) -> None:
        super().__init__(path, CLIENT_FIELDS, interval)
        self._procs = [psutil.Process(pid) for pid in pids]
        self.host_cpu: list[float] = []  # kept for the client-bound flag (SoT §9.3)

    def prime(self) -> None:
        psutil.cpu_percent(None)
        for proc in self._procs:
            try:
                proc.cpu_percent(None)
            except psutil.Error:
                pass

    def sample(self) -> dict:
        cpu = rss = 0.0
        for proc in self._procs:
            try:
                cpu += proc.cpu_percent(None)
                rss += proc.memory_info().rss
            except psutil.Error:  # a worker exited between ticks
                pass
        net = psutil.net_io_counters()
        host_cpu = psutil.cpu_percent(None)
        self.host_cpu.append(host_cpu)
        return {
            "proc_cpu_pct": round(cpu, 1),  # percent of one core, summed over workers
            "host_cpu_pct": host_cpu,
            "logical_cores": psutil.cpu_count(),
            "proc_rss_bytes": int(rss),
            "host_mem_used_bytes": psutil.virtual_memory().used,
            "net_tx_bytes": net.bytes_sent,
            "net_rx_bytes": net.bytes_recv,
            "load_avg_1m": psutil.getloadavg()[0],
        }


class ServerSampler(_Sampler):
    def __init__(self, path: Path, metrics_url: str, interval: float = 1.0,
                 node_url: str | None = None) -> None:
        super().__init__(path, SERVER_FIELDS, interval)
        self._url = metrics_url
        self._node_url = node_url
        self._last: tuple[float, float] | None = None

    def _node(self) -> dict:
        if not self._node_url:
            return {}
        try:
            return {**scrape_node(self._node_url), "node_ok": 1}
        except (OSError, ValueError):
            return {"node_ok": 0}

    def sample(self) -> dict:
        now = time.monotonic()
        try:
            values = scrape_minio(self._url)
        except OSError:
            return {"scrape_ok": 0, **self._node()}
        cpu_pct = None
        if self._last is not None and "proc_cpu_seconds" in values:
            last_time, last_cpu = self._last
            cpu_pct = round(100 * (values["proc_cpu_seconds"] - last_cpu) / (now - last_time), 1)
        if "proc_cpu_seconds" in values:
            self._last = (now, values["proc_cpu_seconds"])
        return {**values, "proc_cpu_pct": cpu_pct, "scrape_ok": 1, **self._node()}
