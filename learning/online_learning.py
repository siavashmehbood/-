from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse, quote_plus, quote
from urllib.request import Request, urlopen
from html.parser import HTMLParser
from datetime import datetime
import json
import re

@dataclass
class WebLesson:
    url: str
    title: str
    text: str
    source: str
    trust: float
    fetched_at: str
    query: str = ""

@dataclass
class KnowledgeProposal:
    proposal_id: str
    query: str
    title: str
    summary: str
    confidence: float
    sources: list
    agreements: list
    conflicts: list
    created_at: str

class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0; self.title=[]
    def handle_starttag(self, tag, attrs):
        if tag in {"script","style","noscript","svg"}: self.skip += 1
        if tag == "title": self.title=[]
    def handle_endtag(self, tag):
        if tag in {"script","style","noscript","svg"}: self.skip=max(0,self.skip-1)
    def handle_data(self, data):
        if self.skip: return
        s=re.sub(r"\s+"," ",data).strip()
        if not s: return
        self.parts.append(s)
        if len(self.title)<20: self.title.append(s)

class OnlineLearning:
    """Controlled web knowledge acquisition; no model/API is required.
    Internet is used only to read approved public sources, cache lessons locally,
    and expose evidence to the existing symbolic retrieval layer.
    """
    DEFAULT_SOURCES=(
        "https://docs.python.org/3/",
        "https://developer.mozilla.org/en-US/docs/Web/",
        "https://docs.github.com/en/rest",
        "https://en.wikipedia.org/wiki/Main_Page",
    )
    TRUST={
        "docs.python.org":1.00,
        "developer.mozilla.org":.98,
        "docs.github.com":.98,
        "github.com":.94,
        "wikipedia.org":.82,
        "wikidata.org":.88,
    }
    def _wiki_search(self,query):
        url='https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=3&srsearch='+quote_plus(query)
        req=Request(url,headers={'User-Agent':'IRAN-Cognitive-Architecture/online-learning'})
        with urlopen(req,timeout=self.timeout) as r:
            data=json.loads(r.read().decode('utf-8','replace'))
        return [x.get('title','') for x in data.get('query',{}).get('search',[]) if x.get('title')]
    def _wiki_page_url(self,title):
        return 'https://en.wikipedia.org/wiki/'+quote(title.replace(' ','_'),safe='_()')
    def _wikidata_search(self,query):
        url='https://www.wikidata.org/w/api.php?action=wbsearchentities&search='+quote_plus(query)+'&language=en&format=json&limit=2'
        req=Request(url,headers={'User-Agent':'IRAN-Cognitive-Architecture/online-learning'})
        with urlopen(req,timeout=self.timeout) as r:
            data=json.loads(r.read().decode('utf-8','replace'))
        return [(x.get('id',''),x.get('label','')) for x in data.get('search',[]) if x.get('id')]
    def _wikidata_lesson(self,entity_id,label,query):
        url='https://www.wikidata.org/wiki/Special:EntityData/'+quote(entity_id)+'.json'
        req=Request(url,headers={'User-Agent':'IRAN-Cognitive-Architecture/online-learning'})
        with urlopen(req,timeout=self.timeout) as r:
            data=json.loads(r.read().decode('utf-8','replace'))
        entity=data.get('entities',{}).get(entity_id,{})
        desc=(entity.get('descriptions',{}).get('en') or {}).get('value','')
        aliases=[x.get('value','') for x in entity.get('aliases',{}).get('en',[])[:5]]
        text=' '.join(x for x in [label,desc,'aliases: '+', '.join(aliases)] if x).strip()
        if len(text)<40: return None
        return {'url':url,'title':label or entity_id,'text':text[:self.max_chars],
                'source':'wikidata.org','trust':self._trust(url),
                'fetched_at':datetime.now().isoformat(timespec='seconds'),'query':query}
    def __init__(self, root, config=None):
        self.root=Path(root); cfg=config or {}; self.cfg=cfg
        self.enabled=bool(cfg.get("enabled",False)); self.auto_fetch=bool(cfg.get("auto_fetch_on_unknown",True))
        self.max_sources=max(1,int(cfg.get("max_sources",3))); self.max_fetches=max(1,int(cfg.get("max_fetches_per_session",3))); self.fetches=0
        self.timeout=max(2,int(cfg.get("timeout",8)))
        self.max_chars=max(1000,int(cfg.get("max_chars",18000)))
        self.path=self.root/str(cfg.get("store","data/web_lessons.json")); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lessons=self._load(); self.last_sync=None
    def _load(self):
        try: return json.loads(self.path.read_text(encoding="utf-8"))[-500:]
        except Exception: return []
    def _save(self):
        tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(self.lessons,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(self.path)
    def _host_ok(self,url):
        host=(urlparse(url).hostname or '').lower()
        return any(host==d or host.endswith('.'+d) for d in self.TRUST)
    def _trust(self,url):
        host=(urlparse(url).hostname or '').lower()
        for domain,score in self.TRUST.items():
            if host==domain or host.endswith('.'+domain): return score
        return 0.0
    def _fetch(self,url):
        if not self._host_ok(url): return None
        req=Request(url,headers={'User-Agent':'IRAN-Cognitive-Architecture/online-learning'})
        with urlopen(req,timeout=self.timeout) as r:
            raw=r.read(900_000); charset=r.headers.get_content_charset() or 'utf-8'
        html=raw.decode(charset,errors='replace')
        parser=_TextParser(); parser.feed(html)
        text=' '.join(parser.parts)
        text=re.sub(r'\s+',' ',text).strip()[:self.max_chars]
        if len(text)<80: return None
        title=' '.join(parser.title[:8]).strip() or url
        return WebLesson(url,title,text,(urlparse(url).hostname or ''),self._trust(url),datetime.now().isoformat(timespec='seconds'))
    def learn_url(self,url,query='',commit=True):
        if not self.enabled: return None
        lesson=self._fetch(url)
        if not lesson: return None
        lesson.query=query
        item=asdict(lesson)
        if not commit: return item
        key=lesson.url
        self.lessons=[x for x in self.lessons if x.get('url')!=key]
        self.lessons.append(item); self.lessons=self.lessons[-500:]; self._save(); return item
    def _token_set(self, text):
        return set(re.findall(r'[\wآ-ی]{3,}', str(text).lower()))

    def build_proposal(self, query, lessons):
        """Create one reviewable, provenance-preserving proposal from multiple sources.
        No proposal is persisted until approve_proposal() is called.
        """
        unique=[]; seen=set()
        for lesson in lessons or []:
            url=str(lesson.get('url',''))
            if url and url not in seen:
                seen.add(url); unique.append(dict(lesson))
        if not unique: return None
        tokens=self._token_set(query)
        source_rows=[]; evidence_sets=[]
        for item in unique:
            evidence=self.excerpt(query,item.get('text',''),700)
            words=self._token_set(item.get('text',''))
            overlap=len(tokens & words)/max(1,len(tokens))
            source_rows.append({'url':item.get('url',''),'source':item.get('source',''),
                'title':item.get('title',''),'trust':float(item.get('trust',0)),
                'evidence':evidence,'text':item.get('text',''),'relevance':round(overlap,3)})
            evidence_sets.append(self._token_set(evidence))
        shared=set.intersection(*evidence_sets) if len(evidence_sets)>1 else (evidence_sets[0] if evidence_sets else set())
        shared -= tokens
        agreements=sorted(shared, key=lambda x: (-len(x), x))[:12]
        conflicts=[]
        for i,left in enumerate(source_rows):
            for right in source_rows[i+1:]:
                a=self._token_set(left['evidence']); b=self._token_set(right['evidence'])
                similarity=len(a & b)/max(1,len(a | b))
                if similarity < .08:
                    conflicts.append({'sources':[left['source'],right['source']], 'reason':'low evidence overlap', 'similarity':round(similarity,3)})
        avg_trust=sum(x['trust'] for x in source_rows)/len(source_rows)
        consensus=min(1.0, len(source_rows)/3) * min(1.0, .55 + .08*len(agreements))
        confidence=round(.55*avg_trust + .45*consensus - min(.18,.04*len(conflicts)),3)
        summary='؛ '.join(x['evidence'] for x in source_rows[:3])
        if conflicts: summary += ' | هشدار: بخشی از شواهد بین منابع همپوشانی کمی دارد و نیازمند بررسی است.'
        stamp=datetime.now().isoformat(timespec='seconds')
        proposal=KnowledgeProposal(
            proposal_id='proposal-'+datetime.now().strftime('%Y%m%d%H%M%S%f'), query=str(query),
            title='پیشنهاد دانش چندمنبعی: '+str(query)[:100], summary=summary[:2400],
            confidence=confidence, sources=source_rows, agreements=agreements,
            conflicts=conflicts, created_at=stamp)
        return asdict(proposal)

    def approve_proposal(self, proposal):
        """Commit all unique source lessons from an approved proposal atomically."""
        if not proposal or not proposal.get('sources'):
            return {'approved':False,'reason':'empty_proposal'}
        approved=[]
        for source in proposal.get('sources',[]):
            url=source.get('url','')
            if not url or not self._host_ok(url): continue
            approved.append({'url':url,'title':source.get('title',''),'text':source.get('text') or source.get('evidence',''),
                'source':source.get('source',''),'trust':float(source.get('trust',0)),
                'fetched_at':proposal.get('created_at',''),'query':proposal.get('query',''),
                'provenance':{'proposal_id':proposal.get('proposal_id'),'relevance':source.get('relevance',0)}})
        if not approved: return {'approved':False,'reason':'no_trusted_sources'}
        by_url={x.get('url'):x for x in self.lessons}
        for item in approved: by_url[item['url']]=item
        self.lessons=list(by_url.values())[-500:]; self._save()
        self.last_sync=datetime.now().isoformat(timespec='seconds')
        return {'approved':True,'proposal':proposal,'committed':len(approved),'lessons':len(self.lessons)}

    def reject_proposal(self, proposal):
        return {'approved':False,'rejected':bool(proposal),'proposal_id':(proposal or {}).get('proposal_id','')}

    def search(self,query):
        """Search trusted public knowledge without persisting fetched evidence."""
        if not self.enabled or not query.strip(): return []
        hits=[]
        try:
            for title in self._wiki_search(query)[:max(1,self.max_sources-1)]:
                item=self.learn_url(self._wiki_page_url(title),query,commit=False)
                if item: hits.append(item)
        except Exception:
            pass
        try:
            if len(hits) < self.max_sources:
                for entity_id,label in self._wikidata_search(query)[:1]:
                    item=self._wikidata_lesson(entity_id,label,query)
                    if item: hits.append(item)
        except Exception:
            pass
        if not hits:
            for url in self.DEFAULT_SOURCES[:self.max_sources]:
                if any(part in url.lower() for part in re.findall(r'[a-z0-9]{3,}',query.lower())):
                    item=self.learn_url(url,query,commit=False)
                    if item: hits.append(item)
        return hits or self.retrieve(query,self.max_sources)

    def retrieve(self,query,limit=3):
        tokens=set(re.findall(r'[\wآ-ی]{3,}',query.lower()))
        ranked=[]
        for row in self.lessons:
            words=set(re.findall(r'[\wآ-ی]{3,}',(row.get('title','')+' '+row.get('text','')).lower()))
            overlap=len(tokens & words)/max(1,len(tokens))
            score=.70*overlap+.30*float(row.get('trust',0))
            if overlap>=.25: ranked.append((score,row))
        ranked.sort(key=lambda x:x[0],reverse=True)
        return [r for _,r in ranked[:int(limit)]]

    def acquire(self,query,urls=None):
        if not self.enabled: return {'enabled':False,'learned':[],'reason':'online_learning_disabled'}
        if self.fetches >= self.max_fetches: return {'enabled':True,'learned':[],'count':0,'query':query,'reason':'session_fetch_limit'}
        self.fetches += 1
        if urls:
            learned=[]
            for url in list(urls)[:self.max_sources]:
                try:
                    item=self.learn_url(url,query,commit=False)
                    if item: learned.append(item)
                except Exception: continue
        else:
            learned=self.search(query)[:self.max_sources]
        proposal=self.build_proposal(query, learned) if learned else None
        return {'enabled':True,'learned':learned,'count':len(learned),'query':query,
                'pending':bool(proposal),'proposal':proposal,
                'reason':'user_approval_required' if proposal else 'no_new_lesson'}

    def approve_lesson(self, lesson):
        if not lesson: return {'approved':False,'reason':'empty_lesson'}
        item=dict(lesson); key=item.get('url','')
        if not key: return {'approved':False,'reason':'missing_url'}
        self.lessons=[x for x in self.lessons if x.get('url')!=key]
        self.lessons.append(item); self.lessons=self.lessons[-500:]; self._save()
        self.last_sync=datetime.now().isoformat(timespec='seconds')
        return {'approved':True,'lesson':item,'lessons':len(self.lessons)}

    def reject_lesson(self, lesson):
        return {'approved':False,'rejected':bool(lesson),'url':(lesson or {}).get('url','')}

    def startup_sync(self):
        if not self.enabled or not self.cfg.get('startup_sync',False): return {'count':0}
        if self.lessons:
            self.last_sync=datetime.now().isoformat(timespec='seconds')
            return {'count':0,'cached':True}
        result=self.acquire('IRAN trusted knowledge bootstrap')
        self.last_sync=datetime.now().isoformat(timespec='seconds')
        return result

    def excerpt(self,query,text,max_chars=900):
        text=str(text); tokens=[t for t in re.findall(r'[\wآ-ی]{3,}',query.lower()) if t not in {'what','which','where','when','does','the','is','are','of','and','for','چیست','چی','کدام','است','از','و'}]
        low=text.lower(); positions=[]
        for token in tokens:
            p=low.find(token.lower())
            if p>=0: positions.append(p)
        start=max(0,(min(positions) if positions else 0)-180)
        piece=text[start:start+max_chars].strip()
        return piece.rsplit(' ',1)[0]+'…' if len(piece)>=max_chars else piece

    def context(self,query,limit=3,max_chars=9000):
        rows=self.retrieve(query,limit)
        out=[]
        for r in rows:
            text=str(r.get('text',''))[:max_chars]
            out.append({'title':r.get('title',''),'url':r.get('url',''),'source':r.get('source',''),
                        'trust':float(r.get('trust',0)),'text':text})
        return out

    def stats(self):
        return {'enabled':self.enabled,'lessons':len(self.lessons),'sources':len(set(x.get('source','') for x in self.lessons)),
                'last_sync':self.last_sync,'store':str(self.path)}

    def approve_session(self):
        """Explicitly enable network learning for the current runtime session."""
        if not self.enabled:
            return {'approved': False, 'reason': 'online_learning_disabled'}
        self.cfg['session_approved'] = True
        result = self.acquire('IRAN trusted knowledge bootstrap')
        self.last_sync = datetime.now().isoformat(timespec='seconds')
        return {'approved': True, **result}

    def session_status(self):
        return {
            'enabled': self.enabled,
            'approved': bool(self.cfg.get('session_approved', False)),
            'lessons': len(self.lessons),
            'sources': len(set(x.get('source','') for x in self.lessons)),
        }
