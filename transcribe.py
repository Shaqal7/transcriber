#!/usr/bin/env python3
"""
Audio transcription script using OpenAI Whisper.
Supports MP3, WAV, M4A, FLAC, OGG and other ffmpeg-compatible formats.
Works on Windows, macOS and Linux.
"""

import argparse
import sys
from pathlib import Path


def get_audio_duration(file_path: str) -> float:
    """Get audio duration in seconds using whisper's audio loader."""
    import whisper.audio
    audio = whisper.audio.load_audio(file_path)
    return len(audio) / whisper.audio.SAMPLE_RATE


def transcribe(input_path: str, output_path: str | None, model_name: str, language: str | None) -> None:
    try:
        import whisper
    except ImportError:
        print("Error: openai-whisper is not installed. Run: pip install openai-whisper")
        sys.exit(1)

    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: file not found: {input_file}")
        sys.exit(1)

    if output_path:
        out = Path(output_path)
    else:
        out = input_file.with_suffix(".txt")

    duration = get_audio_duration(str(input_file))
    print(f"Audio duration: {format_time(duration)}")
    print(f"Loading model '{model_name}'...")
    model = whisper.load_model(model_name)

    print(f"Transcribing: {input_file}")
    # verbose=None shows tqdm progress bar without printing each segment
    transcribe_opts = {"verbose": None}
    if language:
        transcribe_opts["language"] = language

    result = model.transcribe(str(input_file), **transcribe_opts)

    with open(out, "w", encoding="utf-8") as f:
        for seg in result["segments"]:
            start = format_time(seg["start"])
            end = format_time(seg["end"])
            text = seg["text"].strip()
            f.write(f"[{start} - {end}] {text}\n")

    print(f"Detected language: {result['language']}")
    print(f"Segments: {len(result['segments'])}")
    print(f"Saved to: {out}")


def format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio files using Whisper")
    parser.add_argument("input", help="Path to audio file (mp3, wav, m4a, flac, ogg, ...)")
    parser.add_argument("-o", "--output", help="Output .txt path (default: same name as input with .txt)")
    parser.add_argument("-m", "--model", default="medium", choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model size (default: medium)")
    parser.add_argument("-l", "--language", default=None,
                        help="Language code, e.g. 'pl', 'en', 'de' (default: auto-detect)")
    args = parser.parse_args()
    transcribe(args.input, args.output, args.model, args.language)


if __name__ == "__main__":
    main()
