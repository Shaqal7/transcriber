# Audio and Video Transcription (Whisper)

Skrypt do transkrypcji plików audio przy użyciu [OpenAI Whisper](https://github.com/openai/whisper).
Obsługuje też pliki wideo: dla `mp4` i innych popularnych formatów najpierw wyciąga ścieżkę audio do `mp3`, a następnie wykonuje transkrypcję.

Projekt działa na Windows, macOS i Linux.

## Co potrafi

- transkrypcja plików audio: `mp3`, `wav`, `m4a`, `flac`, `ogg` i inne zgodne z ffmpeg
- konwersja wideo do `mp3` przed transkrypcją: `mp4`, `mov`, `mkv`, `avi`, `webm`, `m4v`
- wykrywanie brakujących zależności Pythona
- instalacja brakujących pakietów po potwierdzeniu lub automatycznie przez `--yes`
- użycie systemowego `ffmpeg`, a jeśli go nie ma, skorzystanie z binarki dostarczonej przez `imageio-ffmpeg`
- prosty build do `exe` dla Windows przez PyInstaller

## Wymagania

- **Python 3.10+**

Nie musisz już ręcznie instalować systemowego `ffmpeg`, jeśli zgadzasz się na doinstalowanie pakietów z `requirements.txt`.

## Instalacja

```bash
pip install -r requirements.txt
```

Jeśli nie zrobisz tego ręcznie, skrypt sam wykryje brakujące pakiety i zapyta, czy ma je doinstalować.

## Build do EXE

Dla Windows możesz zbudować pojedynczy plik wykonywalny:

```powershell
./build_exe.ps1
```

Jeśli chcesz od razu zgodzić się na doinstalowanie brakującego `pyinstaller`:

```powershell
./build_exe.ps1 -Yes
```

Po udanym buildzie gotowy plik znajdziesz tutaj:

```text
dist/transcriber.exe
```

Skrypt builda przed pakowaniem sprawdza też, czy w środowisku są dostępne runtime zależności potrzebne do zbundlowania aplikacji, między innymi `openai-whisper` oraz `imageio-ffmpeg`. Jeśli ich brakuje, zaproponuje instalację.

Uruchamianie `exe` jest takie samo jak skryptu `.py`, tylko zamiast `python transcribe.py` wywołujesz plik wykonywalny:

```powershell
./dist/transcriber.exe sciezka/do/pliku.mp3
./dist/transcriber.exe sciezka/do/wideo.mp4 -o wynik.txt
./dist/transcriber.exe sciezka/do/wideo.mp4 -l pl --keep-converted-audio
./dist/transcriber.exe .\KSeF.mp4 -o wynik.txt --llm-provider claude --llm-model haiku --llm-prompt-file .\prompt.txt
```

Uwaga: wynikowy `exe` nie powinien już próbować doinstalowywać modułów Pythona do własnego wnętrza. Te moduły mają być zbundlowane podczas builda. Przy pierwszym użyciu Whisper nadal może natomiast pobrać sam model, jeśli nie ma go jeszcze w cache użytkownika.

## Użycie

```bash
# Podstawowe — plik mp3
python transcribe.py sciezka/do/pliku.mp3

# Plik mp4: konwersja do mp3 i transkrypcja w jednym kroku
python transcribe.py sciezka/do/wideo.mp4

# Wymuszenie języka polskiego
python transcribe.py plik.mp4 -l pl

# Mniejszy model (szybciej, mniej dokładnie)
python transcribe.py plik.mp3 -m small

# Automatyczna zgoda na doinstalowanie braków
python transcribe.py plik.mp4 --yes

# Zachowanie wygenerowanego pliku mp3 obok źródłowego wideo
python transcribe.py plik.mp4 --keep-converted-audio

# Zapis transkrypcji do konkretnego pliku
python transcribe.py plik.mp3 -o wynik.txt

# Po transkrypcji wyślij wynik do Claude CLI
python transcribe.py plik.mp4 -o wynik.txt --llm-provider claude --llm-model haiku --llm-prompt-file prompt.txt

# Po transkrypcji wyślij wynik do Codex/GPT CLI przez własny szablon komendy
python transcribe.py plik.mp4 -o wynik.txt --llm-provider codex --llm-model gpt-5 --llm-prompt-file prompt.txt --llm-command-template "codex -m {model} {prompt}"
```

## Parametry

| Parametr | Opis | Domyślnie |
|----------|------|-----------|
| `input` | Ścieżka do pliku audio lub wideo | — |
| `-o`, `--output` | Ścieżka do pliku wynikowego `.txt` | `<input>.txt` |
| `-m`, `--model` | Rozmiar modelu: `tiny`, `base`, `small`, `medium`, `large` | `medium` |
| `-l`, `--language` | Kod języka (`pl`, `en`, `de`, ...) | auto-detect |
| `--yes` | Automatyczna zgoda na doinstalowanie brakujących pakietów | `False` |
| `--keep-converted-audio` | Zachowuje wygenerowany plik `.mp3` obok pliku wideo | `False` |
| `--llm-provider` | Po transkrypcji uruchamia wybrane CLI: `claude` lub `codex` | — |
| `--llm-model` | Model przekazywany do wybranego CLI | — |
| `--llm-prompt-file` | Plik `.txt` z promptem/instrukcją do połączenia z transkrypcją | — |
| `--llm-command-template` | Własny szablon komendy dla `codex` z placeholderami | — |

## Jak działa instalacja zależności

Przy starcie skrypt:

1. sprawdza, czy jest dostępny `openai-whisper`
2. sprawdza, czy dostępny jest `ffmpeg`
3. jeśli `ffmpeg` nie jest zainstalowany systemowo, używa `imageio-ffmpeg`
4. jeśli któregoś pakietu brakuje, pyta o zgodę na instalację przez `pip`

Jeśli chcesz pominąć pytania i od razu zezwolić na instalację braków, użyj:

```bash
python transcribe.py plik.mp4 --yes
```

## Integracja z Claude CLI i Codex/GPT CLI

Po wygenerowaniu transkrypcji możesz od razu wysłać ją do zewnętrznego CLI.
Skrypt czyta:

- plik z instrukcją, na przykład `prompt.txt`
- plik z transkrypcją, na przykład `wynik.txt`

Następnie łączy je w jeden prompt i uruchamia wybrane narzędzie.

### Claude CLI

Przykład:

```powershell
./dist/transcriber.exe .\KSeF.mp4 -o wynik.txt --llm-provider claude --llm-model haiku --llm-prompt-file .\prompt.txt
```

To odpowiada mniej więcej komendzie:

```text
claude --model haiku --print "<prompt z pliku + treść wynik.txt>"
```

### Codex / GPT CLI

Ponieważ składnia lokalnego `codex` może różnić się między wersjami, dla tego providera podajesz własny szablon komendy:

```powershell
./dist/transcriber.exe .\KSeF.mp4 -o wynik.txt --llm-provider codex --llm-model gpt-5 --llm-prompt-file .\prompt.txt --llm-command-template "codex -m {model} {prompt}"
```

Dostępne placeholdery:

- `{model}` - nazwa modelu
- `{prompt}` - pełny prompt złożony z `prompt.txt` i transkrypcji
- `{prompt_file}` - ścieżka do pliku z instrukcją
- `{transcript_file}` - ścieżka do pliku z transkrypcją

Jeśli Twój lokalny CLI woli dostać ścieżki do plików zamiast sklejonego promptu, możesz użyć na przykład:

```text
codex some-command --instructions {prompt_file} --input {transcript_file}
```

## Format wyjściowy

```text
[00:00:00 - 00:00:05] Tekst pierwszego segmentu.
[00:00:05 - 00:00:12] Tekst drugiego segmentu.
```

## Modele — orientacyjne porównanie

| Model | Rozmiar | RAM | Jakość | Szybkość (CPU) |
|-------|---------|-----|--------|----------------|
| tiny | 39 MB | ~1 GB | niska | bardzo szybko |
| base | 74 MB | ~1 GB | niska-średnia | szybko |
| small | 244 MB | ~2 GB | średnia | umiarkowanie |
| medium | 1.5 GB | ~5 GB | dobra | wolno |
| large | 2.9 GB | ~10 GB | najlepsza | bardzo wolno |

Na CPU model `medium` dla 60 min audio to zwykle około `30-45 min` przetwarzania.
Z GPU (CUDA) czas spada kilkukrotnie.

## GPU (opcjonalnie)

Jeśli masz GPU NVIDIA z CUDA, Whisper może z niego skorzystać.
Wtedy zwykle chcesz mieć wersję PyTorch z obsługą CUDA, na przykład:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```
