#requires -RunAsAdministrator
<#
.SYNOPSIS
  在 Windows 云主机上准备 FlowLens 长稳环境。

.DESCRIPTION
  设置时区、远程桌面断线策略、关闭自动重启类更新、按需安装 Npcap，
  并检查程序目录。默认只打印动作，加 -Apply 才真正修改。

.EXAMPLE
  .\deploy_cloud.ps1 -NpcapInstaller C:\Temp\npcap-1.10.exe -Apply
#>
param(
    [string]$AppDir = 'C:\FlowLens',
    [string]$NpcapInstaller = '',
    [string]$NpcapArgs = '/S /winpcap_mode=yes',
    [switch]$StartApp,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

function Invoke-Step {
    param([string]$Description, [scriptblock]$Action)
    if ($Apply) {
        Write-Host "[apply] $Description"
        & $Action
    }
    else {
        Write-Host "[dry-run] $Description"
    }
}

Write-Host "AppDir: $AppDir"
Write-Host "Apply : $Apply"

# 1) 时区
Invoke-Step '设置时区为 China Standard Time' {
    Set-TimeZone -Id 'China Standard Time'
}

# 2) 远程桌面会话：断线/空闲都不注销
Invoke-Step '设置 RDP 断线与会话空闲永不注销' {
    $path = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services'
    New-Item -Path $path -Force | Out-Null
    Set-ItemProperty -Path $path -Name 'MaxDisconnectionTime' -Value 0 -Type DWord
    Set-ItemProperty -Path $path -Name 'MaxIdleTime' -Value 0 -Type DWord
}

# 3) Windows 更新：不自动重启
Invoke-Step '关闭 Windows 更新自动重启' {
    $path = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
    New-Item -Path $path -Force | Out-Null
    Set-ItemProperty -Path $path -Name 'NoAutoRebootWithLoggedOnUsers' -Value 1 -Type DWord
}

# 4) Npcap
if ($NpcapInstaller) {
    if (-not (Test-Path $NpcapInstaller)) {
        throw "找不到 Npcap 安装包: $NpcapInstaller"
    }
    Invoke-Step "安装 Npcap（$NpcapInstaller）" {
        $process = Start-Process -FilePath $NpcapInstaller -ArgumentList $NpcapArgs -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "Npcap 安装返回 $($process.ExitCode)"
        }
    }
}

# 5) 程序目录
if (-not (Test-Path (Join-Path $AppDir 'FlowLens.exe'))) {
    Write-Warning "$AppDir 下没有 FlowLens.exe，请先复制整个 dist\FlowLens 目录。"
}

# 6) 启动
if ($StartApp) {
    Invoke-Step "启动 $AppDir\FlowLens.exe" {
        Start-Process -FilePath (Join-Path $AppDir 'FlowLens.exe') -WorkingDirectory $AppDir
    }
}

Write-Host ''
Write-Host '后续人工步骤：'
Write-Host '  1. 在界面中选择网卡，点击“开始抓包”，确认运行时长与报文数在增长。'
Write-Host '  2. 截图记录开始时间。'
Write-Host '  3. 直接关闭远程桌面窗口（不要注销）。'
Write-Host '  4. 24.5 小时后重连，截图、停止、把 data 目录拷回。'
