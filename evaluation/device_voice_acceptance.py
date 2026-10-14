"""Explicit user-run device check; not executed as device acceptance in CI."""
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.voice import VoskSpeechToText, PiperTextToSpeech

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vosk-model", required=True)
    parser.add_argument("--piper-model", required=True)
    parser.add_argument("--piper-executable", default="piper")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This playback check uses Windows winsound.")
    print("Speak Persian for five seconds.")
    text = VoskSpeechToText(args.vosk_model).listen()
    print("MICROPHONE_TRANSCRIPT:", text or "(empty; recognition not accepted)")
    result = PiperTextToSpeech(args.piper_executable, args.piper_model).speak("سلام سیاوش، این آزمون صدای فارسی ایران است.")
    print("SYNTHESIZED_WAV:", result["artifact"], "spoken:", result["spoken"])
    import winsound
    try:
        winsound.PlaySound(result["artifact"], winsound.SND_FILENAME)
        print("PLAYBACK_CALL_RETURNED; confirm audible Persian and quality yourself.")
    finally:
        Path(result["artifact"]).unlink(missing_ok=True)

if __name__ == "__main__":
    main()
