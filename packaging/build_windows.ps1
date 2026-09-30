$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$version = (Get-Content assets/app_info.json -Raw | ConvertFrom-Json).version
python -m PyInstaller --noconfirm --clean --distpath dist/windows --workpath build/windows packaging/choroy_reader.spec
if ($LASTEXITCODE -ne 0) { throw 'Falló PyInstaller' }
$bundle = Join-Path $root 'dist/windows/choroy_reader'
$forbidden = Get-ChildItem $bundle -Recurse | Where-Object { $_.Name -in @('config.json','biblioteca','favicons','.git','.venv') -or $_.Name -like 'reader_state.sqlite3*' }
if ($forbidden) { throw 'El paquete contiene datos personales' }
$info = Get-Content "$bundle/_internal/assets/app_info.json" -Raw | ConvertFrom-Json
if ($info.version -ne $version) { throw 'La versión del ejecutable no coincide' }
python packaging/verify_windows.py "$bundle/choroy_reader.exe"
if ($LASTEXITCODE -ne 0) { throw 'Falló la verificación del ejecutable' }
$compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $compiler) {
    $path = "${env:ProgramFiles(x86)}/Inno Setup 6/ISCC.exe"
    if (-not (Test-Path $path)) { throw 'Instala Inno Setup 6 y agrega ISCC.exe a PATH' }
} else { $path = $compiler.Source }
& $path "/DAppVersion=$version" "/DBundleDir=$bundle" packaging/windows.iss
if ($LASTEXITCODE -ne 0) { throw 'Falló Inno Setup' }
$installer = Join-Path $root "dist/Choroy-Reader-Setup-$version-x64.exe"
$hash = (Get-FileHash $installer -Algorithm SHA256).Hash.ToLower()
"$hash  $(Split-Path $installer -Leaf)" | Set-Content "$installer.sha256" -Encoding ascii
Write-Output $installer
