#!/usr/bin/env python3
"""
Audio and video transcription script using OpenAI Whisper.
Supports common audio formats and can convert MP4/video input to MP3 first.
Works on Windows, macOS and Linux.
"""

import argparse
import importlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional, Tuple

PYTHON_DEPENDENCIES = {
    "whisper": "openai-whisper",
    "imageio_ffmpeg": "imageio-ffmpeg",
}

VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm"}


def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def resolve_app_cache_dir() -> Path:
    cache_dir = Path.cwd() / ".transcriber-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def resolve_whisper_cache_dir() -> Path:
    cache_dir = resolve_app_cache_dir() / "whisper"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def prompt_yes_no(message: str, default: bool = True) -> bool:
    if not sys.stdin.isatty():
        return False

    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{message} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "t", "tak"}


def ensure_python_modules(module_names: list[str], auto_confirm: bool) -> None:
    missing_packages: list[str] = []

    for module_name in module_names:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing_packages.append(PYTHON_DEPENDENCIES[module_name])

    if not missing_packages:
        return

    packages_display = ", ".join(missing_packages)
    if auto_confirm:
        should_install = True
    else:
        should_install = prompt_yes_no(
            f"Missing Python packages: {packages_display}. Install them now?",
            default=True,
        )

    if not should_install:
        print(f"Cannot continue without: {packages_display}")
        print("Run again with --yes to allow automatic installation.")
        sys.exit(1)

    install_python_packages(missing_packages)


def install_python_packages(packages: list[str]) -> None:
    print(f"Installing Python packages: {', '.join(packages)}")
    pip_command = resolve_pip_install_command()
    try:
        subprocess.run(
            [*pip_command, *packages],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Failed to install dependencies: {exc}")
        sys.exit(exc.returncode or 1)


def resolve_pip_install_command() -> list[str]:
    return [sys.executable, "-m", "pip", "install"]


def ensure_ffmpeg(auto_confirm: bool) -> Path:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return Path(system_ffmpeg)

    ensure_python_modules(["imageio_ffmpeg"], auto_confirm=auto_confirm)
    import imageio_ffmpeg

    ffmpeg_exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
    install_ffmpeg_shim(ffmpeg_exe)
    return ffmpeg_exe


def install_ffmpeg_shim(ffmpeg_exe: Path) -> None:
    shim_dir = Path(tempfile.gettempdir()) / "transcriber_ffmpeg_shim"
    shim_dir.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        shim_path = shim_dir / "ffmpeg.exe"
        if not shim_path.exists() or ffmpeg_exe.stat().st_mtime > shim_path.stat().st_mtime:
            shutil.copy2(ffmpeg_exe, shim_path)
    else:
        shim_path = shim_dir / "ffmpeg"
        shim_contents = f'#!/bin/sh\n"{ffmpeg_exe}" "$@"\n'
        if not shim_path.exists() or shim_path.read_text(encoding="utf-8") != shim_contents:
            shim_path.write_text(shim_contents, encoding="utf-8")
            shim_path.chmod(0o755)

    current_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{shim_dir}{os.pathsep}{current_path}" if current_path else str(shim_dir)


def get_audio_duration(file_path: str) -> float:
    import whisper.audio

    audio = whisper.audio.load_audio(file_path)
    return len(audio) / whisper.audio.SAMPLE_RATE


def convert_video_to_mp3(
    input_file: Path,
    ffmpeg_exe: Path,
    keep_converted_audio: bool,
) -> Tuple[Path, Optional[tempfile.TemporaryDirectory]]:
    temp_dir = None

    if keep_converted_audio:
        output_mp3 = input_file.with_suffix(".mp3")
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="transcriber_")
        output_mp3 = Path(temp_dir.name) / f"{input_file.stem}.mp3"

    print(f"Converting video to MP3: {input_file}")
    try:
        subprocess.run(
            [
                str(ffmpeg_exe),
                "-y",
                "-i",
                str(input_file),
                "-vn",
                "-acodec",
                "mp3",
                str(output_mp3),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        if temp_dir is not None:
            try:
                temp_dir.cleanup()
            except PermissionError:
                pass
        print("Failed to convert video to MP3.")
        if exc.stderr:
            print(exc.stderr.strip())
        sys.exit(exc.returncode or 1)

    print(f"Prepared MP3: {output_mp3}")
    return output_mp3, temp_dir


def resolve_output_path(input_file: Path, output_path: Optional[str]) -> Path:
    if output_path:
        return Path(output_path)
    return input_file.with_suffix(".txt")


def read_text_file(file_path: Path, label: str) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: {label} file not found: {file_path}")
        sys.exit(1)


def build_llm_prompt(prompt_file: Path, transcript_file: Path) -> str:
    prompt_text = read_text_file(prompt_file, "prompt").strip()
    transcript_text = read_text_file(transcript_file, "transcript").strip()

    if not prompt_text:
        print(f"Error: prompt file is empty: {prompt_file}")
        sys.exit(1)

    if not transcript_text:
        print(f"Error: transcript file is empty: {transcript_file}")
        sys.exit(1)

    return (
        f"{prompt_text}\n\n"
        f"Transcription source: {transcript_file}\n\n"
        "Transcript:\n"
        f"{transcript_text}\n"
    )


def split_command_template(command_template: str) -> list[str]:
    return shlex.split(command_template, posix=os.name != "nt")


def resolve_llm_command(
    provider: str,
    model: Optional[str],
    full_prompt: str,
    prompt_file: Path,
    transcript_file: Path,
    command_template: Optional[str],
) -> list[str]:
    if provider == "claude":
        command = ["claude"]
        if model:
            command.extend(["--model", model])
        command.extend(["--print", full_prompt])
        return command

    if not command_template:
        print(
            "Error: provider 'codex' requires --llm-command-template so the app knows how to call your local Codex CLI."
        )
        print("Use placeholders like {model}, {prompt}, {prompt_file}, {transcript_file}.")
        sys.exit(1)

    safe_model = model or ""
    expanded = command_template.format(
        model=safe_model,
        prompt=full_prompt,
        prompt_file=str(prompt_file),
        transcript_file=str(transcript_file),
    )
    return split_command_template(expanded)


def run_llm_command(
    provider: str,
    model: Optional[str],
    prompt_file: Path,
    transcript_file: Path,
    command_template: Optional[str],
) -> None:
    full_prompt = build_llm_prompt(prompt_file=prompt_file, transcript_file=transcript_file)
    command = resolve_llm_command(
        provider=provider,
        model=model,
        full_prompt=full_prompt,
        prompt_file=prompt_file,
        transcript_file=transcript_file,
        command_template=command_template,
    )

    print(f"Running {provider} CLI...")
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        print(f"Error: could not find CLI command for provider '{provider}'.")
        print(f"Attempted command: {' '.join(command[:3])}")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"LLM command failed with exit code {exc.returncode}.")
        sys.exit(exc.returncode or 1)


def transcribe(
    input_path: str,
    output_path: Optional[str],
    model_name: str,
    language: Optional[str],
    auto_confirm: bool,
    keep_converted_audio: bool,
    llm_provider: Optional[str],
    llm_model: Optional[str],
    llm_prompt_file: Optional[str],
    llm_command_template: Optional[str],
) -> None:
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: file not found: {input_file}")
        sys.exit(1)

    ensure_python_modules(["whisper"], auto_confirm=auto_confirm)
    ffmpeg_exe = ensure_ffmpeg(auto_confirm=auto_confirm)

    import whisper

    working_audio = input_file
    temp_dir = None

    if input_file.suffix.lower() in VIDEO_EXTENSIONS:
        working_audio, temp_dir = convert_video_to_mp3(
            input_file=input_file,
            ffmpeg_exe=ffmpeg_exe,
            keep_converted_audio=keep_converted_audio,
        )

    out = resolve_output_path(input_file, output_path)

    try:
        duration = get_audio_duration(str(working_audio))
        print(f"Audio duration: {format_time(duration)}")
        print(f"Loading model '{model_name}'...")
        model = whisper.load_model(model_name, download_root=str(resolve_whisper_cache_dir()))

        print(f"Transcribing: {working_audio}")
        transcribe_opts = {"verbose": None}
        if language:
            transcribe_opts["language"] = language

        result = model.transcribe(str(working_audio), **transcribe_opts)

        with open(out, "w", encoding="utf-8") as file_handle:
            for seg in result["segments"]:
                start = format_time(seg["start"])
                end = format_time(seg["end"])
                text = seg["text"].strip()
                file_handle.write(f"[{start} - {end}] {text}\n")

        print(f"Detected language: {result['language']}")
        print(f"Segments: {len(result['segments'])}")
        print(f"Saved to: {out}")

        if llm_provider:
            if not llm_prompt_file:
                print("Error: --llm-prompt-file is required when using --llm-provider.")
                sys.exit(1)

            run_llm_command(
                provider=llm_provider,
                model=llm_model,
                prompt_file=Path(llm_prompt_file),
                transcript_file=out,
                command_template=llm_command_template,
            )
    finally:
        if temp_dir is not None:
            try:
                temp_dir.cleanup()
            except PermissionError:
                pass


def build_transcribe_command(
    input_path: str,
    output_path: Optional[str],
    model_name: str,
    language: Optional[str],
    auto_confirm: bool,
    keep_converted_audio: bool,
    llm_provider: Optional[str],
    llm_model: Optional[str],
    llm_prompt_file: Optional[str],
    llm_command_template: Optional[str],
) -> list[str]:
    command = [sys.executable, str(Path(__file__).resolve()), input_path]

    if output_path:
        command.extend(["-o", output_path])
    if model_name:
        command.extend(["-m", model_name])
    if language:
        command.extend(["-l", language])
    if auto_confirm:
        command.append("--yes")
    if keep_converted_audio:
        command.append("--keep-converted-audio")
    if llm_provider:
        command.extend(["--llm-provider", llm_provider])
    if llm_model:
        command.extend(["--llm-model", llm_model])
    if llm_prompt_file:
        command.extend(["--llm-prompt-file", llm_prompt_file])
    if llm_command_template:
        command.extend(["--llm-command-template", llm_command_template])

    return command


def launch_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("Transcriber")
    root.geometry("860x760")
    root.minsize(760, 640)

    container = ttk.Frame(root, padding=16)
    container.pack(fill="both", expand=True)
    container.columnconfigure(1, weight=1)
    container.rowconfigure(11, weight=1)

    input_var = tk.StringVar()
    output_var = tk.StringVar()
    model_var = tk.StringVar(value="medium")
    language_var = tk.StringVar()
    auto_confirm_var = tk.BooleanVar(value=True)
    keep_audio_var = tk.BooleanVar(value=False)
    use_llm_var = tk.BooleanVar(value=False)
    llm_provider_var = tk.StringVar(value="claude")
    llm_model_var = tk.StringVar()
    llm_prompt_var = tk.StringVar()
    llm_template_var = tk.StringVar()
    status_var = tk.StringVar(value="Gotowe")

    process_state = {"running": False, "process": None}

    def append_log(message: str) -> None:
        log_text.configure(state="normal")
        log_text.insert("end", message)
        log_text.see("end")
        log_text.configure(state="disabled")

    def browse_input() -> None:
        file_path = filedialog.askopenfilename(
            title="Wybierz plik audio lub wideo",
            filetypes=[
                ("Audio/Video", "*.mp3 *.wav *.m4a *.flac *.ogg *.mp4 *.mov *.mkv *.avi *.webm *.m4v"),
                ("Wszystkie pliki", "*.*"),
            ],
        )
        if file_path:
            input_var.set(file_path)
            if not output_var.get():
                output_var.set(str(Path(file_path).with_suffix(".txt")))

    def browse_output() -> None:
        file_path = filedialog.asksaveasfilename(
            title="Zapisz transkrypcję jako",
            defaultextension=".txt",
            filetypes=[("Plik tekstowy", "*.txt"), ("Wszystkie pliki", "*.*")],
        )
        if file_path:
            output_var.set(file_path)

    def browse_prompt() -> None:
        file_path = filedialog.askopenfilename(
            title="Wybierz plik promptu",
            filetypes=[("Plik tekstowy", "*.txt"), ("Wszystkie pliki", "*.*")],
        )
        if file_path:
            llm_prompt_var.set(file_path)

    def sync_llm_state(*_args: object) -> None:
        enabled = use_llm_var.get()
        provider_state = "readonly" if enabled else "disabled"
        entry_state = "normal" if enabled else "disabled"
        template_state = "normal" if enabled and llm_provider_var.get() == "codex" else "disabled"
        prompt_button_state = "normal" if enabled else "disabled"

        llm_provider_combo.configure(state=provider_state)
        llm_model_entry.configure(state=entry_state)
        llm_prompt_entry.configure(state=entry_state)
        llm_prompt_button.configure(state=prompt_button_state)
        llm_template_entry.configure(state=template_state)

    def set_controls_enabled(enabled: bool) -> None:
        base_state = "normal" if enabled else "disabled"
        readonly_state = "readonly" if enabled else "disabled"

        input_entry.configure(state=base_state)
        input_button.configure(state=base_state)
        output_entry.configure(state=base_state)
        output_button.configure(state=base_state)
        model_combo.configure(state=readonly_state)
        language_entry.configure(state=base_state)
        auto_confirm_check.configure(state=base_state)
        keep_audio_check.configure(state=base_state)
        use_llm_check.configure(state=base_state)
        start_button.configure(state=base_state)
        sync_llm_state()

    def run_command(command: list[str]) -> None:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            root.after(
                0,
                lambda: (
                    append_log(f"Nie udało się uruchomić procesu: {exc}\n"),
                    status_var.set("Błąd uruchomienia"),
                    set_controls_enabled(True),
                    process_state.update({"running": False, "process": None}),
                ),
            )
            return

        process_state["process"] = process

        if process.stdout is not None:
            for line in process.stdout:
                root.after(0, lambda current_line=line: append_log(current_line))

        return_code = process.wait()

        def finish() -> None:
            process_state["running"] = False
            process_state["process"] = None
            set_controls_enabled(True)
            if return_code == 0:
                status_var.set("Zakończono pomyślnie")
                messagebox.showinfo("Transcriber", "Transkrypcja zakończona.")
            else:
                status_var.set(f"Błąd procesu ({return_code})")
                messagebox.showerror("Transcriber", f"Proces zakończył się błędem: {return_code}")

        root.after(0, finish)

    def start_transcription() -> None:
        if process_state["running"]:
            return

        input_path = input_var.get().strip()
        if not input_path:
            messagebox.showerror("Transcriber", "Wybierz plik wejściowy.")
            return

        if use_llm_var.get() and not llm_prompt_var.get().strip():
            messagebox.showerror("Transcriber", "Dla trybu LLM wskaż plik promptu.")
            return

        if use_llm_var.get() and llm_provider_var.get() == "codex" and not llm_template_var.get().strip():
            messagebox.showerror("Transcriber", "Dla providera 'codex' podaj szablon komendy.")
            return

        command = build_transcribe_command(
            input_path=input_path,
            output_path=output_var.get().strip() or None,
            model_name=model_var.get().strip() or "medium",
            language=language_var.get().strip() or None,
            auto_confirm=auto_confirm_var.get(),
            keep_converted_audio=keep_audio_var.get(),
            llm_provider=llm_provider_var.get() if use_llm_var.get() else None,
            llm_model=llm_model_var.get().strip() or None,
            llm_prompt_file=llm_prompt_var.get().strip() or None,
            llm_command_template=llm_template_var.get().strip() or None,
        )

        log_text.configure(state="normal")
        log_text.delete("1.0", "end")
        log_text.configure(state="disabled")
        append_log("$ " + subprocess.list2cmdline(command) + "\n\n")

        process_state["running"] = True
        status_var.set("Trwa przetwarzanie...")
        set_controls_enabled(False)

        worker = threading.Thread(target=run_command, args=(command,), daemon=True)
        worker.start()

    ttk.Label(container, text="Plik wejściowy").grid(row=0, column=0, sticky="w", pady=(0, 6))
    input_entry = ttk.Entry(container, textvariable=input_var)
    input_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))
    input_button = ttk.Button(container, text="Wybierz...", command=browse_input)
    input_button.grid(row=0, column=2, sticky="ew", pady=(0, 6))

    ttk.Label(container, text="Plik wynikowy").grid(row=1, column=0, sticky="w", pady=(0, 6))
    output_entry = ttk.Entry(container, textvariable=output_var)
    output_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))
    output_button = ttk.Button(container, text="Zapisz jako...", command=browse_output)
    output_button.grid(row=1, column=2, sticky="ew", pady=(0, 6))

    ttk.Label(container, text="Model Whisper").grid(row=2, column=0, sticky="w", pady=(0, 6))
    model_combo = ttk.Combobox(
        container,
        textvariable=model_var,
        values=["tiny", "base", "small", "medium", "large"],
        state="readonly",
    )
    model_combo.grid(row=2, column=1, sticky="w", pady=(0, 6))

    ttk.Label(container, text="Język").grid(row=3, column=0, sticky="w", pady=(0, 6))
    language_entry = ttk.Entry(container, textvariable=language_var)
    language_entry.grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))

    auto_confirm_check = ttk.Checkbutton(
        container,
        text="Automatycznie zgadzaj się na instalację brakujących pakietów",
        variable=auto_confirm_var,
    )
    auto_confirm_check.grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 2))

    keep_audio_check = ttk.Checkbutton(
        container,
        text="Zachowaj wygenerowany plik MP3 obok źródłowego wideo",
        variable=keep_audio_var,
    )
    keep_audio_check.grid(row=5, column=0, columnspan=3, sticky="w", pady=(2, 10))

    llm_frame = ttk.LabelFrame(container, text="Opcjonalne użycie LLM", padding=12)
    llm_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 12))
    llm_frame.columnconfigure(1, weight=1)

    use_llm_check = ttk.Checkbutton(
        llm_frame,
        text="Po transkrypcji uruchom CLI LLM",
        variable=use_llm_var,
        command=sync_llm_state,
    )
    use_llm_check.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

    ttk.Label(llm_frame, text="Provider").grid(row=1, column=0, sticky="w", pady=4)
    llm_provider_combo = ttk.Combobox(
        llm_frame,
        textvariable=llm_provider_var,
        values=["claude", "codex"],
        state="readonly",
    )
    llm_provider_combo.grid(row=1, column=1, sticky="w", pady=4)

    ttk.Label(llm_frame, text="Model LLM").grid(row=2, column=0, sticky="w", pady=4)
    llm_model_entry = ttk.Entry(llm_frame, textvariable=llm_model_var)
    llm_model_entry.grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)

    ttk.Label(llm_frame, text="Plik promptu").grid(row=3, column=0, sticky="w", pady=4)
    llm_prompt_entry = ttk.Entry(llm_frame, textvariable=llm_prompt_var)
    llm_prompt_entry.grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=4)
    llm_prompt_button = ttk.Button(llm_frame, text="Wybierz...", command=browse_prompt)
    llm_prompt_button.grid(row=3, column=2, sticky="ew", pady=4)

    ttk.Label(llm_frame, text="Szablon komendy").grid(row=4, column=0, sticky="w", pady=4)
    llm_template_entry = ttk.Entry(llm_frame, textvariable=llm_template_var)
    llm_template_entry.grid(row=4, column=1, columnspan=2, sticky="ew", pady=4)

    start_button = ttk.Button(container, text="Start", command=start_transcription)
    start_button.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, 10))

    ttk.Label(container, text="Log działania").grid(row=8, column=0, columnspan=3, sticky="w", pady=(0, 6))
    log_text = tk.Text(container, height=18, wrap="word", state="disabled")
    log_text.grid(row=9, column=0, columnspan=3, sticky="nsew")

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=log_text.yview)
    scrollbar.grid(row=9, column=3, sticky="ns")
    log_text.configure(yscrollcommand=scrollbar.set)

    status_label = ttk.Label(container, textvariable=status_var)
    status_label.grid(row=10, column=0, columnspan=3, sticky="w", pady=(10, 0))

    llm_provider_var.trace_add("write", sync_llm_state)
    sync_llm_state()
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe audio files or convert MP4/video to MP3 and transcribe with Whisper"
    )
    parser.add_argument("input", nargs="?", help="Path to audio/video file (mp3, wav, m4a, mp4, mkv, ...)")
    parser.add_argument("-o", "--output", help="Output .txt path (default: same name as input with .txt)")
    parser.add_argument(
        "-m",
        "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: medium)",
    )
    parser.add_argument(
        "-l",
        "--language",
        default=None,
        help="Language code, e.g. 'pl', 'en', 'de' (default: auto-detect)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Automatically approve installation of missing Python dependencies",
    )
    parser.add_argument(
        "--keep-converted-audio",
        action="store_true",
        help="Keep the generated MP3 next to the source video instead of using a temporary file",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["claude", "codex"],
        help="After transcription, send the result to the selected CLI provider",
    )
    parser.add_argument(
        "--llm-model",
        help="Model name passed to the selected provider, e.g. haiku for Claude",
    )
    parser.add_argument(
        "--llm-prompt-file",
        help="Path to a text file containing the prompt/instructions that should be combined with the transcript",
    )
    parser.add_argument(
        "--llm-command-template",
        help=(
            "Custom command template used for provider 'codex'. "
            "Available placeholders: {model}, {prompt}, {prompt_file}, {transcript_file}"
        ),
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch a simple desktop UI for choosing the file and options",
    )
    args = parser.parse_args()

    if args.gui or not args.input:
        launch_gui()
        return

    transcribe(
        input_path=args.input,
        output_path=args.output,
        model_name=args.model,
        language=args.language,
        auto_confirm=args.yes,
        keep_converted_audio=args.keep_converted_audio,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        llm_prompt_file=args.llm_prompt_file,
        llm_command_template=args.llm_command_template,
    )


if __name__ == "__main__":
    main()
