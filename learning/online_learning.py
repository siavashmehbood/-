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
    def learn_url(self,url,query=''):
        if not self.enabled: return None
        lesson=self._fetch(url)
        if not lesson: return None
        lesson.query=query
        key=lesson.url
        self.lessons=[x for x in self.lessons if x.get('url')!=key]
        self.lessons.append(asdict(lesson)); self.lessons=self.lessons[-500:]; self._save(); return asdict(lesson)
    def search(self,query):
        """Search trusted public knowledge, then cache the retrieved evidence."""
        if not self.enabled or not query.strip(): return []
        hits=[]
        try:
            for title in self._wiki_search(query)[:self.max_sources]:
                item=self.learn_url(self._wiki_page_url(title),query)
                if item: hits.append(item)
        except Exception:
            pass
        if not hits:
            for url in self.DEFAULT_SOURCES[:self.max_sources]:
                if any(part in url.lower() for part in re.findall(r'[a-z0-9]{3,}',query.lower())):
                    item=self.learn_url(url,query)
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
        if not self.cfg.get('session_approved',False): return {'enabled':True,'learned':[],'reason':'user_consent_required'}
        if self.fetches >= self.max_fetches: return {'enabled':True,'learned':[],'count':0,'query':query,'reason':'session_fetch_limit'}
        self.fetches += 1
        if urls:
            learned=[]
            for url in list(urls)[:self.max_sources]:
                try:
                    item=self.learn_url(url,query)
                    if item: learned.append(item)
                except Exception: continue
        else:
            learned=self.search(query)[:self.max_sources]
        return {'enabled':True,'learned':learned,'count':len(learned),'query':query}

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
