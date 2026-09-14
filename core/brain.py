from core.language_engine import PersianLanguageEngine
from core.language_memory import DiscourseMemory
from core.semantic import LocalSemanticModel

class Brain:
    """Local cognitive facade: language, discourse and sparse semantic memory."""
    def __init__(self,provider):
        self.provider=provider
        self.language=PersianLanguageEngine()
        self.discourse=DiscourseMemory()
        self.semantic=LocalSemanticModel()

    def ask(self,messages,**kwargs): return self.provider.generate(messages,**kwargs)

    def analyze(self,text):
        analysis=self.language.analyze(text)
        analysis=self.discourse.resolve(text,analysis)
        self.discourse.update(analysis)
        return analysis

    def semantic_frame(self,text): return self.semantic.frame(text)
    def similarity(self,a,b): return self.semantic.similarity(a,b)
    def compare(self,a,b): return self.language.compare(a,b)
    def context(self): return self.discourse.context()

    def health(self):
        status=self.provider.health()
        status.update({'language_engine':'persian-local','semantic_engine':'sparse-local','discourse_memory':'active'})
        return status
