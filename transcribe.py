#!/usr/bin/env python3
"""
Audio and video transcription script using OpenAI Whisper.
Supports common audio formats and can convert MP4/video input to MP3 first.
Works on Windows, macOS and Linux.
"""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PYTHON_DEPENDENCIES = {
    "whisper": "openai-whisper",
    "imageio_ffmpeg": "imageio-ffmpeg",
}

VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm"}


def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


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
        if importlib.util.find_spec(module_name) is None:
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
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", *packages],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Failed to install dependencies: {exc}")
        sys.exit(exc.returncode or 1)


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
        shim_path = shim_dir / "ffmpeg.bat"
        shim_contents = f'@echo off\r\n"{ffmpeg_exe}" %*\r\n'
    else:
        shim_path = shim_dir / "ffmpeg"
        shim_contents = f'#!/bin/sh\n"{ffmpeg_exe}" "$@"\n'

    if not shim_path.exists() or shim_path.read_text(encoding="utf-8") != shim_contents:
        shim_path.write_text(shim_contents, encoding="utf-8")
        if os.name != "nt":
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
) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

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
            temp_dir.cleanup()
        print("Failed to convert video to MP3.")
        if exc.stderr:
            print(exc.stderr.strip())
        sys.exit(exc.returncode or 1)

    print(f"Prepared MP3: {output_mp3}")
    return output_mp3, temp_dir


def resolve_output_path(input_file: Path, output_path: str | None) -> Path:
    if output_path:
        return Path(output_path)
    return input_file.with_suffix(".txt")


def transcribe(
    input_path: str,
    output_path: str | None,
    model_name: str,
    language: str | None,
    auto_confirm: bool,
    keep_converted_audio: bool,
) -> None:
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: file not found: {input_file}")
        sys.exit(1)

    ensure_python_modules(["whisper"], auto_confirm=auto_confirm)
    ffmpeg_exe = ensure_ffmpeg(auto_confirm=auto_confirm)

    import whisper

    working_audio = input_file
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

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
        model = whisper.load_model(model_name)

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
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


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
    args = parser.parse_args()
    transcribe(
        input_path=args.input,
        output_path=args.output,
        model_name=args.model,
        language=args.language,
        auto_confirm=args.yes,
        keep_converted_audio=args.keep_converted_audio,
    )


if __name__ == "__main__":
    main()
