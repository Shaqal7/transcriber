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

python -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --name transcriber `
    --collect-all whisper `
    --collect-all imageio_ffmpeg `
    --collect-all tiktoken `
    --collect-all torch `
    --hidden-import whisper `
    --hidden-import whisper.audio `
    --hidden-import imageio_ffmpeg `
    transcribe.py

Write-Host ""
Write-Host "Build zakonczony. Plik EXE znajduje sie w katalogu dist\\transcriber.exe"
