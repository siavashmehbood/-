# Final integrated acceptance map — IRAN 0.54.1

The authoritative acceptance result is the Actions run for the delivered master SHA, recorded in RELEASE_MANIFEST.json. Build-validation bundles are explicitly marked BUILD_VALIDATION_ONLY. No device acceptance or external model quality is inferred from hosted-runner results.

| Contract | Existing or restored behavioral evidence |
| --- | --- |
| Continuous dialogue, current request, follow-ups, style and no repeated response cycling | test_general_conversation.py, test_chat50_conversation.py, test_offline_conversation_memory_acceptance.py |
| Siavash identity, Dana memory, unrelated memories, project correction/history and restart | test_conversation_fact_memory.py, test_canonical_conversation_red_team.py, test_memory_intelligence_v2.py |
| CognitiveSystem sole owner | test_single_brain_routing.py, test_persian_architecture_contract.py, test_canonical_pipeline_entrypoint.py |
| Actual subordinate language call, invalid responses, no redirect outside loopback | test_final_delivery_regressions.py uses a real local HTTP server through IranRuntime.handle |
| External review, explicit human gate, deduplication and restart | test_chatgpt_review_pipeline.py, test_reviewer_human_gate_restart_acceptance.py, test_effect_learning.py |
| OFF, revoked-generation responses, bounded fallback, cooldown and malformed review | test_internet_permission_recovery.py, test_review_safety.py, test_reviewer_providers.py, test_final_delivery_regressions.py |
| Atomic state, validated backups, corruption recovery, process locks and ownership | test_critical_persistence.py, test_approval_backup_integrity.py, test_learning_gate_concurrency.py, test_shared_file_lock_concurrency.py, test_review_decision_journal_concurrency.py, test_runtime_ownership.py |
| GUI stop/close, background jobs, selected ID and late callbacks | test_gui_responsiveness.py, test_gui_contract.py |
| Persian/Arabic arithmetic, time precedence and observable tool failure | test_offline_arithmetic_acceptance.py, test_temporal_expression_isolation.py, test_remaining_tool_acceptance.py |
| Windows launcher, optional audio failure and synthesis/playback distinction | test_final_delivery_regressions.py; actual Windows venv launcher test on hosted Windows |
| Windows observable tool execution | test_windows_jarvis_acceptance.py and existing Windows Jarvis workflow |
| Complete current regression and benchmark requirements | IRAN Baseline, including pytest, unittest, runtime suite, conversation/Soar/Rasa benchmarks, bundle validation and CLI smoke |

Historical PR #138 is merged. The active #152 conversation fixes are preserved. Historical #113/#114/#116/#117/#119/#122 were inspected rather than blindly merged: whitespace and memory filtering were already present; missing time priority, calculator guards/user-facing validation and failure telemetry were recovered on the current architecture. Their regression behavior is retained in test_remaining_tool_acceptance.py.

The language engine is limited to governed greeting realization; factual answers still use local evidence. No generalized model quality or twenty-language acceptance is claimed. No new model, paid service or credential is provisioned.

External provider credential availability is recorded by Actions without exposing values. A successful status-recording job does not mean live service success: EXTERNAL_ACCEPTANCE_STATUS.json distinguishes BLOCKED_EXTERNAL from TRANSPORT_VERIFIED. The live diagnostic never approves learning for a human. Hosted Windows, local socket transport, FakeSTT and FakeTTS do not prove actual microphone, speaker, Persian voice quality or the user's Windows configuration.

See FINAL_ACCEPTANCE.md for the single user-device check and preservation of the previous data directory.
