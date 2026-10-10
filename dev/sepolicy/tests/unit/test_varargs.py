# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest

from sepolicy.varargs import ArgVarargs, Ioctls, Perms, Types


class PermsTest(unittest.TestCase):
    def test_union(self):
        a = Perms(['read', 'open'], False)
        b = Perms(['open', 'getattr'], False)

        self.assertEqual(a | b, Perms(['read', 'open', 'getattr'], False))

    def test_union_keeps_all(self):
        a = Perms(['read'], True)
        b = Perms(['open'], False)

        self.assertEqual(a | b, Perms(['read', 'open'], True))

    def test_difference(self):
        a = Perms(['read', 'open', 'getattr'], False)
        b = Perms(['open'], False)

        self.assertEqual(a - b, Perms(['read', 'getattr'], False))

    def test_difference_without_overlap_keeps_all(self):
        a = Perms(['read', 'open'], True)
        b = Perms(['getattr'], False)

        self.assertIs(a - b, a)

    def test_difference_with_all(self):
        a = Perms(['read', 'open'], False)
        b = Perms(['getattr'], True)

        self.assertTrue((a - b).is_empty())

    def test_is_empty(self):
        self.assertTrue(Perms([], False).is_empty())
        self.assertFalse(Perms([], True).is_empty())
        self.assertFalse(Perms(['read'], False).is_empty())


class IoctlsTest(unittest.TestCase):
    def test_merge(self):
        a = Ioctls([(0x1, 0x5)])
        b = Ioctls([(0x6, 0x8), (0x10, 0x10)])

        self.assertEqual(a.merge(b), Ioctls([(0x1, 0x8), (0x10, 0x10)]))

    def test_difference(self):
        a = Ioctls([(0x1, 0x10)])
        b = Ioctls([(0x4, 0x6)])

        self.assertEqual(a - b, Ioctls([(0x1, 0x3), (0x7, 0x10)]))

    def test_is_empty(self):
        self.assertTrue(Ioctls([]).is_empty())
        self.assertTrue(
            (Ioctls([(0x1, 0x5)]) - Ioctls([(0x0, 0x10)])).is_empty()
        )
        self.assertFalse(Ioctls([(0x1, 0x1)]).is_empty())


class TypesTest(unittest.TestCase):
    def test_str(self):
        self.assertEqual(
            str(Types({'domain', 'coredomain'})), ', coredomain, domain'
        )

    def test_str_empty(self):
        self.assertEqual(str(Types(set())), '')


class ArgVarargsTest(unittest.TestCase):
    def test_equality(self):
        self.assertEqual(ArgVarargs(3), ArgVarargs(3))
        self.assertNotEqual(ArgVarargs(3), ArgVarargs(4))
        self.assertEqual(hash(ArgVarargs(3)), hash(ArgVarargs(3)))

    def test_str(self):
        self.assertEqual(str(ArgVarargs(3)), '$3')


if __name__ == '__main__':
    unittest.main()
