# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import (
    Dict,
    FrozenSet,
    List,
    Optional,
    Set,
    Tuple,
    cast,
)

from bp.bp_module import BpModule
from bp.bp_parser import bp_parser  # type: ignore
from sepolicy.cil_rule import (
    CIL_CLASSPERM_TYPES,
    CIL_COMMENT_MARKER,
    CilRuleParser,
    CilRuleType,
    unpack_cil_line,
)
from sepolicy.classmap import Classmap
from sepolicy.compile_utils import binary_to_cil_policy
from sepolicy.conditional_type import ConditionalType
from sepolicy.contexts import parse_contexts_texts
from sepolicy.merge import add_mergeable_rule, merge_current_rules
from sepolicy.policy import (
    ContextsType,
    Policy,
    PolicyDumpCilOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyType,
    PolicyVersionSource,
)
from sepolicy.rule import Rule, raw_parts_list
from sepolicy.rule_container import LineMark, RuleContainer
from utils.frozendict import FrozenDict
from utils.utils import (
    android_root,
    read_texts,
    resolve_paths,
    split_normalize_text,
)

cil_line_type = Tuple[str, raw_parts_list, Optional[LineMark]]

LMX_PREFIX = ';;* lmx '
LME_MARKER = ';;* lme'


SEPOLICY_FLAGGING_BP_PATH = Path(
    android_root,
    'system/sepolicy/flagging/Android.bp',
)


@cache
def get_needed_build_flags(flagging_bp_path: Path) -> FrozenSet[str]:
    statements = bp_parser.parse(flagging_bp_path.read_text())  # type: ignore
    statements = cast(List[BpModule], statements)

    flags: Set[str] = set()
    for statement in statements:
        if statement.get('module') != 'se_flags':
            continue

        module_flags = statement.get('flags', [])  # type: ignore
        flags.update(module_flags)

    assert flags, f'Failed to parse se_flags from {flagging_bp_path}'

    return frozenset(flags)


def get_build_prop(lines: List[str], prop_name: str):
    prop_name_eq = f'{prop_name}='

    for line in lines:
        if line.startswith(prop_name_eq):
            return line[len(prop_name_eq) :]

    assert False, f'Failed to find build prop: {prop_name}'


def sdk_value_to_version(sdk_value: str):
    # TODO: find the proper value
    if sdk_value == '36':
        return '202504'
    elif sdk_value == '35':
        return '202404'

    return f'{sdk_value}.0'


def read_build_flags_data(build_flags_path: Path):
    return json.loads(build_flags_path.read_text())


@cache
def get_build_flag_variables(
    build_flags_path: Path,
    build_flags: FrozenSet[str],
):
    build_flags_data = read_build_flags_data(build_flags_path)
    flags = build_flags_data['flags']
    variables: Dict[str, str] = {}

    for flag in flags:
        flag_name = flag['flag_declaration']['name']
        if flag_name not in build_flags:
            continue

        flag_value = flag['value']['Val']
        bool_value = flag_value.get('BoolValue')
        string_value = flag_value.get('StringValue')

        if bool_value is not None:
            value = str(bool_value).lower()
        elif string_value is not None:
            value = string_value
        else:
            assert False, json.dumps(flag)

        variables[f'target_flag_{flag_name}'] = value

    return variables


@cache
def read_build_prop_lines(build_prop_path: Path):
    return build_prop_path.read_text().splitlines()


def read_build_prop(build_prop_path: Path, name: str):
    return get_build_prop(read_build_prop_lines(build_prop_path), name)


@cache
def get_dump_policy_version(
    dump_root: Path,
    version_source: PolicyVersionSource,
):
    if version_source == PolicyVersionSource.SDK:
        platform_build_prop_path = Path(dump_root, 'system/build.prop')
        sdk_value = read_build_prop(
            platform_build_prop_path,
            'ro.build.version.sdk',
        )
        return sdk_value_to_version(sdk_value)
    elif version_source == PolicyVersionSource.BOARD_API:
        vendor_build_prop_path = Path(dump_root, 'vendor/build.prop')
        return read_build_prop(
            vendor_build_prop_path,
            'ro.board.api_level',
        )
    else:
        assert False


def parse_dump_policy_variables(
    dump_root: Path,
    version: str,
    recovery: bool = False,
):
    platform_build_prop_path = Path(dump_root, 'system/build.prop')
    platform_build_flags_path = Path(
        dump_root,
        'system',
        'etc/build_flags.json',
    )
    vendor_build_prop_path = Path(dump_root, 'vendor/build.prop')
    vendor_build_flags_path = Path(
        dump_root,
        'vendor',
        'etc/build_flags.json',
    )

    is_not_recovery_str = 'false' if recovery else 'true'
    is_recovery_str = 'true' if recovery else 'false'

    target_arch = read_build_prop(
        vendor_build_prop_path,
        'ro.bionic.arch',
    )

    build_type = read_build_prop(
        platform_build_prop_path,
        'ro.build.type',
    )

    needed_build_flags = get_needed_build_flags(SEPOLICY_FLAGGING_BP_PATH)
    platform_build_flag_variables = get_build_flag_variables(
        platform_build_flags_path,
        needed_build_flags,
    )
    vendor_build_flag_variables = get_build_flag_variables(
        vendor_build_flags_path,
        needed_build_flags,
    )

    for key in (
        platform_build_flag_variables.keys()
        & vendor_build_flag_variables.keys()
    ):
        assert (
            platform_build_flag_variables[key]
            == vendor_build_flag_variables[key]
        ), key

    #
    # Gather all variables needed for conditional
    #
    variables: Dict[str, str] = {}
    variables.update(platform_build_flag_variables)
    variables.update(vendor_build_flag_variables)

    for flag_name in needed_build_flags:
        variables.setdefault(f'target_flag_{flag_name}', 'false')

    #
    # From system/sepolicy/buid/soong/policy.go
    #

    # MlsSens = 1
    variables['mls_num_sens'] = '1'

    # MlsCats = 1024
    variables['mls_num_cats'] = '1024'

    # TARGET_ARCH
    variables['target_arch'] = target_arch

    # WITH_DEXPREOPT
    variables['target_with_dexpreopt'] = 'false'

    # CLANG_COVERAGE or NATIVE_COVERAGE
    variables['target_with_native_coverage'] = 'false'

    variables['target_full_treble'] = is_not_recovery_str

    variables['target_compatible_property'] = is_not_recovery_str

    # BUILD_BROKEN_TREBLE_SYSPROP_NEVERALLOW
    variables['target_treble_sysprop_neverallow'] = is_not_recovery_str

    # BUILD_BROKEN_ENFORCE_SYSPROP_OWNER
    variables['target_enforce_sysprop_owner'] = is_not_recovery_str

    # Set to true for CTS only
    variables['target_exclude_build_test'] = 'false'

    # PRODUCT_REQUIRES_INSECURE_EXECMEM_FOR_SWIFTSHADER
    variables['target_requires_insecure_execmem_for_swiftshader'] = 'false'

    # PRODUCT_SET_DEBUGFS_RESTRICTIONS
    variables['target_enforce_debugfs_restriction'] = 'true'

    variables['target_recovery'] = is_recovery_str

    # BOARD_API_LEVEL
    variables['target_board_api_level'] = version

    # TARGET_BUILD_VARIANT
    variables['target_build_variant'] = build_type

    try:
        read_build_prop(platform_build_prop_path, 'ro.sanitize.address')
        variables['target_with_asan'] = 'true'
    except AssertionError:
        pass

    return FrozenDict(variables)


def _parse_cil_lines(
    line_parts_list: List[cil_line_type],
    rules: RuleContainer,
    genfs_rules: RuleContainer,
    conditional_types_map: Dict[str, ConditionalType],
    reference_conditional_types_maps: List[Dict[str, ConditionalType]],
    version: str,
    classmap: Optional[Classmap] = None,
    allowed_types: Optional[FrozenSet[str]] = None,
    disallowed_types: Optional[FrozenSet[str]] = None,
):
    mergeable_rules: List[Rule] = []
    mergeable_marks: Set[LineMark] = set()
    current_mark: List[Optional[LineMark]] = [None]

    def add_rule(rule: Rule):
        add_mergeable_rule(
            rule,
            current_mark[0],
            mergeable_rules,
            mergeable_marks,
            rules,
        )

    def add_genfs_rule(rule: Rule):
        genfs_rules.add(rule)

    parser = CilRuleParser(
        conditional_types_map=conditional_types_map,
        reference_conditional_types_maps=reference_conditional_types_maps,
        add_rule=add_rule,
        add_genfs_rule=add_genfs_rule,
        version=version,
        allowed_types=allowed_types,
        disallowed_types=disallowed_types,
        classmap=classmap,
    )

    for line in line_parts_list:
        text, parts, mark = line
        current_mark[0] = mark
        parser.parse_line(text, parts)

    merge_current_rules(mergeable_rules, mergeable_marks, rules)


def parse_cil_lines(
    cil_path: Path,
    rules: RuleContainer,
    genfs_rules: RuleContainer,
    conditional_types_map: Dict[str, ConditionalType],
    reference_conditional_types_maps: List[Dict[str, ConditionalType]],
    classmap: Optional[Classmap],
    version: str,
    name: str,
    verbose: bool,
):
    line_parts_list = read_cil_lines(
        cil_path,
        name=name,
        verbose=verbose,
    )

    if classmap is None:
        classmap_rules = RuleContainer()
        _parse_cil_lines(
            line_parts_list,
            classmap_rules,
            # unused
            RuleContainer(),
            conditional_types_map,
            reference_conditional_types_maps,
            version=version,
            allowed_types=frozenset(CIL_CLASSPERM_TYPES),
        )

        classmap = Classmap.from_rules(classmap_rules)

    # Parse twice to avoid having to deal with generated typeattributesets
    _parse_cil_lines(
        line_parts_list,
        rules,
        genfs_rules,
        conditional_types_map,
        reference_conditional_types_maps,
        classmap=classmap,
        version=version,
        allowed_types=frozenset({CilRuleType.TYPEATTRIBUTESET}),
    )

    _parse_cil_lines(
        line_parts_list,
        rules,
        genfs_rules,
        conditional_types_map,
        reference_conditional_types_maps,
        classmap=classmap,
        version=version,
        disallowed_types=frozenset(
            {CilRuleType.TYPEATTRIBUTESET} | CIL_CLASSPERM_TYPES
        ),
    )

    return classmap


def read_cil_lines(
    cil_path: Path,
    name: str,
    verbose: bool,
):
    if verbose:
        print(f'Loading {name}: {cil_path}')

    cil_data = cil_path.read_text()

    line_parts_list: List[cil_line_type] = []
    current_mark: Optional[LineMark] = None

    for line in cil_data.splitlines():
        if not line:
            continue

        if line.startswith(CIL_COMMENT_MARKER):
            if line.startswith(LMX_PREFIX):
                number, path = line[len(LMX_PREFIX) :].split(' ', 1)
                current_mark = LineMark(path, int(number))
            elif line == LME_MARKER:
                current_mark = None
            continue

        parts = unpack_cil_line(line)
        if parts is None:
            continue

        line_parts_list.append((line, parts, current_mark))

    return line_parts_list


def decompile_binary_to_policy(
    binary_path: Path,
    policy_type: PolicyType,
    metadata: PolicyMetadata,
    verbose: bool,
):
    genfs_rules = RuleContainer()
    rules = RuleContainer()
    conditional_types_map: Dict[str, ConditionalType] = {}

    with binary_to_cil_policy(binary_path) as cil_policy_path:
        parse_cil_lines(
            cil_policy_path,
            rules,
            genfs_rules,
            conditional_types_map,
            reference_conditional_types_maps=[],
            classmap=None,
            version=metadata.version,
            name=policy_type.pretty_name,
            verbose=verbose,
        )

    return Policy(
        policy_type,
        rules,
        genfs_rules,
        contexts={},
        conditional_types_map=conditional_types_map,
        metadata=metadata,
    )


def parse_dump_policy_rules(
    policy_index: PolicyIndex,
    dump_root: Path,
    policy_type: PolicyType,
    metadata: PolicyMetadata,
    verbose: bool,
):
    origin = policy_type.origin
    assert isinstance(origin, PolicyDumpCilOrigin)

    version = get_dump_policy_version(
        dump_root,
        origin.version_source,
    )

    genfs_rules = RuleContainer()
    rules = RuleContainer()
    conditional_types_map: Dict[str, ConditionalType] = {}
    reference_conditional_types_maps: List[Dict[str, ConditionalType]] = []

    for environment_type in origin.needed or ():
        environment_policy = policy_index.get(
            environment_type,
            metadata,
        )

        rules.add_many(environment_policy.rules)

        if environment_policy.conditional_types_map is not None:
            reference_conditional_types_maps.append(
                environment_policy.conditional_types_map,
            )

    classmap = None
    if origin.classmap_source is not None:
        classmap_source_policy = policy_index.find(
            origin.classmap_source,
            metadata,
        )

        if classmap_source_policy is not None:
            classmap = classmap_source_policy.classmap
            assert classmap is not None

    selinux_path = Path(dump_root, origin.partition, 'etc/selinux')
    prefix = (
        origin.file_prefix
        if origin.file_prefix is not None
        else origin.partition
    )
    file_name = origin.file_name or f'{prefix}_sepolicy.cil'
    file_path = Path(selinux_path, file_name)

    if not file_path.exists():
        return None

    classmap = parse_cil_lines(
        file_path,
        rules,
        genfs_rules,
        conditional_types_map,
        reference_conditional_types_maps,
        classmap=classmap,
        version=version,
        name=policy_type.pretty_name,
        verbose=verbose,
    )

    return (
        rules,
        classmap,
        genfs_rules,
        conditional_types_map,
    )


def parse_dump_policy_contexts(
    dump_root: Path,
    partition: str,
    contexts_name_map: FrozenDict[ContextsType, str],
    name: str,
    verbose: bool,
):
    selinux_path = Path(dump_root, partition, 'etc/selinux')

    contexts_texts = {
        context_type: split_normalize_text(
            read_texts(
                resolve_paths(
                    [selinux_path],
                    names={context_name},
                    recursive=False,
                    paths_name=f'{name} {context_name}',
                    verbose=verbose,
                )
            )
        )
        for context_type, context_name in contexts_name_map.items()
    }

    contexts = {
        context_type: parse_contexts_texts(
            context_texts,
        )
        for context_type, context_texts in contexts_texts.items()
    }

    return contexts
