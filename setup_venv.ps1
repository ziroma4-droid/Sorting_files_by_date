# Скрипт пересоздания venv и установки PySide6
# Запуск: правый клик -> "Выполнить с PowerShell" ИЛИ в терминале: .\setup_venv.ps1

$ProjectDir = "l:\Scripts\Sorting_files_by-_date"
Set-Location $ProjectDir

# 1. Удалить старый venv (если папка занята — закройте все терминалы и Cursor, затем удалите venv вручную в проводнике)
if (Test-Path "venv") {
    Write-Host "Удаляю старый venv..."
    try {
        Remove-Item -Recurse -Force venv -ErrorAction Stop
        Write-Host "venv удалён."
    } catch {
        Write-Host "ОШИБКА: Не удалось удалить venv. Закройте все терминалы и Cursor, удалите папку venv вручную, затем снова запустите этот скрипт."
        exit 1
    }
}

# 2. Создать новое виртуальное окружение
Write-Host "Создаю новое виртуальное окружение..."
python -m venv venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "Ошибка создания venv. Убедитесь, что python в PATH."
    exit 1
}

# 3. Активировать и установить зависимости
Write-Host "Устанавливаю PySide6..."
& "$ProjectDir\venv\Scripts\pip.exe" install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Ошибка установки зависимостей."
    exit 1
}

Write-Host ""
Write-Host "Готово. Запуск приложения:"
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host "  python main.py"
Write-Host ""
