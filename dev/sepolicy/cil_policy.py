# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from sepolicy.cil_rule import CilRule, CilRuleType, unpack_cil_line
from sepolicy.conditional_type import ConditionalType
from sepolicy.contexts import (
    parse_contexts_texts,
    split_normalize_contexts_text,
)
from sepolicy.match import flush_same_ioctl_rules, merge_ioctl_rule_or_add
from sepolicy.policy import (
    ContextsType,
    Policy,
    PolicyDumpOrigin,
    PolicyMetadata,
    PolicyName,
    PolicyType,
    PolicyVersionSource,
    get_policy_type_by_name,
    get_policy_types_by_origin,
)
from sepolicy.rule import Rule, raw_parts_list
from sepolicy.rule_container import RuleContainer
from utils.frozendict import FrozenDict
from utils.utils import Color, color_print, read_texts, resolve_paths

# From system/sepolicy/flagging/Android.bp
NEEDED_BUILD_FLAGS = {
    'RELEASE_AVF_SUPPORT_CUSTOM_VM_WITH_PARAVIRTUALIZED_DEVICES',
    'RELEASE_AVF_ENABLE_EARLY_VM',
    'RELEASE_AVF_ENABLE_DEVICE_ASSIGNMENT',
    'RELEASE_AVF_ENABLE_LLPVM_CHANGES',
    'RELEASE_AVF_ENABLE_NETWORK',
    'RELEASE_AVF_ENABLE_MICROFUCHSIA',
    'RELEASE_AVF_ENABLE_VM_TO_TEE_SERVICES_ALLOWLIST',
    'RELEASE_AVF_ENABLE_WIDEVINE_PVM',
    'RELEASE_RANGING_STACK',
    'RELEASE_READ_FROM_NEW_STORAGE',
    'RELEASE_SUPERVISION_SERVICE',
    'RELEASE_HARDWARE_BLUETOOTH_RANGING_SERVICE',
    'RELEASE_UNLOCKED_STORAGE_API',
    'RELEASE_BLUETOOTH_SOCKET_SERVICE',
    'RELEASE_SEPOLICY_RESTRICT_KERNEL_KEYRING_SEARCH',
    'RELEASE_TELEPHONY_MODULE',
}


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


@cache
def read_build_flags_data(build_flags_path: Path):
    return json.loads(build_flags_path.read_text())


def get_build_flag_variables(
    build_flags_path: Path,
    build_flags: Set[str],
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
    partition: str,
):
    platform_build_prop_path = Path(dump_root, 'system/build.prop')
    vendor_build_prop_path = Path(dump_root, 'vendor/build.prop')

    target_arch = read_build_prop(
        vendor_build_prop_path,
        'ro.bionic.arch',
    )

    build_type = read_build_prop(
        platform_build_prop_path,
        'ro.build.type',
    )

    build_flags_path = Path(
        dump_root,
        partition,
        'etc/build_flags.json',
    )
    build_flag_variables = get_build_flag_variables(
        build_flags_path,
        NEEDED_BUILD_FLAGS,
    )

    #
    # Gather all variables needed for conditional
    #
    variables: Dict[str, str] = {}
    variables.update(build_flag_variables)

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

    # TODO: set to false for recovery
    variables['target_full_treble'] = 'true'

    # TODO: set to false for recovery
    variables['target_compatible_property'] = 'true'

    # TODO: set to false for recovery, allow for parsing from user
    # BUILD_BROKEN_TREBLE_SYSPROP_NEVERALLOW
    variables['target_treble_sysprop_neverallow'] = 'true'

    # TODO: set to false for recovery, allow for parsing from user
    # BUILD_BROKEN_ENFORCE_SYSPROP_OWNER
    variables['target_enforce_sysprop_owner'] = 'true'

    # Set to true for CTS only
    variables['target_exclude_build_test'] = 'false'

    # PRODUCT_REQUIRES_INSECURE_EXECMEM_FOR_SWIFTSHADER
    variables['target_requires_insecure_execmem_for_swiftshader'] = 'false'

    # PRODUCT_SET_DEBUGFS_RESTRICTIONS
    variables['target_enforce_debugfs_restriction'] = 'true'

    # TODO: set to true for recovery
    variables['target_recovery'] = 'false'

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
    line_parts_list: List[Tuple[str, raw_parts_list]],
    rules: RuleContainer,
    genfs_rules: RuleContainer,
    conditional_types_map: Dict[str, ConditionalType],
    version: str,
    name: str,
    allowed_types: Optional[FrozenSet[str]] = None,
    disallowed_types: Optional[FrozenSet[str]] = None,
):
    same_rules: List[Rule] = []
    merged_ioctl_rules = 0
    added_ioctl_rules = 0

    # ioctl rules are split at comments / newlines by the compiler
    # merge adjacent ioctl rules of the same type back
    # TODO: this won't work if the rules end up next to eachother but
    # they weren't next to eachother initially, but the chances for that
    # are very low

    def add_rule(rule: Rule):
        nonlocal merged_ioctl_rules
        nonlocal added_ioctl_rules

        new_merged_ioctl_rules, new_added_ioctl_rules = merge_ioctl_rule_or_add(
            rules,
            same_rules,
            rule,
        )

        merged_ioctl_rules += new_merged_ioctl_rules
        added_ioctl_rules += new_added_ioctl_rules

    def add_genfs_rule(rule: Rule):
        genfs_rules.add(rule)

    for line, parts in line_parts_list:
        CilRule.from_line(
            line,
            parts,
            conditional_types_map=conditional_types_map,
            allowed_types=allowed_types,
            disallowed_types=disallowed_types,
            add_rule=add_rule,
            add_genfs_rule=add_genfs_rule,
            version=version,
        )

    new_merged_ioctl_rules, new_added_ioctl_rules = flush_same_ioctl_rules(
        rules,
        same_rules,
    )
    merged_ioctl_rules += new_merged_ioctl_rules
    added_ioctl_rules += new_added_ioctl_rules

    if not merged_ioctl_rules:
        return

    color_print(
        f'Merged {merged_ioctl_rules} rules '
        f'into {added_ioctl_rules} ioctl rules '
        f'for {name}',
        color=Color.GREEN,
    )


def parse_cil_lines(
    dump_root: Path,
    origin: PolicyDumpOrigin,
    rules: RuleContainer,
    genfs_rules: RuleContainer,
    conditional_types_map: Dict[str, ConditionalType],
    version: str,
    name: str,
    verbose: bool,
):

    selinux_path = Path(dump_root, origin.partition, 'etc/selinux')

    cil_prefix = origin.cil_prefix or origin.partition
    cil_name = origin.cil_file_name or f'{cil_prefix}_sepolicy.cil'
    line_parts_list = read_cil_lines(
        selinux_path,
        cil_name,
        name=name,
        verbose=verbose,
    )

    # Parse twice to avoid having to deal with generated typeattributesets
    _parse_cil_lines(
        line_parts_list,
        rules,
        genfs_rules,
        conditional_types_map,
        version,
        name=name,
        allowed_types=frozenset({CilRuleType.TYPEATTRIBUTESET}),
    )

    _parse_cil_lines(
        line_parts_list,
        rules,
        genfs_rules,
        conditional_types_map,
        version,
        name=name,
        disallowed_types=frozenset({CilRuleType.TYPEATTRIBUTESET}),
    )


def read_cil_lines(
    selinux_path: Path,
    cil_name: str,
    name: str,
    verbose: bool,
):
    cil_path = Path(selinux_path, cil_name)
    if verbose:
        print(f'Loading {name}: {cil_path}')

    cil_data = cil_path.read_text()

    line_parts_list: List[Tuple[str, raw_parts_list]] = []
    for line in cil_data.splitlines():
        parts = unpack_cil_line(line)
        if parts is None:
            continue

        line_parts_list.append((line, parts))

    return line_parts_list


def parse_dump_policy_rules(
    dump_root: Path,
    policy_type: PolicyType,
    verbose: bool,
):
    assert isinstance(policy_type.origin, PolicyDumpOrigin)

    version = get_dump_policy_version(
        dump_root,
        policy_type.origin.version_source,
    )

    conditional_types_map: Dict[str, ConditionalType] = {}

    genfs_rules = RuleContainer()
    rules = RuleContainer(sparse_match=True)

    for environment_name in policy_type.origin.needed_policy or ():
        environment_type = get_policy_type_by_name(environment_name)
        assert isinstance(environment_type.origin, PolicyDumpOrigin)

        parse_cil_lines(
            dump_root,
            environment_type.origin,
            rules,
            genfs_rules,
            conditional_types_map,
            version,
            name=environment_type.pretty_name,
            verbose=verbose,
        )

    parse_cil_lines(
        dump_root,
        policy_type.origin,
        rules,
        genfs_rules,
        conditional_types_map,
        version,
        name=policy_type.pretty_name,
        verbose=verbose,
    )

    return rules, genfs_rules


def parse_dump_policy_contexts(
    dump_root: Path,
    partition: str,
    contexts_name_map: FrozenDict[ContextsType, str],
    name: str,
    verbose: bool,
):
    selinux_path = Path(dump_root, partition, 'etc/selinux')

    contexts_texts = {
        context_type: split_normalize_contexts_text(
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


def parse_dump_policies(dump_root: Path, verbose: bool):
    policy_index: Dict[PolicyName, Policy] = {}

    for policy_type in get_policy_types_by_origin(PolicyDumpOrigin):
        assert isinstance(policy_type.origin, PolicyDumpOrigin)

        partition = policy_type.origin.partition

        version = get_dump_policy_version(
            dump_root,
            policy_type.origin.version_source,
        )

        rules, genfs_rules = parse_dump_policy_rules(
            dump_root,
            policy_type,
            verbose=verbose,
        )
        contexts = parse_dump_policy_contexts(
            dump_root,
            partition=partition,
            contexts_name_map=policy_type.origin.contexts_name_map,
            name=policy_type.pretty_name,
            verbose=verbose,
        )
        variables = parse_dump_policy_variables(
            dump_root,
            version=version,
            partition=partition,
        )

        policy = Policy(
            policy_type.name,
            rules,
            genfs_rules,
            contexts,
            metadata=PolicyMetadata(
                version,
                variables,
            ),
        )

        policy_index[policy_type.name] = policy

        print(f'Found policy: {policy}')

    return policy_index
