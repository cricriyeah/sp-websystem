param([string]$Bandera)
# Mantiene el equipo despierto mientras exista el archivo bandera (tope 14 h).
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
$fin = (Get-Date).AddHours(14)
while ((Test-Path $Bandera) -and ((Get-Date) -lt $fin)) {
    [W.P]::SetThreadExecutionState(0x80000001) | Out-Null  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    Start-Sleep -Seconds 30
}
[W.P]::SetThreadExecutionState(0x80000000) | Out-Null
