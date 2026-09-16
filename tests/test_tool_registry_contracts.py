"""Extensibility contracts for the tool registry.

The mission requires the architecture to be extensible: new tools must be addable
without editing the core. The registry was used throughout the suite indirectly but had
no tests of its own, so the extension point itself - registration validation, safe
replacement, removal - was unverified.
"""
import unittest

from tools.registry import Tool, ToolRegistry


class ToolRegistryContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()

    def test_register_and_run(self):
        self.registry.register(Tool('echo', 'بازگشت متن', lambda text: text))
        self.assertEqual(self.registry.run('echo', text='سلام'), 'سلام')

    def test_registered_tool_is_discoverable(self):
        self.registry.register(Tool('echo', 'بازگشت متن', lambda: None))
        listing = self.registry.list()
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]['name'], 'echo')
        self.assertEqual(listing[0]['description'], 'بازگشت متن')
        self.assertIn('echo', self.registry.names())

    def test_duplicate_name_is_rejected(self):
        self.registry.register(Tool('echo', 'اول', lambda: 1))
        with self.assertRaises(ValueError):
            self.registry.register(Tool('echo', 'دوم', lambda: 2))
        # The first registration must survive the rejected one.
        self.assertEqual(self.registry.run('echo'), 1)

    def test_empty_name_is_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register(Tool('', 'بی‌نام', lambda: None))

    def test_non_callable_handler_is_rejected(self):
        # Without this check the failure would surface at call time, far from the code
        # that registered the tool.
        with self.assertRaises(ValueError):
            self.registry.register(Tool('broken', 'خراب', 'not callable'))

    def test_rejected_registration_does_not_occupy_the_name(self):
        try:
            self.registry.register(Tool('broken', 'خراب', 'not callable'))
        except ValueError:
            pass
        self.registry.register(Tool('broken', 'سالم', lambda: 'ok'))
        self.assertEqual(self.registry.run('broken'), 'ok')

    def test_unregister_removes_tool(self):
        self.registry.register(Tool('echo', 'بازگشت متن', lambda: 'ok'))
        removed = self.registry.unregister('echo')
        self.assertIsNotNone(removed)
        self.assertIsNone(self.registry.get('echo'))
        self.assertNotIn('echo', self.registry)
        with self.assertRaises(KeyError):
            self.registry.run('echo')

    def test_unregister_unknown_returns_none(self):
        self.assertIsNone(self.registry.unregister('ناموجود'))

    def test_replace_swaps_implementation(self):
        self.registry.register(Tool('echo', 'نسخه ۱', lambda: 'one'))
        self.registry.replace(Tool('echo', 'نسخه ۲', lambda: 'two'))
        self.assertEqual(self.registry.run('echo'), 'two')
        self.assertEqual(len(self.registry), 1)

    def test_replace_can_add_new_tool(self):
        self.registry.replace(Tool('fresh', 'تازه', lambda: 'new'))
        self.assertEqual(self.registry.run('fresh'), 'new')

    def test_unknown_tool_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.registry.run('ناموجود')

    def test_registries_are_isolated(self):
        other = ToolRegistry()
        self.registry.register(Tool('echo', 'بازگشت متن', lambda: 'ok'))
        self.assertNotIn('echo', other)
        self.assertEqual(len(other), 0)

    def test_permission_defaults_follow_safety(self):
        safe = Tool('read_only', 'خواندن', lambda: None, safe=True)
        unsafe = Tool('write_thing', 'نوشتن', lambda: None, safe=False)
        self.assertEqual(safe.permission, 'read')
        self.assertEqual(unsafe.permission, 'write')

    def test_explicit_permission_is_kept(self):
        tool = Tool('net', 'شبکه', lambda: None, safe=True, permission='network')
        self.assertEqual(tool.permission, 'network')


if __name__ == '__main__':
    unittest.main()
