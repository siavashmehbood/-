"""Local-first voice adapters. Optional dependencies never break text mode."""
from dataclasses import dataclass
from pathlib import Path
import json, os, subprocess, tempfile, wave

class VoiceUnavailable(RuntimeError): pass

class SpeechToText:
    def listen(self) -> str: raise NotImplementedError
    def transcribe_file(self, path) -> str: raise NotImplementedError

class VoskSpeechToText(SpeechToText):
    def __init__(self, model_path, sample_rate=16000):
        self.model_path=str(model_path); self.sample_rate=int(sample_rate)
    def _recognizer(self):
        try:
            from vosk import Model, KaldiRecognizer
        except ImportError as exc: raise VoiceUnavailable("vosk optional dependency is not installed") from exc
        if not Path(self.model_path).exists(): raise VoiceUnavailable("vosk model not found")
        return KaldiRecognizer(Model(self.model_path), self.sample_rate)
    def transcribe_file(self,path):
        rec=self._recognizer()
        with wave.open(str(path),"rb") as wf:
            if wf.getnchannels()!=1 or wf.getsampwidth()!=2:
                raise ValueError("Vosk WAV input must be mono 16-bit PCM")
            while True:
                data=wf.readframes(4000)
                if not data: break
                rec.AcceptWaveform(data)
        return str(json.loads(rec.FinalResult()).get("text","")).strip()
    def listen(self):
        try: import sounddevice as sd
        except ImportError as exc: raise VoiceUnavailable("sounddevice optional dependency is not installed") from exc
        rec=self._recognizer(); chunks=[]
        def callback(indata,frames,time,status): chunks.append(bytes(indata))
        try:
            with sd.RawInputStream(samplerate=self.sample_rate,blocksize=8000,dtype="int16",channels=1,callback=callback):
                import time as _time; _time.sleep(5)
        except Exception as exc: raise VoiceUnavailable(f"microphone unavailable: {type(exc).__name__}") from exc
        for chunk in chunks: rec.AcceptWaveform(chunk)
        return str(json.loads(rec.FinalResult()).get("text","")).strip()

class TextToSpeech:
    def speak(self,text): raise NotImplementedError

class WindowsTextToSpeech(TextToSpeech):
    def speak(self,text):
        if os.name!="nt": raise VoiceUnavailable("Windows TTS is available only on Windows")
        safe=str(text).replace("'","''")
        script=("Add-Type -AssemblyName System.Speech; "
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Speak('{safe}')")
        subprocess.run(["powershell","-NoProfile","-NonInteractive","-Command",script],
                       check=True,timeout=60,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        return {"spoken":True,"backend":"windows"}

class PiperTextToSpeech(TextToSpeech):
    def __init__(self, executable="piper", model_path=None):
        self.executable=executable; self.model_path=model_path
    def speak(self,text):
        if not self.model_path: raise VoiceUnavailable("Piper model is not configured")
        with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as out: output=out.name
        subprocess.run([self.executable,"--model",str(self.model_path),"--output_file",output],
                       input=str(text),text=True,check=True,timeout=60)
        return {"spoken":True,"backend":"piper","artifact":output}

@dataclass
class WakeWord:
    phrase: str="ایران"
    enabled: bool=True
    def detect(self,text):
        return bool(self.enabled and self.phrase.strip() and self.phrase.strip().lower() in str(text).lower())

class VoiceAssistant:
    """Voice is transport only: audio -> canonical runtime -> final text -> TTS."""
    def __init__(self,runtime,stt,tts=None,wake_word=None):
        self.runtime=runtime; self.stt=stt; self.tts=tts; self.wake_word=wake_word
    def handle_audio_file(self,path):
        text=self.stt.transcribe_file(path)
        if self.wake_word and self.wake_word.enabled and not self.wake_word.detect(text):
            return {"accepted":False,"transcript":text}
        answer=self.runtime.handle(text)
        speech=self.tts.speak(answer) if self.tts else None
        return {"accepted":True,"transcript":text,"answer":answer,"speech":speech}
