Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName System.Media

Write-Host "🚀 Iniciando push e deploy automatizado..." -ForegroundColor Cyan

# 1️⃣ Mensagem de commit
$message = Read-Host "📝 Digite a mensagem do commit"
if (-not $message) {
    Write-Host "❌ Nenhuma mensagem informada. Cancelando." -ForegroundColor Red
    exit
}

# 2️⃣ Adiciona tudo e faz commit
Write-Host "📦 Adicionando arquivos modificados..." -ForegroundColor Cyan
git add .
git commit -m "$message"

# 3️⃣ Protege o arquivo serviceAccountKey.json
$tracked = git ls-files serviceAccountKey.json
if ($tracked) {
    Write-Host "⚠️ Removendo serviceAccountKey.json do rastreamento..." -ForegroundColor Yellow
    git rm --cached serviceAccountKey.json
    if (-not (Select-String -Path ".gitignore" -Pattern "serviceAccountKey.json" -Quiet)) {
        Add-Content ".gitignore" "serviceAccountKey.json"
        Write-Host "📄 Adicionado serviceAccountKey.json ao .gitignore." -ForegroundColor Green
    }
}

# 4️⃣ Limpa histórico da chave se necessário
Write-Host "🧹 Limpando histórico antigo de serviceAccountKey.json..." -ForegroundColor Cyan
git filter-repo --path serviceAccountKey.json --invert-paths --force

# 5️⃣ Verifica remote
$remoteCheck = git remote -v
if (-not ($remoteCheck -match "github.com/JCarlos51/millemultiplayer")) {
    Write-Host "🔗 Remote ausente. Recriando..." -ForegroundColor Yellow
    git remote add origin "https://github.com/JCarlos51/millemultiplayer.git"
}

# 6️⃣ Confirma push
$confirm = Read-Host "⚠️ Será feito push forçado (substitui histórico). Continuar? (s/n)"
if ($confirm -ne 's' -and $confirm -ne 'S') {
    Write-Host "❌ Operação cancelada." -ForegroundColor Red
    exit
}

# 7️⃣ Push forçado
Write-Host "🚀 Enviando alterações para GitHub..." -ForegroundColor Cyan
git push origin main --force

# 8️⃣ Notificação sonora e visual
[System.Media.SystemSounds]::Asterisk.Play()
[System.Windows.MessageBox]::Show(
    "✅ Push concluído com sucesso! Agora o Render será atualizado automaticamente.",
    "Push Finalizado",
    [System.Windows.MessageBoxButton]::OK,
    [System.Windows.MessageBoxImage]::Information
) | Out-Null

# 9️⃣ Abre log do Render automaticamente
Write-Host "🌐 Acompanhando o deploy no Render..." -ForegroundColor Cyan
Start-Process "https://dashboard.render.com/web/srv-d45039f5r7bs73b8ano0/logs"

Write-Host ""
Write-Host "✅ Deploy iniciado! O log do Render foi aberto no navegador." -ForegroundColor Green
