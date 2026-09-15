import re

class ToolRouter:
    """Maps natural language to the safest available tool without substring collisions."""
    @staticmethod
    def _has_token(text, token):
        return re.search(rf'(?<![\wآ-ی]){re.escape(token)}(?![\wآ-ی])', text) is not None

    @staticmethod
    def _is_yes_no_question(text):
        """True when the user wants a determination, not a reading.

        `آیا` marks a yes/no question whose answer requires reasoning over knowledge.
        A timestamp cannot answer it, so such a turn must not be pre-empted by the
        clock tool just because it mentions `ساعت` (e.g. "آیا فردا ساعت ۸ باران
        می‌بارد؟"). `ایا` is accepted for users who drop the madda.
        """
        t = str(text).replace('آ', 'ا')
        return bool(re.search(r'(?<![\wا-ی])ایا(?![\wا-ی])', t))

    def choose(self, text):
        t = str(text).lower().strip()
        if any(self._has_token(t, x) for x in ('ساعت','زمان','تاریخ')) and not self._is_yes_no_question(t):
            return 'time_now', {}
        if any(x in t for x in ('مشخصات سیستم','مشخصات کامپیوتر','سیستم من')):
            return 'system_info', {}
        if any(x in t for x in ('ساختار پروژه','فایل های پروژه','فایل‌های پروژه','چه فایل هایی','چه فایل‌هایی')):
            return 'project_summary', {}
        if any(x in t for x in ('لیست فایل','فهرست فایل','فایل‌ها را لیست','فایل ها را لیست')):
            return 'project_files', {}
        if any(x in t for x in ('حافظه را جستجو','حافظه را پیدا','در حافظه جستجو','حافظه پروژه را نشان','memory search')):
            return 'memory_search', {'query': str(text), 'limit': 8}
        if any(self._has_token(t, x) for x in ('cpu','ram','رم','پردازنده')):
            return 'system_info', {}
        return None, {}
