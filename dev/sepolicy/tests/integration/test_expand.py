# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
import unittest

from sepolicy.expand import expand_macro_calls_and_split
from sepolicy.macro import macro_name_body
from sepolicy.rules import split_normalize_rules_text
from utils.frozendict import FrozenDict

if shutil.which('m4') is None:
    raise unittest.SkipTest('m4 not found')

TE_MACROS = """
define(`recovery_only', ifelse(target_recovery, `true', $1, ))
define(`domain_trans', `
allow $1 $2:file execute;
allow $1 $3:process transition;
ifelse($1, `init', `', `allow $3 $1:process sigchld;')
')
define(`domain_auto_trans', `
domain_trans($1,$2,$3)
type_transition $1 $2:process $3;
')
define(`init_daemon_domain', `
domain_auto_trans(init, $1_exec, $1)
')
"""


def expand(text: str, variables: FrozenDict[str, str]):
    return dict(
        expand_macro_calls_and_split(
            texts=[text],
            environment_texts=[],
            variables=variables,
            split_fn=split_normalize_rules_text,
            map_fn=macro_name_body,
            preserve_macros=True,
            text_name='test',
            verbose=False,
        )
    )


class ArgIfelseTest(unittest.TestCase):
    def setUp(self):
        self.macros = expand(
            TE_MACROS, FrozenDict({'target_recovery': 'false'})
        )

    def test_argument_comparison_keeps_both_branches(self):
        for name in ('domain_trans', 'domain_auto_trans'):
            with self.subTest(macro=name):
                lines = self.macros[name].splitlines()

                self.assertIn('ARG_IFELSE $1 init', lines)
                self.assertIn('ARG_ELSE', lines)
                self.assertIn('allow $3 $1:process sigchld;', lines)
                self.assertIn('ARG_END', lines)

    def test_literal_argument_is_evaluated(self):
        body = self.macros['init_daemon_domain']

        self.assertNotIn('ARG_IFELSE', body)
        self.assertNotIn('sigchld', body)
        self.assertIn('allow init $1:process transition;', body)

    def test_variable_comparison_is_evaluated(self):
        self.assertNotIn('ARG_IFELSE', self.macros.get('recovery_only', ''))


if __name__ == '__main__':
    unittest.main()
