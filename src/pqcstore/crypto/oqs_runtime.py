"""Guarded import of liboqs-python.

liboqs-python silently downloads and builds the latest liboqs when it cannot
find the shared library. That would change the measured implementation, so we
refuse to import it unless the pinned build from scripts/install_liboqs.sh is
present (SoT amendment A11), and verify the version and algorithm afterwards.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from types import ModuleType

EXPECTED_LIBOQS_VERSION = "0.16.0"
KEM_NAME = "ML-KEM-768"


class LiboqsEnvironmentError(RuntimeError):
    pass


def install_path() -> Path:
    value = os.environ.get("OQS_INSTALL_PATH")
    if not value:
        raise LiboqsEnvironmentError(
            "OQS_INSTALL_PATH is not set; run `make liboqs` and use the Makefile targets"
        )
    return Path(value)


@cache
def oqs() -> ModuleType:
    prefix = install_path()
    libs = [p for d in ("lib", "lib64") for p in (prefix / d).glob("liboqs.*")]
    if not libs:
        raise LiboqsEnvironmentError(f"no liboqs shared library under {prefix}; run `make liboqs`")

    # Deferred import: loading oqs earlier could trigger its auto-install.
    import oqs as module

    version = module.oqs_version()
    if version != EXPECTED_LIBOQS_VERSION:
        raise LiboqsEnvironmentError(
            f"loaded liboqs {version}, expected {EXPECTED_LIBOQS_VERSION} (wrong library on the "
            "search path?)"
        )
    if KEM_NAME not in module.get_enabled_kem_mechanisms():
        raise LiboqsEnvironmentError(f"{KEM_NAME} is not enabled in this liboqs build")
    return module


def build_info() -> dict[str, str]:
    prefix = install_path()

    def read(name: str) -> str:
        path = prefix / name
        return path.read_text(encoding="utf-8").strip() if path.is_file() else "unknown"

    module = oqs()
    return {
        "liboqs_version": module.oqs_version(),
        "liboqs_commit": read(".commit"),
        "liboqs_cmake_flags": " ".join(read(".cmake-flags").split()),
        "liboqs_python_version": str(module.oqs_python_version()),
        "kem": KEM_NAME,
    }
