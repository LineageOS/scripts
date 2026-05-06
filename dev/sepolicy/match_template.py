# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    FrozenSet,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from sepolicy.conditional_type import ConditionalType
from sepolicy.rule import Rule, rule_hash_value, rule_part


class ArgValues:
    __UNKNOWN = 'UNKNOWN'

    __slots__ = ('__values', '__len')

    def __init__(self, values: List[Optional[rule_part]]):
        self.__values = values
        self.__len = len(values) - 1

    def __len__(self):
        return self.__len

    def __getitem__(self, index: int):
        value = self.__values[index]
        assert value is not None
        return value

    def copy(self):
        return ArgValues(self.__values[:])

    def values(self):
        return tuple(
            v if v is not None else ArgValues.__UNKNOWN
            for v in self.__values[1:]
        )

    @classmethod
    def empty(cls, size: int):
        return cls([None] * (size + 1))

    def has(self, index: int):
        return self.__values[index] is not None

    def get(self, index: int):
        return self.__values[index]

    def with_item(self, index: int, value: Optional[rule_part]):
        existing = self.__values[index]

        if existing is None:
            self.__values[index] = value
            return True

        if existing == value:
            return False

        return None

    def pop_item(self, index: int, pop: Optional[bool]):
        if pop is not True:
            return

        self.__values[index] = None

    def __str__(self):
        return f'{self.__values}'


@dataclass(frozen=True, slots=True)
class PartTemplate:
    arg_indices: FrozenSet[int]


@dataclass(frozen=True, slots=True)
class AffixTemplate(PartTemplate):
    prefix: str
    arg_index: int
    suffix: str


@dataclass(frozen=True, slots=True)
class StringTemplate(PartTemplate):
    segments: Tuple[Union[str, int], ...]


AnyStringTemplate = Union[AffixTemplate, StringTemplate]


@dataclass(frozen=True, slots=True)
class SingleValueTemplate(PartTemplate):
    arg_index: int


@dataclass(frozen=True, slots=True)
class ConditionalTemplate(PartTemplate):
    positive_literals: Tuple[Tuple[int, str], ...]
    positive_literals_set: FrozenSet[str]
    positive_templates: Tuple[Tuple[int, AnyStringTemplate], ...]

    negative_literals: Tuple[Tuple[int, str], ...]
    negative_literals_set: FrozenSet[str]
    negative_templates: Tuple[Tuple[int, AnyStringTemplate], ...]

    arg_indices: FrozenSet[int]
    is_all: bool

    @property
    def num_positive(self):
        return len(self.positive_literals) + len(self.positive_templates)

    @property
    def num_negative(self):
        return len(self.negative_literals) + len(self.negative_templates)


@dataclass(frozen=True, slots=True)
class RuleTemplate:
    rule: Rule
    literals: Tuple[Tuple[int, rule_part], ...]
    templates: Tuple[Tuple[int, PartTemplate], ...]

    @property
    def num_parts(self):
        return len(self.literals) + len(self.templates)

    @property
    def arity(self):
        max_i = 0
        for _, t in self.templates:
            for i in t.arg_indices:
                if i > max_i:
                    max_i = i
        return max_i


def compile_single_value_template(value: str):
    if len(value) != 2 or value[0] != '$' or not value[1].isdigit():
        return None

    arg_index = int(value[1])
    return SingleValueTemplate(
        arg_index=arg_index,
        arg_indices=frozenset((arg_index,)),
    )


def compile_string_template(value: str):
    value_len = len(value)

    segments: List[Union[str, int]] = []
    arg_indices: Set[int] = set()
    literal_start = 0
    i = 0
    while i < value_len:
        if value[i] != '$' or i + 1 >= value_len or not value[i + 1].isdigit():
            i += 1
            continue

        if literal_start < i:
            segments.append(value[literal_start:i])

        index = int(value[i + 1])
        segments.append(index)
        arg_indices.add(index)

        i += 2
        literal_start = i

    if not arg_indices:
        return value

    if literal_start < value_len:
        segments.append(value[literal_start:])

    if len(segments) == 1:
        # $1
        arg_index = segments[0]
        assert isinstance(arg_index, int)
        return AffixTemplate(
            prefix='',
            arg_index=arg_index,
            suffix='',
            arg_indices=frozenset((arg_index,)),
        )

    if len(segments) == 2:
        # $1_a
        if isinstance(segments[0], int) and isinstance(segments[1], str):
            arg_index = segments[0]
            return AffixTemplate(
                prefix='',
                arg_index=arg_index,
                suffix=segments[1],
                arg_indices=frozenset((arg_index,)),
            )

        # a_$1
        if isinstance(segments[0], str) and isinstance(segments[1], int):
            arg_index = segments[1]
            return AffixTemplate(
                prefix=segments[0],
                arg_index=arg_index,
                suffix='',
                arg_indices=frozenset((arg_index,)),
            )

    if len(segments) == 3:
        # a_$1_b
        if (
            isinstance(segments[0], str)
            and isinstance(segments[1], int)
            and isinstance(segments[2], str)
        ):
            arg_index = segments[1]
            return AffixTemplate(
                prefix=segments[0],
                arg_index=arg_index,
                suffix=segments[2],
                arg_indices=frozenset((arg_index,)),
            )

    return StringTemplate(
        segments=tuple(segments),
        arg_indices=frozenset(arg_indices),
    )


def fill_single_value_template(
    template: SingleValueTemplate,
    arg_values: ArgValues,
):
    return arg_values[template.arg_index]


def _fill_affix_template(template: AffixTemplate, arg_values: ArgValues):
    arg_value = arg_values.get(template.arg_index)
    if arg_value is None:
        return None

    if not isinstance(arg_value, str):
        return None

    return f'{template.prefix}{arg_value}{template.suffix}'


def _fill_string_template(template: StringTemplate, arg_values: ArgValues):
    parts: List[str] = []
    for segment in template.segments:
        if isinstance(segment, str):
            parts.append(segment)
            continue

        value = arg_values[segment]
        if not isinstance(value, str):
            return None

        parts.append(value)

    value = ''.join(parts)

    return value


def fill_string_template(template: AnyStringTemplate, arg_values: ArgValues):
    if isinstance(template, AffixTemplate):
        return _fill_affix_template(template, arg_values)

    return _fill_string_template(template, arg_values)


def compile_conditional_template_list(
    parts: List[str],
    arg_indices: Set[int],
):
    literals: List[Tuple[int, str]] = []
    literals_set: Set[str] = set()
    templates: List[Tuple[int, AnyStringTemplate]] = []

    for i, part in enumerate(parts):
        part = compile_string_template(part)
        if isinstance(part, str):
            literals.append((i, part))
            literals_set.add(part)
        else:
            templates.append((i, part))
            arg_indices.update(part.arg_indices)

    return literals, literals_set, templates


def compile_conditional_template(value: ConditionalType):
    negative_literals: List[Tuple[int, str]] = []
    negative_literals_set: Set[str] = set()
    negative_templates: List[Tuple[int, AnyStringTemplate]] = []
    arg_indices: Set[int] = set()

    positive_literals, positive_literals_set, positive_templates = (
        compile_conditional_template_list(value.positive, arg_indices)
    )

    negative_literals, negative_literals_set, negative_templates = (
        compile_conditional_template_list(value.negative, arg_indices)
    )

    if not arg_indices:
        return value

    return ConditionalTemplate(
        positive_literals=tuple(positive_literals),
        positive_literals_set=frozenset(positive_literals_set),
        positive_templates=tuple(positive_templates),
        negative_literals=tuple(negative_literals),
        negative_literals_set=frozenset(negative_literals_set),
        negative_templates=tuple(negative_templates),
        is_all=value.is_all,
        arg_indices=frozenset(arg_indices),
    )


def fill_conditional_template(
    template: ConditionalTemplate,
    arg_values: ArgValues,
):
    positive: List[str] = [''] * template.num_positive
    negative: List[str] = [''] * template.num_negative

    for i, part in template.positive_literals:
        positive[i] = part

    for i, part in template.negative_literals:
        negative[i] = part

    for i, part in template.positive_templates:
        filled = fill_string_template(part, arg_values)
        if filled is None:
            return None

        positive[i] = filled

    for i, part in template.negative_templates:
        filled = fill_string_template(part, arg_values)
        if filled is None:
            return None

        negative[i] = filled

    return ConditionalType(positive, negative, template.is_all)


def compile_rule_template(rule: Rule):
    literals: List[Tuple[int, rule_part]] = []
    templates: List[Tuple[int, PartTemplate]] = []

    arg_indices: Set[int] = set()

    for i, part in enumerate(rule.parts):
        if isinstance(part, str):
            compiled_part = compile_single_value_template(part)
            if compiled_part is None:
                compiled_part = compile_string_template(part)
        elif isinstance(part, ConditionalType):
            compiled_part = compile_conditional_template(part)
        else:
            assert False, rule

        if isinstance(compiled_part, (str, ConditionalType)):
            literals.append((i, part))
            continue

        templates.append((i, compiled_part))
        arg_indices.update(compiled_part.arg_indices)

    return RuleTemplate(
        rule=rule,
        literals=tuple(literals),
        templates=tuple(templates),
    )


def fill_rule_template(rule_template: RuleTemplate, arg_values: ArgValues):
    literals: List[Tuple[int, rule_part]] = list(rule_template.literals)
    templates: List[Tuple[int, PartTemplate]] = []

    for i, part in rule_template.templates:
        has_missing = False
        for arg_index in part.arg_indices:
            if not arg_values.has(arg_index):
                has_missing = True
                break

        if has_missing:
            templates.append((i, part))
            continue

        if isinstance(part, SingleValueTemplate):
            part = fill_single_value_template(part, arg_values)
            assert isinstance(part, (str, ConditionalType))
        elif isinstance(part, (AffixTemplate, StringTemplate)):
            part = fill_string_template(part, arg_values)
            if part is None:
                return None

            assert isinstance(part, str)
        else:
            assert isinstance(part, ConditionalTemplate)
            part = fill_conditional_template(part, arg_values)
            if part is None:
                return None

            assert isinstance(part, ConditionalType)

        literals.append((i, part))

    return RuleTemplate(
        rule=rule_template.rule,
        literals=tuple(literals),
        templates=tuple(templates),
    )


def rule_template_match_keys(rule_template: RuleTemplate):
    parts: List[Optional[rule_hash_value]] = [None] * (rule_template.num_parts)

    for i, part in rule_template.literals:
        parts[i] = part

    return (
        rule_template.rule.rule_type,
        *parts,
        rule_template.rule.varargs,
    )


def _iter_string_template_arg_values(
    arg_values: ArgValues,
    template: StringTemplate,
    segment_index: int,
    value: str,
    value_index: int,
) -> Iterator[ArgValues]:
    num_segments = len(template.segments)

    while segment_index < num_segments:
        segment = template.segments[segment_index]

        if isinstance(segment, str):
            if not value.startswith(segment, value_index):
                return

            value_index += len(segment)
            segment_index += 1
            continue

        arg_index = segment

        if segment_index + 1 == num_segments:
            pop = arg_values.with_item(arg_index, value[value_index:])

            if pop is not None:
                yield arg_values

            arg_values.pop_item(arg_index, pop)

            return

        next_segment = template.segments[segment_index + 1]
        if not isinstance(next_segment, str):
            return

        next_literal = next_segment
        search_start = value_index

        while True:
            next_pos = value.find(next_literal, search_start)
            if next_pos == -1:
                return

            candidate = value[value_index:next_pos]
            pop = arg_values.with_item(arg_index, candidate)

            if pop is not None:
                yield from _iter_string_template_arg_values(
                    arg_values,
                    template,
                    segment_index + 1,
                    value,
                    next_pos,
                )

            arg_values.pop_item(arg_index, pop)

            search_start = next_pos + 1


def _iter_affix_template_arg_values(
    arg_values: ArgValues,
    template: AffixTemplate,
    value: str,
) -> Iterator[ArgValues]:
    if not value.startswith(template.prefix):
        return

    value = value.removeprefix(template.prefix)

    if not value.endswith(template.suffix):
        return

    value = value.removesuffix(template.suffix)

    pop = arg_values.with_item(template.arg_index, value)

    if pop is not None:
        yield arg_values

    arg_values.pop_item(template.arg_index, pop)


def iter_string_template_arg_values(
    arg_values: ArgValues,
    template: AnyStringTemplate,
    value: str,
) -> Iterator[ArgValues]:
    if isinstance(template, AffixTemplate):
        yield from _iter_affix_template_arg_values(
            arg_values,
            template,
            value,
        )
        return

    yield from _iter_string_template_arg_values(
        arg_values,
        template,
        segment_index=0,
        value=value,
        value_index=0,
    )


def iter_single_value_template_arg_values(
    arg_values: ArgValues,
    template: SingleValueTemplate,
    value: Union[str, ConditionalType],
) -> Iterator[ArgValues]:
    pop = arg_values.with_item(template.arg_index, value)

    if pop is not None:
        yield arg_values

    arg_values.pop_item(template.arg_index, pop)


def _iter_string_set_template_arg_values(
    arg_values: ArgValues,
    template_parts: Tuple[Tuple[int, AnyStringTemplate], ...],
    template_part_index: int,
    value_parts: Tuple[str, ...],
    used: List[bool],
) -> Iterator[ArgValues]:
    if template_part_index == len(template_parts):
        yield arg_values
        return

    _, template_part = template_parts[template_part_index]

    for i, value_part in enumerate(value_parts):
        if used[i]:
            continue

        used[i] = True
        for new_arg_values in iter_string_template_arg_values(
            arg_values,
            template_part,
            value_part,
        ):
            yield from _iter_string_set_template_arg_values(
                arg_values=new_arg_values,
                template_parts=template_parts,
                template_part_index=template_part_index + 1,
                value_parts=value_parts,
                used=used,
            )
        used[i] = False


def iter_string_set_template_arg_values(
    arg_values: ArgValues,
    template_parts: Tuple[Tuple[int, AnyStringTemplate], ...],
    value_parts: Tuple[str, ...],
) -> Iterator[ArgValues]:
    used = [False] * len(value_parts)

    yield from _iter_string_set_template_arg_values(
        arg_values=arg_values,
        template_parts=template_parts,
        template_part_index=0,
        value_parts=value_parts,
        used=used,
    )


def iter_conditional_template_arg_values(
    arg_values: ArgValues,
    template: ConditionalTemplate,
    value: ConditionalType,
) -> Iterator[ArgValues]:
    if template.is_all != value.is_all:
        return

    if len(value.positive) != template.num_positive:
        return

    if len(value.negative) != template.num_negative:
        return

    if not template.positive_literals_set <= value.positive_set:
        return

    if not template.negative_literals_set <= value.negative_set:
        return

    positive = tuple(
        v for v in value.positive if v not in template.positive_literals_set
    )
    negative = tuple(
        v for v in value.negative if v not in template.negative_literals_set
    )
    for positive_arg_values in iter_string_set_template_arg_values(
        arg_values,
        template.positive_templates,
        positive,
    ):
        yield from iter_string_set_template_arg_values(
            positive_arg_values,
            template.negative_templates,
            negative,
        )


def _iter_rule_fill_arg_values(
    template_parts: Tuple[Tuple[int, PartTemplate], ...],
    template_part_index: int,
    matched_parts: Tuple[rule_part, ...],
    arg_values: ArgValues,
) -> Iterator[ArgValues]:
    if template_part_index == len(template_parts):
        yield arg_values
        return

    part_index, template_part = template_parts[template_part_index]
    rule_part = matched_parts[part_index]

    new_arg_values_iter: Optional[Iterator[ArgValues]] = None

    if isinstance(template_part, SingleValueTemplate):
        if not isinstance(rule_part, (str, ConditionalType)):
            return

        new_arg_values_iter = iter_single_value_template_arg_values(
            arg_values,
            template_part,
            rule_part,
        )
    elif isinstance(template_part, (AffixTemplate, StringTemplate)):
        if not isinstance(rule_part, str):
            return

        new_arg_values_iter = iter_string_template_arg_values(
            arg_values,
            template_part,
            rule_part,
        )
    elif isinstance(template_part, ConditionalTemplate):
        if not isinstance(rule_part, ConditionalType):
            return

        new_arg_values_iter = iter_conditional_template_arg_values(
            arg_values,
            template_part,
            rule_part,
        )
    else:
        assert False, template_part

    for new_arg_values in new_arg_values_iter:
        yield from _iter_rule_fill_arg_values(
            template_parts=template_parts,
            template_part_index=template_part_index + 1,
            matched_parts=matched_parts,
            arg_values=new_arg_values,
        )


def iter_rule_fill_arg_values(
    rule_template: RuleTemplate,
    arg_values: ArgValues,
    matched_rule: Rule,
) -> Iterator[ArgValues]:
    if matched_rule.rule_type != rule_template.rule.rule_type:
        return

    if matched_rule.varargs != rule_template.rule.varargs:
        return

    if len(matched_rule.parts) != rule_template.num_parts:
        return

    for i, part in rule_template.literals:
        if matched_rule.parts[i] != part:
            return

    yield from _iter_rule_fill_arg_values(
        rule_template.templates,
        template_part_index=0,
        matched_parts=matched_rule.parts,
        arg_values=arg_values,
    )


def rule_template_sort_key(rule_template: RuleTemplate):
    return (
        len(rule_template.literals),
        rule_template.arity,
    )
