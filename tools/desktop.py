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
    def open_file(self,path):
        p=(self.root/str(path)).resolve()
        if not _inside(self.root,p) or not p.is_file(): raise FileNotFoundError(str(path))
        if os.name=="nt": os.startfile(str(p))
        else: subprocess.Popen(["xdg-open",str(p)])
        return {"path":str(p),"opened":True}
    def open_folder(self,path="."):
        p=(self.root/str(path)).resolve()
        if not _inside(self.root,p) or not p.is_dir(): raise FileNotFoundError(str(path))
        if os.name=="nt": os.startfile(str(p))
        else: subprocess.Popen(["xdg-open",str(p)])
        return {"path":str(p),"opened":True}
    def battery(self):
        try:
            import psutil
            value=psutil.sensors_battery()
        except ImportError:
            value=None
        return {"available":value is not None,"percent":None if value is None else value.percent,
                "plugged":None if value is None else value.power_plugged}
    def volume(self):
        if os.name!="nt": raise OSError("volume control requires Windows")
        import ctypes
        VK_VOLUME_MUTE,VK_VOLUME_DOWN,VK_VOLUME_UP=0xAD,0xAE,0xAF
        return {"supported":True,"keys":{"mute":VK_VOLUME_MUTE,"down":VK_VOLUME_DOWN,"up":VK_VOLUME_UP}}
    def change_volume(self,direction,steps=2):
        if os.name!="nt": raise OSError("volume control requires Windows")
        import ctypes
        keys={"mute":0xAD,"down":0xAE,"up":0xAF}; key=keys.get(str(direction).lower())
        if key is None: raise ValueError("direction must be up/down/mute")
        user32=ctypes.windll.user32
        for _ in range(max(1,min(50,int(steps)))):
            user32.keybd_event(key,0,0,0); user32.keybd_event(key,0,2,0)
        return {"requested":True,"direction":direction,"steps":max(1,min(50,int(steps)))}
    def open_application(self,name):
        if os.name!="nt": raise OSError("application control requires Windows")
        aliases={"calculator":"calc.exe","calc":"calc.exe","notepad":"notepad.exe","vscode":"code.exe","vs code":"code.exe"}
        exe=aliases.get(str(name).strip().lower(),str(name).strip())
        proc=subprocess.Popen([exe],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        time.sleep(.6)
        running=proc.poll() is None
        observed=[]
        if not running:
            try:
                out=subprocess.run(["tasklist","/FO","CSV","/NH"],capture_output=True,text=True,check=True,timeout=10).stdout.lower()
                stems={"calc.exe":("calculatorapp.exe","calculator.exe","win32calc.exe"),
                       "notepad.exe":("notepad.exe",),"code.exe":("code.exe",)}
                observed=[candidate for candidate in stems.get(exe.lower(),(exe.lower(),)) if candidate in out]
                running=bool(observed)
            except Exception: pass
        return {"application":exe,"pid":proc.pid,"running":running,"observed_processes":observed}
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

class WindowsDesktop:
    def __init__(self,root): self.root=Path(root)
    @staticmethod
    def _require():
        if os.name!="nt": raise OSError("Windows desktop API requires Windows")
        try:
            import ctypes
            return ctypes.windll.user32
        except Exception as exc: raise OSError("Windows user32 unavailable") from exc
    def enumerate_windows(self):
        user32=self._require(); import ctypes
        rows=[]
        callback_type=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_int,ctypes.c_int)
        def collect(hwnd,lparam):
            if user32.IsWindowVisible(hwnd):
                length=user32.GetWindowTextLengthW(hwnd)
                if length:
                    buf=ctypes.create_unicode_buffer(length+1); user32.GetWindowTextW(hwnd,buf,length+1)
                    rows.append({"hwnd":int(hwnd),"title":buf.value})
            return True
        user32.EnumWindows(callback_type(collect),0)
        return rows[:500]
    def active_window(self):
        user32=self._require(); hwnd=user32.GetForegroundWindow()
        length=user32.GetWindowTextLengthW(hwnd); import ctypes
        buf=ctypes.create_unicode_buffer(length+1); user32.GetWindowTextW(hwnd,buf,length+1)
        return {"hwnd":int(hwnd),"title":buf.value}
    def _show(self,hwnd,code):
        user32=self._require(); ok=bool(user32.ShowWindow(int(hwnd),int(code)))
        return {"hwnd":int(hwnd),"requested":True,"previously_visible":ok}
    def minimize(self,hwnd): return self._show(hwnd,6)
    def maximize(self,hwnd): return self._show(hwnd,3)
    def restore(self,hwnd): return self._show(hwnd,9)
    def focus(self,hwnd):
        user32=self._require(); hwnd=int(hwnd)
        user32.ShowWindow(hwnd,9)
        # Windows foreground-lock can reject a direct SetForegroundWindow from
        # an automation worker; fall back to attached input threads below.
        user32.BringWindowToTop(hwnd); user32.SetForegroundWindow(hwnd)
        if int(user32.GetForegroundWindow())!=hwnd:
            try:
                import ctypes
                kernel32=ctypes.windll.kernel32
                current_tid=kernel32.GetCurrentThreadId()
                foreground=user32.GetForegroundWindow()
                foreground_tid=user32.GetWindowThreadProcessId(foreground,None) if foreground else 0
                target_tid=user32.GetWindowThreadProcessId(hwnd,None)
                if foreground_tid and foreground_tid!=current_tid:user32.AttachThreadInput(current_tid,foreground_tid,True)
                if target_tid and target_tid!=current_tid:user32.AttachThreadInput(current_tid,target_tid,True)
                user32.BringWindowToTop(hwnd); user32.SetForegroundWindow(hwnd); user32.SetFocus(hwnd)
                if target_tid and target_tid!=current_tid:user32.AttachThreadInput(current_tid,target_tid,False)
                if foreground_tid and foreground_tid!=current_tid:user32.AttachThreadInput(current_tid,foreground_tid,False)
            except Exception:
                pass
        return {"hwnd":hwnd,"focused":int(user32.GetForegroundWindow())==hwnd}
    def uia_set_and_read_text(self,hwnd,text):
        self._require()
        try: from pywinauto import Desktop
        except ImportError as exc: raise RuntimeError("pywinauto optional dependency is not installed") from exc
        root=Desktop(backend="uia").window(handle=int(hwnd)); editors=[]
        for child in root.descendants():
            try:
                if str(child.element_info.control_type or "") in {"Document","Edit"}:editors.append(child)
            except Exception: pass
        if not editors:raise RuntimeError("no editable UIA control found")
        editor=editors[0]; editor.set_focus()
        try: editor.type_keys(str(text),with_spaces=True,set_foreground=False)
        except Exception:
            editor.click_input(); editor.type_keys(str(text),with_spaces=True)
        values=[]
        try: values.extend(editor.texts())
        except Exception: pass
        return {"typed":True,"text":"\n".join(str(x) for x in values),"control":str(editor.element_info.control_type),"source":"windows_uia"}
    def uia_document_text(self,hwnd):
        self._require()
        try: from pywinauto import Desktop
        except ImportError as exc: raise RuntimeError("pywinauto optional dependency is not installed") from exc
        root=Desktop(backend="uia").window(handle=int(hwnd)); values=[]
        for child in root.descendants():
            try:
                ctype=str(child.element_info.control_type or "")
                if ctype not in {"Document","Edit"}: continue
                texts=[]
                try: texts.extend(child.texts())
                except Exception: pass
                try:
                    value=str(child.iface_value.CurrentValue or "")
                    if value:texts.append(value)
                except Exception: pass
                values.extend(x for x in texts if x)
            except Exception: continue
        return {"hwnd":int(hwnd),"texts":values,"text":"\n".join(dict.fromkeys(values)),"source":"windows_uia_document"}
    def uia_text(self,hwnd):
        self._require()
        try: from pywinauto import Desktop
        except ImportError as exc: raise RuntimeError("pywinauto optional dependency is not installed") from exc
        root=Desktop(backend="uia").window(handle=int(hwnd)); values=[]
        for child in root.descendants():
            try:
                name=str(child.element_info.name or "")
                if name: values.append(name)
                iface=getattr(child,"iface_value",None)
                if iface is not None:
                    value=str(iface.CurrentValue or "")
                    if value: values.append(value)
            except Exception: continue
        return {"hwnd":int(hwnd),"texts":values,"text":"\n".join(dict.fromkeys(values)),"source":"windows_uia"}
    def uia_elements(self,hwnd):
        self._require()
        try:
            from pywinauto import Desktop
        except ImportError as exc: raise RuntimeError("pywinauto optional dependency is not installed") from exc
        root=Desktop(backend="uia").window(handle=int(hwnd)); rows=[]
        for child in root.descendants():
            try:
                rect=child.rectangle(); label=child.window_text() or child.element_info.name or ""
                rows.append({"role":str(child.element_info.control_type or "unknown"),"label":str(label),
                    "bounds":(rect.left,rect.top,rect.right,rect.bottom),"enabled":bool(child.is_enabled()),
                    "focused":bool(child.has_keyboard_focus()),"window":root.window_text(),
                    "confidence":1.0,"source":"windows_uia"})
            except Exception: continue
        return rows[:1000]
    def automation_text(self,hwnd):
        self._require(); import ctypes
        OBJID_CLIENT=0xFFFFFFFC; UiaRootObjectId=-25
        # Native WM_GETTEXT works for classic controls; modern controls may expose no text.
        user32=ctypes.windll.user32; texts=[]
        callback_type=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_int,ctypes.c_int)
        def collect(child,lparam):
            length=user32.SendMessageW(child,0x000E,0,0)
            if length:
                buf=ctypes.create_unicode_buffer(length+1); user32.SendMessageW(child,0x000D,length+1,buf)
                if buf.value:texts.append(buf.value)
            return True
        user32.EnumChildWindows(int(hwnd),callback_type(collect),0)
        return {"hwnd":int(hwnd),"texts":texts,"text":"\n".join(texts),"source":"win32_message"}
    def window_text(self,hwnd):
        user32=self._require(); import ctypes
        texts=[]
        callback_type=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_int,ctypes.c_int)
        def collect(child,lparam):
            length=user32.GetWindowTextLengthW(child)
            if length:
                buf=ctypes.create_unicode_buffer(length+1); user32.GetWindowTextW(child,buf,length+1)
                if buf.value:texts.append(buf.value)
            return True
        user32.EnumChildWindows(int(hwnd),callback_type(collect),0)
        return {"hwnd":int(hwnd),"texts":texts,"text":"\n".join(texts)}
    def find_window(self,title):
        wanted=str(title).casefold(); matches=[w for w in self.enumerate_windows() if wanted in str(w.get("title","")).casefold()]
        return {"matches":matches,"unique":len(matches)==1,"window":matches[0] if len(matches)==1 else None}
    def clipboard_read(self):
        try:
            from PySide6.QtWidgets import QApplication
            app=QApplication.instance() or QApplication([])
            return app.clipboard().text()
        except Exception as exc: raise RuntimeError("clipboard unavailable") from exc
    def clipboard_write(self,text):
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication([]); app.clipboard().setText(str(text))
        return {"written":True,"length":len(str(text))}

class InputController:
    """Optional input-control adapter; registry permission must gate every call."""
    @staticmethod
    def _api():
        try: import pyautogui
        except ImportError as exc: raise RuntimeError("pyautogui optional dependency is not installed") from exc
        return pyautogui
    def position(self):
        p=self._api().position(); return (int(p.x),int(p.y))
    def move(self,x,y): self._api().moveTo(int(x),int(y)); return {"moved":True}
    def click(self,x=None,y=None,button="left",clicks=1):
        self._api().click(x=x,y=y,button=button,clicks=int(clicks)); return {"clicked":True}
    def scroll(self,amount): self._api().scroll(int(amount)); return {"scrolled":int(amount)}
    def type_text(self,text): self._api().write(str(text)); return {"typed":len(str(text))}
    def press(self,key): self._api().press(str(key)); return {"pressed":str(key)}
    def hotkey(self,*keys): self._api().hotkey(*[str(x) for x in keys]); return {"hotkey":list(keys)}

class ScreenObserver:
    def __init__(self,desktop,windows=None,input_controller=None):
        self.desktop=desktop; self.windows=windows; self.input_controller=input_controller
    def capture(self): return self.desktop.screenshot()
    def observe(self,capture=True):
        from core.screen_perception import ScreenPerception
        return ScreenPerception(self.desktop,self.windows,self.input_controller).observe(capture=capture)
