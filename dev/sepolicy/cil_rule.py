# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from enum import StrEnum
from typing import Dict, List, Optional, Set

from sepolicy.conditional_type import ConditionalType, ConditionalTypeRedirect
from sepolicy.rule import (
    Rule,
    RuleType,
    is_type_generated,
    raw_part,
    raw_parts_list,
    unpack_line,
)
from utils.utils import Color, color_print


def remove_type_suffix(suffix: Optional[str], t: str):
    if suffix is None:
        return t

    if t.endswith(suffix):
        return t[: -len(suffix)]

    return t


def is_conditional_typeattr(part: raw_part):
    if isinstance(part[0], list):
        part = part[0][0]
    else:
        part = part[0]

    return part in ['and', 'not', 'all']


def create_conditional_type(
    version_suffix: Optional[str],
    parts: raw_parts_list,
):
    # ((and (...) ((not (...))))) -> (and (...) ((not (...))))
    # ((not (...))) -> (not (...))

    if len(parts) == 1 and isinstance(parts[0], list):
        parts = parts[0]
        assert parts[0] in ['and', 'not', 'all'], parts

    # (and (...) ((not (...)))) -> (and (...) (not (...)))
    if (
        len(parts) == 3
        and isinstance(parts[2], list)
        and len(parts[2]) == 1
        and parts[2][0][0] == 'not'
    ):
        parts[2] = parts[2][0]

    # (and (...) (not (...))) -> (and (...) not (...))
    if (
        len(parts) == 3
        and parts[0] == 'and'
        and isinstance(parts[2], list)
        and parts[2][0] == 'not'
    ):
        assert isinstance(parts[2], list), parts
        parts.append(parts[2][1])
        parts[2] = parts[2][0]

    # (all)
    if parts == ['all']:
        return ConditionalType([], [], True)

    # Split in groups of two
    if len(parts) not in [2, 4]:
        color_print('Ignored conditional type: ', parts, color=Color.YELLOW)
        return None

    positive: List[str] = []
    negative: List[str] = []

    for i in range(0, len(parts), 2):
        group = parts[i : i + 2]
        assert len(group) == 2, parts
        assert isinstance(group[0], str), parts
        assert group[0] in ['and', 'not'], parts
        assert isinstance(group[1], list), parts

        # Type narrowing
        new_group: List[str] = []
        for t in group[1]:
            if isinstance(t, str):
                new_group.append(t)
                continue

            color_print('Ignored conditional type: ', parts, color=Color.YELLOW)
            return None

        new_types = map(
            lambda t: remove_type_suffix(version_suffix, t),
            new_group,
        )
        if group[0] == 'and':
            positive.extend(new_types)
        elif group[0] == 'not':
            negative.extend(new_types)

    return ConditionalType(positive, negative, False)


def is_valid_cil_line(line: str):
    line = line.strip()

    if not line:
        return False

    if line.startswith('#'):
        return False

    if line.startswith(';'):
        return False

    return True


# TODO: implement this properly by allowing macros to have conditional
# rules based on input params
def is_allow_process_sigchld(parts: raw_parts_list):
    return (
        parts[0] == RuleType.ALLOW
        and len(parts) == 4
        and parts[3] == ['process', ['sigchld']]
    )


def unpack_ioctls(parts: raw_parts_list):
    # (. (range . .) ((range . .)))

    for part in parts:
        if isinstance(part, str):
            yield part
            continue

        assert isinstance(part, list), parts

        if isinstance(part[0], list):
            part = part[0]

        assert part[0] == 'range', parts

        assert isinstance(part[1], str), parts
        start_ioctl = int(part[1], base=16)

        assert isinstance(part[2], str), parts
        end_ioctl = int(part[2], base=16)

        # TODO: maybe do not expand ranges
        for n in range(start_ioctl, end_ioctl + 1):
            yield hex(n)


class CilRuleType(StrEnum):
    ALLOWX = 'allowx'
    NEVERALLOWX = 'neverallowx'
    DONTAUDITX = 'dontauditx'
    EXPANDTYPEATTRIBUTE = 'expandtypeattribute'
    TYPEATTRIBUTE = 'typeattribute'
    TYPEATTRIBUTESET = 'typeattributeset'
    TYPETRANSITION = 'typetransition'


unknown_rule_types: Set[str] = set(
    [
        'category',
        'categoryorder',
        'class',
        'classcommon',
        'classorder',
        'handleunknown',
        'mls',
        'mlsconstrain',
        'policycap',
        'role',
        'roleattribute',
        'roletype',
        'sensitivity',
        'sensitivitycategory',
        'sensitivityorder',
        'sid',
        'sidcontext',
        'sidorder',
        'fsuse',
        'common',
        'type',
        'typealias',
        'typealiasactual',
        'typepermissive',
        'user',
        'userlevel',
        'userrange',
        'userrole',
    ]
)


class CilRule(Rule):
    @classmethod
    def from_line(
        cls,
        line: str,
        conditional_types_map: Dict[str, ConditionalType],
        missing_generated_types: Set[str],
        genfs_rules: List[Rule],
        version: Optional[str],
    ) -> List[Rule]:
        def type_redirect(t: str):
            return ConditionalTypeRedirect(
                t,
                conditional_types_map,
                missing_generated_types,
            )

        version_suffix = None
        if version is not None:
            version = version.replace('.', '_')
            version_suffix = f'_{version}'

        # Skip comments and empty lines
        if not is_valid_cil_line(line):
            return []

        parts = unpack_line(line, '(', ')', ' ')
        if not parts:
            return []

        assert isinstance(parts[0], str), line

        # Remove rules that don't have a meaningful source mapping
        if parts[0] in unknown_rule_types:
            return []

        # Remove allow $3 $1:process sigchld as it is part of an ifelse
        # statement based on one of the parameters and it is not possible
        # to generate the checks for it as part of macro expansion
        if is_allow_process_sigchld(parts):
            return []

        varargs: List[str] = []

        match parts[0]:
            case (
                RuleType.ALLOW.value
                | RuleType.NEVERALLOW.value
                | RuleType.AUDITALLOW.value
                | RuleType.DONTAUDIT.value
            ):
                # (allow a b (c (...)))
                assert len(parts) == 4, line
                assert len(parts[3]) == 2, line
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], str), line
                assert isinstance(parts[3][0], str), line
                assert isinstance(parts[3][1], list), line

                for part in parts[3][1]:
                    assert isinstance(part, str), line
                    varargs.append(part)

                src = remove_type_suffix(version_suffix, parts[1])
                if is_type_generated(src):
                    src = type_redirect(src)

                dst = remove_type_suffix(version_suffix, parts[2])
                if is_type_generated(dst):
                    dst = type_redirect(dst)

                rule = Rule(
                    parts[0],
                    (src, dst, parts[3][0]),
                    tuple(varargs),
                )
                return [rule]
            case (
                CilRuleType.ALLOWX.value
                | CilRuleType.NEVERALLOWX.value
                | CilRuleType.DONTAUDITX.value
            ):
                # (allowx a b (ioctl c (... (range . .) ((range . .)))))
                assert len(parts) == 4, line
                assert len(parts[3]) == 3, line
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], str), line
                assert isinstance(parts[3], list), line
                assert isinstance(parts[3][0], str), line
                assert parts[3][0] == 'ioctl', line
                assert isinstance(parts[3][1], str), line
                assert isinstance(parts[3][2], list), line

                for ioctl in unpack_ioctls(parts[3][2]):
                    varargs.append(ioctl)

                src = remove_type_suffix(version_suffix, parts[1])
                if is_type_generated(src):
                    src = type_redirect(src)

                dst = remove_type_suffix(version_suffix, parts[2])
                if is_type_generated(dst):
                    dst = type_redirect(dst)

                if parts[0] == CilRuleType.ALLOWX.value:
                    rule_type = RuleType.ALLOWXPERM.value
                elif parts[0] == CilRuleType.NEVERALLOWX.value:
                    rule_type = RuleType.NEVERALLOWXPERM.value
                elif parts[0] == CilRuleType.DONTAUDITX.value:
                    rule_type = RuleType.DONTAUDITXPERM.value
                else:
                    assert False, line

                rule = Rule(
                    rule_type,
                    (src, dst, parts[3][1]),
                    tuple(varargs),
                )
                return [rule]
            case CilRuleType.TYPEATTRIBUTE.value:
                # (typeattribute a)
                assert len(parts) == 2, line
                assert isinstance(parts[1], str), line

                # Remove generated typeattribute as they do not map to a source
                # rule
                if is_type_generated(parts[1]):
                    return []

                t = remove_type_suffix(version_suffix, parts[1])

                # Rename typeattribute to attribute to match source
                # typeattribute rules in source expand to typeattributeset,
                # while attribute rules expand to typeattribute
                rule = Rule(
                    RuleType.ATTRIBUTE.value,
                    (t,),
                    (),
                )
                return [rule]
            case CilRuleType.TYPEATTRIBUTESET.value:
                assert isinstance(parts[1], str), line
                v = remove_type_suffix(version_suffix, parts[1])

                # Process conditional types and add them to a map to be replaced
                # into the other rules later
                if is_conditional_typeattr(parts[2]):
                    assert isinstance(parts[2], list)

                    conditional_type = create_conditional_type(
                        version_suffix,
                        parts[2],
                    )
                    if conditional_type is None:
                        return []

                    assert v not in conditional_types_map, line
                    conditional_types_map[v] = conditional_type
                    return []

                # Expand typeattributeset into multiple typeattribute rules
                expanded_rules: List[Rule] = []

                for t in parts[2]:
                    assert isinstance(t, str), line
                    t = remove_type_suffix(version_suffix, t)

                    rule = Rule(
                        RuleType.TYPEATTRIBUTE.value,
                        (t, v),
                        (),
                    )
                    expanded_rules.append(rule)

                return expanded_rules
            case RuleType.GENFSCON.value:
                # (genfscon sysfs /kernel/aov (u object_r sysfs_adspd ((s0) (s0))))
                assert len(parts) == 4, line
                assert len(parts[3]) == 4, line
                assert len(parts[3][3]) == 2, line
                assert len(parts[3][3][0]) == 1, line
                assert len(parts[3][3][1]) == 1, line
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], str), line
                assert isinstance(parts[3][2], str), line
                assert len(parts[2]) > 0, line

                # Remove optional quotes
                if parts[2][0] == '"':
                    assert len(parts[2]) > 2, line
                    assert parts[2][-1] == '"'
                    parts[2] = parts[2][1:-1]

                rule = Rule(
                    parts[0],
                    (parts[1], parts[2], parts[3][2]),
                    (),
                )
                genfs_rules.append(rule)
                return []
            case CilRuleType.TYPETRANSITION.value:
                # (typetransition a b c d)
                # (typetransition a b c "[userfaultfd]" d)
                assert len(parts) in [5, 6], line
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], str), line
                assert isinstance(parts[3], str), line
                assert isinstance(parts[-1], str), line

                if len(parts) == 6:
                    assert isinstance(parts[4], str), line
                    # assert parts[4] == '"[userfaultfd]"', line
                    varargs = [parts[4]]
                else:
                    varargs = []

                src = remove_type_suffix(version_suffix, parts[1])
                if is_type_generated(src):
                    src = type_redirect(src)

                dst = remove_type_suffix(version_suffix, parts[2])
                if is_type_generated(dst):
                    src = type_redirect(dst)

                rule = Rule(
                    RuleType.TYPE_TRANSITION.value,
                    (src, dst, parts[3], parts[-1]),
                    tuple(varargs),
                )
                return [rule]
            case CilRuleType.EXPANDTYPEATTRIBUTE.value:
                # (expandtypeattribute (a) true)
                assert len(parts) == 3, line
                assert isinstance(parts[1], list), line
                assert len(parts[1]) == 1, line
                assert isinstance(parts[1][0], str), line
                assert isinstance(parts[2], str), line

                rule = Rule(
                    RuleType.EXPANDATTRIBUTE.value,
                    (parts[1][0], parts[2]),
                    (),
                )
                return [rule]
            case _:
                assert False, line
