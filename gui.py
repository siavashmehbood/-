import tkinter as tk
from tkinter import scrolledtext, messagebox
import json
from pathlib import Path
import threading
import queue
import traceback
from datetime import datetime

from runtime.app import IranRuntime

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))

def resolve(path):
    return str(ROOT / path)

runtime = IranRuntime(ROOT)
provider = runtime.provider
memory = runtime.memory
goals = runtime.goals

class IranGUI:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.results = queue.Queue()
        self.font = ('Segoe UI', 12)
        self.bold = ('Segoe UI', 12, 'bold')
        root.title('ایران — دستیار هوشمند')
        root.geometry('1000x720')
        root.minsize(760, 520)
        root.configure(bg='#f5f5f5')
        self.build()
        self.add_message('ایران', 'سلام 👋\nمن آماده‌ام. هر چیزی می‌خواهی بنویس.')
        self.write_log('GUI_READY')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(50, self.poll_results)

    def write_log(self, message):
        try:
            path = ROOT / 'logs' / 'gui_startup.log'
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a', encoding='utf-8') as f:
                f.write(datetime.now().isoformat() + ' ' + message + '\n')
        except Exception:
            pass

    def build(self):
        header = tk.Frame(self.root, bg='#202124', height=64)
        header.pack(fill='x')
        tk.Label(header, text='ایران', bg='#202124', fg='white', font=('Segoe UI', 19, 'bold')).pack(side='right', padx=22, pady=10)
        tk.Label(header, text='دستیار شخصی هوشمند', bg='#202124', fg='#c7c7c7', font=('Segoe UI', 10)).pack(side='right', pady=16)
        self.chat = scrolledtext.ScrolledText(self.root, wrap='word', font=self.font, bg='white', fg='#202124', relief='flat', padx=20, pady=16, insertbackground='#202124')
        self.chat.pack(fill='both', expand=True, padx=14, pady=(14, 8))
        self.chat.configure(state='disabled')
        self.chat.tag_configure('iran', justify='right', spacing1=4, spacing3=14)
        self.chat.tag_configure('user', justify='right', spacing1=4, spacing3=14)
        self.chat.tag_configure('name', font=self.bold, justify='right')
        bottom = tk.Frame(self.root, bg='#f5f5f5')
        bottom.pack(fill='x', padx=14, pady=(0, 6))
        self.entry = tk.Entry(bottom, font=self.font, justify='right', relief='solid', bd=1)
        self.entry.pack(side='right', fill='x', expand=True, ipady=10)
        self.entry.bind('<Return>', self.send)
        self.send_btn = tk.Button(bottom, text='ارسال', command=self.send, font=self.bold, bg='#202124', fg='white', relief='flat', padx=22, pady=10)
        self.send_btn.pack(side='right', padx=(0, 8))
        actions = tk.Frame(self.root, bg='#f5f5f5')
        actions.pack(fill='x', padx=14, pady=(0, 2))
        for label, cmd in [('وضعیت', self.show_status), ('حافظه', self.show_memory), ('پاک‌کردن صفحه', self.clear_chat)]:
            tk.Button(actions, text=label, command=cmd, relief='flat', padx=10).pack(side='right', padx=3)
        self.status = tk.Label(self.root, text='آماده | مدل: ' + provider.name, bg='#f5f5f5', fg='#666666', font=('Segoe UI', 9), anchor='e')
        self.status.pack(fill='x', padx=18, pady=(0, 8))
        self.entry.focus_set()

    def add_message(self, name, text):
        self.chat.configure(state='normal')
        self.chat.insert('end', name + '\n', 'name')
        self.chat.insert('end', str(text) + '\n\n', 'iran' if name == 'ایران' else 'user')
        self.chat.see('end')
        self.chat.configure(state='disabled')

    def send(self, event=None):
        if self.busy:
            return 'break'
        text = self.entry.get().strip()
        if not text:
            return 'break'
        self.entry.delete(0, 'end')
        self.add_message('شما', text)
        self.status.config(text='در حال پردازش...')
        self.busy = True
        self.send_btn.config(state='disabled')
        self.write_log('SEND ' + repr(text[:120]))
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()
        return 'break'

    def _worker(self, text):
        started = datetime.now()
        try:
            answer = runtime.handle(text)
            elapsed = (datetime.now() - started).total_seconds()
            self.results.put(('ok', answer, elapsed))
            self.write_log(f'WORKER_OK {elapsed:.3f}s')
        except Exception as exc:
            detail = traceback.format_exc()
            self.results.put(('error', f'{type(exc).__name__}: {exc}', 0))
            self.write_log('WORKER_ERROR ' + repr(detail))

    def poll_results(self):
        try:
            while True:
                kind, answer, elapsed = self.results.get_nowait()
                if kind == 'ok':
                    self.add_message('ایران', answer)
                    self.status.config(text=f'آماده | {elapsed:.2f} ثانیه | مدل: {provider.name}')
                else:
                    self.add_message('ایران', 'خطا در پردازش:\n' + answer)
                    self.status.config(text='خطا — جزئیات در logs/gui_startup.log')
                self.busy = False
                self.send_btn.config(state='normal')
                self.entry.focus_set()
        except queue.Empty:
            pass
        self.root.after(50, self.poll_results)

    def show_status(self):
        try:
            health = runtime.health()
            text = json.dumps(health, ensure_ascii=False, indent=2)
            text += f'\n\nحافظه: {runtime.memory.stats()}'
            text += f'\nاهداف فعال: {len(goals.list(status="active"))}'
            text += f'\nابزارها: {len(runtime.registry.list())}'
            messagebox.showinfo('وضعیت ایران', text)
        except Exception as exc:
            messagebox.showerror('خطا', str(exc))

    def show_memory(self):
        rows = runtime.memory.recent(12)
        text = 'حافظه خالی است.' if not rows else '\n\n'.join(f'[{k}] {c}' for k, c, _ in rows)
        messagebox.showinfo('حافظه اخیر', text)

    def clear_chat(self):
        self.chat.configure(state='normal')
        self.chat.delete('1.0', 'end')
        self.chat.configure(state='disabled')
        self.add_message('ایران', 'صفحه گفتگو پاک شد؛ حافظه ذخیره‌شده حذف نشده است.')

    def close(self):
        try:
            runtime.close()
        finally:
            self.root.destroy()

def launch():
    root = tk.Tk()
    IranGUI(root)
    root.mainloop()

if __name__ == '__main__':
    launch()
