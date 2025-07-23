# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from sepolicy.class_set import ClassSet
from sepolicy.classmap import Classmap
from sepolicy.conditional_type import ConditionalType
from sepolicy.match_extract import (
    args_type,
    merge_arg_values,
    rule_extract_part,
    rule_extract_part_iter,
)
from sepolicy.match_replace import rule_replace_part_iter
from sepolicy.rule import (
    ALLOW_RULE_TYPES,
    CLASS_SETS_RULE_TYPES,
    IOCTL_RULE_TYPES,
    Rule,
    RuleType,
    rule_hash_value,
    rule_part,
    rule_sort_key,
)
from utils.mld import MultiLevelDict
from utils.utils import Color, color_print


class RuleMatch:
    def __init__(
        self,
        macro_name: str,
        rules: Set[Rule] = set(),
        arg_values: args_type = {},
    ):
        self.macro_name = macro_name
        self.rules = rules
        self.arg_values = arg_values
        self.hash_values = tuple(
            [
                self.macro_name,
                frozenset(self.arg_values.items()),
                frozenset(rules),
            ]
        )
        self.hash = hash(self.hash_values)

        args = tuple(arg_values[k] for k in sorted(arg_values.keys()))
        self.macro = Rule(macro_name, args, (), is_macro=True)

    def filled_args(self):
        return self.arg_values.keys()

    def __hash__(self):
        return self.hash

    def __eq__(self, other: object):
        assert isinstance(other, RuleMatch)

        return self.hash_values == other.hash_values

    def __str__(self):
        return str(self.macro)


def rule_match_keys(rule: Rule, is_match_keys_full: bool):
    match_keys: List[Optional[rule_hash_value]] = [rule.rule_type]

    for part in rule.parts:
        # A fully filled rule doesn't need to have its parts tested
        # to check if they need to be filled
        if is_match_keys_full:
            match_keys.append(part)
            continue

        # Match part to itself to see if it has any args
        part_args_values = rule_extract_part(part, part)

        if part_args_values:
            match_keys.append(None)
        else:
            match_keys.append(part)

    match_keys.append(rule.varargs_hash_value)

    return match_keys


def rule_fill(rule: Rule, arg_values: args_type):
    new_parts = rule_replace_part_iter(rule.parts, arg_values)
    if new_parts is None:
        return None

    return Rule(rule.rule_type, tuple(new_parts), rule.varargs)


def match_macro_rule(
    mld: MultiLevelDict[Rule],
    macro_rule: Rule,
    rule_matches: Set[RuleMatch],
):
    print(f'Processing rule: {macro_rule}')

    macro_rule_args = rule_extract_part_iter(
        macro_rule.parts,
        macro_rule.parts,
    )
    assert macro_rule_args is not None

    # Check if this rule requires only already completed args
    rule_match = next(iter(rule_matches))
    is_match_keys_full = macro_rule_args.keys() <= rule_match.filled_args()

    new_rule_matches: Set[RuleMatch] = set()
    for rule_match in rule_matches:
        # TODO: make rule args extraction build a path that can be used for
        # filling no matter the args
        filled_rule = rule_fill(macro_rule, rule_match.arg_values)
        if filled_rule is None:
            continue

        match_keys = rule_match_keys(filled_rule, is_match_keys_full)
        for matched_rule in mld.match(match_keys):
            if is_match_keys_full:
                # If the rule is fully filled don't expand the args
                new_args_values = {}
            else:
                new_args_values = rule_extract_part_iter(
                    filled_rule.parts,
                    matched_rule.parts,
                )

            new_arg_values = merge_arg_values(
                rule_match.arg_values,
                new_args_values,
            )
            if new_arg_values is None:
                continue

            new_rules = rule_match.rules.copy()
            new_rules.add(matched_rule)

            new_rule_match = RuleMatch(
                rule_match.macro_name,
                new_rules,
                new_arg_values,
            )
            new_rule_matches.add(new_rule_match)

    return new_rule_matches


def match_macro_rules(
    mld: MultiLevelDict[Rule],
    macro_name: str,
    macro_rules: List[Rule],
    all_rule_matches: Set[RuleMatch],
):
    print(f'Processing macro: {macro_name}')

    rule_matches: Set[RuleMatch] = set([RuleMatch(macro_name)])
    for macro_rule in macro_rules:
        new_rule_matches = match_macro_rule(
            mld,
            macro_rule,
            rule_matches,
        )
        print(f'Found {len(new_rule_matches)} candidates')
        if not len(new_rule_matches):
            print()
            return

        rule_matches = new_rule_matches

    all_rule_matches.update(rule_matches)

    print(f'Found {len(rule_matches)} macro calls')
    print()


def replace_macro_rules(
    mld: MultiLevelDict[Rule],
    all_rule_matches: Set[RuleMatch],
):
    color_print(
        f'All macros: {len(all_rule_matches)}',
        color=Color.GREEN,
    )

    rule_matches_map: Dict[Rule, Set[RuleMatch]] = {}
    for rule_match in all_rule_matches:
        for rule in rule_match.rules:
            if rule not in rule_matches_map:
                rule_matches_map[rule] = set()
            rule_matches_map[rule].add(rule_match)

    discarded_rule_matches: Set[RuleMatch] = set()

    for rule_match in all_rule_matches:
        candidate_supersets: Optional[Set[RuleMatch]] = None

        for rule in rule_match.rules:
            rule_matches = rule_matches_map[rule]

            if candidate_supersets is None:
                candidate_supersets = set(rule_matches)
            else:
                candidate_supersets = candidate_supersets & rule_matches

        assert candidate_supersets is not None

        candidate_supersets.remove(rule_match)

        for candidate in candidate_supersets:
            if rule_match.rules > candidate.rules:
                continue

            if rule_match.rules == candidate.rules and len(
                rule_match.arg_values
            ) < len(candidate.arg_values):
                continue

            discarded_rule_matches.add(rule_match)
            break

    color_print(
        f'Discarded subset macros: {len(discarded_rule_matches)}',
        color=Color.GREEN,
    )

    for rule_match in discarded_rule_matches:
        all_rule_matches.remove(rule_match)

    removed_rules = 0
    double_removed_rules: Set[Rule] = set()
    for rule_match in all_rule_matches:
        for rule in rule_match.rules:
            try:
                mld.remove(rule.hash_values, rule)
                removed_rules += 1
            except KeyError:
                double_removed_rules.add(rule)

        rule = rule_match.macro
        mld.add(rule.hash_values, rule)

    for rule in sorted(double_removed_rules, key=rule_sort_key):
        color_print(
            f'Rule already removed: {rule}',
            color=Color.YELLOW,
        )

    color_print(
        f'Replaced {removed_rules} rules with {len(all_rule_matches)} macros',
        color=Color.GREEN,
    )


def remove_platform_rules(mld: MultiLevelDict[Rule], rules: List[Rule]):
    removed_rules = 0
    for rule in rules:
        try:
            mld.remove(rule.hash_values, rule)
            removed_rules += 1
        except KeyError:
            pass

    color_print(
        f'Removed {removed_rules} platform rules',
        color=Color.GREEN,
    )


def merge_typeattribute_rules(mld: MultiLevelDict[Rule]):
    types: Dict[str, Set[str]] = {}

    removed_rules: Set[Rule] = set()
    match_keys: Tuple[Optional[rule_hash_value], ...] = (
        RuleType.TYPEATTRIBUTE.value,
        None,
        None,
        frozenset(),
    )
    for rule in mld.match(match_keys):
        t = rule.parts[0]
        v = rule.parts[1]

        assert isinstance(t, str)
        assert isinstance(v, str)

        if t not in types:
            types[t] = set()
        types[t].add(v)

        removed_rules.add(rule)

    for rule in removed_rules:
        mld.remove(rule.hash_values, rule)

    for t, values in types.items():
        new_rule = Rule(
            RuleType.TYPE.value,
            (t,),
            tuple(values),
        )
        mld.add(new_rule.hash_values, new_rule)

    color_print(
        f'Merged {len(removed_rules)} typeattributes into {len(types)} types',
        color=Color.GREEN,
    )


def merge_ioctl_rules(mld: MultiLevelDict[Rule]):
    rules_dict: Dict[Tuple[rule_part, ...], Set[Rule]] = {}
    for rule_type in IOCTL_RULE_TYPES:
        match_tuple = (rule_type.value, None, None, None, None)
        for matched_rule in mld.match(match_tuple):
            # Keep varargs out of the key
            key = (matched_rule.rule_type, *matched_rule.parts)

            if key not in rules_dict:
                rules_dict[key] = set()

            rules_dict[key].add(matched_rule)

    removed_rules = 0
    added_rules = 0
    for rules in rules_dict.values():
        if len(rules) == 1:
            continue

        merged_varargs: Set[str] = set()
        for rule in rules:
            mld.remove(rule.hash_values, rule)
            merged_varargs.update(rule.varargs)
            removed_rules += 1

        matched_rule = next(iter(rules))
        new_rule = Rule(
            matched_rule.rule_type,
            matched_rule.parts,
            tuple(sorted(merged_varargs)),
        )
        mld.add(new_rule.hash_values, new_rule)
        added_rules += 1

    color_print(
        f'Merged {removed_rules} rules into {added_rules} ioctl rules',
        color=Color.GREEN,
    )


def replace_perms_set(
    perms: List[Tuple[str, Set[str]]],
    class_all_perms: Set[str],
    rule_varargs_set: Set[str],
):
    if class_all_perms == rule_varargs_set:
        return set(['*'])

    varargs_set = rule_varargs_set
    for name, caps in perms:
        if caps <= varargs_set:
            varargs_set = varargs_set - caps
            varargs_set.add(name)
            # TODO: find out if there are cases of multiple
            # perms
            break

    return varargs_set


def replace_type_perm(
    mld: MultiLevelDict[Rule],
    classmap: Classmap,
    perms: List[Tuple[str, Set[str]]],
    classes: List[str],
    removed_rules: Set[Rule],
    added_rules: Set[Rule],
):
    for rule_type in ALLOW_RULE_TYPES:
        for c in classes:
            match_tuple = (rule_type.value, None, None, c, None)
            class_all_perms = set(classmap.class_perms(c))

            for matched_rule in mld.match(match_tuple):
                rule_varargs_set = set(matched_rule.varargs)
                varargs_set = replace_perms_set(
                    perms,
                    class_all_perms,
                    rule_varargs_set,
                )

                if varargs_set == rule_varargs_set:
                    continue

                new_rule = Rule(
                    matched_rule.rule_type,
                    matched_rule.parts,
                    tuple(sorted(varargs_set)),
                )
                added_rules.add(new_rule)
                removed_rules.add(matched_rule)


def replace_perms(
    mld: MultiLevelDict[Rule],
    classmap: Classmap,
    all_perms: List[Tuple[str, Set[str]]],
):
    file_classes = list(classmap.class_types('file'))
    dir_classes = list(classmap.class_types('dir'))
    socket_classes = list(classmap.class_types('socket'))

    file_perms: List[Tuple[str, Set[str]]] = []
    dir_perms: List[Tuple[str, Set[str]]] = []
    socket_perms: List[Tuple[str, Set[str]]] = []

    for perm in all_perms:
        name = perm[0]

        if '_file_' in name:
            file_perms.append(perm)
        elif '_dir_' in name:
            dir_perms.append(perm)
        elif '_socket_' in name:
            socket_perms.append(perm)
        elif '_ipc_' in name:
            # _ipc_ perms are unused, don't bother
            continue
        else:
            assert False, perm

    removed_rules: Set[Rule] = set()
    added_rules: Set[Rule] = set()

    def _replace_type_perm(
        perms: List[Tuple[str, Set[str]]],
        classes: List[str],
    ):
        replace_type_perm(
            mld,
            classmap,
            perms,
            classes,
            removed_rules,
            added_rules,
        )

    _replace_type_perm(file_perms, file_classes)
    _replace_type_perm(dir_perms, dir_classes)
    _replace_type_perm(socket_perms, socket_classes)

    for rule in removed_rules:
        mld.remove(rule.hash_values, rule)

    for rule in added_rules:
        mld.add(rule.hash_values, rule)

    color_print(
        f'Replaced perm macros in {len(removed_rules)} rules',
        color=Color.GREEN,
    )


def replace_ioctls(
    mld: MultiLevelDict[Rule],
    ioctls: List[Tuple[str, Set[str]]],
    ioctl_defines: Dict[str, str],
):
    removed_rules: Set[Rule] = set()
    added_rules: Set[Rule] = set()

    for rule_type in IOCTL_RULE_TYPES:
        match_tuple = (rule_type.value, None, None, None, None)
        for matched_rule in mld.match(match_tuple):
            rule_varargs_set = set(matched_rule.varargs)

            varargs_set = rule_varargs_set
            for name, values in ioctls:
                if values <= varargs_set:
                    varargs_set = varargs_set - values
                    varargs_set.add(name)

            added_ioctls: Set[str] = set()
            removed_ioctls: Set[str] = set()
            for value in varargs_set:
                if value in ioctl_defines:
                    removed_ioctls.add(value)
                    added_ioctls.add(ioctl_defines[value])

            if added_ioctls or removed_ioctls:
                varargs_set = varargs_set - removed_ioctls
                varargs_set = varargs_set | added_ioctls

            if varargs_set == rule_varargs_set:
                continue

            new_rule = Rule(
                matched_rule.rule_type,
                matched_rule.parts,
                tuple(sorted(varargs_set)),
            )
            added_rules.add(new_rule)
            removed_rules.add(matched_rule)

    for rule in removed_rules:
        mld.remove(rule.hash_values, rule)

    for rule in added_rules:
        mld.add(rule.hash_values, rule)

    color_print(
        f'Replaced ioctl macros in {len(removed_rules)} rules',
        color=Color.GREEN,
    )


def merge_class_set_rule_type(
    mld: MultiLevelDict[Rule],
    rule_type: RuleType,
    class_sets: List[Tuple[str, Set[str]]],
):
    rules_dict: Dict[
        Tuple[rule_hash_value, ...],
        Tuple[Set[str], Set[Rule]],
    ] = {}

    match_tuple = (rule_type.value, None, None, None, None)
    for matched_rule in mld.match(match_tuple):
        # Keep class out of the key
        key = (
            matched_rule.rule_type,
            matched_rule.parts[0],
            matched_rule.parts[1],
            matched_rule.varargs_hash_value,
        )
        if key not in rules_dict:
            rules_dict[key] = (set(), set())

        # Gather all matched classes
        matched_cls = matched_rule.parts[2]
        assert isinstance(matched_cls, str)
        rules_dict[key][0].add(matched_cls)
        rules_dict[key][1].add(matched_rule)

    removed_rules = 0
    added_rules = 0

    for matched_classes, rules in rules_dict.values():
        if len(matched_classes) == 1:
            continue

        new_classes = matched_classes
        for name, classes in class_sets:
            if classes <= new_classes:
                new_classes = new_classes - classes
                new_classes.add(name)

        for rule in rules:
            mld.remove(rule.hash_values, rule)
            removed_rules += 1

        matched_rule = next(iter(rules))
        new_rule = Rule(
            matched_rule.rule_type,
            tuple(
                [
                    matched_rule.parts[0],
                    matched_rule.parts[1],
                    ClassSet(sorted(new_classes)),
                ]
            ),
            matched_rule.varargs,
        )
        mld.add(new_rule.hash_values, new_rule)
        added_rules += 1

    return removed_rules, added_rules


def merge_class_sets(
    mld: MultiLevelDict[Rule],
    class_sets: List[Tuple[str, Set[str]]],
):
    removed_rules = 0
    added_rules = 0
    for rule_type in CLASS_SETS_RULE_TYPES:
        new_removed_rules, new_added_rules = merge_class_set_rule_type(
            mld,
            rule_type,
            class_sets,
        )
        removed_rules += new_removed_rules
        added_rules += new_added_rules

    color_print(
        f'Merged {removed_rules} rules into {added_rules} class set rules',
        color=Color.GREEN,
    )


def merge_target_domains_rule_type(
    mld: MultiLevelDict[Rule],
    rule_type: RuleType,
):
    rules_dict: Dict[
        Tuple[rule_hash_value, ...],
        Tuple[Set[str], Set[Rule]],
    ] = {}

    match_tuple = (rule_type.value, None, None, None, None)
    for matched_rule in mld.match(match_tuple):
        # Conditional types cannot be merged into another conditional type
        if not isinstance(matched_rule.parts[1], str):
            continue

        # Keep target domain out of the key
        key = (
            matched_rule.rule_type,
            matched_rule.parts[0],
            matched_rule.parts[2],
            matched_rule.varargs_hash_value,
        )

        if key not in rules_dict:
            rules_dict[key] = (set(), set())

        # Gather all target domains
        target_domains = matched_rule.parts[1]
        rules_dict[key][0].add(target_domains)
        rules_dict[key][1].add(matched_rule)

    removed_rules = 0
    added_rules = 0

    for matched_target_domains, rules in rules_dict.values():
        if len(matched_target_domains) == 1:
            continue

        for rule in rules:
            mld.remove(rule.hash_values, rule)
            removed_rules += 1

        matched_rule = next(iter(rules))
        target_domain = ConditionalType(
            sorted(matched_target_domains),
            [],
            False,
        )
        new_rule = Rule(
            matched_rule.rule_type,
            tuple(
                [
                    matched_rule.parts[0],
                    target_domain,
                    matched_rule.parts[2],
                ]
            ),
            matched_rule.varargs,
        )
        mld.add(new_rule.hash_values, new_rule)
        added_rules += 1

    return removed_rules, added_rules


def merge_target_domains(mld: MultiLevelDict[Rule]):
    removed_rules = 0
    added_rules = 0
    for rule_type in CLASS_SETS_RULE_TYPES:
        new_removed_rules, new_added_rules = merge_target_domains_rule_type(
            mld,
            rule_type,
        )
        removed_rules += new_removed_rules
        added_rules += new_added_rules

    color_print(
        f'Merged {removed_rules} rules into {added_rules} with target domains',
        color=Color.GREEN,
    )
