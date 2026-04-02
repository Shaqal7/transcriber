param(
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

function Ensure-Package {
    param(
        [string]$ModuleName,
        [string]$PackageName
    )

    $moduleAvailable = python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$ModuleName') else 1)"
    if ($LASTEXITCODE -eq 0) {
        return
    }

    if (-not $Yes) {
        $answer = Read-Host "Brakuje pakietu $PackageName. Zainstalowac teraz? [Y/n]"
        if ($answer -and $answer.ToLower() -notin @("y", "yes", "t", "tak")) {
            throw "Build anulowany - brak wymaganego pakietu: $PackageName"
        }
    }

    python -m pip install $PackageName
}

Ensure-Package -ModuleName "PyInstaller" -PackageName "pyinstaller"
Ensure-Package -ModuleName "whisper" -PackageName "openai-whisper"
Ensure-Package -ModuleName "imageio_ffmpeg" -PackageName "imageio-ffmpeg"
Ensure-Package -ModuleName "tiktoken" -PackageName "tiktoken"
Ensure-Package -ModuleName "torch" -PackageName "torch"

python -m PyInstaller `
    --clean `
    --noconfirm `
    .\transcriber.spec

Write-Host ""
Write-Host "Build zakonczony. Plik EXE znajduje sie w katalogu dist\\transcriber\\transcriber.exe"
