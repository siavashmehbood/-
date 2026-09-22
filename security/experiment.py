"""Restricted deterministic Python experiments, not a general Python sandbox.

No imports, reflection, classes or arbitrary attributes are accepted. Execution
also requires OS resource limits; unsupported platforms fail closed.
"""
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile

BUILTINS = ('abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'float', 'int',
            'isinstance', 'len', 'list', 'max', 'min', 'print', 'range', 'reversed',
            'round', 'set', 'sorted', 'str', 'sum', 'tuple', 'zip')
NODES = {
    'Module', 'Expr', 'Assign', 'AugAssign', 'FunctionDef', 'arguments', 'arg',
    'Return', 'If', 'IfExp', 'For', 'While', 'Break', 'Continue', 'Pass', 'Assert',
    'Name', 'Load', 'Store', 'Constant', 'List', 'Tuple', 'Set', 'Dict', 'Subscript',
    'Slice', 'Call', 'keyword', 'Attribute', 'BinOp', 'UnaryOp', 'BoolOp', 'Compare',
    'ListComp', 'SetComp', 'DictComp', 'GeneratorExp', 'comprehension',
    'Add', 'Sub', 'Mult', 'Div', 'FloorDiv', 'Mod', 'Pow', 'USub', 'UAdd', 'Not',
    'And', 'Or', 'Eq', 'NotEq', 'Lt', 'LtE', 'Gt', 'GtE', 'In', 'NotIn', 'Is', 'IsNot',
}


def validate(code):
    if len(code) > 12000:
        raise ValueError('sandbox code too large')
    tree = ast.parse(code)
    declared = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    declared.update(n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    declared.update(n.arg for n in ast.walk(tree) if isinstance(n, ast.arg))
    for node in ast.walk(tree):
        if type(node).__name__ not in NODES:
            raise PermissionError('sandbox rejected syntax: ' + type(node).__name__)
        if isinstance(node, ast.Attribute) and node.attr not in {'index', 'count', 'get', 'append', 'sort'}:
            raise PermissionError('sandbox rejected attribute: ' + node.attr)
        if isinstance(node, ast.Name):
            if node.id.startswith('_') or node.id not in declared | set(BUILTINS):
                raise PermissionError('sandbox rejected name: ' + node.id)
        if isinstance(node, ast.FunctionDef) and (node.decorator_list or node.name.startswith('_')):
            raise PermissionError('sandbox rejected decorated/private function')
    return tree


# Limits are installed inside the new interpreter, avoiding preexec_fn in GUI
# threads. User code receives only explicitly selected builtins, no runner globals.
RUNNER = '''import builtins, json, resource, sys
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
resource.setrlimit(resource.RLIMIT_FSIZE, (262144, 262144))
with open(sys.argv[1], encoding='utf-8') as handle:
    code = handle.read()
allowed = json.loads(sys.argv[2])
scope = {'__builtins__': {name: getattr(builtins, name) for name in allowed}}
exec(compile(code, '<restricted-experiment>', 'exec'), scope, scope)
'''


def run_experiment(code, timeout=5):
    code = str(code)
    validate(code)
    try:
        import resource
        if not all(hasattr(resource, name) for name in ('RLIMIT_CORE', 'RLIMIT_AS', 'RLIMIT_CPU', 'RLIMIT_FSIZE')):
            raise ImportError
    except ImportError:
        return {'ok': False, 'returncode': None, 'stdout': '',
                'stderr': 'sandbox_resource_limits_unavailable', 'reason': 'unsupported_platform'}
    with tempfile.TemporaryDirectory(prefix='iran-exp-') as folder:
        script = Path(folder) / 'experiment.py'
        script.write_text(code, encoding='utf-8')
        # Regular files are bounded by RLIMIT_FSIZE; capture_output would buffer
        # unbounded output in the parent, outside the child's memory limit.
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                proc = subprocess.run([sys.executable, '-I', '-S', '-c', RUNNER,
                                       str(script), json.dumps(BUILTINS)], cwd=folder,
                                      env={'PYTHONDONTWRITEBYTECODE': '1'}, stdin=subprocess.DEVNULL,
                                      stdout=out, stderr=err, timeout=max(1, min(15, float(timeout))))
                returncode = proc.returncode
                reason = '' if returncode == 0 else 'experiment_failed'
            except subprocess.TimeoutExpired:
                returncode, reason = None, 'timeout'
            out.seek(0); err.seek(0)
            return {'ok': returncode == 0, 'returncode': returncode,
                    'stdout': out.read(8000).decode('utf-8', errors='replace'),
                    'stderr': err.read(4000).decode('utf-8', errors='replace'), 'reason': reason}
