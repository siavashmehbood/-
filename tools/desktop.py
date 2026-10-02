"""Cross-platform desktop capabilities with Windows-specific adapters where required."""
from dataclasses import dataclass,asdict
from datetime import datetime
from pathlib import Path
import os,platform,shutil,subprocess,time,uuid

def _inside(root,path):
    root=Path(root).resolve(); p=Path(path).resolve()
    return p==root or root in p.parents

class DesktopTools:
    def __init__(self,root):
        self.root=Path(root).resolve()
    def system_info(self):
        return {"platform":platform.platform(),"machine":platform.machine(),"python":platform.python_version(),
                "hostname":platform.node()}
    def find_file(self,name):
        return [str(p) for p in self.root.rglob(str(name)) if p.is_file()][:100]
    def create_folder(self,path):
        p=(self.root/str(path)).resolve()
        if not _inside(self.root,p): raise PermissionError("path outside assistant root")
        p.mkdir(parents=True,exist_ok=True); return {"path":str(p),"exists":p.is_dir()}
    def copy_file(self,source,destination):
        src=(self.root/str(source)).resolve(); dst=(self.root/str(destination)).resolve()
        if not (_inside(self.root,src) and _inside(self.root,dst)): raise PermissionError("path outside assistant root")
        shutil.copy2(src,dst); return {"path":str(dst),"exists":dst.is_file()}
    def move_file(self,source,destination):
        src=(self.root/str(source)).resolve(); dst=(self.root/str(destination)).resolve()
        if not (_inside(self.root,src) and _inside(self.root,dst)): raise PermissionError("path outside assistant root")
        shutil.move(str(src),str(dst)); return {"path":str(dst),"exists":dst.exists()}
    def rename_file(self,source,name):
        src=(self.root/str(source)).resolve(); dst=src.with_name(str(name)).resolve()
        if not (_inside(self.root,src) and _inside(self.root,dst)): raise PermissionError("path outside assistant root")
        src.rename(dst); return {"path":str(dst),"exists":dst.exists()}
    def open_application(self,name):
        if os.name!="nt": raise OSError("application control requires Windows")
        aliases={"calculator":"calc.exe","calc":"calc.exe","notepad":"notepad.exe","vscode":"code.exe","vs code":"code.exe"}
        exe=aliases.get(str(name).strip().lower(),str(name).strip())
        proc=subprocess.Popen([exe],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        time.sleep(.4)
        return {"application":exe,"pid":proc.pid,"running":proc.poll() is None}
    def list_running_apps(self):
        if os.name!="nt": raise OSError("application enumeration requires Windows")
        out=subprocess.run(["tasklist","/FO","CSV","/NH"],capture_output=True,text=True,check=True,timeout=15)
        return out.stdout.splitlines()[:500]
    def close_application(self,pid):
        if os.name!="nt": raise OSError("application control requires Windows")
        os.kill(int(pid),15); return {"pid":int(pid),"requested":True}
    def screenshot(self,path=None):
        try:
            from PySide6.QtGui import QGuiApplication
            from PySide6.QtWidgets import QApplication
        except ImportError as exc: raise RuntimeError("screen capture backend unavailable") from exc
        app=QApplication.instance() or QApplication([])
        screen=QGuiApplication.primaryScreen()
        if screen is None: raise RuntimeError("no screen available")
        target=Path(path) if path else self.root/"data"/"screenshots"/f"screen-{uuid.uuid4().hex[:10]}.png"
        target.parent.mkdir(parents=True,exist_ok=True)
        ok=screen.grabWindow(0).save(str(target))
        if not ok: raise RuntimeError("screenshot save failed")
        geo=screen.geometry()
        return {"path":str(target),"exists":target.is_file(),"width":geo.width(),"height":geo.height(),
                "timestamp":datetime.now().isoformat(timespec="seconds")}

class InputController:
    """Optional input-control adapter; registry permission must gate every call."""
    @staticmethod
    def _api():
        try: import pyautogui
        except ImportError as exc: raise RuntimeError("pyautogui optional dependency is not installed") from exc
        return pyautogui
    def move(self,x,y): self._api().moveTo(int(x),int(y)); return {"moved":True}
    def click(self,x=None,y=None,button="left",clicks=1):
        self._api().click(x=x,y=y,button=button,clicks=int(clicks)); return {"clicked":True}
    def scroll(self,amount): self._api().scroll(int(amount)); return {"scrolled":int(amount)}
    def type_text(self,text): self._api().write(str(text)); return {"typed":len(str(text))}
    def press(self,key): self._api().press(str(key)); return {"pressed":str(key)}
    def hotkey(self,*keys): self._api().hotkey(*[str(x) for x in keys]); return {"hotkey":list(keys)}

class ScreenObserver:
    def __init__(self,desktop): self.desktop=desktop
    def capture(self): return self.desktop.screenshot()
