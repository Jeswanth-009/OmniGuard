param(
    [string]$TemplatePath = "observability/alertmanager.template.yml",
    [string]$OutputPath = "observability/alertmanager.yml"
)

$alertWebhook = if ($env:ALERT_WEBHOOK_URL) { $env:ALERT_WEBHOOK_URL } else { "http://alert-webhook:8080/alerts" }
$criticalWebhook = if ($env:CRITICAL_ALERT_WEBHOOK_URL) { $env:CRITICAL_ALERT_WEBHOOK_URL } else { "http://alert-webhook:8080/critical" }
$slackWebhook = if ($env:SLACK_WEBHOOK_URL) { $env:SLACK_WEBHOOK_URL } else { "https://hooks.slack.com/services/REPLACE/ME" }
$pagerDutyKey = if ($env:PAGERDUTY_SERVICE_KEY) { $env:PAGERDUTY_SERVICE_KEY } else { "YOUR_PAGERDUTY_KEY" }

if (!(Test-Path $TemplatePath)) {
    Write-Error "Template not found: $TemplatePath"
    exit 1
}

$content = Get-Content $TemplatePath -Raw
$content = $content.Replace("__ALERT_WEBHOOK_URL__", $alertWebhook)
$content = $content.Replace("__CRITICAL_ALERT_WEBHOOK_URL__", $criticalWebhook)
$content = $content.Replace("__SLACK_WEBHOOK_URL__", $slackWebhook)
$content = $content.Replace("__PAGERDUTY_SERVICE_KEY__", $pagerDutyKey)

Set-Content -Path $OutputPath -Value $content -NoNewline
Write-Host "Rendered Alertmanager config to $OutputPath"
Write-Host "Default webhook: $alertWebhook"
Write-Host "Critical webhook: $criticalWebhook"
