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
        root.title('Ã˜Â§Ã›Å’Ã˜Â±Ã˜Â§Ã™â€  Ã¢â‚¬â€ Ã™ÂÃ˜Â¶Ã˜Â§Ã›Å’ Ã˜Â´Ã™â€ Ã˜Â§Ã˜Â®Ã˜ÂªÃ›Å’ Ã˜Â¢Ã™ÂÃ™â€žÃ˜Â§Ã›Å’Ã™â€ ')
        root.geometry('1240x820')
        root.minsize(900, 620)
        root.configure(bg='#eef1f5')
        self.build()
        self.add_message('Ã˜Â§Ã›Å’Ã˜Â±Ã˜Â§Ã™â€ ', 'Ã˜Â³Ã™â€žÃ˜Â§Ã™â€¦. Ã™â€¦Ã™â€  Ã™â€¡Ã˜Â³Ã˜ÂªÃ™â€¡ Ã™â€ Ã™â€¦Ã˜Â§Ã˜Â¯Ã›Å’Ã™â€  Ã™Ë† Ã˜Â¢Ã™ÂÃ™â€žÃ˜Â§Ã›Å’Ã™â€  Ã˜Â§Ã›Å’Ã˜Â±Ã˜Â§Ã™â€  Ã™â€¡Ã˜Â³Ã˜ÂªÃ™â€¦.\nÃ˜Â³Ã˜Â¤Ã˜Â§Ã™â€žÃ˜Å’ Ã™â€¡Ã˜Â¯Ã™Â Ã›Å’Ã˜Â§ Ã˜Â¯Ã˜Â±Ã˜Â®Ã™Ë†Ã˜Â§Ã˜Â³Ã˜ÂªÃ˜Âª Ã˜Â±Ã˜Â§ Ã˜Â¨Ã™â€ Ã™Ë†Ã›Å’Ã˜Â³Ã˜â€º Ã™Ë†Ã˜Â¶Ã˜Â¹Ã›Å’Ã˜Âª Ã˜Â´Ã™â€ Ã˜Â§Ã˜Â®Ã˜ÂªÃ›Å’ Ã™â€¡Ã˜Â± Ã™Â¾Ã˜Â§Ã˜Â³Ã˜Â® Ã˜Â¯Ã˜Â± Ã™Â¾Ã™â€ Ã™â€ž ÃšÂ©Ã™â€ Ã˜Â§Ã˜Â±Ã›Å’ Ã˜Â«Ã˜Â¨Ã˜Âª Ã™â€¦Ã›Å’Ã¢â‚¬Å’Ã˜Â´Ã™Ë†Ã˜Â¯.')
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
        tk.Label(header, text='Ã˜Â§Ã›Å’Ã˜Â±Ã˜Â§Ã™â€ ', bg='#172033', fg='white', font=('Segoe UI', 21, 'bold')).pack(side='right', padx=22, pady=10)
        tk.Label(header, text='Ã™â€¦Ã˜Â¹Ã™â€¦Ã˜Â§Ã˜Â±Ã›Å’ Ã˜Â´Ã™â€ Ã˜Â§Ã˜Â®Ã˜ÂªÃ›Å’ Ã™â€¦Ã˜Â³Ã˜ÂªÃ™â€šÃ™â€ž Ã¢â‚¬Â¢ Ã˜Â¢Ã™ÂÃ™â€žÃ˜Â§Ã›Å’Ã™â€  Ã¢â‚¬Â¢ Ã™â€ Ã™â€¦Ã˜Â§Ã˜Â¯Ã›Å’Ã™â€ ', bg='#172033', fg='#b8c7df', font=self.small).pack(side='right', pady=20)
        self.status = tk.Label(header, text='Ã˜Â¢Ã™â€¦Ã˜Â§Ã˜Â¯Ã™â€¡ | Ã™â€¡Ã˜Â³Ã˜ÂªÃ™â€¡ Ã™â€ Ã™â€¦Ã˜Â§Ã˜Â¯Ã›Å’Ã™â€ ', bg='#172033', fg='#79e2a1', font=self.small, anchor='e')
        self.status.pack(side='left', padx=22)

        body = tk.Frame(self.root, bg='#eef1f5')
        body.pack(fill='both', expand=True, padx=12, pady=12)
        sidebar = tk.Frame(body, bg='#ffffff', width=285, bd=1, relief='solid')
        sidebar.pack(side='left', fill='y', padx=(0, 12))
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text='Ã™Ë†Ã˜Â¶Ã˜Â¹Ã›Å’Ã˜Âª Ã˜Â´Ã™â€ Ã˜Â§Ã˜Â®Ã˜ÂªÃ›Å’', bg='#ffffff', fg='#172033', font=('Segoe UI', 14, 'bold')).pack(anchor='e', padx=16, pady=(16, 8))
        self.metric_vars = {}
        for key, label, value in [('mode', 'Ã˜Â­Ã˜Â§Ã™â€žÃ˜Âª Ã™Â¾Ã˜Â§Ã˜Â³Ã˜Â®', 'Ã¢â‚¬â€'), ('confidence', 'Ã˜Â§Ã˜Â·Ã™â€¦Ã›Å’Ã™â€ Ã˜Â§Ã™â€ ', 'Ã¢â‚¬â€'), ('quality', 'ÃšÂ©Ã›Å’Ã™ÂÃ›Å’Ã˜Âª ÃšÂ©Ã™â€žÃ›Å’', 'Ã¢â‚¬â€'), ('evidence', 'Ã˜Â´Ã™Ë†Ã˜Â§Ã™â€¡Ã˜Â¯', 'Ã¢â‚¬â€'), ('intent', 'Ã™â€ Ã›Å’Ã˜Âª Ã˜ÂªÃ˜Â´Ã˜Â®Ã›Å’Ã˜ÂµÃ¢â‚¬Å’Ã˜Â¯Ã˜Â§Ã˜Â¯Ã™â€¡Ã¢â‚¬Å’Ã˜Â´Ã˜Â¯Ã™â€¡', 'Ã¢â‚¬â€'), ('elapsed', 'Ã˜Â²Ã™â€¦Ã˜Â§Ã™â€  Ã™Â¾Ã˜Â§Ã˜Â³Ã˜Â®', 'Ã¢â‚¬â€')]:
            row = tk.Frame(sidebar, bg='#f6f8fb')
            row.pack(fill='x', padx=12, pady=3)
            tk.Label(row, text=label, bg='#f6f8fb', fg='#5e6b7d', font=self.small).pack(anchor='e', padx=8, pady=(5, 0))
            var = tk.StringVar(value=value)
            self.metric_vars[key] = var
            tk.Label(row, textvariable=var, bg='#f6f8fb', fg='#172033', font=('Segoe UI', 10, 'bold')).pack(anchor='e', padx=8, pady=(0, 5))
        net = tk.Frame(sidebar, bg='#eef5ff', bd=1, relief='solid')
        net.pack(fill='x', padx=12, pady=(14, 8))
        tk.Label(net, text='Ã˜Â¯Ã˜Â³Ã˜ÂªÃ˜Â±Ã˜Â³Ã›Å’ Ã˜Â§Ã›Å’Ã™â€ Ã˜ÂªÃ˜Â±Ã™â€ Ã˜Âª', bg='#eef5ff', fg='#172033', font=('Segoe UI', 11, 'bold')).pack(anchor='e', padx=10, pady=(8, 2))
        self.internet_var = tk.StringVar()
        tk.Label(net, textvariable=self.internet_var, bg='#eef5ff', fg='#315a9b', font=self.small).pack(anchor='e', padx=10)
        self.internet_btn = tk.Button(net, text='Ã˜Â®Ã˜Â§Ã™â€¦Ã™Ë†Ã˜Â´ ÃšÂ©Ã˜Â±Ã˜Â¯Ã™â€ ', command=self.toggle_internet, relief='flat', padx=12, pady=5)
        self.internet_btn.pack(fill='x', padx=10, pady=8)
        tk.Label(sidebar, text='Ã›Å’Ã˜Â§Ã˜Â¯ÃšÂ¯Ã›Å’Ã˜Â±Ã›Å’ Ã˜Â¯Ã˜Â§Ã˜Â¦Ã™â€¦Ã›Å’ Ã™â€¡Ã™â€¦Ãšâ€ Ã™â€ Ã˜Â§Ã™â€  Ã™â€ Ã›Å’Ã˜Â§Ã˜Â²Ã™â€¦Ã™â€ Ã˜Â¯ Ã˜ÂªÃ˜Â£Ã›Å’Ã›Å’Ã˜Â¯ Ã˜Â´Ã™â€¦Ã˜Â§Ã˜Â³Ã˜Âª.', bg='#ffffff', fg='#768399', font=('Segoe UI', 8), wraplength=250, justify='right').pack(anchor='e', padx=16, pady=(0, 4))
        tk.Label(sidebar, text='Ã™â€¡Ã˜Â¯Ã™ÂÃ¢â‚¬Å’Ã™â€¡Ã˜Â§Ã›Å’ Ã™ÂÃ˜Â¹Ã˜Â§Ã™â€ž', bg='#ffffff', fg='#172033', font=('Segoe UI', 11, 'bold')).pack(anchor='e', padx=16, pady=(10, 4))
        self.goals_box = tk.Listbox(sidebar, height=6, font=self.small, justify='right', bg='#f6f8fb', relief='flat')
        self.goals_box.pack(fill='x', padx=12)
        tk.Label(sidebar, text='Ã˜Â¢Ã˜Â®Ã˜Â±Ã›Å’Ã™â€  Ã˜Â±Ã™Ë†Ã›Å’Ã˜Â¯Ã˜Â§Ã˜Â¯Ã™â€¡Ã˜Â§', bg='#ffffff', fg='#172033', font=('Segoe UI', 11, 'bold')).pack(anchor='e', padx=16, pady=(18, 4))
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
        self.paste_btn = tk.Button(bottom, text='Ãšâ€ Ã˜Â³Ã˜Â¨Ã˜Â§Ã™â€ Ã˜Â¯Ã™â€ ', command=self.paste_clipboard, font=self.small, relief='flat', padx=12, pady=10)
        self.paste_btn.pack(side='right', padx=(0, 6))
        self.send_btn = tk.Button(bottom, text='Ã˜Â§Ã˜Â±Ã˜Â³Ã˜Â§Ã™â€ž', command=self.send, font=self.bold, bg='#315a9b', fg='white', relief='flat', padx=25, pady=10)
        self.send_btn.pack(side='right', padx=(0, 8))
        actions = tk.Frame(main, bg='#eef1f5')
        actions.pack(fill='x', pady=(8, 0))
        for label, cmd in [('benchmark', self.run_benchmark), ('trace', self.show_trace), ('Ã˜Â­Ã˜Â§Ã™ÂÃ˜Â¸Ã™â€¡', self.show_memory), ('Ã™Â¾Ã˜Â§ÃšÂ©Ã¢â‚¬Å’ÃšÂ©Ã˜Â±Ã˜Â¯Ã™â€ ', self.clear_chat)]:
            tk.Button(actions, text=label, command=cmd, relief='flat', padx=10).pack(side='right', padx=3)
        self.entry.focus_set()
        self.refresh_sidebar()

    def add_message(self, name, text, meta=''):
        self.chat.configure(state='normal')
        self.chat.insert('end', name + '\n', 'name')
        self.chat.insert('end', str(text) + '\n', 'iran' if name == 'Ã˜Â§Ã›Å’Ã˜Â±Ã˜Â§Ã™â€ ' else 'user')
        if meta:
            self.chat.insert('end', meta + '\n', 'meta')
        self.chat.insert('end', '\n', 'iran')
        self.chat.see('end')
        self.chat.configure(state='disabled')

    def paste_clipboard(self, event=None):
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            return 'break'
        text = str(text).replace(chr(13), ' ').replace(chr(10), ' ').strip()
        if text:
            self.entry.insert('insert', text)
        return 'break'

    def send(self, event=None):
        if self.busy:
            return 'break'
        text = self.entry.get().strip()
        if not text:
            return 'break'
        self.entry.delete(0, 'end')
        self.add_message('Ã˜Â´Ã™â€¦Ã˜Â§', text)
        self.status.config(text='Ã˜Â¯Ã˜Â± Ã˜Â­Ã˜Â§Ã™â€ž Ã˜Â§Ã˜Â¯Ã˜Â±Ã˜Â§ÃšÂ©Ã˜Å’ Ã˜Â§Ã˜Â³Ã˜ÂªÃ˜Â¯Ã™â€žÃ˜Â§Ã™â€ž Ã™Ë† Ã™Â¾Ã˜Â§Ã˜Â³Ã˜Â®Ã¢â‚¬Å’Ã˜Â³Ã˜Â§Ã˜Â²Ã›Å’...', fg='#f0b35b')
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
            unified = getattr(runtime.cognitive_system, 'last_output', {}) or {}
            self.results.put(('ok', answer, elapsed, events[before:] if before < len(events) else events[-12:], unified))
        except Exception as exc:
            self.results.put(('error', f'{type(exc).__name__}: {exc}', 0, []))
            self.write_log('WORKER_ERROR ' + repr(traceback.format_exc()))

    def _event(self, events, name):
        rows = [e for e in events if e.get('event') == name]
        return rows[-1].get('data', {}) if rows else {}

    def toggle_internet(self):
        try:
            current = runtime.internet_access.status().get('enabled', False)
            result = runtime.internet_access.disable() if current else runtime.internet_access.enable()
            runtime.events.emit('internet_access_changed', result)
            self.refresh_sidebar()
            self.status.config(text='Ã˜Â¢Ã™â€¦Ã˜Â§Ã˜Â¯Ã™â€¡ | Ã˜Â§Ã›Å’Ã™â€ Ã˜ÂªÃ˜Â±Ã™â€ Ã˜Âª Ã˜Â±Ã™Ë†Ã˜Â´Ã™â€ ' if result['enabled'] else 'Ã˜Â¢Ã™â€¦Ã˜Â§Ã˜Â¯Ã™â€¡ | Ã˜Â§Ã›Å’Ã™â€ Ã˜ÂªÃ˜Â±Ã™â€ Ã˜Âª Ã˜Â®Ã˜Â§Ã™â€¦Ã™Ë†Ã˜Â´',
                               fg='#79e2a1' if result['enabled'] else '#f0b35b')
        except Exception as exc:
            messagebox.showerror('Ã˜Â¯Ã˜Â³Ã˜ÂªÃ˜Â±Ã˜Â³Ã›Å’ Ã˜Â§Ã›Å’Ã™â€ Ã˜ÂªÃ˜Â±Ã™â€ Ã˜Âª', str(exc), parent=self.root)

    def refresh_sidebar(self, events=None, elapsed=None):
        events = events or runtime.events.recent(40)
        net = runtime.internet_access.status()
        self.internet_var.set('Ã™ÂÃ˜Â¹Ã˜Â§Ã™â€ž Ã¢â‚¬â€ Ã˜Â¯Ã˜Â³Ã˜ÂªÃ˜Â±Ã˜Â³Ã›Å’ Ã˜Â´Ã˜Â¨ÃšÂ©Ã™â€¡ Ã™â€¦Ã˜Â¬Ã˜Â§Ã˜Â² Ã˜Â§Ã˜Â³Ã˜Âª' if net['enabled'] else 'Ã˜Â®Ã˜Â§Ã™â€¦Ã™Ë†Ã˜Â´ Ã¢â‚¬â€ Ã˜Â¨Ã˜Â¯Ã™Ë†Ã™â€  Ã˜Â¯Ã˜Â³Ã˜ÂªÃ˜Â±Ã˜Â³Ã›Å’ Ã˜Â´Ã˜Â¨ÃšÂ©Ã™â€¡')
        self.internet_btn.config(text='Ã˜Â®Ã˜Â§Ã™â€¦Ã™Ë†Ã˜Â´ ÃšÂ©Ã˜Â±Ã˜Â¯Ã™â€ ' if net['enabled'] else 'Ã˜Â±Ã™Ë†Ã˜Â´Ã™â€  ÃšÂ©Ã˜Â±Ã˜Â¯Ã™â€  Ã˜Â§Ã›Å’Ã™â€ Ã˜ÂªÃ˜Â±Ã™â€ Ã˜Âª')
        response = self._event(events, 'response_generated')
        quality = self._event(events, 'evaluation_completed').get('quality', {})
        language = self._event(events, 'language_analysis')
        self.metric_vars['mode'].set(str(response.get('mode', 'Ã¢â‚¬â€')))
        self.metric_vars['confidence'].set(str(response.get('confidence', quality.get('uncertainty_calibration', 'Ã¢â‚¬â€'))))
        self.metric_vars['quality'].set(str(quality.get('overall', 'Ã¢â‚¬â€')))
        self.metric_vars['evidence'].set(str(len(self._event(events, 'cognitive_cycle').get('causal', []) or [])))
        self.metric_vars['intent'].set(str(language.get('intent', 'Ã¢â‚¬â€')))
        self.metric_vars['elapsed'].set(f'{elapsed:.2f} Ã˜Â«Ã˜Â§Ã™â€ Ã›Å’Ã™â€¡' if elapsed is not None else 'Ã¢â‚¬â€')
        self.goals_box.delete(0, 'end')
        for goal in runtime.goals.list(status='active')[:8]:
            self.goals_box.insert('end', str(goal.get('title', goal)))
        self.trace_box.delete(0, 'end')
        for event in events[-10:]:
            self.trace_box.insert('end', f"{event.get('event', '')[:24]}")

    def poll_results(self):
        try:
            while True:
                item = self.results.get_nowait()
                kind, answer, elapsed, events = item[:4]
                unified = item[4] if len(item) > 4 else {}
                if kind == 'ok':
                    response = self._event(events, 'response_generated')
                    quality = self._event(events, 'evaluation_completed').get('quality', {})
                    meta = f"Ã˜Â­Ã˜Â§Ã™â€žÃ˜Âª: {response.get('mode', 'Ã¢â‚¬â€')}  |  ÃšÂ©Ã›Å’Ã™ÂÃ›Å’Ã˜Âª: {quality.get('overall', 'Ã¢â‚¬â€')}  |  Ã˜Â²Ã™â€¦Ã˜Â§Ã™â€ : {elapsed:.2f}s"
                    self.add_message('Ã˜Â§Ã›Å’Ã˜Â±Ã˜Â§Ã™â€ ', answer, meta)
                    self.status.config(text=f'Ã˜Â¢Ã™â€¦Ã˜Â§Ã˜Â¯Ã™â€¡ | {response.get("mode", "Ã™Â¾Ã˜Â§Ã˜Â³Ã˜Â® Ã™â€ Ã™â€¦Ã˜Â§Ã˜Â¯Ã›Å’Ã™â€ ")}', fg='#79e2a1')
                    self.refresh_sidebar(events, elapsed)
                    self.root.after(100, self.review_pending_learning)
                else:
                    self.add_message('Ã˜Â§Ã›Å’Ã˜Â±Ã˜Â§Ã™â€ ', 'Ã˜Â®Ã˜Â·Ã˜Â§ Ã˜Â¯Ã˜Â± Ã™Â¾Ã˜Â±Ã˜Â¯Ã˜Â§Ã˜Â²Ã˜Â´:\n' + answer)
                    self.status.config(text='Ã˜Â®Ã˜Â·Ã˜Â§ Ã¢â‚¬â€ ÃšÂ¯Ã˜Â²Ã˜Â§Ã˜Â±Ã˜Â´ Ã˜Â¯Ã˜Â± logs Ã˜Â«Ã˜Â¨Ã˜Âª Ã˜Â´Ã˜Â¯', fg='#e36b6b')
                self.busy = False
                self.send_btn.config(state='normal')
                self.entry.focus_set()
        except queue.Empty:
            pass
        self.root.after(50, self.poll_results)

    def review_pending_learning(self):
        pending = runtime.learning_history(200)
        if not pending:
            return
        win = getattr(self, '_learning_window', None)
        if win is not None:
            try:
                if win.winfo_exists():
                    self._learning_refresh(win, pending)
                    win.lift(); win.focus_force()
                    return
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root)
        self._learning_window = win
        win.title('\u0627\u06cc\u0631\u0627\u0646 | \u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc \u062c\u062f\u06cc\u062f')
        win.geometry('820x650')
        win.transient(self.root)
        win.protocol('WM_DELETE_WINDOW', win.destroy)

        tk.Label(win, text='\u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc\u200c\u0647\u0627\u06cc \u062c\u062f\u06cc\u062f \u0627\u06cc\u0631\u0627\u0646', font=('Segoe UI', 16, 'bold')).pack(anchor='e', padx=18, pady=(16, 4))
        tk.Label(win, text='\u0647\u0631 \u0645\u0648\u0631\u062f \u06cc\u06a9 \u0646\u06a9\u062a\u0647\u0654 \u0645\u0633\u062a\u0642\u0644 \u0627\u0633\u062a. \u06a9\u067e\u06cc \u06a9\u0631\u062f\u0646 \u0641\u0642\u0637 \u0645\u062a\u0646 \u0631\u0627 \u06a9\u067e\u06cc \u0645\u06cc\u200c\u06a9\u0646\u062f \u0648 \u062a\u0623\u06cc\u06cc\u062f \u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc \u0631\u0627 \u0627\u0646\u062c\u0627\u0645 \u0646\u0645\u06cc\u200c\u062f\u0647\u062f.', font=self.small, fg='#5e6b7d').pack(anchor='e', padx=18, pady=(0, 10))

        body = tk.Frame(win); body.pack(fill='both', expand=True, padx=18, pady=8)
        left = tk.Frame(body, width=230); left.pack(side='left', fill='y', padx=(0, 10))
        tk.Label(left, text='\u0644\u06cc\u0633\u062a \u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc\u200c\u0647\u0627', font=('Segoe UI', 11, 'bold')).pack(anchor='e')
        count_var = tk.StringVar()
        tk.Label(left, textvariable=count_var, font=self.small, fg='#315a9b').pack(anchor='e', pady=(2, 6))
        listbox = tk.Listbox(left, font=('Segoe UI', 10), justify='right', exportselection=False); listbox.pack(fill='both', expand=True)

        right = tk.Frame(body); right.pack(side='right', fill='both', expand=True)
        box = scrolledtext.ScrolledText(right, wrap='word', font=('Segoe UI', 10), height=25); box.pack(fill='both', expand=True); box.configure(state='disabled')
        buttons = tk.Frame(win); buttons.pack(fill='x', padx=18, pady=14)
        state = {'pending': pending, 'selected': 0}

        def render_selected():
            rows = state['pending']
            if not rows:
                win.destroy(); self._learning_window = None; return
            idx = max(0, min(state['selected'], len(rows) - 1)); state['selected'] = idx
            payload = rows[idx].get('payload', {}) or {}
            goal = str(payload.get('goal', '\u0645\u0648\u0636\u0648\u0639 \u0645\u0634\u062e\u0635 \u0646\u0634\u062f\u0647'))
            action = str(payload.get('action', '\u0631\u0627\u0647\u0628\u0631\u062f \u0645\u0634\u062e\u0635 \u0646\u0634\u062f\u0647'))
            result = str(payload.get('result', '\u0646\u062a\u06cc\u062c\u0647 \u062b\u0628\u062a \u0646\u0634\u062f\u0647'))
            lesson = str(payload.get('lesson', '\u0646\u06a9\u062a\u0647\u0654 \u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc \u062b\u0628\u062a \u0646\u0634\u062f\u0647'))
            strategy = str(payload.get('strategy', '\u0631\u0627\u0647\u0628\u0631\u062f \u067e\u06cc\u0634\u200c\u0641\u0631\u0636'))
            score = payload.get('score', '\u2014'); intent = str(payload.get('intent', '\u0639\u0645\u0648\u0645\u06cc')); domain = str(payload.get('domain', '\u0639\u0645\u0648\u0645\u06cc'))
            explanation = ('\u0646\u06a9\u062a\u0647\u0654 \u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc\n\n' f'\u0645\u0648\u0636\u0648\u0639:\n{goal}\n\n' f'\u0686\u0647 \u06a9\u0627\u0631\u06cc \u0627\u0646\u062c\u0627\u0645 \u0634\u062f\u061f\n{action}\n\n' f'\u0686\u0647 \u0646\u062a\u06cc\u062c\u0647\u200c\u0627\u06cc \u0628\u0647 \u062f\u0633\u062a \u0622\u0645\u062f\u061f\n{result}\n\n' f'\u0686\u0647 \u0686\u06cc\u0632\u06cc \u06cc\u0627\u062f \u06af\u0631\u0641\u062a\u0647 \u0634\u062f\u061f\n{lesson}\n\n' f'\u0631\u0627\u0647\u0628\u0631\u062f: {strategy}\n\u0642\u0635\u062f: {intent}\n\u062d\u0648\u0632\u0647: {domain}\n\u0627\u0645\u062a\u06cc\u0627\u0632 \u062a\u062c\u0631\u0628\u0647: {score}\n')
            box.configure(state='normal'); box.delete('1.0', 'end'); box.insert('1.0', explanation); box.configure(state='disabled')
            listbox.selection_clear(0, 'end'); listbox.selection_set(idx); listbox.activate(idx); count_var.set(f'{len(rows)} Ø¯Ø±Ø®ÙˆØ§Ø³Øª Ø¯Ø± Ø§Ù†ØªØ¸Ø§Ø± | XP: {len(rows) * 1_000_000:,} | Ù…ÙˆØ±Ø¯ {idx + 1}')

        def refresh():
            rows = runtime.learning_history(200); state['pending'] = rows
            if not rows:
                win.destroy(); self._learning_window = None; self.status.config(text='\u0647\u0645\u0647 \u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc\u200c\u0647\u0627 \u0628\u0631\u0631\u0633\u06cc \u0634\u062f\u0646\u062f', fg='#79e2a1'); return
            listbox.delete(0, 'end')
            for row in rows:
                goal = str((row.get('payload', {}) or {}).get('goal', '\u0645\u0648\u0636\u0648\u0639 \u0645\u0634\u062e\u0635 \u0646\u0634\u062f\u0647')).strip().replace('\n', ' ')
                status = str(row.get('status', 'pending'))
                label = {'approved': '\u062a\u0623\u06cc\u06cc\u062f \u0634\u062f\u0647', 'rejected': '\u0631\u062f \u0634\u062f\u0647', 'pending': '\u062f\u0631 \u0627\u0646\u062a\u0638\u0627\u0631'}.get(status, status)
                listbox.insert('end', f'{label} | {goal[:27]}')
            state['selected'] = min(state['selected'], len(rows) - 1); render_selected()

        def select(event=None):
            sel = listbox.curselection()
            if sel: state['selected'] = sel[0]; render_selected()

        def copy_proposal():
            self.root.clipboard_clear(); self.root.clipboard_append(box.get('1.0', 'end-1c')); self.root.update()
            self.status.config(text='\u0646\u06a9\u062a\u0647\u0654 \u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc \u06a9\u067e\u06cc \u0634\u062f? \u067e\u0646\u062c\u0631\u0647 \u0628\u0633\u062a\u0647 \u0646\u0645\u06cc\u200c\u0634\u0648\u062f', fg='#315a9b'); win.lift(); win.focus_force()

        def export_proposal():
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(parent=win, title='\u0630\u062e\u06cc\u0631\u0647 \u0646\u06a9\u062a\u0647\u0654 \u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc', defaultextension='.txt', filetypes=[('\u0641\u0627\u06cc\u0644 \u0645\u062a\u0646\u06cc', '*.txt'), ('\u0647\u0645\u0647 \u0641\u0627\u06cc\u0644\u200c\u0647\u0627', '*.*')], initialfile='\u0646\u06a9\u062a\u0647_\u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc.txt')
            if path: Path(path).write_text(box.get('1.0', 'end-1c'), encoding='utf-8'); self.status.config(text='\u0646\u06a9\u062a\u0647\u0654 \u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc \u0630\u062e\u06cc\u0631\u0647 \u0634\u062f', fg='#315a9b'); win.lift()

        def decide(action):
            rows = state['pending']
            if not rows: return
            proposal = rows[state['selected']]
            if proposal.get('status') != 'pending':
                messagebox.showinfo('\u06cc\u0627\u062f\u06af\06cc\u0631\06cc', '\u0627\u06cc\0646 \u0645\u0648\u0631\u062f \u0642\u0628\u0644\u0627\u064b \u0628\u0631\u0631\u0633\u06cc \u0634\u062f\u0647 \u0648 \u0648\u0636\u0639\u06cc\u062a \u0622\u0646 \u062f\u0631 \u062a\u0627\u0631\u06cc\u062e\u0686\u0647 \u0630\u062e\u06cc\u0631\u0647 \u0634\u062f\u0647 \u0627\u0633\u062a.', parent=win)
                return
            result = runtime.approve_learning(proposal['proposal_id']) if action == 'approve' else runtime.reject_learning(proposal['proposal_id'])
            if result.get('ok'):
                state['selected'] = min(state['selected'], max(0, len(rows) - 2)); refresh()
                self.status.config(text='\u06cc\u0627\u062f\u06af\06cc\u0631\u06cc \u062a\u0623\u06cc\u06cc\u062f \u0634\u062f' if action == 'approve' else '\u06cc\u0627\u062f\u06af\06cc\u0631\u06cc \u0631\u062f \u0634\u062f', fg='#79e2a1' if action == 'approve' else '#e36b6b')
            else: messagebox.showerror('\u06cc\u0627\u062f\u06af\06cc\u0631\u06cc', str(result), parent=win)

        listbox.bind('<<ListboxSelect>>', select)
        tk.Button(buttons, text='\u0631\u062f \u06a9\u0631\u062f\u0646 \u0627\u06cc\u0646 \u0645\u0648\u0631\u062f', command=lambda: decide('reject'), padx=18, pady=8).pack(side='left')
        tk.Button(buttons, text='\u06a9\u067e\u06cc \u0646\u06a9\u062a\u0647', command=copy_proposal, padx=18, pady=8).pack(side='left', padx=6)
        tk.Button(buttons, text='\u0630\u062e\u06cc\u0631\u0647 \u0641\u0627\u06cc\u0644 \u0645\u062a\u0646\u06cc', command=export_proposal, padx=18, pady=8).pack(side='left', padx=6)
        tk.Button(buttons, text='\u062a\u0623\u06cc\u06cc\u062f \u0648 \u06cc\u0627\u062f\u06af\u06cc\u0631\u06cc', command=lambda: decide('approve'), padx=22, pady=8).pack(side='right')
        refresh()
        listbox.focus_set()

    def _learning_refresh(self, win, pending):
        try:
            if win.winfo_exists(): self._learning_pending_refresh = pending
        except tk.TclError: pass

    def run_benchmark(self):
        try:
            result = runtime.roadmap_benchmark()
            self.add_message('Ã˜Â§Ã›Å’Ã˜Â±Ã˜Â§Ã™â€ ', f'Benchmark Ã˜Â§Ã˜Â¬Ã˜Â±Ã˜Â§ Ã˜Â´Ã˜Â¯. Ã˜Â§Ã™â€¦Ã˜ÂªÃ›Å’Ã˜Â§Ã˜Â²: {result.score} | Ã™Ë†Ã˜Â¶Ã˜Â¹Ã›Å’Ã˜Âª: {"Ã™â€¦Ã™Ë†Ã™ÂÃ™â€š" if result.passed else "Ã™â€ Ã›Å’Ã˜Â§Ã˜Â²Ã™â€¦Ã™â€ Ã˜Â¯ Ã˜Â¨Ã™â€¡Ã˜Â¨Ã™Ë†Ã˜Â¯"}')
            self.refresh_sidebar()
        except Exception as exc:
            messagebox.showerror('Ã˜Â®Ã˜Â·Ã˜Â§Ã›Å’ benchmark', str(exc))

    def show_trace(self):
        rows = runtime.events.recent(30)
        text = '\n'.join(f"{e['time']} | {e['event']} | {e.get('data', {})}" for e in rows)
        messagebox.showinfo('Ã˜Â±Ã˜Â¯Ã›Å’Ã˜Â§Ã˜Â¨Ã›Å’ Ãšâ€ Ã˜Â±Ã˜Â®Ã™â€¡ Ã˜Â´Ã™â€ Ã˜Â§Ã˜Â®Ã˜ÂªÃ›Å’', text or 'Ã˜Â±Ã™Ë†Ã›Å’Ã˜Â¯Ã˜Â§Ã˜Â¯Ã›Å’ Ã˜Â«Ã˜Â¨Ã˜Âª Ã™â€ Ã˜Â´Ã˜Â¯Ã™â€¡ Ã˜Â§Ã˜Â³Ã˜Âª.')

    def show_memory(self):
        rows = runtime.memory.recent(12)
        text = 'Ã˜Â­Ã˜Â§Ã™ÂÃ˜Â¸Ã™â€¡ Ã˜Â®Ã˜Â§Ã™â€žÃ›Å’ Ã˜Â§Ã˜Â³Ã˜Âª.' if not rows else '\n\n'.join(f'[{k}] {c}' for k, c, _ in rows)
        messagebox.showinfo('Ã˜Â­Ã˜Â§Ã™ÂÃ˜Â¸Ã™â€¡ Ã˜Â§Ã˜Â®Ã›Å’Ã˜Â±', text)

    def clear_chat(self):
        self.chat.configure(state='normal')
        self.chat.delete('1.0', 'end')
        self.chat.configure(state='disabled')
        self.add_message('Ã˜Â§Ã›Å’Ã˜Â±Ã˜Â§Ã™â€ ', 'Ã˜ÂµÃ™ÂÃ˜Â­Ã™â€¡ ÃšÂ¯Ã™ÂÃ˜ÂªÃšÂ¯Ã™Ë† Ã™Â¾Ã˜Â§ÃšÂ© Ã˜Â´Ã˜Â¯Ã˜â€º Ã˜Â­Ã˜Â§Ã™ÂÃ˜Â¸Ã™â€¡ Ã™Ë† Ã›Å’Ã˜Â§Ã˜Â¯ÃšÂ¯Ã›Å’Ã˜Â±Ã›Å’ Ã˜Â­Ã˜Â°Ã™Â Ã™â€ Ã˜Â´Ã˜Â¯Ã™â€¡Ã¢â‚¬Å’Ã˜Â§Ã™â€ Ã˜Â¯.')

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
