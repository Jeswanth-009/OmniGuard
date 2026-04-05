# Alert Routing Validation

## Goal

Verify Alertmanager can route critical alerts to a webhook receiver end-to-end.

## Local Validation Setup

- Alertmanager receiver for critical alerts: `http://alert-webhook:8080/critical`
- Local webhook sink service: `alert-webhook` (`mendhak/http-https-echo`)

## Render Config from Environment Variables

Set environment variables and render Alertmanager config from template:

```powershell
$env:ALERT_WEBHOOK_URL = "https://example.com/default-alerts"
$env:CRITICAL_ALERT_WEBHOOK_URL = "https://example.com/critical-alerts"
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/REAL/WEBHOOK"
$env:PAGERDUTY_SERVICE_KEY = "REAL_PAGERDUTY_KEY"

./scripts/render-alertmanager-config.ps1
docker compose up -d --force-recreate alertmanager
```

## Validation Command

```powershell
$alert = @{
  labels = @{ alertname = 'SyntheticCriticalTest'; severity = 'critical'; service = 'omniguard' }
  annotations = @{ summary = 'Synthetic critical alert'; description = 'Validation alert from local test' }
  generatorURL = 'http://localhost/test'
  startsAt = (Get-Date).ToUniversalTime().ToString('o')
  endsAt = (Get-Date).ToUniversalTime().AddMinutes(5).ToString('o')
}

Invoke-RestMethod -Method Post -Uri http://localhost:9093/api/v2/alerts `
  -ContentType 'application/json' -Body (ConvertTo-Json @($alert) -Depth 6)

Start-Sleep -Seconds 40

docker compose logs --tail=120 alert-webhook
```

## Expected Evidence

Look for a `POST /critical` request in webhook logs with payload values:

- `receiver: critical-webhook`
- `status: firing`
- `labels.alertname: SyntheticCriticalTest`
- `labels.severity: critical`

Example observed line:

```text
"POST /critical HTTP/1.1" 200 ... "Alertmanager/0.26.0"
```

## Alerting Latency Objective

- Objective: operator notification path should complete within 5 minutes of alert firing.
- Local validation expectation: critical route group_wait is 10 seconds.
- Observed during synthetic test: alert start and webhook receipt were within tens of seconds.

Validation note:
- Use the synthetic test command and compare alert startsAt with webhook log timestamp.
- Pass condition for submission: delivery time <= 5 minutes.

## Production Routing Update

For automated local validation:

```powershell
./scripts/alert_smoke_test.ps1
```

For CI and Linux environments:

```bash
./scripts/alert_smoke_test.sh
```

If you manually edit routes in `observability/alertmanager.yml`, restart Alertmanager:

```powershell
docker compose up -d --force-recreate alertmanager
```
