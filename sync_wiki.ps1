# Script para sincronizar as páginas locais com o GitHub Wiki
$ErrorActionPreference = "Stop"

Write-Host "Sincronizando GitHub Wiki para Ak4ai/Isometricon..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\wiki_export"
git add .
git commit -m "docs(wiki): update wiki documentation pages" -ErrorAction SilentlyContinue
git push https://github.com/Ak4ai/Isometricon.wiki.git master

Write-Host "Wiki sincronizado com sucesso!" -ForegroundColor Green
