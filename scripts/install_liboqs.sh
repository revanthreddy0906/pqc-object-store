#!/usr/bin/env bash
# Builds liboqs from a pinned release into a repo-local prefix (decision D12).
# liboqs-python finds it through OQS_INSTALL_PATH and never auto-downloads.
set -euo pipefail

LIBOQS_VERSION="${LIBOQS_VERSION:-0.16.0}"
PREFIX="${OQS_INSTALL_PATH:-$(pwd)/.local/liboqs}"
SRC="$(pwd)/.local/src/liboqs-${LIBOQS_VERSION}"

if [[ -f "${PREFIX}/.version" && "$(cat "${PREFIX}/.version")" == "${LIBOQS_VERSION}" ]]; then
  echo "liboqs ${LIBOQS_VERSION} already installed in ${PREFIX}"
  exit 0
fi

rm -rf "${SRC}"
mkdir -p "$(dirname "${SRC}")"
git clone --depth 1 --branch "${LIBOQS_VERSION}" https://github.com/open-quantum-safe/liboqs.git "${SRC}"

# OQS_DIST_BUILD: portable binary with runtime CPU-feature dispatch.
# OQS_USE_OPENSSL=OFF: liboqs uses its own SHA-2/SHA-3/AES, so results do not
# depend on which OpenSSL the host happens to provide.
CMAKE_FLAGS=(
  -DCMAKE_BUILD_TYPE=Release
  -DBUILD_SHARED_LIBS=ON
  -DOQS_BUILD_ONLY_LIB=ON
  -DOQS_DIST_BUILD=ON
  -DOQS_USE_OPENSSL=OFF
  -DCMAKE_INSTALL_PREFIX="${PREFIX}"
)
cmake -S "${SRC}" -B "${SRC}/build" "${CMAKE_FLAGS[@]}"
cmake --build "${SRC}/build" --parallel
cmake --install "${SRC}/build"

echo "${LIBOQS_VERSION}" > "${PREFIX}/.version"
git -C "${SRC}" rev-parse HEAD > "${PREFIX}/.commit"
printf '%s\n' "${CMAKE_FLAGS[@]}" > "${PREFIX}/.cmake-flags"
echo "Installed liboqs ${LIBOQS_VERSION} ($(cat "${PREFIX}/.commit")) into ${PREFIX}"
