import re

class ToolRouter:
    """Maps natural language to the safest available tool without substring collisions."""
    @staticmethod
    def _has_token(text, token):
        return re.search(rf'(?<![\wآ-ی]){re.escape(token)}(?![\wآ-ی])', text) is not None

    @staticmethod
    def _persian_number(token):
        token = re.sub(r'\s+', ' ', str(token).strip())
        if re.fullmatch(r'[-+]?\d+(?:\.\d+)?', token):
            return float(token) if '.' in token else int(token)
        units = {'صفر':0,'یک':1,'دو':2,'سه':3,'چهار':4,'پنج':5,'شش':6,'هفت':7,'هشت':8,'نه':9}
        teens = {'ده':10,'یازده':11,'دوازده':12,'سیزده':13,'چهارده':14,'پانزده':15,'شانزده':16,'هفده':17,'هجده':18,'نوزده':19}
        tens = {'بیست':20,'سی':30,'چهل':40,'پنجاه':50,'شصت':60,'هفتاد':70,'هشتاد':80,'نود':90}
        hundreds = {'صد':100,'یکصد':100,'دویست':200,'سیصد':300,'چهارصد':400,'پانصد':500,'ششصد':600,'هفتصد':700,'هشتصد':800,'نهصد':900}
        total = 0
        seen = False
        for part in (p.strip() for p in token.split(' و ')):
            if part in units: total += units[part]
            elif part in teens: total += teens[part]
            elif part in tens: total += tens[part]
            elif part in hundreds: total += hundreds[part]
            else: return None
            seen = True
        return total if seen else None

    @classmethod
    def _word_arithmetic(cls, text):
        op_patterns = (
            ('به توان', '**'), ('ضربدر', '*'), ('ضرب در', '*'),
            ('تقسیم بر', '/'), ('به علاوه', '+'), ('بعلاوه', '+'), ('منهای', '-'),
        )
        clean = re.sub(r'[؟?!.،,]+', ' ', str(text).lower())
        for phrase in ('چند میشه', 'چند می‌شود', 'چند میشود', 'فقط جواب بده'):
            clean = clean.replace(phrase, ' ')
        clean = re.sub(r'\s+', ' ', clean).strip()
        for marker, op in op_patterns:
            if marker not in clean:
                continue
            left, right = clean.split(marker, 1)
            a, b = cls._persian_number(left.strip()), cls._persian_number(right.strip())
            if a is not None and b is not None:
                return f'{a}{op}{b}'
        return None

    def choose(self, text):
        t = str(text).lower().strip()
        word_expression = self._word_arithmetic(t)
        if word_expression:
            return 'calculate', {'expression': word_expression}
        digits = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
        arithmetic = t.translate(digits)
        words = {
            'به توان': '**', 'ضربدر': '*', 'ضرب در': '*', '×': '*',
            'تقسیم بر': '/', 'تقسیم': '/', '÷': '/',
            'بعلاوه': '+', 'به علاوه': '+', 'منهای': '-',
        }
        for source, target in words.items():
            arithmetic = arithmetic.replace(source, target)
        arithmetic = re.sub(r'[^0-9+*/().%\-]+', ' ', arithmetic)
        candidates = re.findall(r'[-+]?\d+(?:\.\d+)?(?:\s*(?:\*\*|[+*/%\-])\s*[-+]?\d+(?:\.\d+)?)+', arithmetic)
        if candidates:
            return 'calculate', {'expression': candidates[0].replace(' ', '')}
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
        if any(x in t for x in ('اسکرین شات','اسکرین‌شات','screenshot')):
            return 'screenshot', {}
        if any(x in t for x in ('ماشین حساب رو باز','ماشین حساب را باز','open calculator')):
            return 'open_application', {'name':'calculator'}
        if any(x in t for x in ('نوت پد رو باز','نوت پد را باز','open notepad')):
            return 'open_application', {'name':'notepad'}
        if any(x in t for x in ('وی اس کد رو باز','وی‌اس‌کد رو باز','open vscode','open vs code')):
            return 'open_application', {'name':'vscode'}
        if any(x in t for x in ('صدا رو کمتر','صدا را کمتر','volume down')):
            return 'set_volume', {'direction':'down','steps':2}
        if any(x in t for x in ('صدا رو بیشتر','صدا را بیشتر','volume up')):
            return 'set_volume', {'direction':'up','steps':2}
        if any(x in t for x in ('صدا رو قطع','صدا را قطع','mute')):
            return 'set_volume', {'direction':'mute','steps':1}
        if any(x in t for x in ('باتری چقدره','وضعیت باتری','battery')):
            return 'get_battery', {}
        m=re.search(r'(?:create|make) (?:a )?(?:test )?folder(?: named)?[ :]+([\w.-]+)',t)
        if m:return 'create_folder', {'path':m.group(1)}
        return None, {}
