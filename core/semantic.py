import math
import re
from collections import Counter
from dataclasses import dataclass, field

@dataclass
class SemanticFrame:
    text: str
    tokens: list[str] = field(default_factory=list)
    stems: list[str] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)
    domains: list[str] = field(default_factory=list)

class LocalSemanticModel:
    """Offline sparse semantic layer: lexical features, concepts and similarity."""
    DOMAIN_MAP={
        'code':('کد','پایتون','جنگو','برنامه','فایل','تابع','کلاس','خطا','باگ','پروژه'),
        'system':('سیستم','کامپیوتر','ویندوز','پردازنده','رم','دیسک','شبکه'),
        'memory':('حافظه','یادت','یادته','قبلاً','ذخیره','به خاطر'),
        'planning':('برنامه','برنامه‌ریزی','هدف','مراحل','پلن','نقشه','استراتژی'),
        'reasoning':('دلیل','چرا','شواهد','علت','مقایسه','نتیجه','فرضیه'),
        'action':('اجرا','انجام','بساز','تغییر','باز کن','ببند','بررسی'),
    }
    SUFFIXES=('ترین','تر','هایی','ها','های','مان','تان','شان','ات','ان','یم','ید','ند','م','ی')

    def normalize_token(self,token):
        t=token.lower().strip('.,!?؛،:()[]{}"\'')
        for suffix in self.SUFFIXES:
            if len(t)>len(suffix)+3 and t.endswith(suffix):
                t=t[:-len(suffix)]; break
        return t

    def tokenize(self,text):
        return re.findall(r'[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*',str(text).lower())

    def frame(self,text):
        tokens=self.tokenize(text)
        stems=[self.normalize_token(t) for t in tokens]
        counts=Counter(stems); total=max(1,len(stems))
        features={k:round(v/total,4) for k,v in counts.items()}
        domains=[d for d,words in self.DOMAIN_MAP.items() if any(w in str(text).lower() for w in words)]
        return SemanticFrame(str(text),tokens,stems,features,domains)

    def similarity(self,a,b):
        x=self.frame(a); y=self.frame(b); keys=set(x.features)|set(y.features)
        dot=sum(x.features.get(k,0)*y.features.get(k,0) for k in keys)
        nx=math.sqrt(sum(v*v for v in x.features.values())); ny=math.sqrt(sum(v*v for v in y.features.values()))
        cosine=dot/(nx*ny) if nx and ny else 0.0
        shared=len(set(x.stems)&set(y.stems))/max(1,len(set(x.stems)|set(y.stems)))
        domains=len(set(x.domains)&set(y.domains))/max(1,len(set(x.domains)|set(y.domains)))
        return round(.65*cosine+.25*shared+.10*domains,4)

    def rank(self,query,candidates,limit=8):
        scored=[(self.similarity(query,c),c) for c in candidates]
        return [c for _,c in sorted(scored,key=lambda x:x[0],reverse=True)[:int(limit)]]
