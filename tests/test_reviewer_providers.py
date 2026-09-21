import json
from pathlib import Path
import pytest
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

@pytest.mark.parametrize('name',['openrouter','gemini','groq','cerebras'])
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
