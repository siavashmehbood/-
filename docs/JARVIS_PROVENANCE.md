# JARVIS capability research and provenance

IRAN keeps `CognitiveSystem` as the only decision owner. Voice, screen, desktop tools
and computer-use are I/O/action adapters.

## Sources reviewed

- `alphacep/vosk-api` — Apache-2.0. Reviewed for offline STT architecture. IRAN's
  `VoskSpeechToText` is an independent Python adapter over the public Vosk package;
  no source code was copied.
- `rhasspy/piper` — MIT, copyright Michael Hansen. Reviewed for local TTS and CLI
  model invocation. IRAN's adapter is independently implemented and invokes a
  separately installed Piper executable. Voice model licenses must be checked
  separately before distribution.
- `MultiX0/jarvis` — Apache-2.0 source. Reviewed for graceful degradation,
  microphone/wake-word/TTS fallback architecture. No source copied. Its bundled
  hey_jarvis wake-word model has CC BY-NC-SA restrictions, so IRAN does not bundle it.
- `aviarytech/jarvis` — MIT. Reviewed for pluggable offline STT, permission-gated
  skills and opt-in computer-use architecture. No source copied.

## IRAN implementation

All files added in this integration are original IRAN implementations:
`core/voice.py`, `tools/desktop.py`, and `core/computer_use.py`.
No third-party Jarvis source file has been copied or vendored.

Optional dependencies are deliberately not mandatory core requirements. Missing Vosk,
sounddevice, PyAutoGUI, Piper, microphone, voice model, or display produces an explicit
unavailable/error result rather than disabling text cognition.

Windows GUI acceptance must run on a real Windows runner/machine. Linux CI validates
platform-independent filesystem/system behavior, permission denial, failure honesty,
voice-to-canonical routing using a transport test double, and restart persistence.
