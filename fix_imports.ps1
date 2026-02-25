# ============================================================
# fix_imports.ps1
# Автоматическая замена импортов после реструктуризации
# Запускать из корня проекта: Babykea_Bot(alpha)/
# ============================================================

Write-Host "=== Начинаю замену импортов ===" -ForegroundColor Cyan

# Словарь замен (порядок ВАЖЕН — длинные пути первыми!)
$replacements = [ordered]@{
    # --- handlers (конкретные файлы — первыми) ---
    'app.handlers.for_user'          = 'app.platforms.telegram.handlers.user_handlers'
    'app.handlers.for_quiz'          = 'app.platforms.telegram.handlers.quiz_handlers'
    'app.handlers.keyboards'         = 'app.platforms.telegram.keyboards'
    'app.handlers.'                  = 'app.platforms.telegram.handlers.'

    # --- comands_menu → platforms.telegram.handlers ---
    'app.comands_menu.standard_cmds' = 'app.platforms.telegram.handlers.standard_cmds'
    'app.comands_menu.info_cmds'     = 'app.platforms.telegram.handlers.info_cmds'
    'app.comands_menu.ai_cmds'       = 'app.platforms.telegram.handlers.ai_cmds'
    'app.comands_menu.crud_cmds'     = 'app.platforms.telegram.handlers.crud_cmds'
    'app.comands_menu.help_cmds'     = 'app.platforms.telegram.handlers.help_cmds'
    'app.comands_menu.master_cmd'    = 'app.platforms.telegram.handlers.master_cmd'
    'app.comands_menu.email_for_menu'= 'app.platforms.telegram.handlers.email_for_menu'
    'app.comands_menu.states'        = 'app.platforms.telegram.handlers.states'
    'app.comands_menu'               = 'app.platforms.telegram.handlers'

    # --- payments (конкретные файлы — первыми) ---
    'app.payments.payment_routes'           = 'app.web.webhooks'
    'app.payments.security_webhook_YooKassa'= 'app.web.security_webhook'
    'app.payments.yookassa_client'          = 'app.core.services.yookassa_client'
    'app.payments.pay_config'               = 'app.core.services.pay_config'
    'app.payments.'                         = 'app.core.services.'

    # --- posting ---
    'app.posting.'                   = 'app.platforms.telegram.posting.'

    # --- middlewares ---
    'app.middlewares.'               = 'app.platforms.telegram.middlewares.'

    # --- openai_assistant ---
    'app.openai_assistant.'          = 'app.core.openai_assistant.'

    # --- quiz ---
    'app.quiz.'                      = 'app.core.quiz.'

    # --- services ---
    'app.services.'                  = 'app.core.services.'

    # --- db ---
    'app.db.'                        = 'app.core.db.'

    # --- одиночные файлы ---
    'app.schemas'                    = 'app.core.schemas'
    'app.redis_client'               = 'app.core.redis_client'
}

# Находим все .py файлы в app/
$files = Get-ChildItem -Path "app" -Recurse -Filter "*.py" |
         Where-Object { $_.FullName -notmatch '__pycache__' }

# Также проверяем файлы в корне (run_telegram.py, run_vk.py)
$rootFiles = Get-ChildItem -Path "." -Filter "*.py" -File |
             Where-Object { $_.Name -match 'run_|main' }
$files = @($files) + @($rootFiles)

# Добавляем alembic/env.py если есть
if (Test-Path "alembic\env.py") {
    $files = @($files) + @(Get-Item "alembic\env.py")
}

$totalChanges = 0

foreach ($file in $files) {
    if (-not $file) { continue }

    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
    if (-not $content) { continue }

    $original = $content
    $fileChanges = 0

    foreach ($old in $replacements.Keys) {
        $new = $replacements[$old]
        if ($content.Contains($old)) {
            $count = ([regex]::Matches($content, [regex]::Escape($old))).Count
            $content = $content.Replace($old, $new)
            $fileChanges += $count
        }
    }

    if ($fileChanges -gt 0) {
        Set-Content -Path $file.FullName -Value $content -Encoding UTF8 -NoNewline
        $relativePath = $file.FullName.Replace((Get-Location).Path + "\", "")
        Write-Host "  OK  $relativePath ($fileChanges замен)" -ForegroundColor Green
        $totalChanges += $fileChanges
    }
}

Write-Host ""
Write-Host "=== Готово! Всего замен: $totalChanges ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Следующий шаг: проверь что ничего не пропущено:" -ForegroundColor Yellow
Write-Host '  Select-String -Path "app\*.py","app\**\*.py" -Pattern "from app\.(db|services|handlers|comands_menu|posting|middlewares|openai_assistant|quiz|payments|schemas|redis_client)[. ]" | Select-Object -Property Path,LineNumber,Line' -ForegroundColor Gray