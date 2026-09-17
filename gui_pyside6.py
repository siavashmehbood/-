# -*- coding: utf-8 -*-
import sys, threading, json
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QObject, QEvent, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QPlainTextEdit,QTextBrowser,QListWidget,QComboBox,QCheckBox,QSplitter,QMessageBox,QDialog,QFormLayout,QDialogButtonBox)
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from runtime.app import IranRuntime

class Worker(QObject):
 done=Signal(str,float); fail=Signal(str)
 def __init__(self,r,t): super().__init__(); self.r=r; self.t=t
 def run(self):
  import time; started=time.perf_counter()
  try: self.done.emit(str(self.r.handle(self.t)),time.perf_counter()-started)
  except Exception as e: self.fail.emit(f'خطا در پردازش: {e}')

class ChatWindow(QMainWindow):
 def __init__(self):
  super().__init__(); self.setWindowTitle('ایران — میزکار شناختی'); self.resize(1440,900)
  self.setLayoutDirection(Qt.RightToLeft); self.runtime=IranRuntime(ROOT)
  self.last_answer=''; self.messages=[]; self.busy=False; self.build(); self.load_session()
  QTimer.singleShot(700, self.propose_online_lesson)
 def build(self):
  root=QWidget(); self.setCentralWidget(root); o=QVBoxLayout(root); o.setContentsMargins(14,14,14,14)
  top=QHBoxLayout(); t=QLabel('ایران — میزکار شناختی'); t.setObjectName('title'); s=QLabel('گفت‌وگوی محلی، حافظه، ردیابی و ارزیابی شناختی'); s.setObjectName('subtitle')
  top.addWidget(t); top.addStretch(); top.addWidget(s); o.addLayout(top)
  sp=QSplitter(Qt.Horizontal); o.addWidget(sp,1); sp.addWidget(self.sidebar()); sp.addWidget(self.chat_panel()); sp.addWidget(self.rightbar()); sp.setSizes([250,820,300])
  self.status=QLabel('آماده'); self.status.setObjectName('status'); o.addWidget(self.status); self.update_title_stats()
 def sidebar(self):
  w=QWidget(); l=QVBoxLayout(w); l.addWidget(QLabel('گفت‌وگوها')); self.sessions=QListWidget(); self.sessions.addItem('گفت‌وگوی فعلی'); l.addWidget(self.sessions,1)
  self.newbtn=QPushButton('＋ گفت‌وگوی جدید'); self.newbtn.clicked.connect(self.new_chat); l.addWidget(self.newbtn)
  self.clearbtn=QPushButton('پاک‌کردن نمایش'); self.clearbtn.clicked.connect(self.clear_display); l.addWidget(self.clearbtn)
  self.savebtn=QPushButton('ذخیره گفت‌وگو'); self.savebtn.clicked.connect(self.save_chat); l.addWidget(self.savebtn)
  l.addWidget(QLabel('حالت پاسخ')); self.mode=QComboBox(); self.mode.addItems(['خودکار','تحلیل عمیق','پاسخ کوتاه']); l.addWidget(self.mode)
  self.autocopy=QCheckBox('کپی خودکار پاسخ'); l.addWidget(self.autocopy); l.addStretch(); l.addWidget(QLabel('Ctrl+L ورودی  |  Enter ارسال  |  Shift+Enter خط جدید'))
  return w
 def chat_panel(self):
  w=QWidget(); l=QVBoxLayout(w); b=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText('جست‌وجو در گفت‌وگو...'); self.search.returnPressed.connect(self.search_chat); b.addWidget(self.search)
  q=QPushButton('جست‌وجو'); q.clicked.connect(self.search_chat); b.addWidget(q); l.addLayout(b); self.chat=QTextBrowser(); l.addWidget(self.chat,1)
  bot=QHBoxLayout(); self.input=QPlainTextEdit(); self.input.setPlaceholderText('پیام خود را اینجا بنویسید...'); self.input.setFixedHeight(105); self.input.installEventFilter(self); bot.addWidget(self.input,1)
  c=QVBoxLayout(); self.send=QPushButton('ارسال'); self.send.clicked.connect(self.send_message); c.addWidget(self.send); self.copybtn=QPushButton('کپی پاسخ'); self.copybtn.clicked.connect(self.copy_response); c.addWidget(self.copybtn); self.copysel=QPushButton('کپی انتخاب'); self.copysel.clicked.connect(self.copy_selection); c.addWidget(self.copysel); self.attach=QPushButton('چسباندن'); self.attach.clicked.connect(self.paste_clipboard); c.addWidget(self.attach); bot.addLayout(c); l.addLayout(bot); return w
 def rightbar(self):
  w=QWidget(); l=QVBoxLayout(w); l.addWidget(QLabel('وضعیت شناختی')); self.conf=QLabel('اعتماد: —'); self.quality=QLabel('کیفیت: —'); self.intent=QLabel('قصد: —'); self.elapsed=QLabel('زمان: —')
  for x in (self.conf,self.quality,self.intent,self.elapsed): l.addWidget(x)
  l.addSpacing(10); l.addWidget(QLabel('رویدادهای اخیر')); self.events=QListWidget(); l.addWidget(self.events,1)
  for text,fn in [('حافظه',self.show_memory),('ردیابی',self.show_trace),('Benchmark',self.run_benchmark),('تنظیمات',self.show_settings)]: q=QPushButton(text); q.clicked.connect(fn); l.addWidget(q)
  return w
 def eventFilter(self,obj,e):
  if obj is self.input and e.type()==QEvent.Type.KeyPress:
   if e.key() in (Qt.Key_Return,Qt.Key_Enter) and not(e.modifiers()&Qt.ShiftModifier): self.send_message(); return True
   if e.modifiers()&Qt.ControlModifier and e.key()==Qt.Key_L: self.input.setFocus(); return True
   if e.modifiers()==(Qt.ControlModifier|Qt.ShiftModifier) and e.key()==Qt.Key_C: self.copy_response(); return True
   if e.modifiers()==(Qt.ControlModifier|Qt.ShiftModifier) and e.key()==Qt.Key_S: self.save_chat(); return True
  return super().eventFilter(obj,e)
 def add(self,who,text):
  text=str(text); safe=text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br>'); self.chat.append(f'<b>{who}</b><br>{safe}<br>')
  self.messages.append({'who':str(who),'text':text,'time':datetime.now().isoformat(timespec='seconds')});
  if who=='ایران': self.last_answer=text
  self.update_title_stats()
 def send_message(self):
  if self.busy:return
  text=self.input.toPlainText().strip()
  if not text:return
  self.input.clear(); self.add('شما',text); self.busy=True; self.send.setEnabled(False); self.status.setText('در حال پردازش...')
  self.worker=Worker(self.runtime,text); self.thread=threading.Thread(target=self.worker.run,daemon=True); self.worker.done.connect(self.on_done); self.worker.fail.connect(self.on_fail); self.thread.start()
 def on_done(self,text,elapsed):
  self.add('ایران',text); self.elapsed.setText(f'زمان: {elapsed:.3f} ثانیه'); self.conf.setText('اعتماد: محلی'); self.quality.setText(f'حجم پاسخ: {len(str(text))} نویسه'); self.status.setText('آماده'); self.busy=False; self.send.setEnabled(True); self.refresh_events(); self.persist_session(); self.copy_response() if self.autocopy.isChecked() else None
 def on_fail(self,text): self.add('سیستم',text); self.status.setText('خطا'); self.busy=False; self.send.setEnabled(True); self.persist_session()
 def propose_online_lesson(self):
  if not self.runtime.online_learning.enabled: return
  result=self.runtime.propose_online_lesson()
  lessons=result.get('learned') or []
  if not lessons:
   self.status.setText('یادگیری اینترنتی: مورد تازه‌ای برای پیشنهاد پیدا نشد'); return
  proposal=result.get('proposal')
  if not proposal: return
  sources=proposal.get('sources',[])
  source_lines=[]
  for i,src in enumerate(sources,1):
   source_lines.append(f"{i}) {src.get('source','')} — اعتماد {float(src.get('trust',0)):.0%}\n   {src.get('evidence','')[:700]}")
  agreements='، '.join(proposal.get('agreements',[])[:10]) or 'همپوشانی معنادار کافی پیدا نشد'
  conflicts=proposal.get('conflicts',[])
  conflict_text=(f"هشدار: {len(conflicts)} اختلاف/همپوشانی ضعیف بین منابع شناسایی شد." if conflicts else 'تعارض آشکار در شواهد شناسایی نشد.')
  box=QMessageBox(self); box.setWindowTitle('پیشنهاد دانش چندمنبعی — تأیید شما')
  box.setIcon(QMessageBox.Information)
  box.setText('ایران چند منبع را بررسی کرده و یک پیشنهاد واحد ساخته است.')
  box.setInformativeText(
   f"موضوع: {proposal.get('query','')}\nاعتماد ترکیبی: {float(proposal.get('confidence',0)):.0%}\n"
   f"توافق‌های استخراج‌شده: {agreements}\n\n{proposal.get('summary','')[:1800]}\n\nمنابع بررسی‌شده:\n"+'\n'.join(source_lines)+f"\n\n{conflict_text}")
  box.setDetailedText('این پیشنهاد هنوز وارد حافظه نشده است.\nبا تأیید شما، متن کامل هر منبعِ مورد اعتماد با شناسه پیشنهاد و میزان ارتباط آن ذخیره می‌شود.\nرد کردن، هیچ‌یک از منابع را ذخیره نمی‌کند.\nمحتوای وب هرگز به‌عنوان دستور اجرا نمی‌شود.')
  yes=box.addButton('تأیید پیشنهاد؛ اضافه کن', QMessageBox.AcceptRole)
  no=box.addButton('رد پیشنهاد؛ اضافه نکن', QMessageBox.RejectRole)
  box.exec()
  if box.clickedButton() is yes:
   self.runtime.approve_online_proposal(proposal)
   self.status.setText(f"پیشنهاد تأیید شد؛ {len(sources)} منبع با provenance ذخیره شد")
   self.events.addItem(f"پیشنهاد دانش تأیید شد: {proposal.get('title','')}")
  else:
   self.runtime.reject_online_proposal(proposal)
   self.status.setText('پیشنهاد چندمنبعی رد شد و چیزی ذخیره نشد')
   self.events.addItem(f"پیشنهاد دانش رد شد: {proposal.get('title','')}")

 def paste_clipboard(self): self.input.insertPlainText(QApplication.clipboard().text()); self.input.setFocus()
 def copy_response(self):
  if self.last_answer.strip(): QApplication.clipboard().setText(self.last_answer.strip()); self.status.setText('آخرین پاسخ کپی شد')
 def copy_selection(self):
  text=self.chat.textCursor().selectedText().strip()
  if text: QApplication.clipboard().setText(text); self.status.setText('بخش انتخاب‌شده کپی شد')
  else: self.status.setText('ابتدا بخشی از متن را انتخاب کنید')
 def update_title_stats(self): self.setWindowTitle(f'ایران — میزکار شناختی | {len(self.messages)} پیام')
 def persist_session(self):
  try:
   d=ROOT/'logs'; d.mkdir(exist_ok=True); (d/'current_session.json').write_text(json.dumps(self.messages,ensure_ascii=False,indent=2),encoding='utf-8')
  except Exception: pass
 def load_session(self):
  p=ROOT/'logs'/'current_session.json'
  try:
   if p.exists():
    data=json.loads(p.read_text(encoding='utf-8')); self.messages=list(data); self.chat.clear()
    for m in self.messages:
     safe=str(m.get('text','')).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br>'); self.chat.append(f"<b>{m.get('who','')}</b><br>{safe}<br>")
    for m in reversed(self.messages):
     if m.get('who')=='ایران': self.last_answer=str(m.get('text','')); break
    self.update_title_stats()
  except Exception: pass
 def clear_display(self): self.chat.clear(); self.last_answer=''; self.messages=[]; self.update_title_stats(); self.persist_session(); self.status.setText('نمایش پاک شد')
 def new_chat(self): self.clear_display(); self.sessions.addItem(datetime.now().strftime('گفت‌وگو %Y-%m-%d %H:%M:%S')); self.sessions.setCurrentRow(self.sessions.count()-1)
 def search_chat(self):
  q=self.search.text().strip()
  if q: self.chat.find(q); self.status.setText(f'تعداد نتیجه: {self.chat.toPlainText().lower().count(q.lower())}')
 def save_chat(self):
  d=ROOT/'logs'; d.mkdir(exist_ok=True); p=d/f'conversation_{datetime.now():%Y%m%d_%H%M%S}.txt'; p.write_text(self.chat.toPlainText(),encoding='utf-8'); self.persist_session(); self.status.setText(f'ذخیره شد: {p.name}')
 def refresh_events(self):
  try:
   self.events.clear()
   for e in self.runtime.events.recent(10): self.events.addItem(str(e))
  except Exception: pass
 def show_memory(self):
  try:text='\n'.join(map(str,self.runtime.memory.recent(30))) or 'حافظه محلی خالی است.'
  except Exception as e:text=f'خطا: {e}'
  QMessageBox.information(self,'حافظه',text)
 def show_trace(self):
  try:text='\n'.join(map(str,self.runtime.events.recent(50))) or 'ردیابی خالی است.'
  except Exception as e:text=f'خطا: {e}'
  QMessageBox.information(self,'ردیابی شناختی',text)
 def run_benchmark(self):
  try:QMessageBox.information(self,'Benchmark',str(self.runtime.roadmap_benchmark()))
  except Exception as e:QMessageBox.warning(self,'Benchmark',f'خطا: {e}')
 def show_settings(self):
  d=QDialog(self); d.setWindowTitle('تنظیمات'); f=QFormLayout(d); f.addRow('محیط اجرا:','کاملاً محلی / بدون API ابری'); f.addRow('فونت ترجیحی:','IranSans (در صورت نصب) + Tahoma + Segoe UI'); f.addRow('رابط راست‌به‌چپ:','فعال'); z=QDialogButtonBox(QDialogButtonBox.Ok); z.accepted.connect(d.accept); f.addRow(z); d.exec()

if __name__=='__main__':
 app=QApplication(sys.argv); app.setLayoutDirection(Qt.RightToLeft); app.setFont(QFont('IranSans',10)); app.setStyleSheet("QWidget{background:#10151d;color:#e5e7eb;font-family:'IranSans','Tahoma','Segoe UI','Arial';font-size:10pt} QLineEdit,QPlainTextEdit,QTextBrowser,QListWidget,QComboBox{background:#171e28;border:1px solid #2d3745;border-radius:8px;padding:7px} QPushButton{background:#202a38;border:1px solid #354255;border-radius:8px;padding:8px} QPushButton:hover{background:#2a3748} #title{font-size:18pt;font-weight:700} #subtitle{color:#94a3b8} #status{color:#94a3b8;padding:4px}"); w=ChatWindow(); w.show(); sys.exit(app.exec())
