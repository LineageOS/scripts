# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from enum import StrEnum
from typing import Dict, List, Optional, Tuple, Type

from sepolicy.classmap import Classmap
from sepolicy.rule import Rule
from sepolicy.rule_container import RuleContainer
from utils.frozendict import FrozenDict


class ContextsType(StrEnum):
    PROPERTY_CONTEXTS_NAME = 'property_contexts'
    FILE_CONTEXTS_NAME = 'file_contexts'
    HWSERVICE_CONTEXTS_NAME = 'hwservice_contexts'
    VNDSERVICE_CONTEXTS_NAME = 'vndservice_contexts'
    SERVICE_CONTEXTS_NAME = 'service_contexts'
    SEAPP_CONTEXTS_NAME = 'seapp_contexts'
    GENFS_CONTEXTS_NAME = 'genfs_contexts'
    BUG_MAP_NAME = 'bug_map'


class PolicyName(StrEnum):
    AUTOMATICALLY_ADDED = 'automatically_added'

    SOURCE_PLATFORM_PUBLIC = 'source_platform_public'
    SOURCE_PLATFORM_PRIVATE = 'source_platform_private'
    SOURCE_PLATFORM_TECHNICAL_DEBT = 'source_platform_technical_debt'
    SOURCE_SYSTEM_EXT_PUBLIC = 'source_system_ext_public'
    SOURCE_SYSTEM_EXT_PRIVATE = 'source_system_ext_private'
    SOURCE_PRODUCT_PUBLIC = 'source_product_public'
    SOURCE_PRODUCT_PRIVATE = 'source_product_private'
    SOURCE_VENDOR = 'source_vendor'

    CIL_PLATFORM = 'prebuilt_platform'
    CIL_SYSTEM_EXT = 'prebuilt_system_ext'
    CIL_PRODUCT = 'prebuilt_product'
    CIL_VENDOR = 'prebuilt_vendor'
    CIL_VERSIONED_PLATFORM = 'prebuilt_versioned_platform'

    CIL_PLATFORM_PUBLIC = 'prebuilt_platform_public'
    CIL_PLATFORM_PRIVATE = 'prebuilt_platform_private'
    CIL_SYSTEM_EXT_PUBLIC = 'prebuilt_system_ext_public'
    CIL_SYSTEM_EXT_PRIVATE = 'prebuilt_system_ext_private'
    CIL_PRODUCT_PUBLIC = 'prebuilt_product_public'
    CIL_PRODUCT_PRIVATE = 'prebuilt_product_private'


def build_contexts_map(
    prefix: Optional[str] = None,
    bug_map_name: Optional[str] = None,
):
    if prefix is not None:
        prefix = f'{prefix}_'
    else:
        prefix = ''

    if bug_map_name is None:
        bug_map_name = str(ContextsType.BUG_MAP_NAME)

    d = {k: f'{prefix}{k}' for k in ContextsType}

    # Special name on vendor
    d[ContextsType.BUG_MAP_NAME] = bug_map_name

    # This is always unprefixed
    d[ContextsType.VNDSERVICE_CONTEXTS_NAME] = (
        ContextsType.VNDSERVICE_CONTEXTS_NAME
    )

    return FrozenDict(d)


class PolicyParseFormat(StrEnum):
    TE = 'te'
    CIL = 'cil'


class PolicyVersionSource(StrEnum):
    SDK = 'sdk'
    BOARD_API = 'board_api'


@dataclass(frozen=True)
class PolicyOrigin:
    pass


@dataclass(frozen=True)
class PolicyParsedOrigin(PolicyOrigin):
    format: PolicyParseFormat
    contexts_name_map: FrozenDict[ContextsType, str]


@dataclass(frozen=True)
class PolicySourceOrigin(PolicyParsedOrigin):
    subdir: Optional[str] = None
    cil_file_name: Optional[str] = None


@dataclass(frozen=True)
class PolicyDumpOrigin(PolicyParsedOrigin):
    partition: str
    version_source: PolicyVersionSource
    classmap_source_policy: Optional[PolicyName] = None
    location: Optional[str] = None
    file_name: Optional[str] = None
    file_prefix: Optional[str] = None
    optional: bool = False
    # Needed at parse time
    needed_policy: Optional[Tuple[PolicyName, ...]] = None


@dataclass(frozen=True)
class PolicyOutput:
    relative_dir: str
    cleanup_policy: Tuple[PolicyName, ...]


@dataclass(frozen=True)
class PolicyHardcodedOrigin(PolicyOrigin):
    rules: Tuple[Rule, ...]


@dataclass(frozen=True)
class PolicyReferencing:
    name: PolicyName
    in_name: PolicyName
    out_name: PolicyName


@dataclass(frozen=True)
class PolicyType:
    name: PolicyName
    origin: Optional[PolicyOrigin] = None
    output: Optional[PolicyOutput] = None
    referencing: Optional[PolicyReferencing] = None

    @property
    def pretty_name(self):
        return self.name.replace('_', ' ')


policy_type_index: Dict[PolicyName, PolicyType] = {}


def add_policy_type(policy_type: PolicyType):
    # Referencing policy should clean up after splitting
    if policy_type.referencing is not None:
        assert policy_type.output is None

    assert policy_type.name not in policy_type_index
    policy_type_index[policy_type.name] = policy_type


add_policy_type(
    PolicyType(
        PolicyName.AUTOMATICALLY_ADDED,
        origin=PolicyHardcodedOrigin(
            rules=(
                # This rule is automatically added by
                # external/selinux/libsepol/src/module_to_cil.c
                Rule('attribute', ('cil_gen_require',)),
            )
        ),
    )
)
add_policy_type(
    PolicyType(
        name=PolicyName.SOURCE_PLATFORM_TECHNICAL_DEBT,
        origin=PolicySourceOrigin(
            format=PolicyParseFormat.CIL,
            subdir='private',
            cil_file_name='technical_debt.cil',
            contexts_name_map=FrozenDict({}),
        ),
    ),
)
add_policy_type(
    PolicyType(
        name=PolicyName.SOURCE_PLATFORM_PUBLIC,
        origin=PolicySourceOrigin(
            format=PolicyParseFormat.TE,
            subdir='public',
            contexts_name_map=build_contexts_map(),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.SOURCE_PLATFORM_PRIVATE,
        origin=PolicySourceOrigin(
            format=PolicyParseFormat.TE,
            subdir='private',
            contexts_name_map=build_contexts_map(),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.SOURCE_SYSTEM_EXT_PUBLIC,
        origin=PolicySourceOrigin(
            format=PolicyParseFormat.TE,
            contexts_name_map=build_contexts_map(),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.SOURCE_SYSTEM_EXT_PRIVATE,
        origin=PolicySourceOrigin(
            format=PolicyParseFormat.TE,
            contexts_name_map=build_contexts_map(),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.SOURCE_PRODUCT_PUBLIC,
        origin=PolicySourceOrigin(
            format=PolicyParseFormat.TE,
            contexts_name_map=build_contexts_map(),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.SOURCE_PRODUCT_PRIVATE,
        origin=PolicySourceOrigin(
            format=PolicyParseFormat.TE,
            contexts_name_map=build_contexts_map(),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.SOURCE_VENDOR,
        origin=PolicySourceOrigin(
            format=PolicyParseFormat.TE,
            subdir='vendor',
            contexts_name_map=build_contexts_map(),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_PLATFORM,
        origin=PolicyDumpOrigin(
            format=PolicyParseFormat.CIL,
            partition='system',
            version_source=PolicyVersionSource.SDK,
            file_prefix='plat',
            contexts_name_map=build_contexts_map(
                prefix='plat',
            ),
        ),
        referencing=PolicyReferencing(
            name=PolicyName.CIL_VERSIONED_PLATFORM,
            in_name=PolicyName.CIL_PLATFORM_PUBLIC,
            out_name=PolicyName.CIL_PLATFORM_PRIVATE,
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_PLATFORM_PUBLIC,
        output=PolicyOutput(
            relative_dir='system/public',
            cleanup_policy=(
                PolicyName.AUTOMATICALLY_ADDED,
                PolicyName.SOURCE_PLATFORM_PUBLIC,
                PolicyName.SOURCE_PLATFORM_TECHNICAL_DEBT,
            ),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_PLATFORM_PRIVATE,
        output=PolicyOutput(
            relative_dir='system/private',
            cleanup_policy=(
                PolicyName.AUTOMATICALLY_ADDED,
                PolicyName.SOURCE_PLATFORM_PRIVATE,
                PolicyName.SOURCE_PLATFORM_TECHNICAL_DEBT,
            ),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_SYSTEM_EXT,
        origin=PolicyDumpOrigin(
            format=PolicyParseFormat.CIL,
            partition='system_ext',
            version_source=PolicyVersionSource.SDK,
            file_prefix='system_ext',
            contexts_name_map=build_contexts_map(
                prefix='system_ext',
            ),
            needed_policy=(PolicyName.CIL_PLATFORM,),
            classmap_source_policy=PolicyName.CIL_PLATFORM,
        ),
        referencing=PolicyReferencing(
            name=PolicyName.CIL_VERSIONED_PLATFORM,
            in_name=PolicyName.CIL_SYSTEM_EXT_PUBLIC,
            out_name=PolicyName.CIL_SYSTEM_EXT_PRIVATE,
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_SYSTEM_EXT_PUBLIC,
        output=PolicyOutput(
            relative_dir='system_ext/public',
            cleanup_policy=(
                PolicyName.CIL_PLATFORM,
                PolicyName.AUTOMATICALLY_ADDED,
                PolicyName.SOURCE_SYSTEM_EXT_PUBLIC,
                PolicyName.SOURCE_PLATFORM_TECHNICAL_DEBT,
            ),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_SYSTEM_EXT_PRIVATE,
        output=PolicyOutput(
            relative_dir='system_ext/private',
            cleanup_policy=(
                PolicyName.CIL_PLATFORM,
                PolicyName.AUTOMATICALLY_ADDED,
                PolicyName.SOURCE_SYSTEM_EXT_PRIVATE,
                PolicyName.SOURCE_PLATFORM_TECHNICAL_DEBT,
            ),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_PRODUCT,
        origin=PolicyDumpOrigin(
            format=PolicyParseFormat.CIL,
            partition='product',
            version_source=PolicyVersionSource.SDK,
            file_prefix='product',
            contexts_name_map=build_contexts_map(
                prefix='product',
            ),
            needed_policy=(PolicyName.CIL_PLATFORM,),
            classmap_source_policy=PolicyName.CIL_PLATFORM,
        ),
        referencing=PolicyReferencing(
            name=PolicyName.CIL_VERSIONED_PLATFORM,
            in_name=PolicyName.CIL_PRODUCT_PUBLIC,
            out_name=PolicyName.CIL_PRODUCT_PRIVATE,
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_PRODUCT_PUBLIC,
        output=PolicyOutput(
            relative_dir='product/public',
            cleanup_policy=(
                PolicyName.CIL_PLATFORM,
                PolicyName.CIL_SYSTEM_EXT_PUBLIC,
                PolicyName.AUTOMATICALLY_ADDED,
                PolicyName.SOURCE_PRODUCT_PUBLIC,
                PolicyName.SOURCE_PLATFORM_TECHNICAL_DEBT,
            ),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_PRODUCT_PRIVATE,
        output=PolicyOutput(
            relative_dir='product/private',
            cleanup_policy=(
                PolicyName.CIL_PLATFORM,
                PolicyName.CIL_SYSTEM_EXT_PRIVATE,
                PolicyName.AUTOMATICALLY_ADDED,
                PolicyName.SOURCE_PRODUCT_PRIVATE,
                PolicyName.SOURCE_PLATFORM_TECHNICAL_DEBT,
            ),
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_VERSIONED_PLATFORM,
        origin=PolicyDumpOrigin(
            format=PolicyParseFormat.CIL,
            partition='vendor',
            version_source=PolicyVersionSource.BOARD_API,
            file_name='plat_pub_versioned.cil',
            # Do not read contexts
            contexts_name_map=FrozenDict({}),
            classmap_source_policy=PolicyName.CIL_PLATFORM,
        ),
    )
)

add_policy_type(
    PolicyType(
        name=PolicyName.CIL_VENDOR,
        origin=PolicyDumpOrigin(
            format=PolicyParseFormat.CIL,
            partition='vendor',
            version_source=PolicyVersionSource.BOARD_API,
            file_prefix='vendor',
            contexts_name_map=build_contexts_map(
                prefix='vendor',
                bug_map_name='selinux_denial_metadata',
            ),
            classmap_source_policy=PolicyName.CIL_PLATFORM,
            needed_policy=(PolicyName.CIL_VERSIONED_PLATFORM,),
        ),
        output=PolicyOutput(
            relative_dir='vendor',
            cleanup_policy=(
                PolicyName.CIL_VERSIONED_PLATFORM,
                PolicyName.AUTOMATICALLY_ADDED,
                PolicyName.SOURCE_VENDOR,
            ),
        ),
    )
)


def get_policy_types_by_origin(policy_origin: Type[PolicyOrigin]):
    for policy_type in policy_type_index.values():
        if isinstance(policy_type.origin, policy_origin):
            yield policy_type


def get_policy_type_by_name(policy_name: PolicyName):
    return policy_type_index[policy_name]


@dataclass(frozen=True)
class PolicyMetadata:
    version: str
    variables: FrozenDict[str, str]


@dataclass
class Policy:
    name: PolicyName
    rules: RuleContainer
    genfs_rules: RuleContainer
    contexts: Dict[ContextsType, List[Tuple[str, ...]]]
    metadata: Optional[PolicyMetadata] = None
    classmap: Optional[Classmap] = None

    @property
    def type(self):
        return get_policy_type_by_name(self.name)

    @property
    def pretty_name(self):
        return self.type.pretty_name

    def __repr__(self):
        num_contexts = sum(len(c) for c in self.contexts.values())
        return (
            f'{self.type.pretty_name}:\n'
            f'rules: {len(self.rules)}\n'
            f'genfs rules: {len(self.genfs_rules)}\n'
            f'contexts: {num_contexts}\n'
        )


def get_hardcoded_policy():
    for policy_type in get_policy_types_by_origin(PolicyHardcodedOrigin):
        assert isinstance(policy_type.origin, PolicyHardcodedOrigin)
        yield Policy(
            name=policy_type.name,
            rules=RuleContainer(policy_type.origin.rules),
            genfs_rules=RuleContainer(),
            contexts={},
            metadata=None,
        )
