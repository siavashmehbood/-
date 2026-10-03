import shutil
from pathlib import Path

from runtime.app import IranRuntime


MESSAGES = [
    "سلام",
    "اسم من سیاوش است",
    "من روی پروژه دانا کار می‌کنم",
    "هدف دانا فروش کتاب است",
    "موضوع قبلی چی بود؟",
    "یادت هست اسم من چی بود؟",
    "نه، منظورم اسم پروژه بود",
    "همون موضوع قبلی رو ادامه بده",
    "پایتخت ایران چیه؟",
    "این جواب درباره چی بود؟",
    "موضوع قبلی رو ول کن",
    "پروژه ایران چیه؟",
    "منظورم معماری شناختی بود",
    "همین رو بیشتر توضیح بده",
    "یادت هست اول درباره چی گفتم؟",
    "یک بار دیگه بگو",
    "اشتباهه، منظورم پروژه دانا بود",
    "الان موضوع فعال چیه؟",
    "حافظه چیه؟",
    "چه چیزهایی از من یادت هست؟",
    "موضوع اول چی بود؟",
    "موضوع دوم چی بود؟",
    "به بحث دانا برگرد",
    "هدفش چی بود؟",
    "نه، هدفش فروش کتاب نبود، آموزش بود",
    "هدف اصلاح شد؟",
    "همین موضوع رو ادامه بده",
    "حالا درباره ایران بگو",
    "این پروژه آفلاینه؟",
    "گفتم آفلاین باشه",
    "پس چه محدودیت‌هایی داره؟",
    "همون قبلی رو دقیق‌تر بگو",
    "یک موضوع جدید: کتاب",
    "برای کتاب یک پیشنهاد بده",
    "موضوع قبلی چی بود؟",
    "به موضوع ایران برگرد",
    "یادت هست گفتم آفلاین؟",
    "پس خارجی نباشه",
    "نه، منظورم بدون API بود",
    "این اصلاح رو حفظ کن",
    "الان آخرین اصلاح چی بود؟",
    "یک بار دیگه آخرین اصلاح رو بگو",
    "موضوع دانا چی بود؟",
    "هدف دانا چی بود؟",
    "نه، منظورم نسخه اول هدف بود",
    "به نسخه جدید برگرد",
    "حالا یک سوال عمومی: تهران پایتخت کجاست؟",
    "پایتخت ایران؟",
    "یادت هست من چه پروژه‌هایی گفتم؟",
    "آخرین موضوع فعال چی بود؟",
]


def test_full_fifty_turn_persian_conversation_is_ci_enforced(tmp_path):
    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime = IranRuntime(tmp_path)
    try:
        answers = []
        traces = []
        for message in MESSAGES:
            answers.append(runtime.handle(message))
            trace = getattr(runtime.dialogue, "last_trace", None)
            traces.append({
                "answer_status": getattr(trace, "answer_status", ""),
                "verification_status": getattr(trace, "verification_status", ""),
                "verification_reasons": getattr(trace, "verification_reasons", []),
                "evidence_status": getattr(trace, "evidence_status", ""),
            })
        name_facts = runtime.user_model.facts(predicate="name", limit=1)
        checks = {
            "turn_count": len(answers) == 50,
            "name_recall": bool(name_facts) and name_facts[0]["object"] in answers[5],
            "project_identity": "IRAN" in answers[6],
            "answer_reference": "پایتخت ایران" in answers[9],
            "project_explanation": "معماری شناختی" in answers[11],
            "goal_recall": "فروش کتاب" in answers[23],
            "goal_correction": "آموزش" in answers[25],
            "offline_fact": "آفلاین" in answers[28],
            "constraint_recall": "آفلاین" in answers[30],
            "previous_topic": "کتاب" in answers[34],
            "latest_correction": "بدون API" in answers[40] and "بدون API" in answers[41],
            "first_goal_version": "فروش کتاب" in answers[44],
            "latest_goal_version": "آموزش" in answers[45],
            "project_list": "دانا" in answers[48] and "ایران" in answers[48],
            "active_topic": "ایران" in answers[49],
        }
    finally:
        runtime.close()

    failed = [name for name, passed in checks.items() if not passed]
    answer_indexes = {
        "name_recall": 5,
        "project_identity": 6,
        "answer_reference": 9,
        "project_explanation": 11,
        "goal_recall": 23,
        "goal_correction": 25,
        "offline_fact": 28,
        "constraint_recall": 30,
        "previous_topic": 34,
        "latest_correction": 40,
        "first_goal_version": 44,
        "latest_goal_version": 45,
        "project_list": 48,
        "active_topic": 49,
    }
    details = "\n".join(
        f"{name}: {answers[answer_indexes[name]]} | trace={traces[answer_indexes[name]]}"
        for name in failed
        if name in answer_indexes
    )
    assert not failed, f"failed={failed}\n{details}"
