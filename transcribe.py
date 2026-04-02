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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe audio files or convert MP4/video to MP3 and transcribe with Whisper"
    )
    parser.add_argument("input", help="Path to audio/video file (mp3, wav, m4a, mp4, mkv, ...)")
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
    args = parser.parse_args()
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
