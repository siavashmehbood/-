import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from persistence import RuntimeAlreadyRunning
from runtime.app import IranRuntime

ROOT=Path(__file__).parents[1]


def prepare(path):
    path.mkdir(exist_ok=True)
    shutil.copy(ROOT/'config.json',path)


def test_second_runtime_cannot_open_same_stores(tmp_path):
    prepare(tmp_path);first=IranRuntime(tmp_path)
    try:
        with pytest.raises(RuntimeAlreadyRunning):IranRuntime(tmp_path)
        assert first.handle('سلام')
    finally:first.close()
    reopened=IranRuntime(tmp_path)
    assert reopened.handle('سلام')
    reopened.close()


def test_separate_data_roots_are_independent(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';prepare(a);prepare(b)
    first=IranRuntime(a);second=IranRuntime(b)
    first.close();second.close()


def test_process_cannot_open_active_runtime(tmp_path):
    prepare(tmp_path);first=IranRuntime(tmp_path)
    code='''import sys
from runtime.app import IranRuntime
from persistence import RuntimeAlreadyRunning
try:
    r=IranRuntime(sys.argv[1])
except RuntimeAlreadyRunning:
    sys.exit(23)
else:
    r.close()
'''
    try:
        child=subprocess.run([sys.executable,'-c',code,str(tmp_path)],cwd=ROOT,capture_output=True,timeout=20)
        assert child.returncode==23,child.stderr.decode()
    finally:first.close()


def test_abrupt_process_exit_releases_ownership(tmp_path):
    prepare(tmp_path)
    code='import os,sys; from runtime.app import IranRuntime; r=IranRuntime(sys.argv[1]); os._exit(24)'
    child=subprocess.run([sys.executable,'-c',code,str(tmp_path)],cwd=ROOT,capture_output=True,timeout=20)
    assert child.returncode==24,child.stderr.decode()
    r=IranRuntime(tmp_path);r.close()


def test_failed_initialization_releases_ownership(tmp_path):
    prepare(tmp_path);(tmp_path/'config.json').write_text('{broken')
    with pytest.raises(ValueError):IranRuntime(tmp_path)
    prepare(tmp_path)
    r=IranRuntime(tmp_path);r.close()


def test_closed_runtime_cannot_write_after_replacement_starts(tmp_path):
    prepare(tmp_path);first=IranRuntime(tmp_path);first.close()
    second=IranRuntime(tmp_path)
    try:
        with pytest.raises(RuntimeError,match='Runtime is closed'):first.handle('من علی هستم.')
        assert not second.user_model.facts(predicate='name')
    finally:second.close()
