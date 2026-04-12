# expose-mqtt-to-hyperv.ps1
#
# Open the Windows Firewall so Hyper-V VMs can reach Docker Desktop's
# mosquitto listener (port 1883).
#
# Docker Desktop binds `::: :1883` dual-stack, which already accepts IPv4
# traffic on every host interface — NO `netsh portproxy` rule is needed
# (and adding one actively breaks the flow: portproxy loops the traffic
# back to 127.0.0.1 where Docker's dual-stack listener picks it up again,
# triggering ConnectionAborted errors).
#
# This script therefore only ensures the firewall rule exists and, for
# safety, removes any stale portproxy rule for :1883.
#
# Must be run from an elevated PowerShell. Reversible via:
#   Remove-NetFirewallRule -Name 'TC-XAR-MQTT-1883'

param(
    [int]$MqttPort = 1883
)

# Remove any lingering portproxy rule for this port (from older setups).
netsh interface portproxy show v4tov4 | Select-String "^\S+\s+$MqttPort\s" | ForEach-Object {
    $addr = ($_ -split '\s+')[0]
    Write-Host "Removing stale netsh portproxy on $addr`:$MqttPort (not needed with Docker Desktop)"
    netsh interface portproxy delete v4tov4 listenport=$MqttPort listenaddress=$addr 2>$null | Out-Null
}

# Allow inbound MQTT traffic through Windows Firewall for all profiles
$ruleName = "TC-XAR-MQTT-$MqttPort"
Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -Confirm:$false
New-NetFirewallRule -Name $ruleName -DisplayName "TC XAR MQTT ($MqttPort) from Hyper-V" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort $MqttPort `
    -Profile Any | Out-Null

Write-Host "Firewall rule '$ruleName' added for TCP/$MqttPort inbound."
Write-Host ""
Write-Host "From the Hyper-V VM, verify with:"
Write-Host "  Test-NetConnection <your-hostname> -Port $MqttPort"
Write-Host "  (any local name / IP that resolves to the host works — Docker's"
Write-Host "   dual-stack listener on :::1883 covers all interfaces)"
