# Simulated Incident RCA

## Incident Summary

- Incident Type: Alertmanager routing failure during alert-routing configuration update.
- Impact: Alert notifications were not delivered while Alertmanager container restarted continuously.
- Severity: High (loss of alert delivery path).
- Detection Method: docker compose ps and alertmanager container logs.

## Timeline (UTC)

1. Configuration change introduced unsupported Alertmanager runtime flag.
2. Alertmanager entered restart loop.
3. Logs showed startup failure due to unknown flag.
4. Unsupported flag was removed.
5. Alertmanager restarted healthy.
6. Synthetic critical alert was sent and verified at webhook receiver.

## Root Cause

Primary cause:
- An unsupported Alertmanager command flag was added in runtime configuration.

Contributing factors:
- Version-specific runtime flags were not validated before deployment.
- Alert delivery smoke test was not yet automated at that moment.

## Evidence

- Alertmanager startup and health config: docker-compose.yml
- Alert route definitions: observability/alertmanager.yml
- Alert delivery validation procedure: docs/runbooks/alert-routing-validation.md
- Smoke test automation: scripts/alert_smoke_test.ps1 and scripts/alert_smoke_test.sh

## Customer/User Impact

- During the restart loop window, alerts could be missed.
- Service traffic path itself remained available; impact was incident-response visibility.

## Corrective Actions Taken

1. Removed unsupported runtime flag from Alertmanager startup configuration.
2. Stabilized local alert receiver and validated healthy status.
3. Added automated alert smoke test scripts.
4. Added CI resilience smoke job to verify alert delivery path on pipeline runs.

## Preventive Actions

1. Keep Alertmanager config generated from template using supported settings.
2. Validate alert path using synthetic alert before and after routing changes.
3. Keep resilience-smoke CI job mandatory in summary gate.

## Recovery Verification

- Alertmanager health endpoint reports healthy.
- Synthetic critical alert is observed at receiver path /critical.
- Alert delivery smoke test completes successfully.
