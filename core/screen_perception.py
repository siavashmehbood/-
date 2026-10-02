"""Structured desktop observation, native Windows perception, and safe grounding."""
from dataclasses import dataclass,asdict
from datetime import datetime
import hashlib,json,os

@dataclass(frozen=True)
class UIElement:
    role:str; label:str; bounds:tuple|None=None; enabled:bool=True; focused:bool=False
    window:str=""; confidence:float=1.0; source:str="native"

@dataclass
class DesktopObservation:
    screenshot:dict|None; width:int; height:int; active_window:dict|None
    visible_windows:list; cursor:tuple|None; elements:list; extracted_text:str|None
    timestamp:str; confidence:float; provenance:dict
    def signature(self):
        stable={"active":self.active_window,"windows":self.visible_windows,
                "cursor":self.cursor,"elements":self.elements,"text":self.extracted_text}
        return hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()[:20]
    def to_dict(self):
        value=asdict(self); value["signature"]=self.signature(); return value

class WindowsUIPerception:
    """Uses native window metadata first; UIA is optional and never fabricated."""
    def __init__(self,windows): self.windows=windows
    def inspect(self):
        active=self.windows.active_window(); visible=self.windows.enumerate_windows()
        elements=[asdict(UIElement("window",str(w.get("title","")),None,True,
                  w.get("hwnd")==active.get("hwnd"),str(w.get("title","")),1.0,"win32"))
                  for w in visible]
        if active and active.get("hwnd"):
            try: elements.extend(self.windows.uia_elements(active["hwnd"]))
            except Exception: pass
        return active,visible,elements

class ScreenPerception:
    def __init__(self,desktop,windows=None,input_controller=None):
        self.desktop=desktop; self.windows=windows; self.input=input_controller
    def observe(self,capture=True):
        shot=None
        if capture:
            try: shot=self.desktop.screenshot()
            except Exception: shot=None
        width=int((shot or {}).get("width",0)); height=int((shot or {}).get("height",0))
        active=None; visible=[]; elements=[]; confidence=.5
        if self.windows is not None:
            try:
                active,visible,elements=WindowsUIPerception(self.windows).inspect(); confidence=.95
            except Exception: pass
        cursor=None
        if self.input is not None:
            try:
                pos=self.input.position(); cursor=(int(pos[0]),int(pos[1]))
            except Exception: pass
        return DesktopObservation(shot,width,height,active,visible,cursor,elements,None,
            datetime.now().isoformat(timespec="milliseconds"),confidence,
            {"structured":"win32" if visible else "unavailable","screenshot":bool(shot),"ocr":"not_configured"})

class UIGrounder:
    def resolve(self,observation,label,role=None,window=None):
        wanted=str(label).strip().casefold(); matches=[]
        for raw in observation.elements:
            item=raw if isinstance(raw,dict) else asdict(raw)
            if wanted not in str(item.get("label","")).casefold(): continue
            if role and str(item.get("role","")).casefold()!=str(role).casefold(): continue
            if window and str(window).casefold() not in str(item.get("window","")).casefold(): continue
            matches.append(item)
        if not matches:return {"status":"unknown","target":None,"candidates":[]}
        if len(matches)>1:return {"status":"ambiguous","target":None,"candidates":matches}
        return {"status":"grounded","target":matches[0],"candidates":matches}
