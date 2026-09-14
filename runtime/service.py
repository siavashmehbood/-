import threading

class IranService:
    def __init__(self,runtime,interval=10):
        self.runtime=runtime; self.interval=max(1,int(interval)); self._stop=threading.Event(); self._thread=None
    def start(self):
        if self._thread and self._thread.is_alive(): return False
        self._stop.clear(); self._thread=threading.Thread(target=self._loop,name='iran-service',daemon=True); self._thread.start(); self.runtime.events.emit('service_started',{'interval':self.interval}); return True
    def _loop(self):
        while not self._stop.wait(self.interval):
            try: self.runtime.runner.tick(); self.runtime.events.emit('service_tick',{'ok':True})
            except Exception as exc: self.runtime.events.emit('service_error',{'error':str(exc)})
    def stop(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=2)
        self.runtime.events.emit('service_stopped',{})
