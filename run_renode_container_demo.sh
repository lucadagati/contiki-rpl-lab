#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${ROOT_DIR}/demo-runs"
LOG_FILE="${LOG_DIR}/container-demo.log"
TMP_RESC="/tmp/rpl-container-demo.resc"

mkdir -p "${LOG_DIR}"

echo "[1/3] Running Renode container demo..."
# On some macOS Docker Desktop setups, mounting directly from /Users can fail.
# Copy the script to /tmp and mount from there for better compatibility.
cp "${ROOT_DIR}/rpl-container-demo.resc" "${TMP_RESC}"
docker run --rm \
  -v "${TMP_RESC}:/work/rpl-container-demo.resc" \
  antmicro/renode:latest \
  renode --console --disable-gui /work/rpl-container-demo.resc \
  > "${LOG_FILE}" 2>&1

echo "[2/3] Parsing results..."
python3 "${ROOT_DIR}/parse_rpl_udp_logs.py" --combined "${LOG_FILE}"

echo "[3/3] Done."
echo "Log saved to: ${LOG_FILE}"

