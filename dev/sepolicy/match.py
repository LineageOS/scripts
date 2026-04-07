# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict, List, Optional, Set, Tuple

from sepolicy.class_set import ClassSet
from sepolicy.classmap import Classmap
from sepolicy.macro import ioctl_type_name
from sepolicy.match_template import (
    RuleTemplate,
    args_type,
    compile_rule_template,
    fill_rule_template,
    iter_rule_fill_arg_values,
    rule_template_match_keys,
    rule_template_sort_key,
)
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
        rules: Optional[List[Rule]] = None,
        arg_values: Optional[args_type] = None,
    ):
        if rules is None:
            rules = []
        if arg_values is None:
            arg_values = {}

        self.macro_name = macro_name
        self.rules = rules
        self.arg_values = arg_values

        self.__hash_values = (
            self.macro_name,
            frozenset(self.arg_values.items()),
            frozenset(rules),
        )
        self.__hash = hash(self.__hash_values)
        self.__macro: Optional[Rule] = None

    @property
    def macro(self):
        macro = self.__macro
        if macro is None:
            args = tuple(self.arg_values[k] for k in sorted(self.arg_values))
            macro = Rule(self.macro_name, args, (), is_macro=True)
            self.__macro = macro

        return macro

    def filled_args(self):
        return self.arg_values.keys()

    def __hash__(self):
        return self.__hash

    def __eq__(self, other: object):
        if not isinstance(other, RuleMatch):
            return NotImplemented

        return self.__hash_values == other.__hash_values

    def __str__(self):
        return str(self.macro)


def match_macro_rule(
    rules: RuleContainer,
    macro_rule_templates: List[RuleTemplate],
    rule_index: int,
    macro_name: str,
    macro_rules: List[Rule],
    macro_arg_values: args_type,
    results: List[RuleMatch],
    verbose: bool,
):
    if rule_index == len(macro_rule_templates):
        rule_match = RuleMatch(
            macro_name,
            macro_rules.copy(),
            macro_arg_values,
        )
        results.append(rule_match)
        return

    macro_rule_template = macro_rule_templates[rule_index]

    if verbose:
        print(f'Processing rule: {macro_rule_template.rule}')

    filled_macro_rule_template = fill_rule_template(
        macro_rule_template,
        macro_arg_values,
    )
    if filled_macro_rule_template is None:
        return

    if verbose:
        print('Filled rule template:', macro_rule_template)

    match_keys = rule_template_match_keys(filled_macro_rule_template)
    if verbose:
        match_keys_str = [
            sorted(v) if isinstance(v, frozenset) else str(v)
            for v in match_keys
        ]
        print(f'Constructed match keys: {match_keys_str}')

    for matched_rule in rules.match(match_keys):
        if verbose:
            print(f'Found matching rule: {matched_rule}')

        for new_arg_values in iter_rule_fill_arg_values(
            filled_macro_rule_template,
            macro_arg_values,
            matched_rule,
        ):
            if verbose:
                print(f'Found new arg values: {new_arg_values}')

            macro_rules.append(matched_rule)
            match_macro_rule(
                rules,
                macro_rule_templates,
                rule_index + 1,
                macro_name,
                macro_rules,
                new_arg_values,
                results,
                verbose,
            )
            macro_rules.pop()


def match_macro_rules(
    rules: RuleContainer,
    macro_name: str,
    macro_rule_templates: List[RuleTemplate],
    all_rule_matches: List[RuleMatch],
    verbose: bool,
):
    if verbose:
        print(f'Processing macro: {macro_name}')
        for rule_template in macro_rule_templates:
            print(rule_template.rule)
        print()

    rule_matches: List[RuleMatch] = []

    match_macro_rule(
        rules,
        macro_rule_templates,
        0,
        macro_name,
        [],
        {},
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
        macro_rule_templates: List[RuleTemplate] = [
            compile_rule_template(r) for r in macro_rules
        ]

        # Inside the macro, prefer rules with higher arity to help
        # the arg matching algorithm
        macro_rule_templates.sort(
            key=rule_template_sort_key,
            reverse=True,
        )

        match_macro_rules(
            rules,
            macro_name,
            macro_rule_templates,
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

    rule_matches_map: DefaultDict[Rule, Set[RuleMatch]] = defaultdict(set)
    for rule_match in all_rule_matches:
        for rule in rule_match.rules:
            rule_matches_map[rule].add(rule_match)

    if verbose:
        for rule, rule_matches in rule_matches_map.items():
            print(f'Rule matches for: {rule}')
            for rule_match in rule_matches:
                print(rule_match)
            print()

    new_rule_matches: List[RuleMatch] = []
    for rule_match in all_rule_matches:
        if verbose:
            print(f'Finding supersets for rule match: {rule_match}')

        rule_match_sets = [rule_matches_map[rule] for rule in rule_match.rules]
        rule_match_sets.sort(key=len)

        candidate_supersets: Optional[Set[RuleMatch]] = None
        for rule_matches in rule_match_sets:
            if candidate_supersets is None:
                candidate_supersets = rule_matches.copy()
            else:
                candidate_supersets = candidate_supersets & rule_matches

        assert candidate_supersets is not None

        candidate_supersets.remove(rule_match)

        if verbose:
            # TODO: sort output for determinism
            print(f'Found {len(candidate_supersets)} candidates')
            for candidate in candidate_supersets:
                print(candidate)
            print()

        rules_set = set(rule_match.rules)
        discarded = False
        for candidate in candidate_supersets:
            candidate_rules_set = set(candidate.rules)

            if candidate_rules_set < rules_set:
                continue

            if rules_set == candidate_rules_set and len(
                rule_match.arg_values
            ) < len(candidate.arg_values):
                continue

            if verbose:
                # TODO: sort output for determinism
                print(f'Discarding {rule_match}')
                print(f'in favor of {candidate}')

            discarded = True
            break

        if verbose:
            print()

        if not discarded:
            new_rule_matches.append(rule_match)

    num_discarded_rule_matches = len(all_rule_matches) - len(new_rule_matches)
    color_print(
        f'Discarded subset macros: {num_discarded_rule_matches}',
        color=Color.GREEN,
    )

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
