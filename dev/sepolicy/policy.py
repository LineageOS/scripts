# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Dict, Iterator, List, Optional, Tuple, Type

from sepolicy.classmap import Classmap
from sepolicy.conditional_type import ConditionalType
from sepolicy.match import RuleMatch
from sepolicy.rule import Rule
from sepolicy.rule_container import RuleContainer
from sepolicy.source_macros import SourceMacros
from sepolicy.source_text import SourceText
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


SOURCE_PREFIX = 'source_'
PREBUILT_PREFIX = 'prebuilt_'


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


class PolicyVersionSource(StrEnum):
    SDK = 'sdk'
    BOARD_API = 'board_api'


@dataclass(frozen=True)
class PolicyOrigin:
    pass


@dataclass(frozen=True)
class PolicySourceOrigin(PolicyOrigin):
    rules_subdirs: Optional[
        Tuple[
            Tuple[
                # subdir
                str,
                # versioned
                bool,
            ],
            ...,
        ]
    ] = None
    macros_subdirs: Optional[
        Tuple[
            Tuple[
                # subdir
                str,
                # versioned
                bool,
            ],
            ...,
        ]
    ] = None
    macro_sources: Optional[Tuple[PolicyType, ...]] = None
    contexts_name_map: Optional[FrozenDict[ContextsType, str]] = None


@dataclass(frozen=True)
class PolicyCombinedOrigin(PolicyOrigin):
    macro_sources: Optional[Tuple[PolicyType, ...]] = None
    rule_sources: Optional[Tuple[PolicyType, ...]] = None
    attribute_sources: Optional[Tuple[PolicyType, ...]] = None


@dataclass(frozen=True)
class PolicyCompiledOrigin(PolicyOrigin):
    source: PolicyType


@dataclass(frozen=True)
class PolicyBinaryCompiledOrigin(PolicyOrigin):
    source: PolicyType


@dataclass(frozen=True)
class PolicySourceCilOrigin(PolicyOrigin):
    cil_file_name: str


@dataclass(frozen=True)
class PolicyDumpOrigin(PolicyOrigin):
    version_source: PolicyVersionSource


@dataclass(frozen=True)
class PolicyDumpCilOrigin(PolicyDumpOrigin):
    partition: str
    file_name: Optional[str] = None
    file_prefix: Optional[str] = None
    classmap_source: Optional[PolicyType] = None
    contexts_name_map: Optional[FrozenDict[ContextsType, str]] = None
    # Needed at parse time
    needed: Optional[Tuple[PolicyType, ...]] = None


@dataclass(frozen=True)
class PolicyDumpBinaryOrigin(PolicyDumpOrigin):
    file_name: Optional[str] = None
    recovery: Optional[bool] = False


@dataclass(frozen=True)
class PolicyCleanupOrigin(PolicyOrigin):
    source: PolicyType
    removed: Tuple[PolicyType, ...]


@dataclass(frozen=True)
class PolicyHardcodedOrigin(PolicyOrigin):
    rules: Tuple[Rule, ...]


@dataclass(frozen=True)
class PolicyReferencedOrigin(PolicyOrigin):
    source: PolicyType
    reference: PolicyType
    in_or_out: bool


@dataclass(frozen=True)
class PolicyMacroMatchOrigin(PolicyOrigin):
    source: PolicyType
    macros: PolicyType
    references: Tuple[PolicyType, ...] = ()


@dataclass(frozen=True)
class PolicyMacroReplaceOrigin(PolicyOrigin):
    source: PolicyType


@dataclass(frozen=True)
class PolicyGatherSourceTextOrigin(PolicyOrigin):
    source: PolicyType


@dataclass(frozen=True)
class PolicyExpandedGuardOrigin(PolicyOrigin):
    source: PolicyType
    expander_source: PolicyType
    reference: PolicyType
    guard: str


@dataclass(frozen=True)
class PolicyAddOrigin(PolicyOrigin):
    source: PolicyType
    added: PolicyType
    guard: str


@dataclass(frozen=True)
class PolicyOutput:
    relative_dir: str


policy_type_index: Dict[str, PolicyType] = {}


def add_policy_type(policy_type: PolicyType):
    assert policy_type.name not in policy_type_index, policy_type.name
    policy_type_index[policy_type.name] = policy_type


class PolicyType:
    def __init__(
        self,
        name: str,
        origin: PolicyOrigin,
        optional: bool = False,
    ):
        self.__name = name
        self.origin = origin
        self.optional = optional
        self.__output: Optional[PolicyOutput] = None
        add_policy_type(self)

    @property
    def name(self) -> str:
        return self.__name

    @property
    def pretty_name(self) -> str:
        return self.__name.replace('_', ' ')

    @property
    def output(self) -> Optional[PolicyOutput]:
        return self.__output

    def __child(self, suffix: str, origin: PolicyOrigin) -> PolicyType:
        return PolicyType(
            f'{self.__name}_{suffix}',
            origin,
            optional=self.optional,
        )

    def macro_match(
        self,
        *,
        macros: PolicyType,
        references: Tuple[PolicyType, ...] = (),
    ) -> PolicyType:
        return self.__child(
            'matched',
            PolicyMacroMatchOrigin(self, macros, references),
        )

    def public(self, *, reference: PolicyType) -> PolicyType:
        return self.__child(
            'public',
            PolicyReferencedOrigin(self, reference, in_or_out=True),
        )

    def private(self, *, reference: PolicyType) -> PolicyType:
        return self.__child(
            'private',
            PolicyReferencedOrigin(self, reference, in_or_out=False),
        )

    def cleanup(self, *, removed: Tuple[PolicyType, ...]) -> PolicyType:
        return self.__child('clean', PolicyCleanupOrigin(self, removed))

    def macro_replace(self) -> PolicyType:
        return self.__child('replaced', PolicyMacroReplaceOrigin(self))

    def gather_source_text(self) -> PolicyType:
        return self.__child(
            'source_text',
            PolicyGatherSourceTextOrigin(self),
        )

    def expanded_guard(
        self,
        *,
        expander: PolicyType,
        reference: PolicyType,
        guard: str,
    ) -> PolicyType:
        return self.__child(
            'guarded',
            PolicyExpandedGuardOrigin(self, expander, reference, guard),
        )

    def add(
        self,
        *,
        added: PolicyType,
        guard: str,
    ) -> PolicyType:
        return self.__child(
            f'with_{guard}',
            PolicyAddOrigin(self, added, guard),
        )

    def output_to(self, *, relative_dir: str):
        self.__output = PolicyOutput(relative_dir)
        return self


def hardcoded(*, name: str, rules: Tuple[Rule, ...]):
    return PolicyType(name, PolicyHardcodedOrigin(rules=rules))


def source_te(
    *,
    name: str,
    rules_subdirs: Optional[Tuple[Tuple[str, bool], ...]] = None,
    macros_subdirs: Optional[Tuple[Tuple[str, bool], ...]] = None,
    macro_sources: Tuple[PolicyType, ...] = (),
    contexts: Optional[FrozenDict[ContextsType, str]] = None,
):
    return PolicyType(
        f'{SOURCE_PREFIX}{name}',
        PolicySourceOrigin(
            rules_subdirs=rules_subdirs,
            macros_subdirs=macros_subdirs,
            macro_sources=macro_sources or None,
            contexts_name_map=contexts,
        ),
    )


def source_cil(*, name: str, cil_file_name: str):
    return PolicyType(
        f'{SOURCE_PREFIX}{name}',
        PolicySourceCilOrigin(cil_file_name=cil_file_name),
    )


def combined(
    *,
    name: str,
    macro_sources: Tuple[PolicyType, ...] = (),
    rule_sources: Tuple[PolicyType, ...] = (),
    attribute_sources: Tuple[PolicyType, ...] = (),
):
    return PolicyType(
        f'{SOURCE_PREFIX}{name}',
        PolicyCombinedOrigin(
            macro_sources=macro_sources or None,
            rule_sources=rule_sources or None,
            attribute_sources=attribute_sources or None,
        ),
    )


def compiled(
    *,
    name: str,
    source: PolicyType,
):
    return PolicyType(
        f'{SOURCE_PREFIX}{name}',
        PolicyCompiledOrigin(source=source),
    )


def binary_compiled(
    *,
    name: str,
    source: PolicyType,
):
    return PolicyType(
        f'{SOURCE_PREFIX}{name}',
        PolicyBinaryCompiledOrigin(source=source),
    )


def dump_cil(
    *,
    name: str,
    partition: str,
    version_source: PolicyVersionSource,
    file_prefix: Optional[str] = None,
    file_name: Optional[str] = None,
    contexts: Optional[FrozenDict[ContextsType, str]] = None,
    classmap_source: Optional[PolicyType] = None,
    needed: Tuple[PolicyType, ...] = (),
):
    return PolicyType(
        f'{PREBUILT_PREFIX}{name}',
        PolicyDumpCilOrigin(
            version_source=version_source,
            partition=partition,
            file_name=file_name,
            file_prefix=file_prefix,
            classmap_source=classmap_source,
            contexts_name_map=contexts,
            needed=needed or None,
        ),
    )


def dump_binary(
    *,
    name: str,
    version_source: PolicyVersionSource,
    file_name: Optional[str] = None,
    optional: bool = False,
    recovery: bool = False,
):
    return PolicyType(
        f'{PREBUILT_PREFIX}{name}',
        PolicyDumpBinaryOrigin(
            version_source=version_source,
            file_name=file_name,
            recovery=recovery,
        ),
        optional=optional,
    )


# This rule is automatically added by
# external/selinux/libsepol/src/module_to_cil.c
automatically_added = hardcoded(
    name='automatically_added',
    rules=(Rule('attribute', ('cil_gen_require',)),),
)

#
# Source policies
#

source_platform_public = source_te(
    name='platform_public',
    rules_subdirs=(('public', True),),
    macros_subdirs=(('public', True), ('private', True)),
    contexts=build_contexts_map(),
)
source_platform_private = source_te(
    name='platform_private',
    rules_subdirs=(('private', True),),
    macro_sources=(source_platform_public,),
    contexts=build_contexts_map(),
)
source_platform_technical_debt = source_cil(
    name='platform_technical_debt',
    cil_file_name='private/technical_debt.cil',
)
source_system_ext_public = source_te(
    name='system_ext_public',
    macro_sources=(source_platform_public,),
    contexts=build_contexts_map(),
)
source_system_ext_private = source_te(
    name='system_ext_private',
    macro_sources=(source_platform_public,),
    contexts=build_contexts_map(),
)
source_product_public = source_te(
    name='product_public',
    macro_sources=(source_platform_public,),
    contexts=build_contexts_map(),
)
source_product_private = source_te(
    name='product_private',
    macro_sources=(source_platform_public,),
    contexts=build_contexts_map(),
)
source_vendor = source_te(
    name='vendor',
    rules_subdirs=(('vendor', False),),
    macro_sources=(source_platform_public,),
    contexts=build_contexts_map(),
)

source_cleanup = source_te(
    name='cleanup',
    macro_sources=(source_platform_public,),
    contexts=build_contexts_map(),
)

#
# Prebuilt policies
#

platform = dump_cil(
    name='platform',
    partition='system',
    version_source=PolicyVersionSource.SDK,
    file_prefix='plat',
    contexts=build_contexts_map(prefix='plat'),
)
versioned_platform = dump_cil(
    name='versioned_platform',
    partition='vendor',
    version_source=PolicyVersionSource.BOARD_API,
    file_name='plat_pub_versioned.cil',
    # Do not read contexts
    contexts=FrozenDict({}),
    classmap_source=platform,
)
system_ext = dump_cil(
    name='system_ext',
    partition='system_ext',
    version_source=PolicyVersionSource.SDK,
    file_prefix='system_ext',
    contexts=build_contexts_map(prefix='system_ext'),
    needed=(platform,),
    classmap_source=platform,
)
product = dump_cil(
    name='product',
    partition='product',
    version_source=PolicyVersionSource.SDK,
    file_prefix='product',
    contexts=build_contexts_map(prefix='product'),
    needed=(platform,),
    classmap_source=platform,
)
vendor = dump_cil(
    name='vendor',
    partition='vendor',
    version_source=PolicyVersionSource.BOARD_API,
    file_prefix='vendor',
    contexts=build_contexts_map(
        prefix='vendor',
        bug_map_name='selinux_denial_metadata',
    ),
    classmap_source=platform,
    needed=(versioned_platform,),
)
recovery = dump_binary(
    name='recovery',
    version_source=PolicyVersionSource.BOARD_API,
    file_name='recovery/sepolicy',
    optional=True,
    recovery=True,
)

#
# Prebuilt policy pipelines
#

# Platform
platform_public = platform.public(reference=versioned_platform)
platform_private = platform.private(reference=versioned_platform)

platform_public_clean = platform_public.macro_match(
    macros=source_platform_public,
).cleanup(
    removed=(
        automatically_added,
        source_platform_public,
        source_platform_technical_debt,
    ),
)
platform_private_clean = platform_private.macro_match(
    macros=source_platform_public,
    references=(platform_public,),
).cleanup(
    removed=(
        automatically_added,
        source_platform_private,
        source_platform_technical_debt,
    ),
)

# System ext
system_ext_public = system_ext.public(reference=versioned_platform)
system_ext_private = system_ext.private(reference=versioned_platform)

system_ext_public_clean = system_ext_public.macro_match(
    macros=source_platform_public,
    references=(platform_public,),
).cleanup(
    removed=(
        platform,
        automatically_added,
        source_system_ext_public,
        source_platform_public,
        source_platform_private,
        source_platform_technical_debt,
    ),
)
system_ext_private_clean = system_ext_private.macro_match(
    macros=source_platform_public,
    references=(
        platform_public,
        platform_private,
        system_ext_public,
    ),
).cleanup(
    removed=(
        platform,
        automatically_added,
        source_system_ext_private,
        source_platform_public,
        source_platform_private,
        source_platform_technical_debt,
    ),
)

# Product
product_public = product.public(reference=versioned_platform)
product_private = product.private(reference=versioned_platform)

product_public_clean = product_public.macro_match(
    macros=source_platform_public,
    references=(
        platform_public,
        system_ext_public,
    ),
).cleanup(
    removed=(
        platform,
        system_ext_public,
        automatically_added,
        source_product_public,
        source_platform_public,
        source_platform_private,
        source_platform_technical_debt,
    ),
)
product_private_clean = product_private.macro_match(
    macros=source_platform_public,
    references=(
        platform_public,
        platform_private,
        system_ext_public,
        system_ext_private,
        product_public,
    ),
).cleanup(
    removed=(
        platform,
        system_ext_private,
        automatically_added,
        source_product_private,
        source_platform_public,
        source_platform_private,
        source_platform_technical_debt,
    ),
)

# Vendor
vendor_clean = vendor.macro_match(
    macros=source_platform_public,
    references=(versioned_platform,),
).cleanup(
    removed=(
        versioned_platform,
        automatically_added,
        source_vendor,
        source_platform_public,
        source_platform_private,
    ),
)


#
# Recovery reference
#

#
# Gather the prebuilt-only partition rules and compile them with the platform
# source to CIL.
# Then use this reference CIL-compiled policy to help expand individual source
# rules, as the reference CIL contains fully built typeattributesets.
# The expanded source rules can then be mapped to the prebuilt recovery binary.
# Use the mapping to guard source rules which are not present in the recovery
# binary with not_recovery().
#


def reference_gathered(clean: PolicyType) -> PolicyType:
    return clean.macro_replace().gather_source_text()


recovery_reference_gathered = (
    reference_gathered(platform_public_clean),
    reference_gathered(platform_private_clean),
    reference_gathered(system_ext_public_clean),
    reference_gathered(system_ext_private_clean),
    reference_gathered(product_public_clean),
    reference_gathered(product_private_clean),
    reference_gathered(vendor_clean),
)
recovery_reference_combined = combined(
    name='recovery_reference_combined',
    macro_sources=(source_platform_public,),
    attribute_sources=recovery_reference_gathered,
    rule_sources=(
        source_platform_public,
        source_platform_private,
        source_system_ext_public,
        source_system_ext_private,
        source_product_public,
        source_product_private,
        source_vendor,
        *recovery_reference_gathered,
    ),
)
recovery_reference_compiled = compiled(
    name='recovery_reference_compiled',
    source=recovery_reference_combined,
)


def guarded_replaced(clean: PolicyType) -> PolicyType:
    return clean.expanded_guard(
        expander=recovery_reference_compiled,
        reference=recovery,
        guard='not_recovery',
    ).macro_replace()


def cleaned_output(clean: PolicyType) -> PolicyType:
    return guarded_replaced(clean.cleanup(removed=(source_cleanup,)))


#
# Partition rules with the not_recovery() guard data in place
#

platform_public_guarded = guarded_replaced(platform_public_clean)
platform_private_guarded = guarded_replaced(platform_private_clean)
system_ext_public_guarded = guarded_replaced(system_ext_public_clean)
system_ext_private_guarded = guarded_replaced(system_ext_private_clean)
product_public_guarded = guarded_replaced(product_public_clean)
product_private_guarded = guarded_replaced(product_private_clean)
vendor_guarded = guarded_replaced(vendor_clean)

cleaned_output(platform_public_clean).output_to(
    relative_dir='system/public',
)
cleaned_output(platform_private_clean).output_to(
    relative_dir='system/private',
)
cleaned_output(system_ext_public_clean).output_to(
    relative_dir='system_ext/public'
)
cleaned_output(system_ext_private_clean).output_to(
    relative_dir='system_ext/private'
)
cleaned_output(product_public_clean).output_to(
    relative_dir='product/public',
)
cleaned_output(product_private_clean).output_to(
    relative_dir='product/private',
)

#
# Reuse the same guarded output data to find out recovery_only() policy
# Compile the guarded output data down to binary policy and subtract it
# from the prebuilt recovery binary policy.
# The recovery_only() rules will be added to vendor.
#

recovery_reference_guarded_gathered = (
    platform_public_guarded.gather_source_text(),
    platform_private_guarded.gather_source_text(),
    system_ext_public_guarded.gather_source_text(),
    system_ext_private_guarded.gather_source_text(),
    product_public_guarded.gather_source_text(),
    product_private_guarded.gather_source_text(),
    vendor_guarded.gather_source_text(),
)
recovery_reference_guarded_combined = combined(
    name='recovery_reference_guarded_combined',
    macro_sources=(source_platform_public,),
    attribute_sources=recovery_reference_guarded_gathered,
    rule_sources=(
        source_platform_public,
        source_platform_private,
        source_system_ext_public,
        source_system_ext_private,
        source_product_public,
        source_product_private,
        source_vendor,
        *recovery_reference_guarded_gathered,
    ),
)
recovery_reference_guarded_compiled = compiled(
    name='recovery_reference_guarded_compiled',
    source=recovery_reference_guarded_combined,
)
recovery_reference_guarded = binary_compiled(
    name='recovery_reference_guarded',
    source=recovery_reference_guarded_compiled,
)

recovery_only_replaced = (
    recovery.cleanup(
        removed=(
            recovery_reference_guarded,
            # For genfs contexts only
            platform,
            system_ext,
            product,
            versioned_platform,
            vendor,
        ),
    )
    .macro_match(
        macros=source_platform_public,
    )
    .macro_replace()
)

cleaned_output(vendor_clean).add(
    added=recovery_only_replaced,
    guard='recovery_only',
).output_to(
    relative_dir='vendor',
)


def get_policy_types() -> Iterator[PolicyType]:
    yield from policy_type_index.values()


def get_policy_type_by_name(policy_name: str):
    return policy_type_index[policy_name]


@dataclass(frozen=True)
class PolicyMetadata:
    version: str
    variables: FrozenDict[str, str]


@dataclass
class Policy:
    type: PolicyType
    rules: RuleContainer
    genfs_rules: RuleContainer
    contexts: Dict[ContextsType, List[Tuple[str, ...]]]
    conditional_types_map: Optional[Dict[str, ConditionalType]] = None
    metadata: Optional[PolicyMetadata] = None
    classmap: Optional[Classmap] = None
    macros: Optional[SourceMacros] = None
    rule_matches: Optional[List[RuleMatch]] = None
    source_text: Optional[SourceText] = None
    guarded_rules: Optional[Dict[Rule, str]] = None
    absent_memberships: Optional[Dict[Tuple[str, str], str]] = None
    text: Optional[str] = None

    def copy(
        self,
        policy_type: PolicyType,
        rules: RuleContainer,
        genfs_rules: RuleContainer,
        contexts: Dict[ContextsType, List[Tuple[str, ...]]],
    ):
        return Policy(
            policy_type,
            rules,
            genfs_rules,
            contexts,
            self.conditional_types_map,
            self.metadata,
            self.classmap,
            self.macros,
            self.rule_matches,
            self.source_text,
            self.guarded_rules,
            self.absent_memberships,
        )

    @property
    def name(self):
        return self.type.name

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


@dataclass(frozen=True)
class PolicyKey:
    policy_type: PolicyType
    metadata: Optional[PolicyMetadata] = None


class PolicyProvider(ABC):
    def __init__(
        self,
        policy_origin: Type[PolicyOrigin],
    ):
        self.__policy_origin = policy_origin

    def can_provide(self, policy_type: PolicyType) -> bool:
        return isinstance(policy_type.origin, self.__policy_origin)

    @property
    def policy_origin(self) -> Type[PolicyOrigin]:
        return self.__policy_origin

    def resolve_metadata(
        self,
        policy_index: 'PolicyIndex',
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ) -> Optional[PolicyMetadata]:
        return requested

    @abstractmethod
    def get_policy(
        self,
        policy_index: 'PolicyIndex',
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata],
    ) -> Optional[Policy]: ...


class PolicyIndex:
    def __init__(self):
        self.__providers: Dict[Type[PolicyOrigin], PolicyProvider] = {}
        self.__policies: Dict[PolicyKey, Policy] = {}

    def register(self, provider: PolicyProvider):
        self.__providers[provider.policy_origin] = provider

    def __get_policy_type_provider(self, policy_type: PolicyType):
        origin_type = type(policy_type.origin)
        provider = self.__providers[origin_type]
        return provider

    def resolve_metadata(
        self,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata] = None,
    ):
        provider = self.__get_policy_type_provider(policy_type)
        return provider.resolve_metadata(self, policy_type, requested)

    def find(
        self,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata] = None,
    ):
        provider = self.__get_policy_type_provider(policy_type)
        metadata = provider.resolve_metadata(self, policy_type, requested)

        key = PolicyKey(policy_type, metadata)

        if key in self.__policies:
            return self.__policies[key]

        policy = provider.get_policy(self, policy_type, metadata)
        if policy:
            self.__policies[key] = policy
            return policy

        if policy_type.optional:
            return None

        raise ValueError(f'Failed to parse {policy_type.name}')

    def get(
        self,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata] = None,
    ):
        policy = self.find(policy_type, requested)
        assert policy is not None
        return policy
