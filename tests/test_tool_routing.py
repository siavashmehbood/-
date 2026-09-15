"""Tool routing contracts.

Regression guard for a real defect: the router selected the clock tool on the bare
token `ساعت`, so an honesty question such as "آیا فردا ساعت ۸ باران می‌بارد؟" was
answered with a timestamp and never reached the UNKNOWN path.

Routing must follow intent, not keyword presence. These contracts pin both halves of
that rule: determination questions must fall through to the dialogue layer, while
genuine time requests keep the clock route.
"""
import unittest

from core.tool_router import ToolRouter


class ToolRouterContractTests(unittest.TestCase):
    TIME_REQUESTS = (
        'ساعت الان چند است',
        'ساعت را بگو',
        'زمان سیستم',
        'تاریخ امروز چیه؟',
        'ساعت چنده؟',
        'الان ساعت چنده',
        'زمان چقدره؟',
        'تاریخ را نشان بده',
        'ساعت الان چند است؟',
        'زمان سیستم را بگو',
    )
    DETERMINATION_QUESTIONS = (
        'آیا فردا ساعت ۸ باران می‌بارد؟',
        'آیا فردا ساعت ۸ باران می‌بارد؟',
        'آیا ساعت ۸ هوا سرد است؟',
        'آیا در سال ۱۴۲۰ هسته مشتری جامد می‌شود؟',
        'ایا فردا ساعت ۸ باران می‌بارد؟',
        'آیا تاریخ پایان جهان مشخص است؟',
        'آیا هر روز ساعت ۹ باید جلسه برگزار شود؟',
        'آیا زمان حال بهترین زمان است؟',
        'آیا ساعت طلایی وجود دارد؟',
        'آیا این تاریخ درست است؟',
    )

    def setUp(self):
        self.router = ToolRouter()

    def test_genuine_time_requests_still_route_to_clock(self):
        for text in self.TIME_REQUESTS:
            with self.subTest(text=text):
                self.assertEqual(self.router.choose(text)[0], 'time_now')

    def test_determination_questions_do_not_route_to_clock(self):
        for text in self.DETERMINATION_QUESTIONS:
            with self.subTest(text=text):
                self.assertNotEqual(
                    self.router.choose(text)[0], 'time_now',
                    'a determination question cannot be answered by a timestamp',
                )

    def test_yes_no_detection_requires_a_word_boundary(self):
        # `آیا` must be its own word; it must not fire inside a longer word.
        self.assertFalse(self.router._is_yes_no_question('آیات قرآن'))
        self.assertFalse(self.router._is_yes_no_question('ساعت'))
        self.assertTrue(self.router._is_yes_no_question('آیا فردا باران می‌بارد'))
        self.assertTrue(self.router._is_yes_no_question('ایا فردا باران می‌بارد'))

    def test_other_routes_are_unaffected(self):
        self.assertEqual(self.router.choose('ساختار پروژه را نشان بده')[0], 'project_summary')
        self.assertEqual(self.router.choose('مشخصات سیستم')[0], 'system_info')
        self.assertEqual(self.router.choose('چی گفتم؟')[0], None)


if __name__ == '__main__':
    unittest.main()
