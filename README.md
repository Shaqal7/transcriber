# Audio Transcription (Whisper)

Skrypt do transkrypcji plików audio przy użyciu [OpenAI Whisper](https://github.com/openai/whisper).
Działa na Windows, macOS i Linux.

## Wymagania

- **Python 3.10+**
- **ffmpeg** — wymagany przez Whisper do dekodowania audio

### Instalacja ffmpeg

| System | Polecenie |
|--------|-----------|
| **macOS** | `brew install ffmpeg` |
| **Ubuntu / Debian** | `sudo apt install ffmpeg` |
| **Windows (winget)** | `winget install Gyan.FFmpeg` |
| **Windows (choco)** | `choco install ffmpeg` |
| **Windows (scoop)** | `scoop install ffmpeg` |

Po instalacji sprawdź: `ffmpeg -version`

### Instalacja zależności Python

```bash
pip install -r requirements.txt
```

## Użycie

```bash
# Podstawowe — auto-detekcja języka, model medium, wynik obok pliku wejściowego
python transcribe.py sciezka/do/pliku.mp3

# Wymuszenie języka polskiego
python transcribe.py plik.mp3 -l pl

# Mniejszy model (szybciej, mniej dokładnie)
python transcribe.py plik.mp3 -m small

# Większy model (wolniej, najdokładniej)
python transcribe.py plik.mp3 -m large

# Zapis do konkretnego pliku
python transcribe.py plik.mp3 -o wynik.txt
```

### Parametry

| Parametr | Opis | Domyślnie |
|----------|------|-----------|
| `input` | Ścieżka do pliku audio (mp3, wav, m4a, flac, ogg, ...) | — |
| `-o`, `--output` | Ścieżka do pliku wynikowego .txt | `<input>.txt` |
| `-m`, `--model` | Rozmiar modelu: `tiny`, `base`, `small`, `medium`, `large` | `medium` |
| `-l`, `--language` | Kod języka (`pl`, `en`, `de`, ...) | auto-detect |

### Modele — orientacyjne porównanie

| Model | Rozmiar | RAM | Jakość | Szybkość (CPU) |
|-------|---------|-----|--------|----------------|
| tiny | 39 MB | ~1 GB | niska | bardzo szybko |
| base | 74 MB | ~1 GB | niska-średnia | szybko |
| small | 244 MB | ~2 GB | średnia | umiarkowanie |
| medium | 1.5 GB | ~5 GB | dobra | wolno |
| large | 2.9 GB | ~10 GB | najlepsza | bardzo wolno |

Na CPU model `medium` dla 60 min audio to ~30-45 min przetwarzania.
Z GPU (CUDA) czas spada kilkukrotnie.

## Format wyjściowy

```
[00:00:00 - 00:00:05] Tekst pierwszego segmentu.
[00:00:05 - 00:00:12] Tekst drugiego segmentu.
```

## GPU (opcjonalnie)

Jeśli masz GPU NVIDIA z CUDA, Whisper automatycznie z niego skorzysta.
Wymagana instalacja PyTorch z obsługą CUDA:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```
