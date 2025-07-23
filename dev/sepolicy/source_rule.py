# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Iterable, List

from sepolicy.classmap import Classmap
from sepolicy.conditional_type import ConditionalType
from sepolicy.rule import (
    Rule,
    RuleType,
    flatten_parts,
    raw_part,
    raw_parts_list,
    unpack_line,
)


def cleanup_ioctls(ioctls: Iterable[str]):
    # Only keep bottom two bits for type and number
    return list(map(lambda i: hex(int(i, base=16) & 0xffff), ioctls))



def is_allow_process_sigchld(parts: raw_parts_list):
    return (
        parts[0] == RuleType.ALLOW
        and len(parts) == 5
        and parts[3:] == ['process', 'sigchld']
    )


def structure_conditional_type(parts: raw_part):
    if isinstance(parts, str):
        return parts

    positives: List[str] = []
    negatives: List[str] = []

    if len(parts) == 1 and parts[0] == '*':
        return ConditionalType([], [], True)

    for part in parts:
        assert isinstance(part, str)
        if part.startswith('-'):
            negatives.append(part[1:])
        else:
            assert part[0].isalpha() or part[0] == '$', parts
            positives.append(part)

    return ConditionalType(positives, negatives, False)


class SourceRule(Rule):
    @classmethod
    def from_line(cls, line: str, classmap: Classmap) -> List[Rule]:
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
                assert len(parts) == 5, line

                src = structure_conditional_type(parts[1])
                dst = structure_conditional_type(parts[2])

                classes = list(flatten_parts(parts[3]))
                varargs = list(flatten_parts(parts[4]))

                for class_name in classes:
                    class_varargs = varargs
                    if varargs == ['*']:
                        class_varargs = classmap.class_perms(class_name)

                    rule = Rule(
                        parts[0],
                        (src, dst, class_name),
                        tuple(class_varargs),
                    )
                    rules.append(rule)
            case RuleType.TYPE_TRANSITION.value:
                assert len(parts) in [5, 6], line
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], str), line
                assert isinstance(parts[4], str), line

                class_names = flatten_parts(parts[3])

                # Optional string for userfaultfd
                if len(parts) == 6:
                    assert isinstance(parts[5], str), line
                    # assert parts[5] == '"[userfaultfd]"', line
                    varargs = [parts[5]]
                else:
                    varargs = []

                for class_name in class_names:
                    rule = Rule(
                        parts[0],
                        (parts[1], parts[2], class_name, parts[4]),
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
                assert len(parts) == 6
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], str), line
                assert isinstance(parts[3], str), line
                assert isinstance(parts[4], str), line
                assert parts[4] == 'ioctl'

                varargs = list(flatten_parts(parts[5]))
                ioctls = cleanup_ioctls(varargs)

                rule = Rule(
                    parts[0],
                    (parts[1], parts[2], parts[3]),
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
                assert len(parts) == 3, line
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], str), line

                rule = Rule(
                    parts[0],
                    (parts[1], parts[2]),
                    (),
                )
                rules.append(rule)
            case RuleType.TYPE.value:
                assert isinstance(parts[1], str), line

                # Convert type rules to typeattribute to allow easy
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
