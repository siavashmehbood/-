import re

class ToolRouter:
    """Maps natural language to the safest available tool without substring collisions."""
    @staticmethod
    def _has_token(text, token):
        return re.search(rf'(?<![\wآ-ی]){re.escape(token)}(?![\wآ-ی])', text) is not None

    def choose(self, text):
        t = str(text).lower().strip()
        if any(self._has_token(t, x) for x in ('ساعت','زمان','تاریخ')):
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
