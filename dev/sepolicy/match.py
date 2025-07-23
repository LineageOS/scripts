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
)
from utils.mld import MultiLevelDict
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


def rule_arity(rule: Rule):
    macro_rule_args = rule_extract_part_iter(
        rule.parts,
        rule.parts,
    )
    assert macro_rule_args is not None
    return len(macro_rule_args)


def match_macro_rule(
    mld: MultiLevelDict[Rule],
    macro_rule: Rule,
    rule_matches: List[RuleMatch],
    verbose: bool,
):
    print(f'Processing rule: {macro_rule}')

    macro_rule_args = rule_extract_part_iter(
        macro_rule.parts,
        macro_rule.parts,
    )
    assert macro_rule_args is not None

    # Check if this rule requires only already completed args
    is_match_keys_full = macro_rule_args.keys() <= rule_matches[0].filled_args()

    new_rule_matches: List[RuleMatch] = []
    for rule_match in rule_matches:
        if verbose:
            print(f'Processing rule match: {rule_match}')

        # TODO: make rule args extraction build a path that can be used for
        # filling no matter the args
        filled_rule = rule_fill(macro_rule, rule_match.arg_values)
        if verbose:
            print(f'Constructed filled rule: {filled_rule}')
        if filled_rule is None:
            continue

        match_keys = rule_match_keys(filled_rule, is_match_keys_full)
        if verbose:
            print(f'Constructed match keys: {match_keys}')

        for matched_rule in mld.match(match_keys):
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
                print(f'Merging arg values: {rule_match.arg_values}')
                print(f'with: {new_args_values}')
                print(f'= {new_arg_values}')

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


def match_macro_rules(
    mld: MultiLevelDict[Rule],
    macro_name: str,
    macro_rules: List[Rule],
    all_rule_matches: List[RuleMatch],
    verbose: bool,
):
    print(f'Processing macro: {macro_name}')
    if verbose:
        for macro_rule in macro_rules:
            print(macro_rule)
        print()

    # Inside the macro, prefer rules with higher arity to help
    # the arg matching algorithm
    macro_rules.sort(key=rule_arity, reverse=True)

    rule_matches: List[RuleMatch] = [RuleMatch(macro_name)]
    for macro_rule in macro_rules:
        new_rule_matches = match_macro_rule(
            mld,
            macro_rule,
            rule_matches,
            verbose,
        )
        print(f'Found {len(new_rule_matches)} candidates')
        if verbose:
            for rule_match in new_rule_matches:
                print(rule_match)
            print()
        if not len(new_rule_matches):
            print()
            return

        rule_matches = new_rule_matches

    all_rule_matches.extend(rule_matches)

    print(f'Found {len(rule_matches)} macro calls')
    if verbose:
        for rule_match in rule_matches:
            print(rule_match)
    print()


def match_macros_rules(
    mld: MultiLevelDict[Rule],
    macros_name_rules: List[Tuple[str, List[Rule]]],
    verbose: bool,
):
    rule_matches: List[RuleMatch] = []

    for macro_name, macro_rules in macros_name_rules:
        match_macro_rules(
            mld,
            macro_name,
            macro_rules,
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
    mld: MultiLevelDict[Rule],
    all_rule_matches: List[RuleMatch],
    name: str,
    verbose: bool,
):
    removed_rules = 0
    double_removed_rules: Set[Rule] = set()
    for rule_match in all_rule_matches:
        if verbose:
            print(f'Removing rules for match: {rule_match}')
        removed_any = False
        for rule in rule_match.rules:
            try:
                mld.remove(rule.hash_values, rule)
                removed_any = True
                removed_rules += 1
                if verbose:
                    print(f'Removed rule: {rule}')
            except KeyError:
                if verbose:
                    print(f'Already removed rule: {rule}')
                double_removed_rules.add(rule)

        if not removed_any:
            if verbose:
                print(f'No rules left in macro: {rule_match}')
                print()
            continue

        if verbose:
            print()

        rule = rule_match.macro
        mld.add(rule.hash_values, rule)

    # for rule in sorted(double_removed_rules, key=rule_sort_key):
    #     color_print(
    #         f'Rule already removed: {rule}',
    #         color=Color.YELLOW,
    #     )

    color_print(
        f'Replaced {removed_rules} rules with {len(all_rule_matches)} macros in {name}',
        color=Color.GREEN,
    )


def remove_rules_from_rule_matches(
    all_rule_matches: List[RuleMatch],
    source_rules: List[Rule],
    source_name: str,
):
    source_rules_set = set(source_rules)

    removed_rule_matches: Set[RuleMatch] = set()
    removed_rules_in_matches: Set[Rule] = set()
    added_rule_matches: List[RuleMatch] = []
    for rule_match in all_rule_matches:
        removed_rules_in_match: Set[Rule] = set()

        for rule in rule_match.rules:
            if rule in source_rules_set:
                removed_rules_in_match.add(rule)

        if not removed_rules_in_match:
            continue

        removed_rule_matches.add(rule_match)
        removed_rules_in_matches.update(removed_rules_in_match)

        new_rule_match_rules: List[Rule] = []
        for rule in rule_match.rules:
            if rule not in removed_rules_in_match:
                new_rule_match_rules.append(rule)

        if not new_rule_match_rules:
            continue

        new_rule_match = RuleMatch(
            rule_match.macro_name,
            new_rule_match_rules,
            rule_match.arg_values,
        )
        added_rule_matches.append(new_rule_match)

    new_rule_matches: List[RuleMatch] = []
    for rule_match in all_rule_matches:
        if rule_match not in removed_rule_matches:
            new_rule_matches.append(rule_match)

    for rule_match in added_rule_matches:
        new_rule_matches.append(rule_match)

    color_print(
        f'Removed {len(removed_rule_matches)} {source_name} macros',
        color=Color.GREEN,
    )
    color_print(
        f'Removed {len(removed_rules_in_matches)} {source_name} rules from macros',
        color=Color.GREEN,
    )

    return new_rule_matches


def remove_rules(
    mld: MultiLevelDict[Rule],
    rules: List[Rule],
    source: str,
    name: str,
):
    removed_rules = 0
    for rule in rules:
        try:
            mld.remove(rule.hash_values, rule)
            removed_rules += 1
        except KeyError:
            pass

    color_print(
        f'Removed {removed_rules} {source} rules in {name}',
        color=Color.GREEN,
    )


def merge_typeattribute_rules(
    mld: MultiLevelDict[Rule],
    name: str,
):
    types: Dict[str, Set[str]] = {}

    removed_rules: Set[Rule] = set()
    match_keys: Tuple[Optional[rule_hash_value], ...] = (
        RuleType.TYPE.value,
        None,
        frozenset(),
    )

    for rule in mld.match(match_keys):
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
    for rule in mld.match(match_keys):
        t = rule.parts[0]
        v = rule.parts[1]

        assert isinstance(t, str)
        assert isinstance(v, str)

        if t not in types:
            continue

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
        f'Merged {len(removed_rules)} typeattributes into {len(types)} types in {name}',
        color=Color.GREEN,
    )


def merge_ioctl_rules(rules: List[Rule], name: str):
    new_rules: List[Rule] = []
    same_rules: List[Rule] = []
    removed_rules = 0
    added_rules = 0

    def merge_same_rules():
        nonlocal removed_rules
        nonlocal added_rules

        if not len(same_rules):
            return

        first_rule = same_rules[0]

        if len(same_rules) == 1:
            merged_rule = first_rule
        else:
            removed_rules += len(same_rules)
            added_rules += 1
            all_varargs = tuple(v for r in same_rules for v in r.varargs)
            merged_rule = Rule(
                first_rule.rule_type,
                first_rule.parts,
                all_varargs,
            )

        new_rules.append(merged_rule)
        same_rules.clear()

    for rule in rules:
        if rule.rule_type not in IOCTL_RULE_TYPES:
            merge_same_rules()
            new_rules.append(rule)
            continue

        first_rule = same_rules[0] if len(same_rules) else None

        if first_rule is not None and (
            rule.rule_type != first_rule.rule_type
            or rule.parts != first_rule.parts
        ):
            merge_same_rules()

        same_rules.append(rule)

    merge_same_rules()

    color_print(
        f'Merged {removed_rules} rules into {added_rules} ioctl rules for {name}',
        color=Color.GREEN,
    )

    return new_rules


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
        f'Replaced perm macros in {len(removed_rules)} rules in {name}',
        color=Color.GREEN,
    )


def replace_ioctls(
    mld: MultiLevelDict[Rule],
    ioctls: List[Tuple[str, Set[str]]],
    ioctl_defines: Dict[str, str],
    name: str,
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
        f'Replaced ioctl macros in {len(removed_rules)} rules in {name}',
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
    name: str,
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
        f'Merged {removed_rules} rules into {added_rules} class set rules in {name}',
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


def find_used_types(rules: List[Rule], used_types: Set[str]):
    def handle_type(t: rule_part):
        if isinstance(t, str):
            used_types.add(t)
        elif isinstance(t, ConditionalType):
            for p in t.positive:
                used_types.add(p)
            for n in t.negative:
                used_types.add(n)

    for rule in rules:
        match rule.rule_type:
            case (
                RuleType.ALLOW.value
                | RuleType.NEVERALLOW.value
                | RuleType.AUDITALLOW.value
                | RuleType.DONTAUDIT.value
                | RuleType.ALLOWXPERM.value
                | RuleType.NEVERALLOWXPERM.value
                | RuleType.DONTAUDITXPERM.value
                | RuleType.TYPE_TRANSITION.value
            ):
                handle_type(rule.parts[0])
                handle_type(rule.parts[1])
            case RuleType.GENFSCON.value:
                handle_type(rule.parts[2])
            case RuleType.TYPE | RuleType.TYPEATTRIBUTE:
                # These are the unused rules we're trying to remove
                pass
            case RuleType.ATTRIBUTE | RuleType.EXPANDATTRIBUTE:
                # TODO: figure out if these should be taken into account
                pass
            case _:
                assert False, rule


def _remove_unused_types(
    mld: MultiLevelDict[Rule],
    match_keys: Tuple[Optional[rule_hash_value], ...],
    used_types: Set[str],
):
    removed_rules: Set[Rule] = set()
    for rule in mld.match(match_keys):
        t = rule.parts[0]
        if t in used_types:
            continue

        removed_rules.add(rule)

    for rule in removed_rules:
        mld.remove(rule.hash_values, rule)

    return len(removed_rules)


def remove_unused_types(mld: MultiLevelDict[Rule], used_types: Set[str]):
    removed_rules = _remove_unused_types(
        mld,
        (
            RuleType.TYPEATTRIBUTE,
            None,
            None,
            frozenset(),
        ),
        used_types,
    )
    removed_rules += _remove_unused_types(
        mld,
        (
            RuleType.TYPE,
            None,
            # This only works before typeattributes are merged into types
            frozenset(),
        ),
        used_types,
    )

    color_print(
        f'Removed {removed_rules} unused types',
        color=Color.GREEN,
    )


def find_public_rules(
    mld: MultiLevelDict[Rule],
    referencing_rules: List[Rule],
    public_types: Set[str],
):
    public_rules: List[Rule] = []

    for rule in referencing_rules:
        for matched_rule in mld.match(rule.hash_values):
            if rule.rule_type == RuleType.TYPEATTRIBUTE:
                assert isinstance(rule.parts[0], str)
                public_types.add(rule.parts[0])
            public_rules.append(matched_rule)

    color_print(
        f'Found {len(public_rules)} public rules',
        color=Color.GREEN,
    )

    return public_rules
