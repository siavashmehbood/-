"""Canonical composition order for IranRuntime.

The runtime is assembled by monkeypatching: `runtime/app.py` reassigns
`IranRuntime.handle` 22 times, `IranRuntime.__init__` 13 times, and ~30 further
methods once each. The *order* of those assignments defines the effective
behaviour of the runtime, but that order is only implicit in the file layout —
nothing declares it, and nothing checks it.

That is a real maintenance hazard. A patch inserted or moved in the wrong place
silently changes routing and answer generation, and no test names the invariant
being broken.

This module does not change any behaviour. It records the composition order as
inspectable data so it can be asserted, reviewed and diffed. Enforcement lives in
`tests/test_runtime_composition.py`.

`LAYER_ORDER` entries are the function name assigned to `IranRuntime.handle`, in the
order `app.py` assigns them. Enforcement lives in
`tests/test_runtime_composition.py`, which parses `app.py`, extracts every
`IranRuntime.handle = <fn>` assignment in file order, and asserts the sequence equals
`HANDLE_LAYER_ORDER`. Because these are module-level assignments, textual order is
execution order, so this is a genuine ordering proof and not a grep. Adding, removing
or reordering a layer fails the test until this file is updated deliberately.
"""

# Order in which each function becomes IranRuntime.handle. Last one wins at
# runtime, and the outermost wrapper runs first for a given call.
HANDLE_LAYER_ORDER = (
    '_handle_v2',
    '_handle_v3',
    '_handle_v4',
    '_handle_v5',
    '_handle_lang28',
    '_handle_usermodel',
    '_handle_um_identity',
    '_handle_v32_user_record',
    '_unified_handle',
    '_unified_handle_v2',
    '_unified_handle_v3',
    '_unified_handle_v4',
    '_unified_handle_v5',
    '_unified_handle_v6',
    '_unified_handle_commands',
    '_unified_handle_goals',
    '_unified_handle_verified_command',
    '_unified_handle_role',
    '_canonical_dialogue_handle',
    '_canonical_dialogue_handle_v2',
    '_handle_v41',
    '_chat_final_runtime_handle',
)

# Order in which LocalDialogueEngine.handle is wrapped by core/chat_upgrade.py.
# These run inside the runtime handle chain, so their order also matters.
DIALOGUE_LAYER_ORDER = (
    'install',
    'install_v2',
    'install_v3',
    'install_v4',
    'install_v5',
    'install_v6',
    'install_v7',
    'install_v8',
)

# Other IranRuntime attributes that are monkeypatched, and how many times. Repeated
# assignment is itself a smell: it means the later definition silently supersedes the
# earlier one with no record that both exist.
METHOD_PATCH_COUNTS = {
    'handle': 22,
    '__init__': 13,
    'benchmark_run': 3,
    'execute_recoverable_task': 2,
    'close': 2,
    'create_task': 1,
    'execute_verified_action': 1,
    'execute_verified_goal': 1,
    'fail_and_replan': 1,
    'learn_procedure_skill': 1,
    'retrieve_skill': 1,
    'run_goal': 1,
    'start_autonomous_daemon': 1,
    'stop_autonomous_daemon': 1,
    'autonomous_run': 1,
    'autonomous_step': 1,
    'autonomous_benchmark': 1,
    'autonomy_snapshot': 1,
    'autonomous_supervisor_run': 1,
    'autonomous_supervisor_step': 1,
    'autonomous_supervisor_snapshot': 1,
    'conversation_snapshot': 1,
    'conversation_trace': 1,
    'advanced_cognitive_snapshot': 1,
    'virtual_world_benchmark': 1,
}

# Attributes that are assigned more than once. These are the ones where ordering is
# load-bearing and where a future refactor must preserve semantics explicitly.
ORDER_SENSITIVE = tuple(sorted(k for k, v in METHOD_PATCH_COUNTS.items() if v > 1))


def expected_handle_layers():
    return len(HANDLE_LAYER_ORDER)


def describe():
    return {
        'handle_layers': expected_handle_layers(),
        'dialogue_layers': len(DIALOGUE_LAYER_ORDER),
        'method_patch_sites': sum(METHOD_PATCH_COUNTS.values()),
        'order_sensitive': list(ORDER_SENSITIVE),
    }
