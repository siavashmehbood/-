import json
import queue
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime
from pathlib import Path

from runtime.app import IranRuntime

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
runtime = IranRuntime(ROOT)
provider = runtime.provider


class IranGUI:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.results = queue.Queue()
        self.font = ('Segoe UI', 12)
        self.small = ('Segoe UI', 9)
        self.bold = ('Segoe UI', 12, 'bold')
        root.title('ایران — فضای شناختی آفلاین')
        root.geometry('1240x820')
        root.minsize(900, 620)
        root.configure(bg='#eef1f5')
        self.build()
        self.add_message('ایران', 'سلام. من هسته نمادین و آفلاین ایران هستم.\nسؤال، هدف یا درخواستت را بنویس؛ وضعیت شناختی هر پاسخ در پنل کناری ثبت می‌شود.')
        self.write_log('GUI_READY_COGNITIVE_WORKSPACE')
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
        header = tk.Frame(self.root, bg='#172033', height=68)
        header.pack(fill='x')
        tk.Label(header, text='ایران', bg='#172033', fg='white', font=('Segoe UI', 21, 'bold')).pack(side='right', padx=22, pady=10)
        tk.Label(header, text='معماری شناختی مستقل • آفلاین • نمادین', bg='#172033', fg='#b8c7df', font=self.small).pack(side='right', pady=20)
        self.status = tk.Label(header, text='آماده | هسته نمادین', bg='#172033', fg='#79e2a1', font=self.small, anchor='e')
        self.status.pack(side='left', padx=22)

        body = tk.Frame(self.root, bg='#eef1f5')
        body.pack(fill='both', expand=True, padx=12, pady=12)
        sidebar = tk.Frame(body, bg='#ffffff', width=285, bd=1, relief='solid')
        sidebar.pack(side='left', fill='y', padx=(0, 12))
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text='وضعیت شناختی', bg='#ffffff', fg='#172033', font=('Segoe UI', 14, 'bold')).pack(anchor='e', padx=16, pady=(16, 8))
        self.metric_vars = {}
        for key, label, value in [('mode', 'حالت پاسخ', '—'), ('confidence', 'اطمینان', '—'), ('quality', 'کیفیت کلی', '—'), ('evidence', 'شواهد', '—'), ('intent', 'نیت تشخیص‌داده‌شده', '—'), ('elapsed', 'زمان پاسخ', '—')]:
            row = tk.Frame(sidebar, bg='#f6f8fb')
            row.pack(fill='x', padx=12, pady=3)
            tk.Label(row, text=label, bg='#f6f8fb', fg='#5e6b7d', font=self.small).pack(anchor='e', padx=8, pady=(5, 0))
            var = tk.StringVar(value=value)
            self.metric_vars[key] = var
            tk.Label(row, textvariable=var, bg='#f6f8fb', fg='#172033', font=('Segoe UI', 10, 'bold')).pack(anchor='e', padx=8, pady=(0, 5))
        tk.Label(sidebar, text='هدف‌های فعال', bg='#ffffff', fg='#172033', font=('Segoe UI', 11, 'bold')).pack(anchor='e', padx=16, pady=(18, 4))
        self.goals_box = tk.Listbox(sidebar, height=6, font=self.small, justify='right', bg='#f6f8fb', relief='flat')
        self.goals_box.pack(fill='x', padx=12)
        tk.Label(sidebar, text='آخرین رویدادها', bg='#ffffff', fg='#172033', font=('Segoe UI', 11, 'bold')).pack(anchor='e', padx=16, pady=(18, 4))
        self.trace_box = tk.Listbox(sidebar, height=9, font=('Consolas', 8), justify='left', bg='#f6f8fb', relief='flat')
        self.trace_box.pack(fill='both', expand=True, padx=12, pady=(0, 12))

        main = tk.Frame(body, bg='#eef1f5')
        main.pack(side='right', fill='both', expand=True)
        self.chat = scrolledtext.ScrolledText(main, wrap='word', font=self.font, bg='white', fg='#172033', relief='solid', bd=1, padx=20, pady=16, insertbackground='#172033')
        self.chat.pack(fill='both', expand=True)
        self.chat.configure(state='disabled')
        self.chat.tag_configure('iran', justify='right', foreground='#172033', spacing1=4, spacing3=14)
        self.chat.tag_configure('user', justify='right', foreground='#315a9b', spacing1=4, spacing3=14)
        self.chat.tag_configure('name', font=self.bold, justify='right')
        self.chat.tag_configure('meta', justify='right', foreground='#768399', font=self.small)

        bottom = tk.Frame(main, bg='#eef1f5')
        bottom.pack(fill='x', pady=(10, 0))
        self.entry = tk.Entry(bottom, font=self.font, justify='right', relief='solid', bd=1)
        self.entry.pack(side='right', fill='x', expand=True, ipady=11)
        self.entry.bind('<Return>', self.send)
        self.entry.bind('<Control-v>', self.paste_clipboard)
        self.entry.bind('<Control-V>', self.paste_clipboard)
        self.entry.bind('<Shift-Insert>', self.paste_clipboard)
        self.paste_btn = tk.Button(bottom, text='چسباندن', command=self.paste_clipboard, font=self.small, relief='flat', padx=10, pady=10)
        self.paste_btn.pack(side='right', padx=(0, 6))
        self.send_btn = tk.Button(bottom, text='ارسال', command=self.send, font=self.bold, bg='#315a9b', fg='white', relief='flat', padx=25, pady=10)
        self.send_btn.pack(side='right', padx=(0, 8))
        actions = tk.Frame(main, bg='#eef1f5')
        actions.pack(fill='x', pady=(8, 0))
        for label, cmd in [('benchmark', self.run_benchmark), ('trace', self.show_trace), ('حافظه', self.show_memory), ('پاک‌کردن', self.clear_chat)]:
            tk.Button(actions, text=label, command=cmd, relief='flat', padx=10).pack(side='right', padx=3)
        self.entry.focus_set()
        self.refresh_sidebar()

    def add_message(self, name, text, meta=''):
        self.chat.configure(state='normal')
        self.chat.insert('end', name + '\n', 'name')
        self.chat.insert('end', str(text) + '\n', 'iran' if name == 'ایران' else 'user')
        if meta:
            self.chat.insert('end', meta + '\n', 'meta')
        self.chat.insert('end', '\n', 'iran')
        self.chat.see('end')
        self.chat.configure(state='disabled')

    def paste_clipboard(self, event=None):
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            try:
                text = self.root.selection_get(selection='CLIPBOARD')
            except tk.TclError:
                return 'break'
        if text is None:
            return 'break'
        text = str(text).replace('\r\n', '\n').replace('\r', '\n')
        text = ' '.join(line.strip() for line in text.split('\n') if line.strip())
        if text:
            self.entry.insert('insert', text)
            self.entry.focus_set()
        return 'break'
    def send(self, event=None):
        if self.busy:
            return 'break'
        text = self.entry.get().strip()
        if not text:
            return 'break'
        self.entry.delete(0, 'end')
        self.add_message('شما', text)
        self.status.config(text='در حال ادراک، استدلال و پاسخ‌سازی...', fg='#f0b35b')
        self.busy = True
        self.send_btn.config(state='disabled')
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()
        return 'break'

    def _worker(self, text):
        started = datetime.now()
        try:
            before = len(runtime.events.recent(100))
            answer = runtime.handle(text)
            elapsed = (datetime.now() - started).total_seconds()
            events = runtime.events.recent(100)
            self.results.put(('ok', answer, elapsed, events[before:] if before < len(events) else events[-12:]))
        except Exception as exc:
            self.results.put(('error', f'{type(exc).__name__}: {exc}', 0, []))
            self.write_log('WORKER_ERROR ' + repr(traceback.format_exc()))

    def _event(self, events, name):
        rows = [e for e in events if e.get('event') == name]
        return rows[-1].get('data', {}) if rows else {}

    def refresh_sidebar(self, events=None, elapsed=None):
        events = events or runtime.events.recent(40)
        response = self._event(events, 'response_generated')
        quality = self._event(events, 'evaluation_completed').get('quality', {})
        language = self._event(events, 'language_analysis')
        self.metric_vars['mode'].set(str(response.get('mode', '—')))
        self.metric_vars['confidence'].set(str(response.get('confidence', quality.get('uncertainty_calibration', '—'))))
        self.metric_vars['quality'].set(str(quality.get('overall', '—')))
        self.metric_vars['evidence'].set(str(len(self._event(events, 'cognitive_cycle').get('causal', []) or [])))
        self.metric_vars['intent'].set(str(language.get('intent', '—')))
        self.metric_vars['elapsed'].set(f'{elapsed:.2f} ثانیه' if elapsed is not None else '—')
        self.goals_box.delete(0, 'end')
        for goal in runtime.goals.list(status='active')[:8]:
            self.goals_box.insert('end', str(goal.get('title', goal)))
        self.trace_box.delete(0, 'end')
        for event in events[-10:]:
            self.trace_box.insert('end', f"{event.get('event', '')[:24]}")

    def poll_results(self):
        try:
            while True:
                kind, answer, elapsed, events = self.results.get_nowait()
                if kind == 'ok':
                    response = self._event(events, 'response_generated')
                    quality = self._event(events, 'evaluation_completed').get('quality', {})
                    meta = f"حالت: {response.get('mode', '—')}  |  کیفیت: {quality.get('overall', '—')}  |  زمان: {elapsed:.2f}s"
                    self.add_message('ایران', answer, meta)
                    self.status.config(text=f'آماده | {response.get("mode", "پاسخ نمادین")}', fg='#79e2a1')
                    self.refresh_sidebar(events, elapsed)
                else:
                    self.add_message('ایران', 'خطا در پردازش:\n' + answer)
                    self.status.config(text='خطا — گزارش در logs ثبت شد', fg='#e36b6b')
                self.busy = False
                self.send_btn.config(state='normal')
                self.entry.focus_set()
        except queue.Empty:
            pass
        self.root.after(50, self.poll_results)

    def run_benchmark(self):
        try:
            result = runtime.roadmap_benchmark()
            self.add_message('ایران', f'Benchmark اجرا شد. امتیاز: {result.score} | وضعیت: {"موفق" if result.passed else "نیازمند بهبود"}')
            self.refresh_sidebar()
        except Exception as exc:
            messagebox.showerror('خطای benchmark', str(exc))

    def show_trace(self):
        rows = runtime.events.recent(30)
        text = '\n'.join(f"{e['time']} | {e['event']} | {e.get('data', {})}" for e in rows)
        messagebox.showinfo('ردیابی چرخه شناختی', text or 'رویدادی ثبت نشده است.')

    def show_memory(self):
        rows = runtime.memory.recent(12)
        text = 'حافظه خالی است.' if not rows else '\n\n'.join(f'[{k}] {c}' for k, c, _ in rows)
        messagebox.showinfo('حافظه اخیر', text)

    def clear_chat(self):
        self.chat.configure(state='normal')
        self.chat.delete('1.0', 'end')
        self.chat.configure(state='disabled')
        self.add_message('ایران', 'صفحه گفتگو پاک شد؛ حافظه و یادگیری حذف نشده‌اند.')

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

