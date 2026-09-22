import sys, json, threading, atexit
from datetime import datetime
try:
    import msvcrt
except ImportError:
    msvcrt = None
from pathlib import Path
import sys
import threading
from PySide6.QtCore import QEvent, Qt, Signal, QObject, QTimer, QThread
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
 QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
 QLabel, QPushButton, QLineEdit, QPlainTextEdit, QTextBrowser,
 QListWidget, QComboBox, QCheckBox, QSplitter, QMessageBox,
 QDialog, QDialogButtonBox, QScrollArea, QFrame, QSizePolicy, QTabWidget, QInputDialog
)
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from runtime.app import IranRuntime

_GUI_LOCK_HANDLE = None

def _acquire_gui_lock():
    global _GUI_LOCK_HANDLE
    if msvcrt is None:
        return True
    lock_path = ROOT / "data" / ".iran_gui.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return False
    _GUI_LOCK_HANDLE = handle
    def release():
        try:
            _GUI_LOCK_HANDLE.seek(0)
            msvcrt.locking(_GUI_LOCK_HANDLE.fileno(), msvcrt.LK_UNLCK, 1)
            _GUI_LOCK_HANDLE.close()
        except Exception:
            pass
    atexit.register(release)
    return True

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

class BackgroundJob(QObject):
    done = Signal(str, object)
    failed = Signal(str, str)
    ended = Signal()
    def __init__(self, name, operation):
        super().__init__(); self.name = name; self.operation = operation
    def run(self):
        try: self.done.emit(self.name, self.operation())
        except Exception as exc: self.failed.emit(self.name, type(exc).__name__)
        finally: self.ended.emit()

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ایران — معماری شناختی")
        self.resize(1440, 900)
        self.setLayoutDirection(Qt.RightToLeft)
        self.runtime = IranRuntime(ROOT)
        self.last_answer = ""; self.messages = []; self.busy = False
        self._jobs = {}
        self._job_callbacks = {}
        self._closing = False
        self.autonomy_busy = False
        self.chatgpt_review_busy = False
        self.build(); self.load_session()
        self.autonomy_timer = QTimer(self)
        self.autonomy_timer.timeout.connect(self.run_autonomous_learning)
        self.autonomy_timer.start(7000)
        self.chatgpt_review_timer = QTimer(self)
        self.chatgpt_review_timer.timeout.connect(self.run_chatgpt_review_once)
        self.chatgpt_review_timer.start(1000)
        QTimer.singleShot(1200, self.run_autonomous_learning)
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
        self.conf = QLabel("اطمینان: —"); self.quality = QLabel("کیفیت: —"); self.intent = QLabel("هدف: —"); self.elapsed = QLabel("زمان: —"); self.experience_xp = QLabel("XP تأییدشده: ۰")
        self.chatgpt_pending = QLabel("درخواست‌های بازبینی ناظر: ۰")
        for x in (self.conf, self.quality, self.intent, self.elapsed, self.experience_xp, self.chatgpt_pending): l.addWidget(x)
        self.internet_button = QPushButton()
        self.internet_button.clicked.connect(self.toggle_internet)
        l.addWidget(self.internet_button); self.refresh_internet()
        l.addSpacing(8); l.addWidget(QLabel("آخرین رویدادها")); self.events = QListWidget(); l.addWidget(self.events, 1)
        buttons = [("حافظه", self.show_memory), ("ردیابی پاسخ", self.show_trace),
                   ("وضعیت ناظر آنلاین", self.show_chatgpt_reviews),
                   ("آزمون بنچمارک", self.run_benchmark), ("بازبینی یادگیری", self.review_pending_learning),
                   ("درس‌های یادگرفته‌شده", self.show_learned_lessons),
                   ("تایید همه یادگیری‌ها", self.approve_all_learning_ui),
                   ("رد موارد صف یادگیری", self.clear_all_learning_ui),
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
        if self.busy or self._closing or "autonomy" in self._jobs: return
        text = self.input.toPlainText().strip()
        if not text: return
        self.input.clear(); self.add("شما", text); self.busy = True; self.send.setEnabled(False); self.status.setText("در حال پردازش...")
        self.thread = QThread(self)
        self.worker = Worker(self.runtime, text)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.done.connect(self.on_done)
        self.worker.fail.connect(self.on_fail)
        self.worker.done.connect(self._finish_worker)
        self.worker.fail.connect(self._finish_worker)
        self.thread.start()
    def on_done(self, text, elapsed):
        self.add("ایران", text); self.elapsed.setText(f"زمان: {elapsed:.3f} ثانیه")
        trace = self.runtime.cognitive_system.last_trace
        self.conf.setText(f"اطمینان: {trace.confidence:.0%}" if trace is not None else "اطمینان: —")
        self.quality.setText(f"بررسی پاسخ: {trace.verification_status}" if trace is not None else "بررسی پاسخ: —")
        self.status.setText("آماده"); self.busy = False; self.send.setEnabled(True); self.refresh_events(); self.refresh_learning_stats(); self.persist_session()
        if self.autocopy.isChecked(): self.copy_response()
        self.queue_chatgpt_review(text); self.refresh_chatgpt_count()
    def on_fail(self, text):
        self.add("خطا", text); self.status.setText("خطا"); self.busy = False; self.send.setEnabled(True); self.persist_session()

    def _start_job(self, name, operation, on_result=None):
        if self._closing or name in self._jobs: return False
        if on_result is not None: self._job_callbacks[name] = on_result
        thread = QThread(self); thread.setObjectName(name)
        worker = BackgroundJob(name, operation); worker.moveToThread(thread)
        self._jobs[name] = (thread, worker)
        thread.started.connect(worker.run)
        worker.done.connect(self._job_result, Qt.QueuedConnection)
        worker.failed.connect(self._job_error, Qt.QueuedConnection)
        worker.ended.connect(thread.quit)
        worker.ended.connect(worker.deleteLater)
        thread.finished.connect(self._job_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start(); return True

    def _job_result(self, name, result):
        callback = self._job_callbacks.pop(name, None)
        if callback is not None: callback(result)
        if name == "review":
            reason = result.get("reason", "")
            self.status.setText("ناظر: " + reason)
        elif name == "benchmark":
            self._dialog("نتیجه ارزیابی", str(result))
        self.refresh_chatgpt_count(); self.refresh_learning_stats(); self.refresh_events()

    def _job_error(self, name, reason):
        callback = self._job_callbacks.pop(name, None)
        if callback is not None: callback({"ok": False, "reason": reason})
        self.status.setText(f"خطا در {name}: {reason}")

    def _job_finished(self):
        name = self.sender().objectName()
        self._jobs.pop(name, None)
        if self._closing and not self._jobs and not self.busy:
            QTimer.singleShot(0, self.close)

    def run_chatgpt_review_once(self):
        self._start_job("review", self.runtime.process_one_chatgpt_learning_review)

    def refresh_internet(self):
        enabled = self.runtime.internet_access.status()["enabled"]
        self.internet_button.setText("اینترنت: روشن — خاموش کن" if enabled else "اینترنت: خاموش — روشن کن")

    def toggle_internet(self):
        access = self.runtime.internet_access
        try:
            access.disable() if access.status()["enabled"] else access.enable()
        except OSError as exc:
            self.refresh_internet()
            self.status.setText(f"خطا در ذخیره تنظیم اینترنت؛ اتصال خاموش ماند: {exc}")
            return
        self.refresh_internet()
        self.run_chatgpt_review_once()

    def _dialog(self, title, text):
        d=QDialog(self); d.setWindowTitle(title); d.resize(850,550)
        layout=QVBoxLayout(d); view=QPlainTextEdit(); view.setReadOnly(True)
        view.setPlainText(text); layout.addWidget(view)
        button=QPushButton("بستن");button.clicked.connect(d.accept);layout.addWidget(button)
        d.exec()

    def _finish_worker(self, *args):
        thread = self.thread
        worker = self.worker
        worker.deleteLater()
        thread.quit()
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._chat_finished)

    def _chat_finished(self):
        if self._closing and not self._jobs: QTimer.singleShot(0, self.close)

    def approve_all_learning_ui(self):
        try:
            stats = self.runtime.learning_status()
            pending = int(stats.get("pending", 0))
            if pending == 0:
                QMessageBox.information(self, "یادگیری", "درخواستی برای تایید وجود ندارد.")
                return
            answer = QMessageBox.question(
                self, "تایید همه یادگیری‌ها",
                f"تعداد {pending:,} درخواست یادگیری در صف است. همه تایید شوند؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._start_job("approve_all", lambda: self.runtime.approve_all_learning(max(5000, pending)),
                            lambda result: self.status.setText(f"یادگیری‌های تأییدشده: {result.get('approved', 0)}"))
        except Exception as e:
            QMessageBox.warning(self, "خطا", str(e))

    def clear_all_learning_ui(self):
        answer = QMessageBox.question(
            self, "حذف کامل صف یادگیری",
            "همه درخواست‌های در انتظار رد و از صف فعال خارج شوند؟\n\n"
            "موارد ردشده حفظ می‌شوند. تاریخچه برای جلوگیری از یادگیری تکراری حفظ می‌شود.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            def reject_pending():
                pending = self.runtime.learning_pending(100000)
                count = sum(bool(self.runtime.reject_learning(r["proposal_id"]).get("ok")) for r in pending)
                return {"rejected": count}
            self._start_job("reject_all", reject_pending,
                            lambda result: self.status.setText(f"درخواست‌های ردشده: {result.get('rejected', 0)}"))
        except Exception as e:
            QMessageBox.warning(self, "خطا در پاک‌سازی", str(e))

    def review_pending_learning(self):
        """نمایش همه درخواست‌های یادگیری در انتظار تأیید."""
        try:
            rows = self.runtime.human_learning_pending(50)
        except Exception as e:
            QMessageBox.warning(self, "بازبینی یادگیری", f"خطا: {e}")
            return
        if not rows:
            stats = self.runtime.learning_status()
            QMessageBox.information(self, "بازبینی یادگیری", f"درخواست در انتظار تأیید وجود ندارد.\n\nکل درخواست‌ها: {stats.get('total', 0):,}\nتأییدشده: {stats.get('approved', 0):,}\nردشده: {stats.get('rejected', 0):,}\nXP کل: {stats.get('xp', 0):,}")
            self.refresh_learning_stats()
            return
        d = QDialog(self)
        d.setWindowTitle(f"بازبینی یادگیری — {len(rows)} درخواست")
        d.resize(980, 720)
        d.setLayoutDirection(Qt.RightToLeft)
        outer = QVBoxLayout(d)
        outer.addWidget(QLabel(f"درخواست‌های در انتظار: {len(rows):,} | XP پس از ارزیابی اثر ثبت می‌شود"))
        tabs = QTabWidget()
        outer.addWidget(tabs, 1)
        for index, row in enumerate(rows, 1):
            page = QWidget()
            l = QVBoxLayout(page)
            payload = row.get("payload", {}) or {}
            goal = str(payload.get("goal", row.get("summary", "هدف مشخص نشده")))
            action = str(payload.get("action", ""))
            result = str(payload.get("result", ""))
            lesson = str(payload.get("lesson", ""))
            kind = str(row.get("kind", ""))
            proposal_id = str(row.get("proposal_id", ""))
            review = self.runtime.chatgpt_learning_review_status(proposal_id).get("row", {})
            try:
                chatgpt = json.loads(str(review.get("review", "{}")))
            except Exception:
                chatgpt = {}
            l.addWidget(QLabel(f"درخواست {index} از {len(rows)} | نوع: {kind} | شناسه: {proposal_id}"))
            box = QPlainTextEdit()
            box.setReadOnly(True)
            box.setPlainText(
                f"هدف:\n{goal}\n\nعمل انجام‌شده:\n{action}\n\nنتیجه:\n{result}\n\nدرس استخراج‌شده:\n{lesson}\n\n"
                f"نظر ناظر: {chatgpt.get('answer', '')}\n"
                f"دلیل ناظر: {chatgpt.get('reason', '')}\n"
                f"اصلاحات پیشنهادی: {chatgpt.get('corrections', [])}\n"
                f"اعتماد ناظر: {chatgpt.get('confidence', '?')}\n"
                f"وضعیت ناظر: {'تأیید شده — منتظر تأیید شما' if review.get('chatgpt_decision') == 'learn' else 'رد شده توسط ناظر'}\n"
                f"زمان بررسی: {review.get('reviewed_at', '—')}\n"
                f"منبع: {review.get('source', 'learning_gate')}\n\n"
                f"امتیاز: {payload.get('score', '?')}\nمحتوای کامل و منابع:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
            )
            l.addWidget(box, 1)
            buttons = QHBoxLayout()
            copy = QPushButton("کپی درخواست")
            reject = QPushButton("رد کردن")
            approve = QPushButton("تأیید یادگیری")
            next_item = QPushButton("مورد بعدی")
            buttons.addWidget(copy); buttons.addWidget(reject); buttons.addWidget(approve); buttons.addWidget(next_item); l.addLayout(buttons)
            copy.clicked.connect(lambda checked=False, text=box.toPlainText(): (QApplication.clipboard().setText(text), self.status.setText("درخواست کپی شد")))
            pid = proposal_id
            def finish_decision(result, page=page, approve=approve, reject=reject):
                approve.setEnabled(True); reject.setEnabled(True)
                if not result.get("ok"):
                    self.status.setText("ثبت تصمیم ناموفق: " + str(result.get("reason", "unknown")))
                    return
                self.status.setText("تصمیم ثبت شد؛ XP فقط پس از ارزیابی اثر ثبت می‌شود")
                tab_index = tabs.indexOf(page)
                if tab_index >= 0: tabs.removeTab(tab_index)
                if tabs.count() == 0: d.accept()
            def do_approve(checked=False, proposal_id=pid, approve=approve, reject=reject, finish=finish_decision):
                if self._start_job("decision:" + proposal_id,
                                   lambda: self.runtime.approve_learning(proposal_id), finish):
                    approve.setEnabled(False); reject.setEnabled(False)
            def do_reject(checked=False, proposal_id=pid, approve=approve, reject=reject, finish=finish_decision):
                if self._start_job("decision:" + proposal_id,
                                   lambda: self.runtime.reject_learning(proposal_id), finish):
                    approve.setEnabled(False); reject.setEnabled(False)
            approve.clicked.connect(do_approve); reject.clicked.connect(do_reject)
            next_item.clicked.connect(lambda checked=False, index=index: tabs.setCurrentIndex(min(index, tabs.count() - 1)))
            tabs.addTab(page, f"درخواست {index}")
        close = QPushButton("بستن")
        close.clicked.connect(d.reject)
        outer.addWidget(close)
        d.exec()

    def show_learned_lessons(self):
        try:
            rows = self.runtime.learning.learned_lesson_rows(100)
        except Exception as e:
            QMessageBox.warning(self, "درس‌های یادگرفته‌شده", f"خطا: {e}")
            return
        d=QDialog(self); d.setWindowTitle(f"درس‌های یادگرفته‌شده — {len(rows)} مورد"); d.resize(1050,760); d.setLayoutDirection(Qt.RightToLeft)
        l=QVBoxLayout(d)
        l.addWidget(QLabel(f"درس‌های پایدار استخراج‌شده از تجربه‌های واقعی: {len(rows):,}"))
        box=QPlainTextEdit(); box.setReadOnly(True)
        if rows:
            blocks=[]
            for i,row in enumerate(rows,1):
                blocks.append(f"درس {i}\nموضوع: {row.get('goal','')}\nعمل: {row.get('action','')}\nامتیاز: {row.get('score','')} | تکرار/شواهد: {row.get('samples',1)}\n\n{row.get('lesson','')}")
            box.setPlainText("\n\n────────────────────\n\n".join(blocks))
        else:
            box.setPlainText("هنوز درس پایدار ثبت نشده است. ابتدا یک تجربه را تأیید کنید.")
        l.addWidget(box,1); close=QPushButton("بستن"); close.clicked.connect(d.accept); l.addWidget(close); d.exec()

    def queue_chatgpt_review(self, answer):
        try:
            self.runtime.sync_chatgpt_learning_reviews()
        except Exception as exc:
            self.status.setText(f"خطا در صف ناظر: {exc}")

    def refresh_chatgpt_count(self):
        try:
            status = self.runtime.chatgpt_review_status()
            if status.get("state") == "ERROR":
                self.chatgpt_pending.setText(f"ناظر: خطا در داده‌های ذخیره‌شده | {status.get('last_error', '')}")
            elif status.get("cooldown"):
                self.chatgpt_pending.setText(
                    f"ناظر: در انتظار / Rate Limit | صف: {status.get('pending', 0):,} | تلاش بعدی: {status.get('next_allowed_at', '—')}"
                )
            else:
                self.chatgpt_pending.setText(
                    f"درخواست‌های بازبینی ناظر: {status.get('pending', 0):,} | بازبینی انسانی: {status.get('human_pending', 0):,}"
                )
        except Exception:
            self.chatgpt_pending.setText("درخواست‌های بازبینی ناظر: خطا")

    def show_chatgpt_reviews(self):
        # Pending candidate content is private until the external review accepts it.
        try:
            status = self.runtime.chatgpt_review_status()
        except Exception as exc:
            self._dialog("وضعیت ناظر آنلاین", f"خطا در خواندن وضعیت ناظر: {exc}")
            return
        health = "\n".join(f"{p['provider']}: {p['state']} — {p['reason']}" for p in status.get("providers", []))
        self._dialog("وضعیت ناظر آنلاین", f"صف: {status.get('pending',0)}\nدر انتظار ناظر: {status.get('waiting',0)}\nآماده بازبینی شما: {status.get('human_pending',0)}\nآخرین خطا: {status.get('last_error') or '—'}\n\n{health}")

    def paste_clipboard(self):
        self.input.insertPlainText(QApplication.clipboard().text()); self.input.setFocus()
    def copy_response(self):
        if self.last_answer.strip(): QApplication.clipboard().setText(self.last_answer.strip()); self.status.setText("پاسخ کپی شد")
    def copy_selection(self):
        text = self.chat.textCursor().selectedText().strip()
        if text: QApplication.clipboard().setText(text); self.status.setText("متن انتخاب‌شده کپی شد")
        else: self.status.setText("متنی انتخاب نشده است")
    def update_title_stats(self): self.setWindowTitle(f"ایران — معماری شناختی | {len(self.messages)} پیام")
    def closeEvent(self, event):
        self._closing = True
        self.autonomy_timer.stop(); self.chatgpt_review_timer.stop()
        if self._jobs or self.busy:
            self.status.setText("در انتظار پایان عملیات برای بستن امن…")
            event.ignore(); return
        self.persist_session(); self.runtime.close(); event.accept()

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
        self.update_title_stats(); self.refresh_learning_stats(); self.refresh_chatgpt_count()
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
    def run_autonomous_learning(self):
        if self.busy or self._jobs: return
        self._start_job("autonomy", self.runtime.maintenance_step)

    def queue_autonomous_review(self, request):
        self.runtime.sync_chatgpt_learning_reviews()
        self.refresh_chatgpt_count()

    def refresh_learning_stats(self):
        try:
            stats = self.runtime.learning_status()
            self.experience_xp.setText(
                f"درخواست: {stats.get('total', 0):,} | در انتظار: {stats.get('pending', 0):,} | "
                f"تأیید: {stats.get('approved', 0):,} | رد: {stats.get('rejected', 0):,} | "
                f"XP کل: {stats.get('xp', 0):,} | انتقال: {stats.get('transfer_passed', 0):,}/{stats.get('transfer_total', 0):,} | "
                f"بهبود: {stats.get('improved_cases', 0):,}/{stats.get('improvement_cases', 0):,} | "
                f"میانگین بهبود: {stats.get('mean_improvement', 0):.3f} | "
                f"یادگیری اثرگذار: {stats.get('effect_validated', 0):,} | "
                f"درس‌های واقعی: {stats.get('verified_lessons', 0):,} | "
                f"قواعد یادگرفته‌شده: {len(getattr(self.runtime.learning, 'learned_rules', []) or []):,}"
            )
        except Exception as e:
            self.experience_xp.setText(f"یادگیری: خطا در دریافت وضعیت — {e}")

    def refresh_events(self):
        try:
            self.events.clear()
            event_names = {
                "runtime_ready": "آماده‌سازی هسته", "language_analysis": "تحلیل زبان",
                "cognitive_cycle": "چرخه شناختی", "plan_created": "ساخت برنامه",
                "reflection": "بازتاب", "learning_update": "به‌روزرسانی یادگیری",
                "response_generated": "تولید پاسخ", "canonical_cognitive_turn": "نوبت شناختی اصلی",
                "learning_goal_created": "ایجاد هدف یادگیری", "self_correction_snapshot": "وضعیت خوداصلاحی"
            }
            for e in self.runtime.events.recent(10):
                event = event_names.get(str(e.get("event", "")), str(e.get("event", "رویداد")))
                stage = str(e.get("stage", "—")); status = str(e.get("status", "—"))
                status_fa = {"completed": "تکمیل شد", "failed": "ناموفق", "running": "در حال اجرا"}.get(status, status)
                self.events.addItem(f"{event} | مرحله: {stage} | وضعیت: {status_fa}")
        except Exception: pass
    def show_memory(self):
        try: text = "\n".join(map(str, self.runtime.memory.recent(30))) or "حافظه‌ای برای نمایش نیست"
        except Exception as e: text = f"خطا: {e}"
        QMessageBox.information(self, "حافظه", text)
    def show_trace(self):
        try:
            rows = self.runtime.events.recent(50)
            if not rows:
                text = "ردیابی‌ای برای نمایش نیست"
            else:
                labels = {
                    "time": "زمان", "event": "رویداد", "turn_id": "شناسه نوبت",
                    "stage": "مرحله", "status": "وضعیت", "duration_ms": "مدت (میلی‌ثانیه)",
                    "data": "جزئیات", "intent": "هدف/نیت", "confidence": "اطمینان",
                    "goal": "هدف", "topic": "موضوع", "reference": "مرجع",
                    "reasoning_status": "وضعیت استدلال", "answer_status": "وضعیت پاسخ",
                    "verification_status": "وضعیت راستی‌آزمایی", "verification_reasons": "دلایل راستی‌آزمایی",
                    "memory_count": "تعداد حافظه", "knowledge_count": "تعداد دانش",
                    "elapsed_ms": "زمان پردازش", "verified": "تأییدشده", "score": "امتیاز",
                    "route": "مسیر پاسخ", "mode": "حالت پاسخ", "canonical": "مسیر اصلی"
                }
                def render(value, level=0):
                    if isinstance(value, dict):
                        return "\n".join(f"{labels.get(str(k), str(k))}: {render(v, level + 1)}" for k, v in value.items())
                    if isinstance(value, list):
                        return " | ".join(render(v, level + 1) for v in value)
                    if isinstance(value, bool):
                        return "بله" if value else "خیر"
                    return str(value)
                blocks = []
                for i, row in enumerate(rows, 1):
                    blocks.append(f"ردیابی {i}\n{render(row)}")
                text = "\n\n────────────────────\n\n".join(blocks)
        except Exception as e:
            text = f"خطا در ردیابی پاسخ: {e}"
        d = QDialog(self); d.setWindowTitle("ردیابی پاسخ"); d.resize(1000, 720); d.setLayoutDirection(Qt.RightToLeft)
        l = QVBoxLayout(d); box = QPlainTextEdit(); box.setReadOnly(True); box.setPlainText(text); l.addWidget(box, 1)
        close = QPushButton("بستن"); close.clicked.connect(d.accept); l.addWidget(close); d.exec()
    def run_benchmark(self):
        if not self.busy and not self._jobs:
            self._start_job("benchmark", self.runtime.roadmap_benchmark)
    def show_settings(self):
        d = QDialog(self); d.setWindowTitle("تنظیمات"); d.setLayoutDirection(Qt.RightToLeft); l = QVBoxLayout(d)
        l.addWidget(QLabel("هسته: IRAN Symbolic Core")); l.addWidget(QLabel("حالت: کاملاً محلی و نمادین"))
        l.addWidget(QLabel("یادگیری اینترنتی: فقط با تأیید کاربر"))
        z = QDialogButtonBox(QDialogButtonBox.Ok); z.accepted.connect(d.accept); l.addWidget(z); d.exec()

if __name__ == "__main__":
    if not _acquire_gui_lock():
        sys.exit(0)
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
