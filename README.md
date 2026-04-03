# Audio and Video Transcription (Whisper)

Skrypt do transkrypcji plików audio i wideo przy użyciu [OpenAI Whisper](https://github.com/openai/whisper).
Projekt uruchamiamy bezpośrednio przez Pythona, bez budowania `exe`.

Obsługiwane jest:
- audio: `mp3`, `wav`, `m4a`, `flac`, `ogg` i inne formaty zgodne z `ffmpeg`
- wideo: `mp4`, `mov`, `mkv`, `avi`, `webm`, `m4v`
- opcjonalne przekazanie gotowej transkrypcji do `Claude CLI` albo lokalnego `Codex CLI`

## Wymagania

- Python 3.10+
- na Windows najlepiej uruchamiać jawnie przez `py -3.13` albo pełną ścieżkę do Pythona, jeśli masz kilka wersji

## Instalacja

```bash
pip install -r requirements.txt
```

Jeśli nie zrobisz tego ręcznie, skrypt sam wykryje brakujące pakiety i może je doinstalować po potwierdzeniu lub przez `--yes`.

## Użycie

Windows:

```powershell
py -3.13 .\transcribe.py --gui
py -3.13 .\transcribe.py .\plik.mp3
py -3.13 .\transcribe.py .\plik.mp4 -o wynik.txt
py -3.13 .\transcribe.py .\plik.mp4 --keep-converted-audio
```

macOS / Linux:

```bash
python3 transcribe.py --gui
python3 transcribe.py ./plik.mp3
python3 transcribe.py ./plik.mp4 -o wynik.txt
python3 transcribe.py ./plik.mp4 --keep-converted-audio
```

## Proste UI

Skrypt ma też prosty interfejs okienkowy oparty o `tkinter`.
Pozwala wybrać:

- plik wejściowy
- plik wynikowy
- model Whisper
- język
- `--yes`
- `--keep-converted-audio`
- włączenie LLM oraz wszystkie powiązane opcje

Uruchomienie UI:

```powershell
py -3.13 .\transcribe.py --gui
```

Możesz też po prostu uruchomić skrypt bez argumentów:

```powershell
py -3.13 .\transcribe.py
```

Przykłady:

```powershell
# Wymuszenie języka polskiego
py -3.13 .\transcribe.py .\plik.mp4 -l pl

# Mniejszy model
py -3.13 .\transcribe.py .\plik.mp3 -m small

# Automatyczna zgoda na doinstalowanie braków
py -3.13 .\transcribe.py .\plik.mp4 --yes

# Zapis transkrypcji do konkretnego pliku
py -3.13 .\transcribe.py .\plik.mp3 -o wynik.txt

# Po transkrypcji wyślij wynik do Claude CLI
py -3.13 .\transcribe.py .\KSeF.mp4 -o wynik.txt --llm-provider claude --llm-model haiku --llm-prompt-file .\prompt.txt

# Po transkrypcji wyślij wynik do Codex CLI przez własny szablon komendy
py -3.13 .\transcribe.py .\KSeF.mp4 -o wynik.txt --llm-provider codex --llm-model gpt-5 --llm-prompt-file .\prompt.txt --llm-command-template "codex -m {model} {prompt}"
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
| `--llm-command-template` | Własny szablon komendy dla wybranego providera LLM z placeholderami | — |
| `--gui` | Uruchamia proste okno desktopowe do wyboru pliku i opcji | `False` |

## Jak działa skrypt

Przy starcie skrypt:

1. sprawdza, czy dostępny jest `openai-whisper`
2. sprawdza, czy dostępny jest `ffmpeg`
3. jeśli `ffmpeg` nie jest zainstalowany systemowo, używa `imageio-ffmpeg`
4. jeśli któregoś pakietu brakuje, pyta o zgodę na instalację przez `pip`
5. zapisuje modele Whisper w lokalnym katalogu projektu `.transcriber-cache/whisper`

Jeśli chcesz pominąć pytania:

```powershell
py -3.13 .\transcribe.py .\plik.mp4 --yes
```

## Integracja z Claude CLI i Codex CLI

Po wygenerowaniu transkrypcji możesz od razu wysłać ją do zewnętrznego CLI.
Skrypt czyta:

- plik z instrukcją, na przykład `prompt.txt`
- plik z transkrypcją, na przykład `wynik.txt`

Następnie łączy je w jeden prompt i uruchamia wybrane narzędzie.
Odpowiedź LLM jest zapisywana do pliku Markdown obok transkrypcji, na przykład `wynik.txt` -> `wynik.md`.

Claude CLI:

```powershell
py -3.13 .\transcribe.py .\KSeF.mp4 -o wynik.txt --llm-provider claude --llm-model haiku --llm-prompt-file .\prompt.txt
```

Jeśli na Windows `claude` działa u Ciebie tylko przez `cmd`, możesz też jawnie podać szablon:

```powershell
py -3.13 .\transcribe.py .\KSeF.mp4 -o wynik.txt --llm-provider claude --llm-model haiku --llm-prompt-file .\prompt.txt --llm-command-template "cmd /c claude --model {model} --print {prompt}"
```

Codex CLI:

```powershell
py -3.13 .\transcribe.py .\KSeF.mp4 -o wynik.txt --llm-provider codex --llm-model gpt-5 --llm-prompt-file .\prompt.txt --llm-command-template "codex -m {model} {prompt}"
```

Dostępne placeholdery:

- `{model}` - nazwa modelu
- `{prompt}` - pełny prompt złożony z `prompt.txt` i transkrypcji
- `{prompt_file}` - ścieżka do pliku z instrukcją
- `{transcript_file}` - ścieżka do pliku z transkrypcją

## Format wyjściowy

```text
[00:00:00 - 00:00:05] Tekst pierwszego segmentu.
[00:00:05 - 00:00:12] Tekst drugiego segmentu.
```

## Modele

| Model | Rozmiar | RAM | Jakość | Szybkość (CPU) |
|-------|---------|-----|--------|----------------|
| tiny | 39 MB | ~1 GB | niska | bardzo szybko |
| base | 74 MB | ~1 GB | niska-średnia | szybko |
| small | 244 MB | ~2 GB | średnia | umiarkowanie |
| medium | 1.5 GB | ~5 GB | dobra | wolno |
| large | 2.9 GB | ~10 GB | najlepsza | bardzo wolno |

Na CPU model `medium` dla 60 min audio to zwykle około `30-45 min` przetwarzania.

## GPU (opcjonalnie)

Jeśli masz GPU NVIDIA z CUDA, Whisper może z niego skorzystać. Wtedy zwykle chcesz mieć wersję PyTorch z obsługą CUDA, na przykład:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```
