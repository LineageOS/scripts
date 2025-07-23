# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from itertools import product
from typing import List, Optional, Set

from sepolicy.classmap import Classmap
from sepolicy.conditional_type import ConditionalType
from sepolicy.rule import (
    GENFSCON_LABEL_END,
    GENFSCON_LABEL_START,
    Rule,
    RuleType,
    flatten_parts,
    raw_part,
    raw_parts_list,
    unpack_line,
)


def trim_ioctl(ioctl: int):
    # Only keep bottom two bytes for type and number
    return ioctl & 0xFFFF


def format_ioctl(ioctl: int):
    return hex(trim_ioctl(ioctl))


def format_ioctl_str(ioctl_str: str):
    return format_ioctl(int(ioctl_str, base=16))


def unpack_ioctls(ioctls: List[str], negative_ioctls: bool = False):
    if negative_ioctls:
        missing_ioctls = set(trim_ioctl(int(i, base=16)) for i in ioctls)

        # TODO: maybe do not expand ranges
        for n in range(0x0000, 0x10000):
            if n in missing_ioctls:
                continue

            yield format_ioctl(n)

        return

    for part in ioctls:
        if '-' not in part:
            yield format_ioctl(int(part, base=16))
            continue

        parts = part.split('-', 1)
        start_ioctl = int(parts[0], base=16)
        end_ioctl = int(parts[1], base=16)

        # TODO: maybe do not expand ranges
        for n in range(start_ioctl, end_ioctl + 1):
            yield format_ioctl(n)


# TODO: implement this properly by allowing macros to have conditional
# rules based on input params
def is_allow_process_sigchld(parts: raw_parts_list):
    return (
        parts[0] == RuleType.ALLOW
        and len(parts) == 5
        and parts[3:] == ['process', 'sigchld']
    )


def structure_conditional_types(parts: raw_part, all_negatives: bool = False):
    if isinstance(parts, str):
        if parts == '*':
            return [ConditionalType([], [], True)]

        if parts.startswith('~'):
            parts = parts[1:]
            return [ConditionalType([], [parts], False)]

        return [parts]

    positives: List[str] = []
    negatives: List[str] = []

    flat_parts = flatten_parts(parts)

    negative_next_part = False
    for part in flat_parts:
        assert isinstance(part, str), parts

        # Squash dash into the following part for instances like this
        # neverallow { a - b } e:f g;
        if part == '-':
            negative_next_part = True
        elif part.startswith('-'):
            assert not negative_next_part
            negatives.append(part[1:])
        elif negative_next_part:
            negatives.append(part)
            negative_next_part = False
        else:
            assert part[0].isalpha() or part[0] == '$', parts
            positives.append(part)

    if all_negatives:
        assert not negatives
        negatives = positives
        positives = []

    if positives and not negatives:
        return positives

    return [ConditionalType(positives, negatives, False)]


unknown_rule_types: Set[str] = set(
    [
        'permissive',
        'typealias',
    ]
)


class SourceRule(Rule):
    @classmethod
    def genfscon_from_line(cls, line: str):
        parts = unpack_line(
            line,
            '{',
            '}',
            ' ',
            open_by_default=True,
        )

        assert len(parts) == 4, line
        assert isinstance(parts[0], str), line
        assert isinstance(parts[1], str), line
        assert isinstance(parts[2], str), line
        assert isinstance(parts[3], str), line
        assert parts[0] == RuleType.GENFSCON, line

        assert parts[3].startswith(GENFSCON_LABEL_START)
        assert parts[3].endswith(GENFSCON_LABEL_END)
        parts[3] = parts[3][
            len(GENFSCON_LABEL_START) : -len(GENFSCON_LABEL_END)
        ]

        rule = Rule(
            parts[0],
            (parts[1], parts[2], parts[3]),
            (),
        )
        return rule

    @classmethod
    def from_line(cls, line: str, classmap: Optional[Classmap]) -> List[Rule]:
        parts = unpack_line(
            line,
            '{',
            '}',
            ' :,',
            open_by_default=True,
            ignored_chars=';',
        )
        if not parts:
            return []

        if not isinstance(parts[0], str) or len(parts) == 1:
            raise ValueError(f'Invalid line: {line}')

        if parts[0] in unknown_rule_types:
            return []

        # Remove allow $3 $1:process sigchld as it is part of an ifelse
        # statement based on one of the parameters and it is not possible
        # to generate the checks for it as part of macro expansion
        if is_allow_process_sigchld(parts):
            return []

        rules: List[Rule] = []

        match parts[0]:
            case (
                RuleType.ALLOW.value
                | RuleType.NEVERALLOW.value
                | RuleType.AUDITALLOW.value
                | RuleType.DONTAUDIT.value
            ):
                # neverallow ~{ a b }:d e;
                negative_srcs = False
                if len(parts) > 5 and parts[1] == '~':
                    negative_srcs = True
                    del parts[1]

                # neverallow a ~{ b c }:d e;
                negative_dsts = False
                if len(parts) > 5 and parts[2] == '~':
                    negative_dsts = True
                    del parts[2]

                # neverallow a b:c ~{ d e };
                negative_varargs = False
                if len(parts) > 5 and parts[4] == '~':
                    negative_varargs = True
                    del parts[4]

                # neverallow a b:c ~d;
                if (
                    len(parts) == 5
                    and isinstance(parts[4], str)
                    and parts[4].startswith('~')
                ):
                    negative_varargs = True
                    parts[4] = parts[4][1:]

                assert len(parts) == 5, line

                srcs = structure_conditional_types(parts[1], negative_srcs)
                dsts = structure_conditional_types(parts[2], negative_dsts)
                class_names = list(flatten_parts(parts[3]))
                varargs = list(flatten_parts(parts[4]))

                for src, dst, class_name in product(srcs, dsts, class_names):
                    class_varargs = varargs
                    if varargs == ['*'] or negative_varargs:
                        assert classmap is not None
                        class_varargs = classmap.class_perms(class_name)

                    if negative_varargs:
                        for v in varargs:
                            class_varargs.remove(v)

                    rule = Rule(
                        parts[0],
                        (src, dst, class_name),
                        tuple(class_varargs),
                    )
                    rules.append(rule)
            case RuleType.TYPE_TRANSITION.value:
                assert len(parts) in [5, 6], line
                assert isinstance(parts[4], str), line

                srcs = structure_conditional_types(parts[1])
                dsts = structure_conditional_types(parts[2])
                class_names = flatten_parts(parts[3])

                # Optional string for userfaultfd
                if len(parts) == 6:
                    assert isinstance(parts[5], str), line
                    # assert parts[5] == '"[userfaultfd]"', line
                    varargs = [parts[5]]
                else:
                    varargs = []

                for src, dst, class_name in product(srcs, dsts, class_names):
                    rule = Rule(
                        parts[0],
                        (src, dst, class_name, parts[4]),
                        tuple(varargs),
                    )
                    rules.append(rule)
            case (
                RuleType.ALLOWXPERM.value
                | RuleType.NEVERALLOWXPERM.value
                | RuleType.DONTAUDITXPERM.value
            ):
                # TODO: ioctl rules are split at comments by the compiler
                # and later merged as part of the final processing steps
                # Try merging them ahead of time.

                # neverallowxperm a b:c ioctl ~{ d };
                negative_ioctls = False
                if len(parts) > 6 and parts[5] == '~':
                    negative_ioctls = True
                    del parts[5]

                assert len(parts) == 6
                assert isinstance(parts[4], str), line
                assert parts[4] == 'ioctl'

                srcs = structure_conditional_types(parts[1])
                dsts = structure_conditional_types(parts[2])
                class_names = flatten_parts(parts[3])
                varargs = list(flatten_parts(parts[5]))
                ioctls = list(unpack_ioctls(varargs, negative_ioctls))

                for src, dst, class_name in product(srcs, dsts, class_names):
                    rule = Rule(
                        parts[0],
                        (src, dst, class_name),
                        tuple(ioctls),
                    )
                    rules.append(rule)

            case RuleType.ATTRIBUTE.value:
                assert len(parts) == 2, line
                assert isinstance(parts[1], str), line

                rule = Rule(
                    parts[0],
                    (parts[1],),
                    (),
                )
                return [rule]
            case RuleType.TYPEATTRIBUTE.value:
                assert isinstance(parts[1], str), line

                for t in parts[2:]:
                    assert isinstance(t, str), line
                    rule = Rule(
                        parts[0],
                        (parts[1], t),
                        (),
                    )
                    rules.append(rule)
            case RuleType.TYPE.value:
                assert isinstance(parts[1], str), line

                # Convert type rules to typeattribute to allow easy matching
                # with split typeattributeset rules
                for t in parts[2:]:
                    assert isinstance(t, str)
                    rule = Rule(
                        RuleType.TYPEATTRIBUTE.value,
                        (parts[1], t),
                        (),
                    )
                    rules.append(rule)
            case RuleType.EXPANDATTRIBUTE.value:
                assert len(parts) == 3
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], str), line

                rule = Rule(
                    parts[0],
                    (parts[1], parts[2]),
                    (),
                )
                rules.append(rule)
            case _:
                assert False, line

        return rules
