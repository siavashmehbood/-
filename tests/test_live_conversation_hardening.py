import shutil
from pathlib import Path
from runtime.app import IranRuntime

def test_dirty_memory_unknown_and_topic_switch_live(tmp_path):
    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    r=IranRuntime(tmp_path)
    try:
        # Seed unrelated/stale work memory that must never become project identity.
        r.memory.add("user", "بدون API")
        turns=[
            ("سلام", lambda a: "سلام" in a),
            ("اسم من سیاوش است", lambda a: bool(a)),
            ("اسم من چیه؟", lambda a: "سیاوش" in a),
            ("من روی پروژه دانا کار می‌کنم", lambda a: bool(a)),
            ("اسم پروژه من چی بود؟", lambda a: "دانا" in a and "API" not in a),
            ("یک موضوع جدید: کتاب", lambda a: bool(a)),
            ("به بحث دانا برگرد", lambda a: "دانا" in a),
            ("اسم پروژه من چی بود؟", lambda a: "دانا" in a and "API" not in a),
            ("جواب تکراری نده", lambda a: bool(a)),
            ("موضوع فعال چیه؟", lambda a: bool(a)),
        ]
        answers=[]
        for q,check in turns:
            a=r.handle(q); answers.append((q,a))
            assert check(a), answers
        # An unsupported external fact must not be fabricated from conversation memory.
        unknown=r.handle("شماره سریال لپ‌تاپ من چیه؟")
        assert "اطلاعات کافی" in unknown or "نمی" in unknown or "نامشخص" in unknown, unknown
    finally:
        r.close()
