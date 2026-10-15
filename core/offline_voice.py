"""Offline, optional Persian voice transport for the existing desktop runtime.

No downloading or networking happens here. Models are configured per device.
"""
import json
import os
from pathlib import Path
import threading

from core.voice import PiperTextToSpeech, VoskSpeechToText, VoiceUnavailable


class OfflineVoice:
    def __init__(self, stt, tts, seconds=5, playback=None, stop_playback=None):
        self.stt, self.tts = stt, tts
        self.seconds = max(1, min(15, float(seconds)))
        self.cancelled = threading.Event()
        self.playback = playback or self._play_windows
        self.stop_playback = stop_playback or self._stop_windows
        self._playing = False

    def prepare(self):
        self.cancelled.clear()

    def cancel(self):
        self.cancelled.set()
        if self._playing:
            self.stop_playback()

    def _play_windows(self, path):
        if os.name != "nt":
            raise VoiceUnavailable("Offline speaker playback requires Windows")
        import winsound, wave
        with wave.open(str(path), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
        if self.cancelled.is_set(): return
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        try:
            self.cancelled.wait(duration)
        finally:
            winsound.PlaySound(None, 0)

    @staticmethod
    def _stop_windows():
        if os.name == "nt":
            import winsound
            winsound.PlaySound(None, 0)

    def listen(self):
        text = self.stt.listen(duration=self.seconds, cancel_event=self.cancelled)
        if self.cancelled.is_set():
            return {"ok": False, "reason": "cancelled"}
        return {"ok": bool(text.strip()), "text": text.strip(),
                "reason": "" if text.strip() else "no_speech"}

    def speak(self, text):
        if self.cancelled.is_set():
            return {"ok": False, "reason": "cancelled"}
        text = str(text).strip()
        if not text:
            return {"ok": False, "reason": "empty_text"}
        result = self.tts.speak(text)
        path = Path(result["artifact"])
        try:
            if self.cancelled.is_set():
                return {"ok": False, "reason": "cancelled"}
            self._playing = True
            # Recheck after publishing playback ownership so cancel cannot miss
            # the transition between synthesis and the speaker call.
            if self.cancelled.is_set():
                return {"ok": False, "reason": "cancelled"}
            self.playback(path)
            return {"ok": not self.cancelled.is_set(),
                    "played": not self.cancelled.is_set(),
                    "reason": "cancelled" if self.cancelled.is_set() else ""}
        finally:
            self._playing = False
            path.unlink(missing_ok=True)


def create_offline_voice(root):
    """Return (adapter, availability reason), without loading model weights."""
    root = Path(root)
    config_path = root / "voice.local.json"
    if not config_path.exists():
        return None, "مدل‌های صدای آفلاین تنظیم نشده‌اند"
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8-sig"))
        if not isinstance(cfg, dict):
            return None, "تنظیمات صدای آفلاین معتبر نیست"
        if cfg.get("enabled") is not True:
            return None, "صدای آفلاین خاموش است"
        def resolve(key):
            path = Path(cfg[key])
            return path if path.is_absolute() else root / path
        stt_model, tts_model, executable = (
            resolve("vosk_model"), resolve("piper_model"), resolve("piper_executable"))
        if not stt_model.is_dir() or not tts_model.is_file() or not executable.is_file():
            return None, "فایل مدل یا برنامهٔ صدای آفلاین پیدا نشد"
        if not Path(str(tts_model) + ".json").is_file():
            return None, "تنظیمات مدل صدای فارسی پیدا نشد"
        from importlib.util import find_spec
        if not find_spec("vosk") or not find_spec("sounddevice"):
            return None, "وابستگی‌های میکروفون آفلاین نصب نشده‌اند"
        return OfflineVoice(VoskSpeechToText(stt_model),
                            PiperTextToSpeech(str(executable), str(tts_model)),
                            seconds=cfg.get("record_seconds", 5)), ""
    except (OSError, ValueError, TypeError, KeyError):
        return None, "تنظیمات صدای آفلاین معتبر نیست"
