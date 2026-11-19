param(
    [switch]$SelfTest
)

$ErrorActionPreference = "Stop"
$env:QT_QPA_PLATFORM = "offscreen"
$exe = "E:\CN_work\dist\NetworkTrafficAnalyzer\NetworkTrafficAnalyzer.exe"
$arguments = @()
if ($SelfTest) {
    $arguments += "--self-test"
    $env:PACKET_ANALYZER_SELF_TEST = "1"
    Remove-Item -LiteralPath "E:\CN_work\data\self_test.json" -Force -ErrorAction SilentlyContinue
}
if ($arguments.Count -gt 0) {
    $process = Start-Process -FilePath $exe -ArgumentList $arguments -WindowStyle Hidden -WorkingDirectory "E:\CN_work" -PassThru
} else {
    $process = Start-Process -FilePath $exe -WindowStyle Hidden -WorkingDirectory "E:\CN_work" -PassThru
}
if ($SelfTest) {
    $process | Wait-Process -Timeout 30 -ErrorAction SilentlyContinue
    $process.Refresh()
    Write-Output ("alive=" + (-not $process.HasExited))
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    } else {
        Write-Output ("exit=" + $process.ExitCode)
    }
} else {
    Start-Sleep -Seconds 6
    $process.Refresh()
    Write-Output ("alive=" + (-not $process.HasExited))
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    } else {
        Write-Output ("exit=" + $process.ExitCode)
    }
}
if ($SelfTest -and (Test-Path -LiteralPath "E:\CN_work\data\self_test.json")) {
    Get-Item -LiteralPath "E:\CN_work\data\self_test.json" | Select-Object LastWriteTime,Length | Format-List
    Get-Content -LiteralPath "E:\CN_work\data\self_test.json"
}
