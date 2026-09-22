import pytest
from tools.builtin import build_registry


def test_sandbox_cannot_write_through_builtin_alias(tmp_path):
    marker=tmp_path/'outside-experiment.txt'
    code=f"import builtins\nwriter = builtins.open\nwriter({str(marker)!r}, 'w').write('unexpected')"
    tool=build_registry(tmp_path,None).get('sandbox_python')
    with pytest.raises(PermissionError):
        tool.run(code=code)
    assert not marker.exists()


@pytest.mark.parametrize('code',[
    'import builtins as b\nprint(b)',
    'value = (1).__class__.__mro__',
    'namespace = globals()',
    'import urllib.request as client',
    'class Custom:\n    pass',
])
def test_sandbox_rejects_reflection_and_imports(tmp_path,code):
    with pytest.raises(PermissionError):
        build_registry(tmp_path,None).run('sandbox_python',code=code)


def test_restricted_experiment_executes_real_function(tmp_path):
    pytest.importorskip('resource')
    result=build_registry(tmp_path,None).run('sandbox_python',code='def add(a,b):\n    return a+b\nassert add(2,4)==6\nprint(add(-2,5))')
    assert result['ok'] and result['stdout'].strip()=='3'


@pytest.mark.parametrize('code', ['while True:\n    pass', "print('x' * 1000000)", 'huge = [0] * 100000000'])
def test_resource_exhaustion_is_bounded_failure(tmp_path,code):
    pytest.importorskip('resource')
    result=build_registry(tmp_path,None).run('sandbox_python',code=code,timeout=1)
    assert not result['ok']
    assert len(result['stdout'])<=8000 and len(result['stderr'])<=4000


def test_missing_os_limits_does_not_run_child(tmp_path,monkeypatch):
    import sys
    import security.experiment as experiment
    monkeypatch.setitem(sys.modules,'resource',None)
    monkeypatch.setattr(experiment.subprocess,'run',lambda *a,**kw: pytest.fail('unsafe child launched'))
    assert experiment.run_experiment('assert 1 == 1')['reason']=='unsupported_platform'


def test_all_builtin_capability_templates_execute_under_restrictions(tmp_path):
    pytest.importorskip('resource')
    from learning.capability_learning import CapabilityLearningEngine
    from tests.test_capability_learning import FakeRuntime
    engine=CapabilityLearningEngine(FakeRuntime(tmp_path))
    tool=build_registry(tmp_path,None).get('sandbox_python')
    for topic in ('python programming','algorithm','software test','memory','planning','novel domain'):
        candidate={'topic':topic,'claim':'fixture only','candidate_id':topic}
        for step in engine._experiment_plan(candidate)['steps']:
            result=tool.run(code=step['code'])
            assert result['ok'], (topic,step['test'],result)
