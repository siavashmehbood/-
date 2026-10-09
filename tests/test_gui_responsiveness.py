import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
import shutil
from pathlib import Path
import pytest
QtWidgets=pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import QTimer
import gui

def test_slow_reviewer_keeps_gui_responsive_and_closes_safely(tmp_path,monkeypatch):
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    monkeypatch.setattr(gui,'ROOT',tmp_path)
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window=gui.ChatWindow();window.show()
    window.autonomy_timer.stop();window.chatgpt_review_timer.stop()
    window.runtime.internet_access.enable()
    window.runtime.queue_learning_candidate(
        "memory.add_lesson",
        {"goal":"probe","lesson":"test result","confidence":.9,"source":"gui_responsiveness"},
        "gui responsiveness fixture",
    )
    def slow(row):
        time.sleep(.3)
        return {'learn':True,'reason':'test'}
    window.runtime.chatgpt_review_worker.transport=slow
    ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(10)
    window.run_chatgpt_review_once()
    until=time.monotonic()+2
    while time.monotonic()<until and (window._jobs or len(ticks)<10):
        app.processEvents();time.sleep(.002)
    timer.stop()
    assert not window._jobs
    assert len(ticks)>=10
    assert max(b-a for a,b in zip(ticks,ticks[1:]))<.2
    assert len(window.runtime.human_learning_pending())==1
    window.close();app.processEvents()


def test_human_decision_wait_does_not_block_gui(tmp_path, monkeypatch):
    import threading
    from tests.chatgpt_test_helper import mark_chatgpt_correct
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    monkeypatch.setattr(gui,'ROOT',tmp_path)
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window=gui.ChatWindow(); window.show()
    window.autonomy_timer.stop(); window.chatgpt_review_timer.stop()
    p=window.runtime.learning_gate.request('knowledge.add_fact', {'subject':'gui fixture','predicate':'is','object':'blue'})
    mark_chatgpt_correct(window.runtime,p['proposal_id'],'fixture')
    locked=threading.Event()
    def hold_runtime():
        with window.runtime._mutation_lock:
            locked.set(); time.sleep(.25)
    holder=threading.Thread(target=hold_runtime); holder.start(); assert locked.wait(1)
    results=[]; ticks=[]; timer=QTimer(); timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(10)
    assert window._start_job('decision:'+p['proposal_id'], lambda:window.runtime.approve_learning(p['proposal_id'], human_confirmed=True, source='test_human'),results.append)
    until=time.monotonic()+2
    while time.monotonic()<until and window._jobs:
        app.processEvents();time.sleep(.002)
    holder.join();timer.stop()
    assert results and results[0]['ok']
    assert len(ticks)>=10 and max(b-a for a,b in zip(ticks,ticks[1:]))<.2
    assert window.runtime.effect_learning.stats()['xp']==0
    window.close();app.processEvents()


def test_corrupt_review_state_is_visible_without_stranding_chat(tmp_path, monkeypatch):
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    monkeypatch.setattr(gui,'ROOT',tmp_path)
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window=gui.ChatWindow();window.show()
    window.autonomy_timer.stop();window.chatgpt_review_timer.stop()
    state=window.runtime.chatgpt_review_worker.state_path
    state.write_text('{broken');state.with_suffix('.json.bak').write_text('{broken')
    window.refresh_chatgpt_count()
    assert 'خطا' in window.chatgpt_pending.text()
    assert 'Rate Limit' not in window.chatgpt_pending.text()
    queue=window.runtime._chatgpt_review_path()
    queue.write_text('{broken');queue.with_suffix('.json.bak').write_text('{broken')
    window.busy=True;window.send.setEnabled(False)
    window.on_done('پاسخ محلی آزمایشی',.01)
    assert not window.busy and window.send.isEnabled()
    assert 'خطا' in window.status.text()
    assert queue.read_text()=='{broken'
    dialogs=[]
    monkeypatch.setattr(window,'_dialog',lambda title,text:dialogs.append((title,text)))
    window.show_chatgpt_reviews()
    assert dialogs and 'خطا' in dialogs[-1][1]
    window.close();app.processEvents()



def test_missing_and_schema_corrupt_reviewer_state_render_clear_status(tmp_path,monkeypatch):
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    monkeypatch.setattr(gui,'ROOT',tmp_path)
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window=gui.ChatWindow();window.show()
    window.autonomy_timer.stop();window.chatgpt_review_timer.stop()
    worker=window.runtime.chatgpt_review_worker
    worker.state_path.unlink(missing_ok=True)
    worker.state_path.with_suffix('.json.bak').unlink(missing_ok=True)

    window.refresh_chatgpt_count()
    assert worker.status()['state']=='UNINITIALIZED'
    assert 'وضعیت بازبینی هنوز ثبت نشده' in window.chatgpt_pending.text()
    assert 'وضعیت اولیه' in window.integrity_status.text()
    assert 'وضعیت ناظر هنوز ثبت نشده' in window.recovery_status.text()

    worker.state_path.write_text('{"backoff_seconds":"invalid"}',encoding='utf-8')
    window.refresh_chatgpt_count()
    assert worker.status()['state']=='ERROR'
    assert 'خطا در داده‌های ذخیره‌شده' in window.chatgpt_pending.text()
    assert 'یکپارچگی: خطا' in window.integrity_status.text()
    assert 'worker_state_corrupt' in window.review_errors.text()
    window.close();app.processEvents()


def test_failed_internet_toggle_stays_off_and_visible(tmp_path,monkeypatch):
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    monkeypatch.setattr(gui,'ROOT',tmp_path)
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window=gui.ChatWindow();window.show()
    window.autonomy_timer.stop();window.chatgpt_review_timer.stop()
    def fail(): raise OSError('fixture disk failure')
    monkeypatch.setattr(window.runtime.internet_access,'_save',fail)
    window.toggle_internet()
    assert not window.runtime.internet_access.status()['enabled']
    assert 'خاموش' in window.internet_button.text()
    assert 'خطا' in window.status.text()
    assert not window._jobs
    window.close();app.processEvents()


def test_selected_lesson_review_targets_id_without_reordering_queue(tmp_path, monkeypatch):
    import json
    shutil.copy(Path(__file__).parents[1] / 'config.json', tmp_path)
    monkeypatch.setattr(gui, 'ROOT', tmp_path)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = gui.ChatWindow()
    window.autonomy_timer.stop(); window.chatgpt_review_timer.stop()
    try:
        target = window.runtime.learning_gate.request('memory.add_lesson',
            {'goal': 'selected lesson', 'lesson': 'target', 'source': 'fixture'})
        priority = window.runtime.learning_gate.request('knowledge.add_fact',
            {'subject': 'priority', 'predicate': 'is', 'object': 'other', 'source': 'fixture'})
        window.runtime.sync_chatgpt_learning_reviews()
        queue = window.runtime._chatgpt_review_path()
        before = queue.read_text(encoding='utf-8')
        calls = []
        monkeypatch.setattr(window, '_selected_lesson_row',
            lambda: {'proposal_id': target['proposal_id'], 'status': 'pending'})
        monkeypatch.setattr(window.runtime, 'process_one_chatgpt_learning_review',
            lambda **kwargs: calls.append(kwargs) or {'ok': True})
        monkeypatch.setattr(window, '_start_job',
            lambda name, operation, callback: operation())
        window.review_selected_lesson()
        assert calls == [{'proposal_id': target['proposal_id']}]
        assert queue.read_text(encoding='utf-8') == before
    finally:
        window.close(); app.processEvents()
