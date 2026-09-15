"""Composition-order contracts for IranRuntime.

`runtime/app.py` builds the runtime by monkeypatching. The behaviour of the runtime
depends on the *order* of those assignments, but until now nothing declared or
checked that order — it was implied by file layout alone, so a patch moved by accident
would quietly change routing.

These tests make the composition order explicit and enforced. They parse the real
source file rather than importing and introspecting, so they also catch a layer that
was deleted or duplicated.
"""
import re
import unittest
from pathlib import Path

from runtime import composition

APP_SOURCE = Path(__file__).resolve().parents[1] / 'runtime' / 'app.py'


def handle_assignments_in_file_order():
    source = APP_SOURCE.read_text(encoding='utf-8')
    return re.findall(r'^IranRuntime\.handle\s*=\s*(\w+)\s*$', source, re.MULTILINE)


class RuntimeCompositionTests(unittest.TestCase):
    def test_handle_layer_order_matches_declared_composition(self):
        actual = tuple(handle_assignments_in_file_order())
        self.assertEqual(
            actual, composition.HANDLE_LAYER_ORDER,
            'IranRuntime.handle composition order changed; runtime behaviour depends '
            'on this order, so update runtime/composition.py deliberately',
        )

    def test_handle_layer_count_is_unchanged(self):
        self.assertEqual(len(handle_assignments_in_file_order()), composition.expected_handle_layers())

    def test_every_handle_layer_is_defined_before_it_is_assigned(self):
        source = APP_SOURCE.read_text(encoding='utf-8')
        assigned_at = {}
        for index, line in enumerate(source.splitlines()):
            match = re.match(r'^IranRuntime\.handle\s*=\s*(\w+)\s*$', line)
            if match:
                assigned_at[match.group(1)] = index
        for name, line_index in assigned_at.items():
            definition = re.search(rf'^def {re.escape(name)}\(', source, re.MULTILINE)
            self.assertIsNotNone(definition, f'{name} is assigned to handle but never defined')
            self.assertLess(
                source[:definition.start()].count('\n'), line_index,
                f'{name} must be defined before it is assigned to handle',
            )

    def test_no_layer_is_assigned_twice(self):
        names = handle_assignments_in_file_order()
        duplicates = {n for n in names if names.count(n) > 1}
        self.assertEqual(duplicates, set(), 'a handle layer is installed more than once')

    def test_order_sensitive_attributes_are_declared(self):
        source = APP_SOURCE.read_text(encoding='utf-8')
        declared = composition.ORDER_SENSITIVE
        # Every attribute the runtime assigns more than once must be named as
        # order-sensitive, so a future refactor cannot miss one silently.
        self.assertIn('handle', declared)
        self.assertIn('__init__', declared)
        for attribute in declared:
            count = len(re.findall(rf'^IranRuntime\.{re.escape(attribute)}\s*=\s*\w+\s*$', source, re.MULTILINE))
            self.assertGreater(count, 1, f'{attribute} is declared order-sensitive but assigned once')

    def test_describe_reports_real_numbers(self):
        described = composition.describe()
        self.assertEqual(described['handle_layers'], len(composition.HANDLE_LAYER_ORDER))
        self.assertEqual(described['dialogue_layers'], 8)
        self.assertGreater(described['method_patch_sites'], 50)

    def test_chat_upgrade_install_order_is_declared(self):
        self.assertEqual(
            composition.DIALOGUE_LAYER_ORDER,
            ('install', 'install_v2', 'install_v3', 'install_v4', 'install_v5',
             'install_v6', 'install_v7', 'install_v8'),
        )


if __name__ == '__main__':
    unittest.main()
