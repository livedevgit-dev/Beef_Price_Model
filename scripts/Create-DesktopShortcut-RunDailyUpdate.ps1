# Beef_Price_Model 바탕화면 바로가기: run_daily_update.bat 실행
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BatPath = Join-Path $ProjectRoot "run_daily_update.bat"
if (-not (Test-Path -LiteralPath $BatPath)) {
    Write-Error "찾을 수 없음: $BatPath"
}

$Desktop = [Environment]::GetFolderPath("Desktop")
# 한글 파일명은 일부 환경에서 인코딩 오류가 나므로 ASCII 이름 사용 (바로가기 이름은 탐색기에서 바꿀 수 있음)
$LinkPath = Join-Path $Desktop "Beef_Daily_Update.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($LinkPath)
$shortcut.TargetPath = $BatPath
$shortcut.WorkingDirectory = $ProjectRoot
$shortcut.WindowStyle = 1
$shortcut.Description = "Beef_Price_Model run_daily_update (데이터 수집 파이프라인)"
$shortcut.Save()

Write-Host "바로가기 생성: $LinkPath"
