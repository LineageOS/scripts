# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Callable, Dict, FrozenSet, List, Optional, Set, Tuple, cast

from sepolicy.classmap import Classmap
from sepolicy.conditional_type import ConditionalType
from sepolicy.rule import (
    Rule,
    RuleType,
    is_type_generated,
    raw_part,
    raw_parts_list,
    unpack_line,
)
from sepolicy.varargs import Ioctls, OrderedPerms, Perms, TypeTransitionTag
from utils.utils import Color, color_print

CIL_COMMENT_MARKER = ';'


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


def unpack_ioctls(parts: raw_parts_list):
    # (. (range . .) ((range . .)))

    ranges: List[Tuple[int, int]] = []

    def collect(items: raw_parts_list):
        for part in items:
            if isinstance(part, str):
                ioctl = int(part, base=16)
                ranges.append((ioctl, ioctl))
                continue

            assert isinstance(part, list), parts

            if part[0] == 'range':
                assert isinstance(part[1], str), parts
                start_ioctl = int(part[1], base=16)

                assert isinstance(part[2], str), parts
                end_ioctl = int(part[2], base=16)

                ranges.append((start_ioctl, end_ioctl))
                continue

            # A nested list of values / ranges - flatten it.
            collect(part)

    collect(parts)

    return Ioctls(ranges)


class CilRuleType:
    ALLOWX = 'allowx'
    AUDITALLOWX = 'auditallowx'
    NEVERALLOWX = 'neverallowx'
    DONTAUDITX = 'dontauditx'
    EXPANDTYPEATTRIBUTE = 'expandtypeattribute'
    TYPEATTRIBUTE = 'typeattribute'
    TYPEATTRIBUTESET = 'typeattributeset'
    TYPETRANSITION = 'typetransition'
    COMMON = 'common'
    CLASSCOMMON = 'classcommon'
    CLASS = 'class'


CIL_CLASSPERM_TYPES = {
    CilRuleType.COMMON,
    CilRuleType.CLASSCOMMON,
    CilRuleType.CLASS,
}


CIL_XPERM_RULE_MAP = {
    CilRuleType.ALLOWX: RuleType.ALLOWXPERM,
    CilRuleType.AUDITALLOWX: RuleType.AUDITALLOWXPERM,
    CilRuleType.NEVERALLOWX: RuleType.NEVERALLOWXPERM,
    CilRuleType.DONTAUDITX: RuleType.DONTAUDITXPERM,
}

unknown_rule_types: Set[str] = set(
    [
        'category',
        'categoryorder',
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


class CilRuleParser:
    def __init__(
        self,
        conditional_types_map: Dict[str, ConditionalType],
        reference_conditional_types_maps: List[Dict[str, ConditionalType]],
        add_rule: Callable[[Rule], None],
        add_genfs_rule: Optional[Callable[[Rule], None]],
        version: Optional[str],
        allowed_types: Optional[FrozenSet[str]] = None,
        disallowed_types: Optional[FrozenSet[str]] = None,
        classmap: Optional[Classmap] = None,
    ):
        self.conditional_types_map = conditional_types_map
        self.reference_conditional_types_maps = reference_conditional_types_maps
        self.add_rule = add_rule
        self.add_genfs_rule = add_genfs_rule
        self.allowed_types = allowed_types
        self.disallowed_types = disallowed_types
        self.classmap = classmap

        self.version_suffix = ''
        if version is not None:
            version = version.replace('.', '_')
            self.version_suffix = f'_{version}'

    def conditional_type_by_name(self, name: str):
        if name in self.conditional_types_map:
            return self.conditional_types_map[name]

        for m in self.reference_conditional_types_maps:
            if name in m:
                return m[name]

        assert False, f'Failed to find conditional type: {name}'

    def prepare_type(self, name: str):
        name = name.removesuffix(self.version_suffix)
        if is_type_generated(name):
            return self.conditional_type_by_name(name)

        return name

    def parse_line(
        self,
        line: str,
        parts: raw_parts_list,
    ):
        rule_type = parts[0]
        assert isinstance(rule_type, str), line

        if (
            self.allowed_types is not None
            and rule_type not in self.allowed_types
        ):
            return

        if (
            self.disallowed_types is not None
            and rule_type in self.disallowed_types
        ):
            return

        # Remove rules that don't have a meaningful source mapping
        if rule_type in unknown_rule_types:
            return

        match rule_type:
            case (
                RuleType.ALLOW
                | RuleType.NEVERALLOW
                | RuleType.AUDITALLOW
                | RuleType.DONTAUDIT
            ):
                # Remove allow $3 $1:process sigchld as it is part of an ifelse
                # statement based on one of the parameters and it is not
                # possible to generate the checks for it as part of macro
                # expansion
                # TODO: implement this properly by allowing macros to have
                # conditional rules based on input params
                if len(parts) == 4 and parts[3] == ['process', ['sigchld']]:
                    return

                # (allow a b (c (...)))
                assert len(parts) == 4, line
                assert len(parts[3]) == 2, line
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], str), line
                assert isinstance(parts[3][0], str), line
                assert isinstance(parts[3][1], list), line

                src = self.prepare_type(parts[1])
                dst = self.prepare_type(parts[2])
                class_name = parts[3][0]

                perms = cast(List[str], parts[3][1])
                is_all = False
                if self.classmap is not None:
                    class_perms = self.classmap.class_perms(class_name)

                    is_all = perms == class_perms
                    if not is_all:
                        assert frozenset(perms) != frozenset(class_perms)

                rule = Rule(
                    rule_type,
                    (src, dst, class_name),
                    Perms(perms, is_all),
                )
                self.add_rule(rule)
            case (
                CilRuleType.ALLOWX
                | CilRuleType.AUDITALLOWX
                | CilRuleType.NEVERALLOWX
                | CilRuleType.DONTAUDITX
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

                src = self.prepare_type(parts[1])
                dst = self.prepare_type(parts[2])

                rule = Rule(
                    CIL_XPERM_RULE_MAP[rule_type],
                    (src, dst, parts[3][1], parts[3][0]),
                    unpack_ioctls(parts[3][2]),
                )
                self.add_rule(rule)
            case CilRuleType.TYPEATTRIBUTE:
                # (typeattribute a)
                assert len(parts) == 2, line
                assert isinstance(parts[1], str), line

                # Remove generated typeattribute as they do not map to a source
                # rule
                if is_type_generated(parts[1]):
                    return

                t = parts[1].removesuffix(self.version_suffix)

                # Rename typeattribute to attribute to match source
                # typeattribute rules in source expand to typeattributeset,
                # while attribute rules expand to typeattribute
                rule = Rule(
                    RuleType.ATTRIBUTE,
                    (t,),
                )
                self.add_rule(rule)
            case CilRuleType.TYPEATTRIBUTESET:
                assert isinstance(parts[1], str), line
                v = parts[1].removesuffix(self.version_suffix)

                # Process conditional types and add them to a map to be replaced
                # into the other rules later
                if is_conditional_typeattr(parts[2]):
                    assert isinstance(parts[2], list)

                    conditional_type = create_conditional_type(
                        self.version_suffix,
                        parts[2],
                    )
                    if conditional_type is None:
                        return

                    assert v not in self.conditional_types_map, line
                    self.conditional_types_map[v] = conditional_type
                    return

                # Expand typeattributeset into multiple typeattribute rules
                for t in parts[2]:
                    assert isinstance(t, str), line
                    t = t.removesuffix(self.version_suffix)
                    rule = Rule(
                        RuleType.TYPEATTRIBUTE,
                        (t, v),
                    )
                    self.add_rule(rule)
            case RuleType.GENFSCON:
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
                )
                assert self.add_genfs_rule is not None
                self.add_genfs_rule(rule)
            case CilRuleType.TYPETRANSITION:
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
                    tag = TypeTransitionTag(parts[4])
                else:
                    tag = None

                src = self.prepare_type(parts[1])
                dst = self.prepare_type(parts[2])

                rule = Rule(
                    RuleType.TYPE_TRANSITION,
                    (src, dst, parts[3], parts[-1]),
                    tag,
                )
                self.add_rule(rule)
            case CilRuleType.EXPANDTYPEATTRIBUTE:
                # (expandtypeattribute (a) true)
                assert len(parts) == 3, line
                assert isinstance(parts[1], list), line
                assert len(parts[1]) == 1, line
                assert isinstance(parts[1][0], str), line
                assert isinstance(parts[2], str), line

                attr = parts[1][0].removesuffix(self.version_suffix)

                rule = Rule(
                    RuleType.EXPANDATTRIBUTE,
                    (attr, parts[2]),
                )
                self.add_rule(rule)
            case RuleType.TYPE:
                assert len(parts) == 2
                assert isinstance(parts[1], str)

                t = parts[1].removesuffix(self.version_suffix)

                rule = Rule(
                    rule_type,
                    (t,),
                )
                self.add_rule(rule)
            case CilRuleType.COMMON | CilRuleType.CLASS:
                assert len(parts) == 3, line
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], list), line

                perms = cast(List[str], parts[2])
                rule = Rule(
                    rule_type,
                    (parts[1],),
                    OrderedPerms(perms),
                )
                self.add_rule(rule)
            case CilRuleType.CLASSCOMMON:
                assert len(parts) == 3, line
                assert isinstance(parts[1], str), line
                assert isinstance(parts[2], str), line
                rule = Rule(
                    rule_type,
                    (
                        parts[1],
                        parts[2],
                    ),
                )
                self.add_rule(rule)
            case _:
                assert False, line
