# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from typing import (
    DefaultDict,
    Dict,
    FrozenSet,
    Hashable,
    List,
    Optional,
    Set,
    Tuple,
)

from sepolicy.class_set import ClassSet
from sepolicy.match_template import (
    ArgValues,
    RuleTemplate,
    compile_rule_template,
    fill_rule_template,
    iter_rule_fill_arg_values,
    rule_template_match_keys,
    rule_template_sort_key,
)
from sepolicy.rule import (
    ALLOW_RULE_TYPES,
    IOCTL_RULE_TYPES,
    Rule,
    RuleType,
    rule_hash_value,
)
from sepolicy.rule_container import LineMark, RuleContainer
from sepolicy.varargs import Types
from utils.utils import Color, color_print


class RuleMatch:
    def __init__(
        self,
        macro_name: str,
        rules: FrozenSet[Rule],
        arg_values: ArgValues,
    ):
        self.macro_name = macro_name
        self.rules = rules
        self.arg_values = arg_values

        self.__hash_values = (
            self.macro_name,
            self.arg_values,
            rules,
        )
        self.__hash = hash(self.__hash_values)
        self.__macro: Optional[Rule] = None

    @property
    def macro(self):
        macro = self.__macro
        if macro is None:
            macro = Rule(
                self.macro_name,
                self.arg_values.values(),
                is_macro=True,
                expanded_rules=self.rules,
            )
            self.__macro = macro

        return macro

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
    macro_arg_values: ArgValues,
    results: List[RuleMatch],
    rule_match_cache: Dict[Hashable, List[Rule]],
    verbose: bool,
):
    indent = '\t' * rule_index

    if rule_index == len(macro_rule_templates):
        rule_match = RuleMatch(
            macro_name,
            frozenset(macro_rules),
            macro_arg_values.copy(),
        )
        results.append(rule_match)
        return

    macro_rule_template = macro_rule_templates[rule_index]

    if verbose:
        print(f'{indent}Processing rule: {macro_rule_template.rule}')

    filled_macro_rule_template = fill_rule_template(
        macro_rule_template,
        macro_arg_values,
    )
    if filled_macro_rule_template is None:
        return

    if verbose:
        print(f'{indent}Filled rule template:', filled_macro_rule_template)

    match_keys = rule_template_match_keys(filled_macro_rule_template)
    if verbose:
        match_keys_str = [
            sorted(v) if isinstance(v, frozenset) else str(v)
            for v in match_keys
        ]
        print(f'{indent}Constructed match keys: {match_keys_str}')

    matched_rules = rule_match_cache.get(match_keys)
    if matched_rules is None:
        matched_rules = rules.match(match_keys)
        rule_match_cache[match_keys] = matched_rules

    for matched_rule in matched_rules:
        if verbose:
            print(f'{indent}Found matching rule: {matched_rule}')

        found = False
        for new_arg_values in iter_rule_fill_arg_values(
            filled_macro_rule_template,
            macro_arg_values,
            matched_rule,
        ):
            found = True
            if verbose:
                print(f'{indent}Found new arg values: {new_arg_values}')

            macro_rules.append(matched_rule)
            match_macro_rule(
                rules,
                macro_rule_templates,
                rule_index + 1,
                macro_name,
                macro_rules,
                new_arg_values,
                results,
                rule_match_cache,
                verbose,
            )
            macro_rules.pop()

        if verbose:
            if not found:
                print(f'{indent}Found no matching arg values')


def match_macro_rules(
    rules: RuleContainer,
    macro_name: str,
    macro_rule_templates: List[RuleTemplate],
    all_rule_matches: List[RuleMatch],
    rule_match_cache: Dict[Hashable, List[Rule]],
    verbose: bool,
):
    if verbose:
        print(f'Processing macro: {macro_name}')
        for rule_template in macro_rule_templates:
            print(rule_template.rule)
        print()

    rule_matches: List[RuleMatch] = []

    arity = max(m.arity for m in macro_rule_templates)
    match_macro_rule(
        rules,
        macro_rule_templates,
        0,
        macro_name,
        [],
        ArgValues.empty(arity),
        rule_matches,
        rule_match_cache,
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
    rule_match_cache: Dict[Hashable, List[Rule]] = {}

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
            rule_match_cache,
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

        rule_match_str = str(rule_match.macro)
        discarded = False
        for candidate in candidate_supersets:
            if candidate.rules < rule_match.rules:
                continue

            if rule_match.rules == candidate.rules:
                arg_diff = len(rule_match.arg_values) - len(
                    candidate.arg_values
                )
                if arg_diff < 0:
                    continue

                # If rule sets and arg counts are equal, keep the match with the
                # smaller output
                if arg_diff == 0 and rule_match_str < str(candidate.macro):
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

        marks: Optional[Set[LineMark]] = None
        for body_rule in rule_match.rules:
            body_marks = rules.marks(body_rule)
            if not body_marks:
                continue

            if marks is None:
                marks = set(body_marks)
            else:
                marks = marks & set(body_marks)

            if not marks:
                break

        removed_count = rules.remove_many(rule_match.rules, optional=True)
        if not removed_count:
            if verbose:
                print(f'No rules left in macro: {rule_match}')
                print()
            continue

        removed_rules += removed_count
        added_macros += 1
        rule = rule_match.macro
        rules.add(rule, marks)

    color_print(
        f'Replaced {removed_rules} rules with {added_macros} macros in {name}',
        color=Color.GREEN,
    )


def merge_typeattribute_rules(
    rules: RuleContainer,
    rule_guard: Optional[Dict[Rule, str]] = None,
):
    types: Dict[str, Set[str]] = {}

    removed_rules: Set[Rule] = set()
    match_keys: Tuple[Optional[rule_hash_value], ...] = (
        RuleType.TYPE,
        None,
        None,
    )

    for rule in rules.match(match_keys):
        t = rule.parts[0]
        assert isinstance(t, str)

        assert t not in types
        types[t] = set()

        removed_rules.add(rule)

    match_keys = (
        RuleType.TYPEATTRIBUTE,
        None,
        None,
        None,
    )
    for rule in rules.match(match_keys):
        t = rule.parts[0]
        v = rule.parts[1]

        assert isinstance(t, str)
        assert isinstance(v, str)

        if t not in types:
            continue

        if rule_guard is not None and rule in rule_guard:
            continue

        types[t].add(v)

        removed_rules.add(rule)

    for rule in removed_rules:
        rules.remove(rule)

    for t, values in types.items():
        new_rule = Rule(
            RuleType.TYPE,
            (t,),
            Types(values),
        )
        rules.add(new_rule)


def merge_class_set_rule_type(
    rules: RuleContainer,
    match_keys: Tuple[Optional[rule_hash_value], ...],
    class_sets: List[Tuple[str, Set[str]]],
    mark_source: Optional[RuleContainer] = None,
):
    rules_dict: Dict[
        Tuple[Optional[rule_hash_value], ...],
        Tuple[Set[str], Set[Rule]],
    ] = {}

    for matched_rule in rules.match(match_keys):
        # Keep class out of the key
        key = (
            matched_rule.rule_type,
            matched_rule.parts[0],
            matched_rule.parts[1],
            *matched_rule.parts[3:],
            matched_rule.varargs,
        )
        if key not in rules_dict:
            rules_dict[key] = (set(), set())

        # Gather all matched classes
        matched_cls = matched_rule.parts[2]
        assert isinstance(matched_cls, str), matched_rule
        rules_dict[key][0].add(matched_cls)
        rules_dict[key][1].add(matched_rule)

    for matched_classes, matched_rules in rules_dict.values():
        if len(matched_classes) == 1:
            continue

        # Only merge classes in rules that come from a single source statement
        if mark_source is not None:
            common_marks: Optional[Set[LineMark]] = None
            for rule in matched_rules:
                rule_marks = mark_source.marks(rule)
                if common_marks is None:
                    common_marks = set(rule_marks)
                else:
                    common_marks = common_marks & rule_marks
                if not common_marks:
                    break
            if not common_marks:
                continue

        names: Set[str] = set()
        remaining_classes = matched_classes
        for name, classes in class_sets:
            if classes <= remaining_classes:
                remaining_classes = remaining_classes - classes
                names.add(name)

        for rule in matched_rules:
            rules.remove(rule)

        names = names | remaining_classes

        matched_rule = next(iter(matched_rules))
        new_rule = Rule(
            matched_rule.rule_type,
            (
                matched_rule.parts[0],
                matched_rule.parts[1],
                ClassSet(
                    sorted(names),
                    sorted(matched_classes),
                ),
                *matched_rule.parts[3:],
            ),
            matched_rule.varargs,
        )
        rules.add(new_rule)


def merge_class_sets(
    rules: RuleContainer,
    class_sets: List[Tuple[str, Set[str]]],
    mark_source: Optional[RuleContainer] = None,
):
    for rule_type in ALLOW_RULE_TYPES:
        merge_class_set_rule_type(
            rules,
            (rule_type, None, None, None, None),
            class_sets,
            mark_source,
        )

    for rule_type in IOCTL_RULE_TYPES:
        merge_class_set_rule_type(
            rules,
            (rule_type, None, None, None, None, None),
            class_sets,
            mark_source,
        )


def device_marks(
    rule_match: RuleMatch,
    rules: RuleContainer,
    reference: RuleContainer,
):
    common: Optional[Set[LineMark]] = None
    for rule in rule_match.rules:
        if rule in reference:
            continue

        marks = rules.marks(rule)
        if not marks:
            continue

        common = set(marks) if common is None else common & set(marks)
        if not common:
            break

    return common


def select_macros_by_group(
    rule_matches: List[RuleMatch],
    rules: RuleContainer,
    reference: RuleContainer,
    verbose: bool,
) -> List[RuleMatch]:
    anchored = [
        rule_match
        for rule_match in rule_matches
        if device_marks(rule_match, rules, reference) != set()
    ]

    return discard_rule_matches(anchored, verbose)
