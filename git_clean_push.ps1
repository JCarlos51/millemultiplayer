Write-Host ""
Write-Host "Iniciando push e deploy automatizado..." -ForegroundColor Cyan

# 1️⃣ Mensagem de commit
$message = Read-Host "Digite a mensagem do commit"
if (-not $message) {
    Write-Host "Nenhuma mensagem informada. Cancelando." -ForegroundColor Red
    exit
}

# 2️⃣ Adiciona tudo e faz commit
Write-Host ""
Write-Host "Adicionando arquivos modificados..." -ForegroundColor Cyan
git add .
git commit -m "$message"

# 3️⃣ Protege o arquivo serviceAccountKey.json
$tracked = git ls-files serviceAccountKey.json
if ($tracked) {
    Write-Host "Removendo serviceAccountKey.json do rastreamento..." -ForegroundColor Yellow
    git rm --cached serviceAccountKey.json
    if (-not (Select-String -Path ".gitignore" -Pattern "serviceAccountKey.json" -Quiet)) {
        Add-Content ".gitignore" "serviceAccountKey.json"
        Write-Host "Adicionado serviceAccountKey.json ao .gitignore." -ForegroundColor Green
    }
}

# 4️⃣ Limpa histórico da chave
Write-Host ""
Write-Host "Limpando histórico antigo de serviceAccountKey.json..." -ForegroundColor Cyan
git filter-repo --path serviceAccountKey.json --invert-paths --force

# 5️⃣ Verifica remote
$remoteCheck = git remote -v
if (-not ($remoteCheck -match "github.com/JCarlos51/millemultiplayer")) {
    Write-Host "Remote ausente. Recriando..." -ForegroundColor Yellow
    git remote add origin "https://github.com/JCarlos51/millemultiplayer.git"
}

# 6️⃣ Confirma push forçado
$confirm = Read-Host "Será feito push forçado (substitui histórico). Continuar? (s/n)"
if ($confirm -ne 's' -and $confirm -ne 'S') {
    Write-Host "Operação cancelada." -ForegroundColor Red
    exit
}

# 7️⃣ Push forçado
Write-Host ""
Write-Host "Enviando alterações para GitHub..." -ForegroundColor Cyan
git push origin main --force

# 8️⃣ Notificação sonora e visual
Write-Host ""
Write-Host "Push concluído com sucesso! O Render será atualizado automaticamente." -ForegroundColor Green

try {
    [System.Media.SystemSounds]::Asterisk.Play()
} catch {
    Write-Host "Não foi possível reproduzir o som (ignorado)." -ForegroundColor Yellow
}

try {
    Start-Process "https://dashboard.render.com/web/srv-d45039f5r7bs73b8ano0"
    Write-Host "Painel do Render aberto no navegador padrão." -ForegroundColor Cyan
} catch {
    Write-Host "Não foi possível abrir o navegador automaticamente." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Script finalizado com sucesso!" -ForegroundColor Green
