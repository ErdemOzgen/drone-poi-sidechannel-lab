#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

required_files=(
  "$ROOT_DIR/data/generated/frame_metadata.csv"
  "$ROOT_DIR/data/logs/sender_log.csv"
  "$ROOT_DIR/data/logs/receiver_log.csv"
  "$ROOT_DIR/data/metrics/traffic_timeseries.csv"
  "$ROOT_DIR/data/reports/final_report.md"
  "$ROOT_DIR/data/reports/stimulus_overlay.png"
)

missing=0
for f in "${required_files[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing: $f"
    missing=1
  else
    echo "OK: $f"
  fi
done

if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

echo "All expected outputs are present."
