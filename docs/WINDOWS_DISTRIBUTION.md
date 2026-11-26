# Distribuição para Windows

Use Windows x64 com um driver compatível com OpenGL 3.3. No pacote portátil, extraia o
ZIP inteiro e abra `Isometricon.exe`. Mantenha a pasta `_internal` junto ao executável.
O arquivo OneFile tem o sufixo histórico `Windows-Installer.exe` e pode ser aberto
diretamente.

Os dois formatos usam `%LOCALAPPDATA%\Isometricon`. Mundos, preferências, mapas,
personagens e modelos GLB ficam em `saves`. Roupas baixadas e malhas geradas ficam
em `assets\models` nessa mesma pasta de dados. Os recursos empacotados ficam separados
e podem ser substituídos por uma nova versão sem mudar a localização dos saves.

A execução pelo código-fonte mantém `saves` e os assets gerados no checkout. Para
transferir dados do código-fonte ou de um portátil anterior, feche o aplicativo e
copie os arquivos de `saves` para `%LOCALAPPDATA%\Isometricon\saves`.
No portátil anterior, procure `_internal\saves` ou `saves` junto ao executável.
Copie também as pastas auxiliares, como `modelos` e `schematics`. Se um save
ainda referenciar uma esquemática externa, mantenha a fonte disponível durante
a primeira abertura.

## Compilar e verificar

Em um checkout limpo no Windows com Python e as dependências de
`requirements.txt` instaladas, execute:

```powershell
python -m pip install pyinstaller
python scripts/build.py --windows --onefile
$version = (Get-Content VERSION.txt -Raw).Trim()
python scripts/smoke_windows_package.py "dist/Isometricon-v${version}-Windows-Portable.zip" "dist/Isometricon-v${version}-Windows-Installer.exe"
```

O teste extrai o ZIP e copia o OneFile para diretórios temporários. Cada executável
inicia com um ambiente sem o Python do desenvolvimento no `PATH` e usa um
`ISOMETRICON_DATA_DIR` isolado. O teste renderiza o menu, cria um mundo, verifica o
save após encerrar o processo e abre o mesmo mundo em uma nova execução. A opção
`--evidence-dir` permite reter as capturas e o save de teste em um diretório novo.

No GitHub Actions, o teste usa as DLLs de OpenGL por software da [build Mesa 25.2.8
para Windows](https://github.com/pal1000/mesa-dist-win/releases/tag/25.2.8), com
SHA-256 fixo. Essas DLLs ficam nas cópias temporárias usadas pelo teste. A publicação exige os testes dos dois formatos Windows,
a validação do pacote Linux e o acionamento manual descrito no
[guia de contribuição](../CONTRIBUTING.md).
