import sys, json, threading
from datetime import datetime
from pathlib import Path
import sys
import threading
from PySide6.QtCore import QEvent, Qt, Signal, QObject
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
 QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
 QLabel, QPushButton, QLineEdit, QPlainTextEdit, QTextBrowser,
 QListWidget, QComboBox, QCheckBox, QSplitter, QMessageBox,
 QDialog, QDialogButtonBox, QScrollArea, QFrame, QSizePolicy, QTabWidget
)
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from runtime.app import IranRuntime

class Worker(QObject):
    done = Signal(str, float)
    fail = Signal(str)
    def __init__(self, runtime, text):
        super().__init__(); self.runtime = runtime; self.text = text
    def run(self):
        import time
        started = time.perf_counter()
        try:
            self.done.emit(str(self.runtime.handle(self.text)), time.perf_counter() - started)
        except Exception as e:
            self.fail.emit(f"خطا در پاسخ: {e}")

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ایران — معماری شناختی")
        self.resize(1440, 900)
        self.setLayoutDirection(Qt.RightToLeft)
        self.runtime = IranRuntime(ROOT)
        self.last_answer = ""; self.messages = []; self.busy = False
        self.build(); self.load_session()
    def build(self):
        root = QWidget(); self.setCentralWidget(root); outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 14); outer.setSpacing(10)
        top = QHBoxLayout()
        title = QLabel("ایران — معماری شناختی"); title.setObjectName("title")
        sub = QLabel("گفت‌وگوی فارسی، حافظه، استدلال و یادگیری کنترل‌شده"); sub.setObjectName("subtitle")
        self.status = QLabel("آماده")
        top.addWidget(title); top.addWidget(sub); top.addStretch(); top.addWidget(self.status); outer.addLayout(top)
        splitter = QSplitter(Qt.Horizontal); outer.addWidget(splitter, 1)
        splitter.addWidget(self.sidebar()); splitter.addWidget(self.chat_panel()); splitter.addWidget(self.rightbar())
        splitter.setSizes([260, 850, 330])
    def sidebar(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(7)
        l.addWidget(QLabel("گفت‌وگوها")); self.sessions = QListWidget()
        self.sessions.addItem("گفت‌وگوی فعلی"); l.addWidget(self.sessions, 1)
        self.newbtn = QPushButton("+ گفت‌وگوی جدید"); self.newbtn.clicked.connect(self.new_chat); l.addWidget(self.newbtn)
        self.clearbtn = QPushButton("پاک کردن گفت‌وگو"); self.clearbtn.clicked.connect(self.clear_display); l.addWidget(self.clearbtn)
        self.savebtn = QPushButton("ذخیره گفت‌وگو"); self.savebtn.clicked.connect(self.save_chat); l.addWidget(self.savebtn)
        l.addWidget(QLabel("حالت پاسخ")); self.mode = QComboBox()
        self.mode.addItems(["گفت‌وگوی عادی", "تحلیل عمیق", "پاسخ مستند"]); l.addWidget(self.mode)
        self.autocopy = QCheckBox("کپی خودکار پاسخ"); l.addWidget(self.autocopy); l.addStretch()
        l.addWidget(QLabel("Enter: ارسال  |  Shift+Enter: خط جدید")); return w
    def chat_panel(self):
        w = QWidget(); l = QVBoxLayout(w)
        searchbar = QHBoxLayout(); self.search = QLineEdit()
        self.search.setPlaceholderText("جست‌وجو در گفت‌وگو..."); self.search.returnPressed.connect(self.search_chat)
        searchbar.addWidget(self.search); q = QPushButton("جست‌وجو"); q.clicked.connect(self.search_chat); searchbar.addWidget(q); l.addLayout(searchbar)
        self.chat = QTextBrowser(); l.addWidget(self.chat, 1)
        bottom = QHBoxLayout(); self.input = QPlainTextEdit(); self.input.setPlaceholderText("پیام خود را اینجا بنویسید...")
        self.input.setFixedHeight(105); self.input.installEventFilter(self); bottom.addWidget(self.input, 1)
        actions = QVBoxLayout(); self.send = QPushButton("ارسال"); self.send.clicked.connect(self.send_message); actions.addWidget(self.send)
        self.copybtn = QPushButton("کپی پاسخ"); self.copybtn.clicked.connect(self.copy_response); actions.addWidget(self.copybtn)
        self.copysel = QPushButton("کپی انتخاب"); self.copysel.clicked.connect(self.copy_selection); actions.addWidget(self.copysel)
        self.attach = QPushButton("درج از کلیپ‌برد"); self.attach.clicked.connect(self.paste_clipboard); actions.addWidget(self.attach)
        bottom.addLayout(actions); l.addLayout(bottom); return w
    def rightbar(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(7); l.addWidget(QLabel("وضعیت شناختی"))
        self.conf = QLabel("اطمینان: —"); self.quality = QLabel("کیفیت: —"); self.intent = QLabel("هدف: —"); self.elapsed = QLabel("زمان: —"); self.experience_xp = QLabel("XP این نشست: ۱,۰۰۰,۰۰۰ | تجربه جدید: ۰")
        for x in (self.conf, self.quality, self.intent, self.elapsed, self.experience_xp): l.addWidget(x)
        l.addSpacing(8); l.addWidget(QLabel("رویدادهای اخیر")); self.events = QListWidget(); l.addWidget(self.events, 1)
        buttons = [("حافظه", self.show_memory), ("ردیابی پاسخ", self.show_trace),
                   ("بازبینی ChatGPT", self.show_chatgpt_reviews),
                   ("آزمون بنچمارک", self.run_benchmark), ("یادگیری جدید", self.propose_online_lesson),
                   ("تنظیمات", self.show_settings)]
        for text, fn in buttons:
            b = QPushButton(text); b.clicked.connect(fn); l.addWidget(b)
        return w
    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                self.send_message(); return True
        return super().eventFilter(obj, event)
    def add(self, who, text):
        text = str(text); safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        self.chat.append(f"<b>{who}</b><br>{safe}<br>")
        self.messages.append({"who": who, "text": text, "time": datetime.now().isoformat(timespec="seconds")})
        if who == "ایران": self.last_answer = text
        self.update_title_stats()
    def send_message(self):
        if self.busy: return
        text = self.input.toPlainText().strip()
        if not text: return
        self.input.clear(); self.add("شما", text); self.busy = True; self.send.setEnabled(False); self.status.setText("در حال پردازش...")
        self.worker = Worker(self.runtime, text); self.thread = threading.Thread(target=self.worker.run, daemon=True)
        self.worker.done.connect(self.on_done); self.worker.fail.connect(self.on_fail); self.thread.start()
    def on_done(self, text, elapsed):
        self.add("ایران", text); self.elapsed.setText(f"زمان: {elapsed:.3f} ثانیه")
        self.conf.setText("اطمینان: محاسبه شد"); self.quality.setText(f"کیفیت: {len(str(text))} نویسه")
        self.status.setText("آماده"); self.busy = False; self.send.setEnabled(True); self.refresh_events(); self.refresh_learning_stats(); self.persist_session()
        if self.autocopy.isChecked(): self.copy_response()
    def on_fail(self, text):
        self.add("خطا", text); self.status.setText("خطا"); self.busy = False; self.send.setEnabled(True); self.persist_session()
    def review_pending_learning(self):
        try:
            rows=self.runtime.learning_history(200)
        except Exception as e:
            QMessageBox.warning(self, "??????? ???????", f"???: {e}"); return
        pending=[r for r in rows if r.get("status")=="pending"]
        if not pending:
            QMessageBox.information(self, "??????? ???????", "??????? ??????? ?? ?????? ????? ???? ?????.")
            self.refresh_learning_stats(); return
        d=QDialog(self); d.setWindowTitle(f"??????? ? {len(pending)} ??????? ?? ?????? ?????"); d.resize(980,720); d.setLayoutDirection(Qt.RightToLeft)
        outer=QVBoxLayout(d); outer.addWidget(QLabel(f"????? ??????????: {len(pending)} | XP ?? ??????: {len(pending)*1_000_000:,}"))
        tabs=QTabWidget(); outer.addWidget(tabs,1)
        for index,row in enumerate(pending,1):
            page=QWidget(); l=QVBoxLayout(page)
            payload=row.get('payload',{}) or {}
            goal=str(payload.get('goal','????? ???? ????')); action=str(payload.get('action','')); result=str(payload.get('result','')); lesson=str(payload.get('lesson',''))
            l.addWidget(QLabel(f"??????? {index} ?? {len(pending)} | ?????: {row.get('proposal_id','')}"))
            box=QPlainTextEdit(); box.setReadOnly(True); box.setPlainText(f"?????:\n{goal}\n\n??? ?????????:\n{action}\n\n?????:\n{result}\n\n???? ??? ????? ???:\n{lesson}\n\n?????? ?????: {payload.get('score','?')}\nXP: 1,000,000"); l.addWidget(box,1)
            buttons=QHBoxLayout(); copy=QPushButton('??? ?????'); reject=QPushButton('?? ?????'); approve=QPushButton('????? ? ??????? ?,???,??? XP'); buttons.addWidget(copy); buttons.addWidget(reject); buttons.addWidget(approve); l.addLayout(buttons)
            copy.clicked.connect(lambda checked=False, text=box.toPlainText(): (QApplication.clipboard().setText(text), self.status.setText('????? ??? ??')))
            pid=row.get('proposal_id','')
            def do_approve(checked=False, proposal_id=pid, page=page):
                r=self.runtime.approve_learning(proposal_id)
                if not r.get('ok'):
                    QMessageBox.warning(d,'????? ???',str(r)); return
                self.status.setText('??????? ????? ?? ? ?,???,??? XP ??? ??'); self.refresh_learning_stats(); self.refresh_events(); tabs.removeTab(tabs.indexOf(page))
                if tabs.count()==0: d.accept()
            def do_reject(checked=False, proposal_id=pid, page=page):
                r=self.runtime.reject_learning(proposal_id)
                if not r.get('ok'):
                    QMessageBox.warning(d,'?? ???',str(r)); return
                self.status.setText('??????? ?? ?? ? ????? ???'); self.refresh_learning_stats(); self.refresh_events(); tabs.removeTab(tabs.indexOf(page))
                if tabs.count()==0: d.reject()
            approve.clicked.connect(do_approve); reject.clicked.connect(do_reject); tabs.addTab(page,f'??????? {index}')
        close=QPushButton('????'); close.clicked.connect(d.reject); outer.addWidget(close); d.exec()

    def show_chatgpt_reviews(self):
        # The current IRAN build is offline-only: do not create an external API path.
        path=ROOT/'data'/'chatgpt_reviews.json'
        rows=[]
        try:
            if path.exists():
                rows=json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            QMessageBox.warning(self,'??????? ChatGPT',f'??? ?? ?????? ????? ????: {e}'); return
        if not rows:
            QMessageBox.information(self,'??????? ChatGPT','????? ??????? ChatGPT ?? ??? ???? ???? ???? ???.\n\n????? ?????? ChatGPT ?? ???? ?????? ???? ???? ???.')
            return
        d=QDialog(self); d.setWindowTitle(f'??????? ChatGPT ? {len(rows)} ???? ????'); d.resize(980,720); d.setLayoutDirection(Qt.RightToLeft)
        l=QVBoxLayout(d); l.addWidget(QLabel('??? ????? ??? ????? ???? ?? ????? ??????? ??? ????? ?????? ?? ????? ????? ???????.'))
        tabs=QTabWidget(); l.addWidget(tabs,1)
        for i,row in enumerate(rows,1):
            page=QWidget(); pl=QVBoxLayout(page); q=QPlainTextEdit(); q.setReadOnly(True); q.setPlainText('????:\n'+str(row.get('question',''))+'\n\n???? ???????:\n'+str(row.get('answer',''))); pl.addWidget(q,1); cp=QPushButton('??? ????'); cp.clicked.connect(lambda checked=False, a=str(row.get('answer','')): QApplication.clipboard().setText(a)); pl.addWidget(cp); tabs.addTab(page,f'???? {i}')
        close=QPushButton('????'); close.clicked.connect(d.accept); l.addWidget(close); d.exec()

    def paste_clipboard(self):
        self.input.insertPlainText(QApplication.clipboard().text()); self.input.setFocus()
    def copy_response(self):
        if self.last_answer.strip(): QApplication.clipboard().setText(self.last_answer.strip()); self.status.setText("پاسخ کپی شد")
    def copy_selection(self):
        text = self.chat.textCursor().selectedText().strip()
        if text: QApplication.clipboard().setText(text); self.status.setText("متن انتخاب‌شده کپی شد")
        else: self.status.setText("متنی انتخاب نشده است")
    def update_title_stats(self): self.setWindowTitle(f"ایران — معماری شناختی | {len(self.messages)} پیام")
    def persist_session(self):
        try: (ROOT / "logs" / "current_session.json").write_text(json.dumps(self.messages, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception: pass
    def load_session(self):
        try:
            p = ROOT / "logs" / "current_session.json"
            if p.exists():
                self.messages = json.loads(p.read_text(encoding="utf-8"))
                for m in self.messages:
                    safe = str(m.get("text", "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                    self.chat.append(f"<b>{m.get('who','')}</b><br>{safe}<br>")
                for m in reversed(self.messages):
                    if m.get("who") == "ایران": self.last_answer = str(m.get("text", "")); break
        except Exception: pass
        self.update_title_stats(); self.refresh_learning_stats()
    def clear_display(self):
        self.chat.clear(); self.last_answer = ""; self.messages = []; self.update_title_stats(); self.persist_session(); self.status.setText("گفت‌وگو پاک شد")
    def new_chat(self):
        self.clear_display(); self.sessions.addItem(datetime.now().strftime("گفت‌وگو %Y-%m-%d %H:%M:%S")); self.sessions.setCurrentRow(self.sessions.count() - 1)
    def search_chat(self):
        q = self.search.text().strip()
        if q: self.chat.find(q); self.status.setText(f"نتایج جست‌وجو: {self.chat.toPlainText().lower().count(q.lower())}")
    def save_chat(self):
        d = ROOT / "logs"; d.mkdir(exist_ok=True); p = d / f"conversation_{datetime.now():%Y%m%d_%H%M%S}.txt"
        p.write_text(self.chat.toPlainText(), encoding="utf-8"); self.status.setText(f"ذخیره شد: {p.name}")
    def refresh_learning_stats(self):
        try:
            stats=self.runtime.learning.stats()
            self.experience_xp.setText(f"XP این نشست: {stats.get('session_xp',1_000_000):,} | تجربه جدید: {stats.get('session_experiences',0):,}")
        except Exception:
            self.experience_xp.setText("XP این نشست: ۱,۰۰۰,۰۰۰ | تجربه جدید: ۰")

    def refresh_events(self):
        try:
            self.events.clear()
            for e in self.runtime.events.recent(10): self.events.addItem(str(e))
        except Exception: pass
    def show_memory(self):
        try: text = "\n".join(map(str, self.runtime.memory.recent(30))) or "حافظه‌ای برای نمایش نیست"
        except Exception as e: text = f"خطا: {e}"
        QMessageBox.information(self, "حافظه", text)
    def show_trace(self):
        try: text = "\n".join(map(str, self.runtime.events.recent(50))) or "ردیابی‌ای برای نمایش نیست"
        except Exception as e: text = f"خطا: {e}"
        QMessageBox.information(self, "ردیابی پاسخ", text)
    def run_benchmark(self):
        try: QMessageBox.information(self, "آزمون بنچمارک", str(self.runtime.roadmap_benchmark()))
        except Exception as e: QMessageBox.warning(self, "آزمون بنچمارک", f"خطا: {e}")
    def show_settings(self):
        d = QDialog(self); d.setWindowTitle("تنظیمات"); d.setLayoutDirection(Qt.RightToLeft); l = QVBoxLayout(d)
        l.addWidget(QLabel("هسته: IRAN Symbolic Core")); l.addWidget(QLabel("حالت: کاملاً محلی و نمادین"))
        l.addWidget(QLabel("یادگیری اینترنتی: فقط با تأیید کاربر"))
        z = QDialogButtonBox(QDialogButtonBox.Ok); z.accepted.connect(d.accept); l.addWidget(z); d.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setLayoutDirection(Qt.RightToLeft); app.setFont(QFont("Tahoma", 10))
    app.setStyleSheet("""
    QWidget { background:#10151d; color:#e5e7eb; font-family:'Tahoma','Segoe UI','Arial'; font-size:10pt; }
    QLineEdit,QPlainTextEdit,QTextBrowser,QListWidget,QComboBox { background:#171e28; border:1px solid #2d3745; border-radius:8px; padding:7px; }
    QPushButton { background:#202a38; border:1px solid #354255; border-radius:8px; padding:8px; }
    QPushButton:hover { background:#2a3748; }
    QFrame { background:#151c26; border:1px solid #303b4b; border-radius:10px; }
    #title { font-size:18pt; font-weight:700; }
    #subtitle { color:#94a3b8; }
    #learningHeader { font-size:17pt; font-weight:700; padding:4px; }
    #sourceLabel { font-weight:700; color:#cbd5e1; }
    """)
    window = ChatWindow(); window.show(); sys.exit(app.exec())
