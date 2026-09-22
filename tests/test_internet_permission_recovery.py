import json
import pytest
from security.internet_access import InternetAccessManager


@pytest.mark.parametrize('value',['false','true',1,[],{},None])
def test_non_boolean_permission_never_enables_network(tmp_path,value):
    path=tmp_path/'internet.json';path.write_text(json.dumps({'enabled':value}))
    manager=InternetAccessManager(path)
    assert manager.status()['enabled'] is False
    with pytest.raises(PermissionError): manager.require()


def test_corrupt_revocation_does_not_restore_old_enabled_backup(tmp_path):
    path=tmp_path/'internet.json'
    manager=InternetAccessManager(path);manager.enable();manager.disable()
    assert json.loads(path.with_suffix('.json.bak').read_text())['enabled'] is True
    path.write_text('{broken')
    restored=InternetAccessManager(path)
    assert not restored.status()['enabled']
    assert path.read_text()=='{broken'
    restored.enable()
    assert InternetAccessManager(path).status()['enabled']


def test_missing_revocation_does_not_restore_old_enabled_backup(tmp_path):
    path=tmp_path/'internet.json'
    manager=InternetAccessManager(path);manager.enable();manager.disable();path.unlink()
    assert not InternetAccessManager(path).status()['enabled']


@pytest.mark.parametrize('operation',['enable','disable'])
def test_permission_write_failure_leaves_network_off(tmp_path,monkeypatch,operation):
    manager=InternetAccessManager(tmp_path/'internet.json')
    if operation=='disable': manager.enable()
    def failed_save(): raise OSError('fixture disk failure')
    monkeypatch.setattr(manager,'_save',failed_save)
    with pytest.raises(OSError): getattr(manager,operation)()
    assert not manager.status()['enabled']
