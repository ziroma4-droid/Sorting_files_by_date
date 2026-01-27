# Сборка exe с гарантированным использованием venv (PySide6 и PyInstaller).
# Запуск: .\build_exe.ps1   или   .\build_exe.ps1 -Onedir

param(
    [switch]$Onedir = $false   # по умолчанию onefile
)

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = "$ProjectDir\venv\Scripts\python.exe"
$VenvPip   = "$ProjectDir\venv\Scripts\pip.exe"

Set-Location $ProjectDir

if (-not (Test-Path $VenvPython)) {
    Write-Host "ОШИБКА: venv не найден. Создайте: python -m venv venv" -ForegroundColor Red
    Write-Host "Затем: .\venv\Scripts\pip.exe install -r requirements.txt pyinstaller" -ForegroundColor Yellow
    exit 1
}

# Проверка PySide6 в venv
$hasPySide6 = & $VenvPython -c "import PySide6; print('ok')" 2>$null
if ($LASTEXITCODE -ne 0 -or $hasPySide6 -ne "ok") {
    Write-Host "ОШИБКА: PySide6 не установлен в venv." -ForegroundColor Red
    Write-Host "Выполните: .\venv\Scripts\pip.exe install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Установка PyInstaller в venv, если нет
$hasPyInstaller = & $VenvPython -m pyinstaller --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Устанавливаю PyInstaller в venv..."
    & $VenvPip install pyinstaller
}

if ($Onedir) {
    Write-Host 'Sbornka v papku (onedir)...' -ForegroundColor Cyan
    & $VenvPython -m PyInstaller SortingFilesByDate_onedir.spec
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'Gotovo. Zapusk: .\dist\SortingFilesByDate\SortingFilesByDate.exe' -ForegroundColor Green
    }
} else {
    Write-Host 'Sbornka v one exe (onefile)...' -ForegroundColor Cyan
    & $VenvPython -m PyInstaller SortingFilesByDate.spec
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'Gotovo. Zapusk: .\dist\SortingFilesByDate.exe' -ForegroundColor Green
    }
}
