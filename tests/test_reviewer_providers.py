import json
from pathlib import Path
import pytest
import providers.reviewer as reviewer_module
from providers.reviewer import ProviderManager, ReviewerProvider, ReviewFailure, decision
from security.internet_access import InternetAccessManager

class FakeProvider:
    def __init__(self,name,outcome):
        self.name=name;self.outcome=outcome;self.calls=0
        self.config={};self.timeout=1;self.cooldown=60;self.retries=0;self.model='fixture'
    def availability(self): return 'AVAILABLE',''
    def review(self,row):
        self.calls+=1
        if isinstance(self.outcome,Exception): raise self.outcome
        return self.outcome

def manager(tmp_path, providers):
    internet=InternetAccessManager(tmp_path/'internet.json');internet.enable()
    return ProviderManager(tmp_path,{},internet,providers,clock=lambda:1000)

@pytest.mark.parametrize('failure',[ReviewFailure('unavailable','UNAVAILABLE'),ReviewFailure('429','RATE_LIMITED',180),ReviewFailure('bad_json'),TimeoutError()])
def test_fallback(tmp_path,failure):
    a=FakeProvider('a',failure);b=FakeProvider('b',{'learn':True})
    m=manager(tmp_path,[a,b]);result=m.review({'claim':'test'})
    assert result['ok'] and result['result']['provider']=='b'
    assert a.calls==b.calls==1
    restored=manager(tmp_path,[a,b]);restored.review({})
    assert a.calls==1
    assert restored.health()[0]['state'] in ('RATE_LIMITED','COOLDOWN')

def test_all_unavailable_preserves_wait_state(tmp_path):
    a=FakeProvider('a',ReviewFailure('down'))
    assert manager(tmp_path,[a]).review({})['state']=='WAITING_FOR_REVIEWER'

def test_offline_sends_nothing_and_resumes(tmp_path):
    a=FakeProvider('a',{'learn':False});m=manager(tmp_path,[a]);m.internet.disable()
    assert m.review({})['reason']=='internet_off' and a.calls==0
    m.internet.enable();assert m.review({})['ok'] and a.calls==1

def test_retry_is_bounded(tmp_path):
    a=FakeProvider('a',ReviewFailure('down'));a.retries=2
    b=FakeProvider('b',ReviewFailure('down'));b.retries=2
    m=manager(tmp_path,[a,b]);m.max_attempts=4
    assert len(m.review({})['attempts'])==4
    assert a.calls+b.calls==4

@pytest.mark.parametrize('name',['openrouter','gemini','groq','cerebras','mistral'])
def test_no_implicit_paid_activation(name):
    p=ReviewerProvider(name,{'enabled':True,'model':'some-model'})
    assert p.availability()==('INVALID_CONFIG','free_access_unconfirmed')

@pytest.mark.parametrize('value',[{'learn':'true'},'not JSON',{'decision':'MAYBE'},{'learn':True,'confidence':float('nan')}])
def test_malformed_review_never_approves(value):
    with pytest.raises(ReviewFailure):decision(value)

def test_correction_does_not_approve_original():
    assert not decision({'learn':True,'corrections':['replace the claim']})['learn']

def test_secret_endpoint_redirect_not_allowed():
    p=ReviewerProvider('groq',{'enabled':True,'model':'test','base_url':'https://attacker.invalid'})
    assert p.availability()==('INVALID_CONFIG','untrusted_endpoint')

@pytest.mark.parametrize('config', [None, [], {'enabled': True, 'timeout': 'oops'}, {'enabled': True, 'cooldown': float('nan')}, {'enabled': True, 'retries': None}])
def test_invalid_provider_configuration_is_health_not_crash(config):
    assert ReviewerProvider('groq', config).availability()[0] == 'INVALID_CONFIG'

@pytest.mark.parametrize('settings', [None, [], {'providers': []}, {'max_seconds': 'oops'}, {'max_attempts': None}])
def test_invalid_manager_configuration_preserves_waiting(tmp_path, settings):
    internet = InternetAccessManager(tmp_path/'internet.json'); internet.enable()
    m = ProviderManager(tmp_path, {'reviewers': settings}, internet)
    assert m.review({})['state'] == 'WAITING_FOR_REVIEWER'
    assert m.health()[0]['state'] == 'INVALID_CONFIG'


def test_remaining_budget_limits_provider_timeout(tmp_path):
    p = FakeProvider('a', {'learn': False})
    p.timeout = 30
    original = p.review
    observed = []
    def review(row):
        observed.append(p.timeout)
        return original(row)
    p.review = review
    m = manager(tmp_path, [p]); m.max_seconds = 1
    assert m.review({})['ok']
    assert 0 < observed[0] <= 1
    assert p.timeout == 30


def test_legacy_provider_does_not_bypass_network_manager(tmp_path, monkeypatch):
    from providers.factory import create_provider
    from providers.remote import RemoteProvider
    import urllib.request
    def forbidden(*a, **kw): raise AssertionError('legacy network request')
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    legacy = create_provider({'model':{'provider':'openrouter'}})
    assert legacy.validate('candidate')['reason']=='reviewer_manager_not_configured'
    assert isinstance(legacy.generate([{'role':'user','content':'سلام'}]), str)
    assert RemoteProvider().validate('candidate')['decision']=='ERROR'


def test_corrupt_health_blocks_requests_without_erasing_cooldown(tmp_path):
    p=FakeProvider('a',{'learn':True})
    m=manager(tmp_path,[p])
    m.path.parent.mkdir(parents=True,exist_ok=True)
    m.path.write_text('{broken')
    m.path.with_suffix('.json.bak').write_text('{broken backup')
    assert m.health()[0]['state']=='ERROR'
    assert m.review({})['state']=='WAITING_FOR_REVIEWER'
    assert p.calls==0
    assert m.path.read_text()=='{broken'


def test_provider_recovers_rate_limit_from_backup(tmp_path):
    from persistence import atomic_write_json
    p=FakeProvider('a',{'learn':True});m=manager(tmp_path,[p])
    state={'a':{'state':'RATE_LIMITED','next_allowed':1200,'reason':'http_429'}}
    atomic_write_json(m.path,state);atomic_write_json(m.path,state)
    m.path.write_text('{broken')
    assert m.health()[0]['state']=='RATE_LIMITED'
    assert m.review({})['state']=='WAITING_FOR_REVIEWER'
    assert p.calls==0


def test_credential_free_policy_blocks_keyed_provider_before_availability(tmp_path):
    provider = FakeProvider('keyed', {'learn': True})
    provider.requires_credentials = True
    provider.availability = lambda: (_ for _ in ()).throw(AssertionError('must not inspect credentials'))
    internet = InternetAccessManager(tmp_path/'internet.json'); internet.enable()
    manager = ProviderManager(tmp_path, {'external_access': {'credential_free_only': True}}, internet, [provider])
    assert manager.health()[0]['reason'] == 'credentials_disallowed'
    assert manager.review({})['state'] == 'WAITING_FOR_REVIEWER'
    assert provider.calls == 0


def test_credential_free_policy_allows_explicit_anonymous_fixture(tmp_path):
    provider = FakeProvider('anonymous_fixture', {'learn': False})
    provider.requires_credentials = False
    internet = InternetAccessManager(tmp_path/'internet.json'); internet.enable()
    manager = ProviderManager(tmp_path, {'external_access': {'credential_free_only': True}}, internet, [provider])
    assert manager.review({})['ok']
    assert provider.calls == 1


def test_runtime_local_provider_config_cannot_override_credential_free_policy(tmp_path):
    import shutil
    from runtime.app import IranRuntime
    shutil.copy(Path(__file__).parents[1]/'config.json', tmp_path)
    (tmp_path/'reviewers.local.json').write_text(json.dumps({'providers': {'groq': {'enabled': True}}, 'external_access': {'credential_free_only': False}}))
    runtime = IranRuntime(tmp_path)
    try:
        runtime.internet_access.enable()
        proposal = runtime.learning_gate.request('knowledge.add_fact', {'subject': 'test', 'predicate': 'is', 'object': 'pending'})
        assert runtime.reviewer_manager.health()[0]['reason'] == 'credentials_disallowed'
        assert runtime.reviewer_manager.review(proposal)['state'] == 'WAITING_FOR_REVIEWER'
        assert runtime.learning_gate.get(proposal['proposal_id'])['status'] == 'pending'
        assert runtime.human_learning_pending() == []
    finally:
        runtime.close()


@pytest.mark.parametrize('entry', [None, [], {'next_allowed': 'bad'}, {'next_allowed': float('nan')}, {'next_allowed': True}])
def test_structurally_corrupt_health_never_sends_request(tmp_path, entry):
    provider = FakeProvider('a', {'learn': True})
    m = manager(tmp_path, [provider])
    m.path.parent.mkdir(parents=True, exist_ok=True)
    m.path.write_text(json.dumps({'a': entry}))
    assert m.health()[0]['reason'] == 'provider_state_corrupt'
    assert m.review({})['state'] == 'WAITING_FOR_REVIEWER'
    assert provider.calls == 0


def test_openrouter_dynamic_free_pool_requires_key(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    original = reviewer_module.env_value
    monkeypatch.setattr(reviewer_module, 'env_value', lambda name: '' if name == 'OPENROUTER_API_KEY' else original(name))
    p=ReviewerProvider('openrouter', {'enabled':True, 'dynamic_free_models':True})
    assert p.availability()==('UNAVAILABLE','api_key_missing')


def test_openrouter_dynamic_pool_filters_only_verified_zero_cost_free_models(monkeypatch):
    import urllib.request
    monkeypatch.setenv('OPENROUTER_API_KEY','test-key')
    rows=[
        *[{'id':f'vendor/model-{i}:free',
           'pricing':{'prompt':'0','completion':'0','request':'0'}} for i in range(30)],
        {'id':'vendor/paid:free','pricing':{'prompt':'0.1','completion':'0','request':'0'}},
        {'id':'vendor/sneaky:free','pricing':{'prompt':'0','completion':'0','request':'0.01'}},
        {'id':'vendor/zero-not-free','pricing':{'prompt':'0','completion':'0','request':'0'}},
    ]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self,n): return json.dumps({'data':rows}).encode()
    class Opener:
        def open(self,*a,**k): return Response()
    monkeypatch.setattr(urllib.request,'build_opener',lambda *a,**k:Opener())
    p=ReviewerProvider('openrouter',{
        'enabled':True,'dynamic_free_models':True,
        'free_model_limit':25,'free_models_ttl':900,
    },clock=lambda:1000)
    models=p.review_models()
    assert len(models)==25
    assert all(model.endswith(':free') for model in models)
    assert 'vendor/paid:free' not in models
    assert 'vendor/sneaky:free' not in models
    assert 'vendor/zero-not-free' not in models


def test_openrouter_dynamic_fallback_moves_past_rate_limited_model(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-key')
    p=ReviewerProvider('openrouter',{
        'enabled':True,'dynamic_free_models':True,'model_attempts':3,
    })
    monkeypatch.setattr(p,'review_models',lambda:['a:free','b:free','c:free'])
    calls=[]
    def fake_review(candidate, model):
        calls.append(model)
        if model=='a:free':
            raise ReviewFailure('http_429','RATE_LIMITED',60)
        return {'learn':False,'reason':'ok','confidence':1.0,
                'corrections':[],'provider':'openrouter','model':model}
    monkeypatch.setattr(p,'_review_with_model',fake_review)
    result=p.review({'claim':'x'})
    assert calls==['a:free','b:free']
    assert result['model']=='b:free'


def test_zero_budget_keyed_openrouter_can_be_explicitly_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-key')
    internet=InternetAccessManager(tmp_path/'internet.json'); internet.enable()
    provider=ReviewerProvider('openrouter',{
        'enabled':True,'dynamic_free_models':True,
    })
    m=ProviderManager(tmp_path,{
        'external_access':{
            'credential_free_only':True,
            'zero_budget_credentials_allowed':True,
        },
        'reviewers':{}
    },internet,[provider])
    assert m.health()[0]['state']=='AVAILABLE'


def test_decision_accepts_single_embedded_json_object():
    result=decision('Result: {"learn": false, "reason": "insufficient", "confidence": 0.7, "corrections": []}')
    assert result['learn'] is False and result['confidence']==0.7


def test_openrouter_dynamic_pool_continues_after_model_specific_403(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-key')
    p=ReviewerProvider('openrouter', {'enabled':True,'dynamic_free_models':True,'model_attempts':3})
    monkeypatch.setattr(p,'_discover_openrouter_free_models',lambda:['a:free','b:free'])
    seen=[]
    def call(candidate, model):
        seen.append(model)
        if model=='a:free':
            raise ReviewFailure('http_403','UNAVAILABLE')
        return {'learn':False,'reason':'ok','confidence':1.0,'corrections':[],'provider':'openrouter','model':model}
    monkeypatch.setattr(p,'_review_with_model',call)
    result=p.review({'claim':'x'})
    assert result['model']=='b:free'
    assert seen==['a:free','b:free']


def test_mistral_endpoint_and_free_policy_fail_closed(monkeypatch):
    monkeypatch.setenv('MISTRAL_API_KEY','test-key')
    p=ReviewerProvider('mistral',{
        'enabled':True,
        'model':'mistral-small-latest',
        'base_url':'https://api.mistral.ai/v1',
        'free_policy':{
            'budget':0,'confirmed':False,
            'models':['mistral-small-latest'],'expires_at':''
        }
    })
    assert p.availability()==('INVALID_CONFIG','free_access_unconfirmed')


def test_mistral_free_policy_can_activate_with_explicit_attestation(monkeypatch):
    monkeypatch.setenv('MISTRAL_API_KEY','test-key')
    p=ReviewerProvider('mistral',{
        'enabled':True,
        'model':'mistral-small-latest',
        'base_url':'https://api.mistral.ai/v1',
        'free_policy':{
            'budget':0,'confirmed':True,
            'models':['mistral-small-latest'],
            'expires_at':'2099-12-31T23:59:59Z'
        }
    })
    assert p.availability()==('AVAILABLE','')


def test_openrouter_model_cooldown_persists_across_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-key')
    internet=InternetAccessManager(tmp_path/'internet.json'); internet.enable()
    p=ReviewerProvider('openrouter',{
        'enabled':True,'dynamic_free_models':True,'model_attempts':3,
        'cooldown':60,'min_interval':0,
    },clock=lambda:1000)
    monkeypatch.setattr(p,'_discover_openrouter_free_models',lambda:['a:free','b:free'])
    seen=[]
    def call(candidate, model):
        seen.append(model)
        if model=='a:free':
            raise ReviewFailure('http_429','RATE_LIMITED',120)
        return {'learn':False,'reason':'ok','confidence':1.0,'corrections':[],
                'provider':'openrouter','model':model}
    monkeypatch.setattr(p,'_review_with_model',call)
    m=ProviderManager(tmp_path,{
        'external_access':{'credential_free_only':False},
        'reviewers':{'max_attempts':4,'max_seconds':40},
    },internet,[p],clock=lambda:1000)
    result=m.review({'claim':'x'})
    assert result['ok'] and result['result']['model']=='b:free'
    assert seen==['a:free','b:free']
    stored=json.loads(m.path.read_text())
    assert stored['openrouter']['models']['a:free']['state']=='RATE_LIMITED'
    assert stored['openrouter']['models']['a:free']['next_allowed']==1120

    p2=ReviewerProvider('openrouter',{
        'enabled':True,'dynamic_free_models':True,'model_attempts':3,
        'cooldown':60,'min_interval':0,
    },clock=lambda:1000)
    monkeypatch.setattr(p2,'_discover_openrouter_free_models',lambda:['a:free','b:free'])
    m2=ProviderManager(tmp_path,{
        'external_access':{'credential_free_only':False},
        'reviewers':{'max_attempts':4,'max_seconds':40},
    },internet,[p2],clock=lambda:1000)
    assert m2.health()[0]['state']=='AVAILABLE'
    assert p2.review_models()==['b:free']


def test_corrupt_nested_model_health_blocks_requests(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-key')
    internet=InternetAccessManager(tmp_path/'internet.json'); internet.enable()
    p=ReviewerProvider('openrouter',{'enabled':True,'dynamic_free_models':True})
    m=ProviderManager(tmp_path,{
        'external_access':{'credential_free_only':False}
    },internet,[p],clock=lambda:1000)
    m.path.parent.mkdir(parents=True,exist_ok=True)
    m.path.write_text(json.dumps({
        'openrouter':{
            'state':'AVAILABLE','next_allowed':0,'last_success':0,
            'models':{'a:free':{'next_allowed':'bad','last_success':0}}
        }
    }))
    assert m.health()[0]['reason']=='provider_state_corrupt'
    assert m.review({})['state']=='WAITING_FOR_REVIEWER'


def test_dynamic_pool_status_is_local_and_reports_ready_cooling(monkeypatch, tmp_path):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-key')
    p=ReviewerProvider('openrouter',{
        'enabled':True,'dynamic_free_models':True,'free_model_limit':25
    },clock=lambda:1000)
    p._free_models_cache=['a:free','b:free','c:free']
    p.set_model_health({
        'a:free':{'state':'RATE_LIMITED','reason':'http_429','next_allowed':1120,'last_success':0},
        'b:free':{'state':'AVAILABLE','reason':'','next_allowed':0,'last_success':990},
    })
    pool=p.model_pool_status()
    assert pool['capacity']==25
    assert pool['cached_catalog_count']==3
    assert pool['known_count']==3
    assert pool['ready_count']==2
    assert pool['cooling_down_count']==1
    assert pool['last_successful_model']=='b:free'
    states={row['model']:row['state'] for row in pool['models']}
    assert states['a:free']=='COOLDOWN'
    assert states['b:free']=='AVAILABLE'
    assert states['c:free']=='READY'

    internet=InternetAccessManager(tmp_path/'internet.json'); internet.enable()
    m=ProviderManager(tmp_path,{
        'external_access':{'credential_free_only':False}
    },internet,[p],clock=lambda:1000)
    m.path.parent.mkdir(parents=True,exist_ok=True)
    m.path.write_text(json.dumps({
        'openrouter':{
            'state':'AVAILABLE','reason':'','next_allowed':0,'last_success':990,
            'models':p.model_health_snapshot()
        }
    }))
    health=m.health()[0]
    assert health['model_pool']['known_count']==3
    assert health['model_pool']['cooling_down_count']==1


def test_local_proxy_outage_does_not_poison_model_health(monkeypatch):
    p=ReviewerProvider('openrouter', {
        'enabled':True, 'dynamic_free_models':True, 'free_model_limit':25,
        'model_attempts':4, 'free_models_ttl':900,
    }, clock=lambda:1000)
    monkeypatch.setenv('OPENROUTER_API_KEY','test-key')
    monkeypatch.setattr(reviewer_module, 'local_proxy_status', lambda timeout=0.6: (False, 'http://127.0.0.1:10808'))
    with pytest.raises(ReviewFailure) as exc:
        p.review_models()
    assert exc.value.reason == 'proxy_unavailable'
    assert p.model_health_snapshot() == {}


def test_provider_manager_uses_short_cooldown_for_proxy_flap(tmp_path, monkeypatch):
    internet=InternetAccessManager(tmp_path/'internet.json'); internet.enable()
    p=ReviewerProvider('openrouter', {
        'enabled':True, 'dynamic_free_models':True, 'free_model_limit':25,
        'model_attempts':4, 'free_models_ttl':900, 'cooldown':60,
    }, clock=lambda:1000)
    monkeypatch.setenv('OPENROUTER_API_KEY','test-key')
    monkeypatch.setattr(reviewer_module, 'local_proxy_status', lambda timeout=0.6: (False, 'http://127.0.0.1:10808'))
    m=ProviderManager(tmp_path, {
        'reviewers': {'providers': {}},
        'external_access': {'credential_free_only':False, 'zero_budget_credentials_allowed':True},
    }, internet, [p], clock=lambda:1000)
    result=m.review({'claim':'x'})
    assert result['state']=='WAITING_FOR_REVIEWER'
    assert result['reason']=='proxy_unavailable'
    state=json.loads((tmp_path/'data'/'reviewer_health.json').read_text())['openrouter']
    assert state['next_allowed'] == 1005
    assert state['models'] == {}


def test_openrouter_failover_can_reach_fifth_free_model(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','test-key')
    p=ReviewerProvider('openrouter',{
        'enabled':True,'dynamic_free_models':True,'model_attempts':16,
    })
    models=[f'm{i}:free' for i in range(1,7)]
    monkeypatch.setattr(p,'review_models',lambda:list(models))
    calls=[]
    def fake_review(candidate, model):
        calls.append(model)
        if model in models[:4]:
            raise ReviewFailure('http_429','RATE_LIMITED',60)
        return {'learn':True,'reason':'fifth model accepted','confidence':.9,
                'corrections':[],'provider':'openrouter','model':model}
    monkeypatch.setattr(p,'_review_with_model',fake_review)
    result=p.review({'claim':'x'})
    assert calls==models[:5]
    assert result['model']==models[4]
    assert result['learn'] is True
