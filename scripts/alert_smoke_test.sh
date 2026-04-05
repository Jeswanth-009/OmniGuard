#!/usr/bin/env bash
set -euo pipefail

ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"
WEBHOOK_SERVICE="${WEBHOOK_SERVICE:-alert-webhook}"
EXPECTED_PATH="${EXPECTED_PATH:-/critical}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-90}"

alert_name="SyntheticCriticalTest_$(date +%s)"
start_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
end_time="$(date -u -d "+5 minutes" +%Y-%m-%dT%H:%M:%SZ)"

payload="[{\"labels\":{\"alertname\":\"${alert_name}\",\"severity\":\"critical\",\"service\":\"omniguard\"},\"annotations\":{\"summary\":\"Synthetic critical alert\",\"description\":\"Validation alert from smoke test\"},\"generatorURL\":\"http://localhost/ci-smoke\",\"startsAt\":\"${start_time}\",\"endsAt\":\"${end_time}\"}]"

status_code="$(curl -sS -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" -d "${payload}" "${ALERTMANAGER_URL}/api/v2/alerts")"
if [[ "${status_code}" != "200" ]]; then
  echo "Failed to submit synthetic alert. HTTP ${status_code}"
  exit 1
fi

echo "Submitted synthetic alert: ${alert_name}"

deadline=$((SECONDS + MAX_WAIT_SECONDS))
while (( SECONDS < deadline )); do
  logs="$(docker compose logs --tail=300 "${WEBHOOK_SERVICE}" 2>/dev/null || true)"
  if grep -q "${alert_name}" <<<"${logs}" && grep -q "POST ${EXPECTED_PATH} HTTP/1.1\" 200" <<<"${logs}"; then
    echo "Alert delivery verified in webhook logs for ${alert_name}"
    exit 0
  fi
  sleep 5
done

echo "Timed out waiting for webhook delivery for ${alert_name}"
docker compose logs --tail=300 "${WEBHOOK_SERVICE}" || true
exit 1
