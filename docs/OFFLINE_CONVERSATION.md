# Local conversation on the desktop

The canonical IranRuntime owns memory, facts, tools and learning. The optional local language model supplies ordinary Persian social conversation with the current profile, topic, constraints and three recent turn pairs. It does not execute tools or write personal facts. Explicit identity questions (including punctuation-free spoken paraphrases) use structured memory before language generation. Historical malformed name records remain stored but are excluded from active name recall.

The desktop shows whether local generation was used or was unavailable on the latest turn. A configured endpoint alone is not evidence that a model server is running. Model failure retains the symbolic runtime; output quality is not established by an HTTP success or deterministic test.

For an existing llama.cpp Windows CPU installation, create the ignored `language.local.json` beside config.json:

```json
{
  "enabled": true,
  "executable": "C:/Users/NAME/AppData/Local/IRAN/language/llama/llama-server.exe",
  "model_path": "C:/Users/NAME/AppData/Local/IRAN/language/qwen2.5-1.5b-instruct-q4_k_m.gguf"
}
```

The existing language_engine settings in config.json identify the model alias and loopback endpoint. Run launch_gui.pyw (or the existing desktop shortcut). It starts the explicitly configured server on 127.0.0.1 with two CPU threads, 2048 context tokens and one slot, and stops only its own child when the application exits. An already running server is not owned or stopped. Missing files are logged without preventing text-mode startup. No model is downloaded automatically. Keep model weights outside git and use an ASCII-only device path when native libraries require it.

Tests in tests/test_spoken_conversation_repair.py use isolated runtime roots, fixture model responses and no downloads. Real local-model latency, subjective Persian fluency and human microphone recognition require separate device acceptance. This integration does not promote the small deployment model as a winner of the multilingual foundation benchmark.
