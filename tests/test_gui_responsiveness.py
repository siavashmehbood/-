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
    window.runtime.learning.record('probe','test','result',.9)
    def slow(row):
        time.sleep(.3)
        return {'learn':True,'reason':'test'}
    window.runtime.chatgpt_review_worker.transport=slow
    ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(10)
    window.run_chatgpt_review_once()
    until=time.monotonic()+2
    while time.monotonic()<until and (window._jobs or len(ticks)<5):
        app.processEvents();time.sleep(.002)
    timer.stop()
    assert not window._jobs
    assert len(ticks)>=10
    assert max(b-a for a,b in zip(ticks,ticks[1:]))<.2
    assert len(window.runtime.human_learning_pending())==1
    window.close();app.processEvents()
