# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from sepolicy.class_set import ClassSet
from sepolicy.classmap import Classmap
from sepolicy.macro import ioctl_type_name
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
)
from sepolicy.rule_container import RuleContainer
from utils.utils import Color, color_print


class RuleMatch:
    def __init__(
        self,
        macro_name: str,
        rules: List[Rule] = [],
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
    rules: RuleContainer,
    macro_rule: Rule,
    macro_rule_args: args_type,
    rule_match: RuleMatch,
    verbose: bool,
):
    if verbose:
        print(f'Processing rule: {macro_rule}')

    # Check if this rule requires only already completed args
    is_match_keys_full = macro_rule_args.keys() <= rule_match.filled_args()

    new_rule_matches: List[RuleMatch] = []
    if verbose:
        print(f'Processing rule match: {rule_match}')

    # TODO: make rule args extraction build a path that can be used for
    # filling no matter the args
    filled_rule = rule_fill(macro_rule, rule_match.arg_values)
    if verbose:
        print(f'Constructed filled rule: {filled_rule}')
    if filled_rule is None:
        return new_rule_matches

    match_keys = rule_match_keys(filled_rule, is_match_keys_full)
    if verbose:
        match_keys_str = [
            sorted(v) if isinstance(v, frozenset) else str(v)
            for v in match_keys
        ]
        print(f'Constructed match keys: {match_keys_str}')

    for matched_rule in rules.match(match_keys):
        if verbose:
            print(f'Found matching rule: {matched_rule}')

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

        if verbose:
            arg_values_str = {
                k: str(v) for k, v in rule_match.arg_values.items()
            }
            new_arg_values_str = (
                {k: str(v) for k, v in new_args_values.items()}
                if new_args_values is not None
                else 'None'
            )
            merged_arg_values_str = (
                {k: str(v) for k, v in new_arg_values.items()}
                if new_arg_values is not None
                else 'None'
            )

            print(f'Merging arg values: {arg_values_str}')
            print(f'with: {new_arg_values_str}')
            print(f'= {merged_arg_values_str}')
            print()

        if new_arg_values is None:
            if verbose:
                print('Arg values incompatible, skip')
            continue

        new_rules = rule_match.rules.copy()
        new_rules.append(matched_rule)

        new_rule_match = RuleMatch(
            rule_match.macro_name,
            new_rules,
            new_arg_values,
        )
        new_rule_matches.append(new_rule_match)

    if not new_rule_matches:
        if verbose:
            print('No matched rules')

    return new_rule_matches


def match_macro_rule_depth(
    rules: RuleContainer,
    macro_rules_args: List[Tuple[Rule, args_type]],
    rule_match: RuleMatch,
    results: List[RuleMatch],
    verbose: bool,
):
    if not macro_rules_args:
        results.append(rule_match)
        return

    macro_rule, macro_rule_args = macro_rules_args[0]

    next_matches = match_macro_rule(
        rules,
        macro_rule,
        macro_rule_args,
        rule_match,
        verbose,
    )

    if not next_matches:
        return

    for next_match in next_matches:
        match_macro_rule_depth(
            rules,
            macro_rules_args[1:],
            next_match,
            results,
            verbose,
        )


def match_macro_rules(
    rules: RuleContainer,
    macro_name: str,
    macro_rules_args: List[Tuple[Rule, args_type]],
    all_rule_matches: List[RuleMatch],
    verbose: bool,
):
    if verbose:
        print(f'Processing macro: {macro_name}')
        for macro_rule, _ in macro_rules_args:
            print(macro_rule)
        print()

    rule_matches: List[RuleMatch] = []

    match_macro_rule_depth(
        rules,
        macro_rules_args,
        RuleMatch(macro_name),
        rule_matches,
        verbose,
    )

    all_rule_matches.extend(rule_matches)

    if verbose:
        print(f'Found {len(rule_matches)} macro calls')
        for rule_match in rule_matches:
            print(rule_match)
        print()


def match_macros_rules(
    rules: RuleContainer,
    macros_name_rules: List[Tuple[str, List[Rule]]],
    verbose: bool,
):
    rule_matches: List[RuleMatch] = []

    for macro_name, macro_rules in macros_name_rules:
        macro_rules_args: List[Tuple[Rule, args_type]] = []

        for macro_rule in macro_rules:
            macro_rule_args = rule_extract_part_iter(
                macro_rule.parts,
                macro_rule.parts,
            )
            assert macro_rule_args is not None
            macro_rules_args.append((macro_rule, macro_rule_args))

        # Inside the macro, prefer rules with higher arity to help
        # the arg matching algorithm
        macro_rules_args.sort(key=lambda ma: len(ma[1]), reverse=True)

        match_macro_rules(
            rules,
            macro_name,
            macro_rules_args,
            rule_matches,
            verbose,
        )

    return rule_matches


def discard_rule_matches(
    all_rule_matches: List[RuleMatch],
    verbose: bool,
):
    color_print(
        f'All macros: {len(all_rule_matches)}',
        color=Color.GREEN,
    )

    rule_matches_map: Dict[Rule, List[RuleMatch]] = {}
    for rule_match in all_rule_matches:
        for rule in rule_match.rules:
            if rule not in rule_matches_map:
                rule_matches_map[rule] = []
            rule_matches_map[rule].append(rule_match)

    discarded_rule_matches: Set[RuleMatch] = set()

    if verbose:
        for rule, rule_matches in rule_matches_map.items():
            print(f'Rule matches for: {rule}')
            for rule_match in rule_matches:
                print(rule_match)
            print()

    for rule_match in all_rule_matches:
        if verbose:
            print(f'Finding supersets for rule match: {rule_match}')

        candidate_supersets: Optional[List[RuleMatch]] = None

        for rule in rule_match.rules:
            rule_matches = rule_matches_map[rule]

            if verbose:
                print(f'Found {len(rule_matches)} candidates for rule: {rule}')
                for r in rule_matches:
                    print(r)
                print()

            if candidate_supersets is None:
                candidate_supersets = rule_matches
            else:
                new_candidate_supersets: List[RuleMatch] = []
                for r in rule_matches:
                    if r in candidate_supersets:
                        new_candidate_supersets.append(r)
                candidate_supersets = new_candidate_supersets

        assert candidate_supersets is not None

        candidate_supersets.remove(rule_match)

        if verbose:
            print(f'Found {len(candidate_supersets)} candidates')
            for candidate in candidate_supersets:
                print(candidate)
            print()

        rules_set = set(rule_match.rules)
        for candidate in candidate_supersets:
            candidate_rules_set = set(candidate.rules)

            if rules_set > candidate_rules_set:
                continue

            if rules_set == candidate_rules_set and len(
                rule_match.arg_values
            ) < len(candidate.arg_values):
                continue

            if verbose:
                print(f'Discarding {rule_match}')
                print(f'in favor of {candidate}')

            discarded_rule_matches.add(rule_match)
            break

        if verbose:
            print()

    color_print(
        f'Discarded subset macros: {len(discarded_rule_matches)}',
        color=Color.GREEN,
    )

    new_rule_matches: List[RuleMatch] = []
    for rule_match in all_rule_matches:
        if rule_match not in discarded_rule_matches:
            new_rule_matches.append(rule_match)

    return new_rule_matches


def replace_macro_rules(
    rules: RuleContainer,
    all_rule_matches: List[RuleMatch],
    name: str,
    verbose: bool,
):
    removed_rules = 0
    added_macros = 0
    for rule_match in all_rule_matches:
        if verbose:
            print(f'Removing rules for match: {rule_match}')
            for rule in rule_match.rules:
                print(rule)
            print()
        removed_count = rules.remove_many(rule_match.rules, optional=True)
        if not removed_count:
            if verbose:
                print(f'No rules left in macro: {rule_match}')
                print()
            continue

        removed_rules += removed_count
        added_macros += 1
        rule = rule_match.macro
        rules.add(rule)

    color_print(
        f'Replaced {removed_rules} rules with {added_macros} macros in {name}',
        color=Color.GREEN,
    )


def merge_typeattribute_rules(
    rules: RuleContainer,
    name: str,
):
    types: Dict[str, Set[str]] = {}

    removed_rules: Set[Rule] = set()
    match_keys: Tuple[Optional[rule_hash_value], ...] = (
        RuleType.TYPE.value,
        None,
        frozenset(),
    )

    for rule in rules.match(match_keys):
        t = rule.parts[0]
        assert isinstance(t, str)

        assert t not in types
        types[t] = set()

        removed_rules.add(rule)

    match_keys: Tuple[Optional[rule_hash_value], ...] = (
        RuleType.TYPEATTRIBUTE.value,
        None,
        None,
        frozenset(),
    )
    for rule in rules.match(match_keys):
        t = rule.parts[0]
        v = rule.parts[1]

        assert isinstance(t, str)
        assert isinstance(v, str)

        if t not in types:
            continue

        types[t].add(v)

        removed_rules.add(rule)

    for rule in removed_rules:
        rules.remove(rule)

    for t, values in types.items():
        new_rule = Rule(
            RuleType.TYPE.value,
            (t,),
            tuple(values),
        )
        rules.add(new_rule)

    color_print(
        f'Merged {len(removed_rules)} typeattributes into {len(types)} types in {name}',
        color=Color.GREEN,
    )


def flush_same_ioctl_rules(
    rules: RuleContainer,
    same_rules: list[Rule],
):
    if not same_rules:
        return 0, 0

    first = same_rules[0]

    if len(same_rules) == 1:
        rules.add(first)
        same_rules.clear()
        return 0, 0

    rules.add(
        Rule(
            first.rule_type,
            first.parts,
            tuple(v for r in same_rules for v in r.varargs),
        )
    )
    removed = len(same_rules)
    same_rules.clear()
    return removed, 1


def merge_ioctl_rule_or_add(
    rules: RuleContainer,
    same_rules: list[Rule],
    rule: Rule,
):
    if rule.rule_type not in IOCTL_RULE_TYPES:
        removed, added = flush_same_ioctl_rules(rules, same_rules)
        rules.add(rule)
        return removed, added

    if same_rules:
        first = same_rules[0]
        if rule.rule_type != first.rule_type or rule.parts != first.parts:
            removed, added = flush_same_ioctl_rules(rules, same_rules)
            same_rules.append(rule)
            return removed, added

    same_rules.append(rule)
    return 0, 0


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
    rules: RuleContainer,
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

            for matched_rule in rules.match(match_tuple):
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
    rules: RuleContainer,
    classmap: Classmap,
    all_perms: List[Tuple[str, Set[str]]],
    name: str,
):
    file_classes = list(classmap.class_types('file'))
    dir_classes = list(classmap.class_types('dir'))
    socket_classes = list(classmap.class_types('socket'))

    file_perms: List[Tuple[str, Set[str]]] = []
    dir_perms: List[Tuple[str, Set[str]]] = []
    socket_perms: List[Tuple[str, Set[str]]] = []

    for perm in all_perms:
        perm_name = perm[0]

        if '_file_' in perm_name:
            file_perms.append(perm)
        elif '_dir_' in perm_name:
            dir_perms.append(perm)
        elif '_socket_' in perm_name:
            socket_perms.append(perm)
        elif '_ipc_' in perm_name:
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
            rules,
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
        rules.remove(rule)

    for rule in added_rules:
        rules.add(rule)

    color_print(
        f'Replaced perm macros in {len(removed_rules)} rules in {name}',
        color=Color.GREEN,
    )


def replace_ioctls(
    rules: RuleContainer,
    ioctls: List[Tuple[str, Set[str]]],
    ioctl_defines: Dict[str, str],
    name: str,
    is_nlmsg: bool,
):
    removed_rules: Set[Rule] = set()
    added_rules: Set[Rule] = set()

    for rule_type in IOCTL_RULE_TYPES:
        match_tuple = (rule_type.value, None, None, None, None, None)
        for matched_rule in rules.match(match_tuple):
            ioctl_rule_type = matched_rule.parts[3]
            if ioctl_rule_type == 'ioctl':
                if is_nlmsg:
                    continue
            elif ioctl_rule_type == 'nlmsg':
                if not is_nlmsg:
                    continue
            else:
                assert False, ioctl_rule_type

            rule_varargs_set = set(matched_rule.varargs)

            varargs_set = rule_varargs_set
            for ioctl_name, values in ioctls:
                if values <= varargs_set:
                    varargs_set = varargs_set - values
                    varargs_set.add(ioctl_name)

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
        rules.remove(rule)

    for rule in added_rules:
        rules.add(rule)

    ioctl_type_name_str = ioctl_type_name(is_nlmsg)
    color_print(
        f'Replaced {ioctl_type_name_str} macros in {len(removed_rules)} rules in {name}',
        color=Color.GREEN,
    )


def merge_class_set_rule_type(
    rules: RuleContainer,
    rule_type: RuleType,
    class_sets: List[Tuple[str, Set[str]]],
):
    rules_dict: Dict[
        Tuple[rule_hash_value, ...],
        Tuple[Set[str], Set[Rule]],
    ] = {}

    match_tuple = (rule_type.value, None, None, None, None)
    for matched_rule in rules.match(match_tuple):
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
        assert isinstance(matched_cls, str), matched_rule
        rules_dict[key][0].add(matched_cls)
        rules_dict[key][1].add(matched_rule)

    removed_rules = 0
    added_rules = 0

    for matched_classes, matched_rules in rules_dict.values():
        if len(matched_classes) == 1:
            continue

        new_classes = matched_classes
        for name, classes in class_sets:
            if classes <= new_classes:
                new_classes = new_classes - classes
                new_classes.add(name)

        for rule in matched_rules:
            rules.remove(rule)
            removed_rules += 1

        matched_rule = next(iter(matched_rules))
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
        rules.add(new_rule)
        added_rules += 1

    return removed_rules, added_rules


def merge_class_sets(
    rules: RuleContainer,
    class_sets: List[Tuple[str, Set[str]]],
    name: str,
):
    removed_rules = 0
    added_rules = 0
    for rule_type in CLASS_SETS_RULE_TYPES:
        new_removed_rules, new_added_rules = merge_class_set_rule_type(
            rules,
            rule_type,
            class_sets,
        )
        removed_rules += new_removed_rules
        added_rules += new_added_rules

    color_print(
        f'Merged {removed_rules} rules into {added_rules} class set rules in {name}',
        color=Color.GREEN,
    )
