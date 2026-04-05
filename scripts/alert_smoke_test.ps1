param(
    [string]$AlertmanagerUrl = "http://localhost:9093",
    [string]$WebhookService = "alert-webhook",
    [int]$TimeoutSeconds = 90
)

$alertName = "SyntheticCriticalTest_$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
$payload = @(
    @{
        labels = @{
            alertname = $alertName
            severity = "critical"
            service = "omniguard"
        }
        annotations = @{
            summary = "Synthetic critical alert"
            description = "Validation alert from smoke test"
        }
        generatorURL = "http://localhost/ci-smoke"
        startsAt = (Get-Date).ToUniversalTime().ToString("o")
        endsAt = (Get-Date).ToUniversalTime().AddMinutes(5).ToString("o")
    }
)

try {
    $body = ConvertTo-Json $payload -Depth 8
    Invoke-RestMethod -Method Post -Uri "$AlertmanagerUrl/api/v2/alerts" -ContentType "application/json" -Body $body | Out-Null
}
catch {
    Write-Error "Failed to submit synthetic alert: $($_.Exception.Message)"
    exit 1
}

Write-Host "Submitted synthetic alert: $alertName"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

while ((Get-Date) -lt $deadline) {
    $logs = docker compose logs --tail=300 $WebhookService 2>$null | Out-String
    if ($logs -match [Regex]::Escape($alertName) -and $logs -match 'POST /critical HTTP/1.1" 200') {
        Write-Host "Alert delivery verified in webhook logs for $alertName"
        exit 0
    }

    Start-Sleep -Seconds 5
}

Write-Error "Timed out waiting for webhook delivery for $alertName"
docker compose logs --tail=300 $WebhookService
exit 1
