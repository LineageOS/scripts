# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from enum import StrEnum
from typing import Callable, Dict, FrozenSet, List, Optional, Set, cast

from sepolicy.conditional_type import ConditionalType
from sepolicy.rule import (
    Rule,
    RuleType,
    is_type_generated,
    raw_part,
    raw_parts_list,
    unpack_line,
)
from utils.utils import Color, color_print


def assert_parts_str_list(value: raw_parts_list, line: str) -> List[str]:
    assert isinstance(value, list), line
    assert all(isinstance(item, str) for item in value), line
    return cast(List[str], value)


def is_conditional_typeattr(part: raw_part):
    if isinstance(part[0], list):
        part = part[0][0]
    else:
        part = part[0]

    return part in ['and', 'not', 'all']


def create_conditional_type(version_suffix: str, parts: raw_parts_list):
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
            lambda t: t.removesuffix(version_suffix),
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
    AUDITALLOWX = 'auditallowx'
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
        'typealias',
        'typealiasactual',
        'typepermissive',
        'user',
        'userlevel',
        'userrange',
        'userrole',
    ]
)


def unpack_cil_line(line: str):
    # Skip comments and empty lines
    if not is_valid_cil_line(line):
        return None

    parts = unpack_line(line, '(', ')', ' ')
    if not parts:
        return None

    return parts


class CilRule(Rule):
    @classmethod
    def from_line(
        cls,
        line: str,
        parts: raw_parts_list,
        conditional_types_map: Dict[str, ConditionalType],
        add_rule: Callable[[Rule], None],
        add_genfs_rule: Optional[Callable[[Rule], None]],
        version: Optional[str],
        allowed_types: Optional[FrozenSet[str]] = None,
        disallowed_types: Optional[FrozenSet[str]] = None,
    ):
        version_suffix = ''
        if version is not None:
            version = version.replace('.', '_')
            version_suffix = f'_{version}'

        rule_type = parts[0]
        assert isinstance(rule_type, str), line

        if allowed_types is not None and rule_type not in allowed_types:
            return

        if disallowed_types is not None and rule_type in disallowed_types:
            return

        # Remove rules that don't have a meaningful source mapping
        if rule_type in unknown_rule_types:
            return

        # Remove allow $3 $1:process sigchld as it is part of an ifelse
        # statement based on one of the parameters and it is not possible
        # to generate the checks for it as part of macro expansion
        if is_allow_process_sigchld(parts):
            return

        match rule_type:
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

                src = parts[1].removesuffix(version_suffix)
                if is_type_generated(src):
                    src = conditional_types_map[src]

                dst = parts[2].removesuffix(version_suffix)
                if is_type_generated(dst):
                    dst = conditional_types_map[dst]

                perms = assert_parts_str_list(parts[3][1], line)

                rule = Rule(
                    rule_type,
                    (src, dst, parts[3][0]),
                    tuple(perms),
                )
                add_rule(rule)
            case (
                CilRuleType.ALLOWX.value
                | CilRuleType.AUDITALLOWX.value
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
                assert isinstance(parts[3][1], str), line
                assert isinstance(parts[3][2], list), line

                src = parts[1].removesuffix(version_suffix)
                if is_type_generated(src):
                    src = conditional_types_map[src]

                dst = parts[2].removesuffix(version_suffix)
                if is_type_generated(dst):
                    dst = conditional_types_map[dst]

                if rule_type == CilRuleType.ALLOWX.value:
                    rule_type = RuleType.ALLOWXPERM.value
                elif rule_type == CilRuleType.AUDITALLOWX.value:
                    rule_type = RuleType.AUDITALLOWXPERM.value
                elif rule_type == CilRuleType.NEVERALLOWX.value:
                    rule_type = RuleType.NEVERALLOWXPERM.value
                elif rule_type == CilRuleType.DONTAUDITX.value:
                    rule_type = RuleType.DONTAUDITXPERM.value
                else:
                    assert False, line

                rule = Rule(
                    rule_type,
                    (src, dst, parts[3][1], parts[3][0]),
                    tuple(unpack_ioctls(parts[3][2])),
                )
                add_rule(rule)
            case CilRuleType.TYPEATTRIBUTE.value:
                # (typeattribute a)
                assert len(parts) == 2, line
                assert isinstance(parts[1], str), line

                # Remove generated typeattribute as they do not map to a source
                # rule
                if is_type_generated(parts[1]):
                    return

                t = parts[1].removesuffix(version_suffix)

                # Rename typeattribute to attribute to match source
                # typeattribute rules in source expand to typeattributeset,
                # while attribute rules expand to typeattribute
                rule = Rule(
                    RuleType.ATTRIBUTE.value,
                    (t,),
                    (),
                )
                add_rule(rule)
            case CilRuleType.TYPEATTRIBUTESET.value:
                assert isinstance(parts[1], str), line
                v = parts[1].removesuffix(version_suffix)

                # Process conditional types and add them to a map to be replaced
                # into the other rules later
                if is_conditional_typeattr(parts[2]):
                    assert isinstance(parts[2], list)

                    conditional_type = create_conditional_type(
                        version_suffix,
                        parts[2],
                    )
                    if conditional_type is None:
                        return

                    assert v not in conditional_types_map, line
                    conditional_types_map[v] = conditional_type
                    return

                # Expand typeattributeset into multiple typeattribute rules
                for t in parts[2]:
                    assert isinstance(t, str), line
                    t = t.removesuffix(version_suffix)

                    rule = Rule(
                        RuleType.TYPEATTRIBUTE.value,
                        (t, v),
                        (),
                    )
                    add_rule(rule)
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
                    rule_type,
                    (parts[1], parts[2], parts[3][2]),
                    (),
                )
                assert add_genfs_rule is not None
                add_genfs_rule(rule)
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
                    varargs = (parts[4],)
                else:
                    varargs = tuple()

                src = parts[1].removesuffix(version_suffix)
                if is_type_generated(src):
                    src = conditional_types_map[src]

                dst = parts[2].removesuffix(version_suffix)
                if is_type_generated(dst):
                    dst = conditional_types_map[dst]

                rule = Rule(
                    RuleType.TYPE_TRANSITION.value,
                    (src, dst, parts[3], parts[-1]),
                    varargs,
                )
                add_rule(rule)
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
                add_rule(rule)
            case RuleType.TYPE.value:
                assert len(parts) == 2
                assert isinstance(parts[1], str)

                rule = Rule(
                    rule_type,
                    (parts[1],),
                    (),
                )
                add_rule(rule)
            case _:
                assert False, line
