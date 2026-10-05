<#
.SYNOPSIS
    Fusiona un PR a main y publica la versión de version.py como release (tag vX.Y.Z).

.DESCRIPTION
    1. Fusiona el PR indicado (o el único PR abierto contra main).
    2. Cambia a main y hace pull.
    3. Lee __version__ de version.py y crea/empuja el tag v<versión>,
       que dispara la Action de release (.github/workflows/release.yml).

    El tag debe coincidir con version.py (la Action lo verifica), así que
    sube la versión en version.py dentro del PR antes de publicar.

.EXAMPLE
    .\scripts\publicar.ps1            # usa el único PR abierto
.EXAMPLE
    .\scripts\publicar.ps1 -Pr 2      # fusiona el PR #2
.EXAMPLE
    .\scripts\publicar.ps1 -SinPr     # solo publica lo que ya está en main
#>
param(
    [int]$Pr,
    [switch]$SinPr,
    [switch]$Si   # no pedir confirmación
)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Ejecutar {
    param([string]$Desc, [scriptblock]$Cmd)
    Write-Host "> $Desc" -ForegroundColor Cyan
    & $Cmd
    if ($LASTEXITCODE -ne 0) { throw "Falló: $Desc (código $LASTEXITCODE)" }
}

function Confirmar([string]$Pregunta) {
    if ($Si) { return }
    $r = Read-Host "$Pregunta [s/N]"
    if ($r -notmatch '^(s|si|sí|y|yes)$') { Write-Host 'Cancelado.'; exit 1 }
}

# Árbol limpio: el checkout y el pull no deben pisar cambios locales
if (git status --porcelain) {
    throw 'Tienes cambios sin commitear. Haz commit o stash antes de publicar.'
}

# 1. Fusionar el PR
if (-not $SinPr) {
    if (-not $Pr) {
        $abiertos = gh pr list --state open --base main --json number,title,headRefName | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar los PR con gh.' }
        if (-not $abiertos -or @($abiertos).Count -eq 0) {
            throw 'No hay PR abiertos contra main. Usa -SinPr para publicar lo que ya está en main.'
        }
        if (@($abiertos).Count -gt 1) {
            $abiertos | ForEach-Object { Write-Host ("  #{0}  {1}  ({2})" -f $_.number, $_.title, $_.headRefName) }
            throw 'Hay varios PR abiertos. Indica cuál con -Pr <número>.'
        }
        $Pr = @($abiertos)[0].number
    }

    $info = gh pr view $Pr --json number,title,headRefName,state,mergeable | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw "No se encontró el PR #$Pr." }
    if ($info.state -ne 'OPEN') { throw "El PR #$Pr no está abierto (estado: $($info.state))." }
    Write-Host ("PR #{0}: {1}  ({2} -> main, mergeable: {3})" -f $info.number, $info.title, $info.headRefName, $info.mergeable)
    Confirmar "¿Fusionar el PR #$Pr?"

    Ejecutar "Fusionando PR #$Pr" { gh pr merge $Pr --merge }
}

# 2. Actualizar main
Ejecutar 'Cambiando a main' { git checkout main }
Ejecutar 'Actualizando main' { git pull --ff-only }

# 3. Tag a partir de version.py
$linea = Select-String -Path version.py -Pattern '__version__\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $linea) { throw 'No encontré __version__ en version.py.' }
$tag = 'v' + $linea.Matches[0].Groups[1].Value

if (git tag -l $tag) {
    throw "El tag $tag ya existe. Sube __version__ en version.py (en un PR) antes de publicar."
}
if (git ls-remote --tags origin "refs/tags/$tag") {
    throw "El tag $tag ya existe en GitHub. Sube __version__ en version.py antes de publicar."
}

Confirmar "¿Crear y publicar el tag $tag (dispara la release)?"
Ejecutar "Creando tag $tag" { git tag $tag }
Ejecutar "Empujando tag $tag" { git push origin $tag }

$url = gh repo view --json url -q .url
Write-Host ''
Write-Host "Listo. La release $tag se está construyendo en: $url/actions" -ForegroundColor Green
Write-Host "Cuando termine, descarga ReelStudio-win-Setup.exe desde: $url/releases/tag/$tag"
