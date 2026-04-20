#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/compose/docker-compose.yml"
ENV_FILE="$ROOT_DIR/compose/.env"

EXPERIMENT_NAME="${1:-baseline}"
EXPERIMENT_CONFIG_FILE="$ROOT_DIR/configs/experiments/${EXPERIMENT_NAME}.yaml"

if [[ ! -f "$EXPERIMENT_CONFIG_FILE" ]]; then
  echo "Unknown experiment config: $EXPERIMENT_CONFIG_FILE"
  echo "Available configs:"
  ls -1 "$ROOT_DIR/configs/experiments"
  exit 1
fi

"$ROOT_DIR/scripts/host/generate_certs.sh"

export EXPERIMENT_ID="${EXPERIMENT_NAME}-$(date +%Y%m%d-%H%M%S)"
export EXPERIMENT_CONFIG="/app/configs/experiments/${EXPERIMENT_NAME}.yaml"

echo "Running experiment: $EXPERIMENT_ID"

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans

rm -f "$ROOT_DIR/data/generated/generator.done"
rm -f "$ROOT_DIR/data/generated/sender.done"
rm -f "$ROOT_DIR/data/received/receiver.done"

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build video-generator stream-receiver stream-sender

sender_done="$ROOT_DIR/data/generated/sender.done"
receiver_done="$ROOT_DIR/data/received/receiver.done"
timeout_s="${RUN_TIMEOUT_SECONDS:-600}"
deadline=$((SECONDS + timeout_s))

while true; do
  if [[ -f "$sender_done" && -f "$receiver_done" ]]; then
    echo "Pipeline completed."
    break
  fi

  if (( SECONDS >= deadline )); then
    echo "Timed out waiting for pipeline completion after ${timeout_s}s."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs --no-color --tail=200 video-generator stream-sender stream-receiver || true
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans
    exit 1
  fi

  sleep 1
done

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop video-generator stream-sender stream-receiver

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm analyzer

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans

echo "Done. Outputs are in data/generated, data/logs, data/metrics, and data/reports."
