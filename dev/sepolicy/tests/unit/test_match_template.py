# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest

from sepolicy.match_template import (
    ArgValues,
    StringTemplate,
    compile_string_template,
    iter_string_template_arg_values,
)


def arg_values(template: str, value: str):
    compiled = compile_string_template(template)
    assert isinstance(compiled, StringTemplate)
    return [
        tuple(a.values())
        for a in iter_string_template_arg_values(
            ArgValues.empty(3),
            compiled,
            value,
        )
    ]


class StringTemplateTest(unittest.TestCase):
    def test_argument_last(self):
        self.assertEqual(
            arg_values('$1_$2', 'x_y'),
            [('x', 'y', 'UNKNOWN')],
        )

    def test_literal_last(self):
        self.assertEqual(
            arg_values('$2_$3_property_type', 'vendor_public_property_type'),
            [('UNKNOWN', 'vendor', 'public')],
        )

    def test_literals_around(self):
        self.assertEqual(
            arg_values('a_$1_$2_b', 'a_x_y_b'),
            [('x', 'y', 'UNKNOWN')],
        )

    def test_literal_last_with_trailing_value(self):
        self.assertEqual(arg_values('$1_$2_c', 'x_y_cd'), [])

    def test_ambiguous_split(self):
        self.assertEqual(
            arg_values('a_$1_$2_b', 'a_x_y_z_b'),
            [('x', 'y_z', 'UNKNOWN'), ('x_y', 'z', 'UNKNOWN')],
        )


if __name__ == '__main__':
    unittest.main()
