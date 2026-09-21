import shutil
from pathlib import Path
import pytest
from runtime.app import IranRuntime
from core.semantic_verifier import VerificationResult

@pytest.mark.parametrize('question', ['اسم من چیست؟', 'اسم من چیه؟', 'نام من چیست؟', 'اسمم چی بود؟'])
def test_current_identity_survives_correction_and_restart(tmp_path, question):
    shutil.copy(Path(__file__).parents[1]/'config.json', tmp_path)
    r = IranRuntime(tmp_path)
    assert 'UNKNOWN' in r.handle(question)
    r.handle('من علی هستم.'); r.handle('من رضا هستم.')
    assert 'رضا' in r.handle(question)
    r.close()
    r = IranRuntime(tmp_path)
    assert 'رضا' in r.handle(question)
    r.close()


def test_short_route_calls_actual_verifier(tmp_path, monkeypatch):
    shutil.copy(Path(__file__).parents[1]/'config.json', tmp_path)
    r = IranRuntime(tmp_path)
    calls = []
    def reject(question, answer, *args, **kwargs):
        calls.append((question,answer))
        return VerificationResult(False, .1, ['fixture_failed_consistency'], [])
    monkeypatch.setattr(r.cognitive_system.pipeline.semantic_verifier, 'verify', reject)
    assert 'UNKNOWN' in r.handle('سلام')
    assert any(row[0] == 'assistant' and 'UNKNOWN' in row[1] for row in r.memory.recent(10))
    assert calls and r.cognitive_system.last_trace.verification_status == 'UNKNOWN'
    assert 'fixture_failed_consistency' in r.cognitive_system.last_trace.verification_reasons
    r.close()


def test_role_statement_does_not_replace_personal_name(tmp_path):
    shutil.copy(Path(__file__).parents[1]/'config.json', tmp_path)
    r=IranRuntime(tmp_path)
    r.handle('من علی هستم.'); r.handle('من دانشجو هستم.')
    assert 'علی' in r.handle('اسم من چیست؟')
    assert all(f['object']!='دانشجو' for f in r.user_model.facts(predicate='name'))
    assert any(f['object']=='دانشجو' for f in r.user_model.facts(predicate='role'))
    r.close()
