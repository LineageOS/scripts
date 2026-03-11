# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import functools
import os
import re
from fnmatch import fnmatch
from os import path
from typing import (
    Callable,
    DefaultDict,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Union,
)

from lxml import etree

from apk.arsc_decode_string import ASCII_WHITESPACE, str_needs_whitespace_quotes
from rro.manifest import NAMESPACE
from rro.resource import (
    RawResource,
    Resource,
    XMLResource,
    is_by_rel_path_raw_resources,
    is_by_rel_path_xml_resources,
    is_raw_resource,
    is_xml_resource,
)
from rro.resource_map import IndexFlags, ResourceMap
from rro.utils import is_referenced_resource_element
from utils.frozendict import FrozenDict
from utils.utils import Color, color_print
from utils.xml_utils import (
    XML_COMMENT_TEXT,
    xml_attrib_matches,
    xml_read_prefix_before_tag,
)

Element = etree._Element  # type: ignore
ElementTree = etree._ElementTree  # type: ignore
Comment = etree._Comment  # type: ignore

TRANSLATABLE_KEY = 'translatable'
FEATURE_FLAG_KEY = f'{{{NAMESPACE}}}featureFlag'
MSGID_KEY = 'msgid'
RESOURCES_TAG = 'resources'
RESOURCES_DIR = 'res'
NAME_KEY = 'name'
PRODUCT_KEY = 'product'
DEFAULT_PRODUCT = 'default'
DIMEN_TAG = 'dimen'
STRING_TAG = 'string'


def node_has_space_after(node: Element):
    return node.tail is not None and node.tail.count('\n') > 1


UNITS = (
    'dip',
    'dp',
    'sp',
    'px',
    'pt',
    'in',
    'mm',
)


def normalize_node_text_dimens_units(text: str):
    left = text[: len(text) - len(text.lstrip())]
    right = text[len(text.rstrip()) :]
    core = text[len(left) : len(text) - len(right)]

    for u in UNITS:
        if not core.endswith(u):
            continue

        num = core[: -len(u)]

        if u == 'dip':
            u = 'dp'

        if num.endswith('.0'):
            num = num[:-2]

        core = num + u
        break

    return left + core + right


ANY_WS_PATTERN = re.compile(rf'[{re.escape(ASCII_WHITESPACE)}]+')


def normalize_node_text_string(text: str):
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        # Replace \' with '
        text = text.replace("\\'", "'")

        inner = text[1:-1]
        if not str_needs_whitespace_quotes(inner):
            # No whitespace issues, add \' back
            inner = inner.replace("'", "\\'")
            return inner

        return text

    return ANY_WS_PATTERN.sub(' ', text).strip(ASCII_WHITESPACE)


SKIP_TAGS = {
    'java-symbol',
    'eat-comment',
    'skip',
    'public',
}

PSEUDOLOCALES = (
    'en-rXA',
    'ar-rXB',
    'en-rXC',
)


def parse_xml_resources(
    res_dir: str,
    dir_name: str,
    file_name: str,
    is_default: bool,
    track_index: bool,
    data: bytes,
    resources: Set[Resource],
    resource_names: Optional[FrozenSet[str]],
):
    root = etree.fromstring(data)

    if root.tag != RESOURCES_TAG:
        return None

    comments: List[Comment] = []
    prev_was_comment = False
    if track_index:
        index = 0
    else:
        index = -1
    for node in root:
        if isinstance(node, Comment):
            # Last element was not a comment, don't stack them
            # Or it was a comment, but they were not stacked
            if (not prev_was_comment) or (
                comments and node_has_space_after(comments[-1])
            ):
                comments = []

            comments.append(node)
            prev_was_comment = True
            continue

        prev_was_comment = False

        tag = node.tag
        if tag in SKIP_TAGS:
            comments = []
            continue

        name = node.attrib.get(NAME_KEY, '')
        if not name:
            raise ValueError('Node has no name')

        if resource_names is not None and name not in resource_names:
            if node_has_space_after(node):
                comments = []
            continue

        product = node.attrib.get(PRODUCT_KEY, '')
        # TODO: find out if this is really correct
        if product == DEFAULT_PRODUCT:
            product = ''

        feature_flag = node.attrib.get(FEATURE_FLAG_KEY, '')

        if node.text is not None:
            # TODO: this is just a hack for wrong @*
            node.text = node.text.replace('@*', '@')

            if tag == DIMEN_TAG:
                node.text = normalize_node_text_dimens_units(node.text)

            if tag == STRING_TAG:
                node.text = normalize_node_text_string(node.text)

        # Overlays don't have translatable=false, remove it to fix
        # equality check
        if TRANSLATABLE_KEY in node.attrib:
            del node.attrib[TRANSLATABLE_KEY]

        if MSGID_KEY in node.attrib:
            del node.attrib[MSGID_KEY]

        resource = XMLResource(
            index=index,
            res_dir=res_dir,
            file_name=file_name,
            dir_name=dir_name,
            is_default=is_default,
            tag=tag,
            name=name,
            element=node,
            comments=comments,
            product=product,
            feature_flag=feature_flag,
        )
        if track_index:
            index += 1

        # Assign the same comment to entries following each other without a
        # newline
        if node_has_space_after(node):
            comments = []

        resources.add(resource)


def resources_reference_name_sorted(resources: Set[Resource]):
    return sorted(set(r.reference_name for r in resources))


def sorted_scandir(dir_path: str):
    return sorted(os.scandir(dir_path), key=lambda e: e.path)


@functools.cache
def parse_package_resources_dir(
    resources_path: str,
    parse_all_values: bool,
    read_raw_resources: bool,
    track_index: bool,
    dir_names: Optional[FrozenDict[str, FrozenSet[str]]],
):
    resources: Set[Resource] = set()

    for dir_file in sorted_scandir(resources_path):
        if not dir_file.is_dir():
            continue

        dir_name = dir_file.name
        is_values = dir_name.startswith('values')
        is_default = '-' not in dir_name

        resource_names = None
        if dir_names is not None:
            resource_names = dir_names.get(dir_name)

        if (
            is_values
            and not is_default
            and any(locale in dir_name for locale in PSEUDOLOCALES)
        ):
            continue

        if dir_names is not None and dir_name not in dir_names:
            continue

        if not parse_all_values and not is_default:
            continue

        for resource_file in sorted_scandir(dir_file.path):
            if not resource_file.is_file():
                continue

            if (
                resource_file.name.startswith('public-')
                or resource_file.name == 'public.xml'
            ):
                continue

            if resource_file.name == 'symbols.xml':
                continue

            # Some apps don't place their res directory directly under
            # the package directory
            # Only keep the resource directory name
            file_name = path.basename(resource_file.path)

            data = None
            if is_values or read_raw_resources:
                with open(resource_file.path, 'rb') as f:
                    data = f.read()

            if is_values:
                assert data is not None
                parse_xml_resources(
                    res_dir=resources_path,
                    dir_name=dir_name,
                    file_name=file_name,
                    is_default=is_default,
                    track_index=track_index,
                    data=data,
                    resources=resources,
                    resource_names=resource_names,
                )
            else:
                if (
                    resource_names is not None
                    and file_name not in resource_names
                ):
                    continue

                resource = RawResource(
                    dir_name=dir_name,
                    name=file_name,
                    is_default=is_default,
                    data=data,
                )
                resources.add(resource)

    return resources


def parse_resources(
    resource_map: ResourceMap,
    resources_paths: Iterable[str],
    parse_all_values: bool,
    read_raw_resources: bool,
    track_index: bool,
    dir_names: Optional[FrozenDict[str, FrozenSet[str]]],
):
    for resources_path in resources_paths:
        resources = parse_package_resources_dir(
            resources_path=resources_path,
            parse_all_values=parse_all_values,
            read_raw_resources=read_raw_resources,
            track_index=track_index,
            dir_names=dir_names,
        )
        resource_map.add_many(resources)


@functools.cache
def get_target_package_resources(
    resources_paths: Tuple[str, ...],
    parse_all_values: bool,
    dir_names: FrozenDict[str, FrozenSet[str]],
):
    resource_map = ResourceMap(
        indices=IndexFlags.BY_NAME,
    )
    parse_resources(
        resource_map=resource_map,
        resources_paths=resources_paths,
        parse_all_values=parse_all_values,
        read_raw_resources=False,
        track_index=True,
        dir_names=dir_names,
    )
    return resource_map


def find_target_package_resources(
    target_packages: List[Tuple[str, str, List[str]]],
    resources: ResourceMap,
    parse_all_values: bool,
    dir_names: Optional[FrozenDict[str, FrozenSet[str]]],
):
    assert len(target_packages)

    if len(target_packages) == 1:
        _, module_name, resources_paths = target_packages[0]
        package_resources = get_target_package_resources(
            resources_paths=tuple(resources_paths),
            parse_all_values=parse_all_values,
            dir_names=dir_names,
        )
        return package_resources, module_name

    best_matching_resources = None
    best_module_name = None
    best_resources = None

    for _, module_name, resources_paths in target_packages:
        package_resources = get_target_package_resources(
            resources_paths=tuple(resources_paths),
            parse_all_values=parse_all_values,
            dir_names=dir_names,
        )

        matching_resources = 0
        for resource in resources:
            package_resource = package_resources.one_by_name(
                resource.name,
            )
            if package_resource is not None:
                matching_resources += 1

        if (
            best_matching_resources is None
            or matching_resources > best_matching_resources
        ):
            best_matching_resources = matching_resources
            best_module_name = module_name
            best_resources = package_resources

    assert best_resources is not None
    assert best_module_name is not None

    return best_resources, best_module_name


def keep_referenced_resources_from_removal(
    resources_to_remove: Set[Resource],
    all_resources: ResourceMap,
    package: str,
    verbose: bool,
    device: Optional[str] = None,
):
    device_str = ''
    if device is not None:
        device_str = f'{device}: '

    keep_resources: Set[Resource] = set()

    for resource in resources_to_remove:
        # If there are any resources referenced by this resource which will not
        # get removed, do not remove any of them
        resource_referenced_by = all_resources.resources_referenced_by(resource)
        referenced_in_remove = resource_referenced_by & resources_to_remove
        not_in_remove = resource_referenced_by - resources_to_remove
        if not_in_remove:
            keep_resources.add(resource)
            keep_resources.update(referenced_in_remove)

            if verbose:
                for ref_resource in not_in_remove:
                    color_print(
                        f'{device_str}'
                        f'{package}: keeping {resource.reference_name} -> '
                        f'{ref_resource.reference_name}',
                        color=Color.YELLOW,
                    )

        # If there are resources referencing this resource which will not get
        # removed, do not remove this resource either
        resources_referencing = all_resources.resources_referencing(resource)
        not_in_remove = resources_referencing - resources_to_remove
        if not_in_remove:
            keep_resources.add(resource)

            if verbose:
                for ref_resource in not_in_remove:
                    color_print(
                        f'{device_str}'
                        f'{package}: keeping {resource.reference_name} <- '
                        f'{ref_resource.reference_name}',
                        color=Color.YELLOW,
                    )

    resources_to_remove -= keep_resources


def overlay_resources_process(
    resources: ResourceMap,
    fn: Callable[
        [Resource],
        Union[
            # Replace
            Tuple[
                Resource,
                Resource,
            ],
            # Remove
            Literal[True],
            # Skip
            None,
        ],
    ],
    package: str,
    keep_if_referenced: bool = False,
    verbose: bool = False,
):
    removed_resources: Set[Resource] = set()
    added_resources: Set[Resource] = set()

    for resource in resources:
        result = fn(resource)
        if result is None:
            continue

        if result is True:
            removed_resources.add(resource)
            continue

        remove_resource, add_resource = result
        removed_resources.add(remove_resource)
        added_resources.add(add_resource)

    if keep_if_referenced:
        keep_referenced_resources_from_removal(
            removed_resources,
            resources,
            package=package,
            verbose=verbose,
        )

    for resource in removed_resources:
        resources.remove(resource)

    for resource in added_resources:
        resources.add(resource)

    return removed_resources, added_resources


def is_resource_entry_wildcard(resource_entry: str):
    return any(c in resource_entry for c in '*?[')


def filter_resource_entries(
    resource_entries: DefaultDict[Optional[str], Set[str]],
    package: str,
):
    none_entries = resource_entries[None]
    package_entries = resource_entries[package]

    normal_entries: Set[str] = set()
    wildcard_entries: Set[str] = set()
    for entry in none_entries | package_entries:
        if is_resource_entry_wildcard(entry):
            wildcard_entries.add(entry)
        else:
            normal_entries.add(entry)

    return frozenset(normal_entries), frozenset(wildcard_entries)


def is_resource_in_entries(
    resource: Resource,
    resource_entries: Tuple[FrozenSet[str], FrozenSet[str]],
):
    if not resource_entries:
        return False

    normal_entries = resource_entries[0]
    wildcard_entries = resource_entries[1]

    if is_raw_resource(resource):
        if resource.name in normal_entries:
            return True
        if resource.rel_path in normal_entries:
            return True

        for pattern in wildcard_entries:
            if fnmatch(resource.name, pattern):
                return True
            if fnmatch(resource.rel_path, pattern):
                return True

    elif is_xml_resource(resource):
        if resource.name in normal_entries:
            return True

        for pattern in wildcard_entries:
            if fnmatch(resource.name, pattern):
                return True
    else:
        assert False

    return False


def overlay_resources_remove(
    package: str,
    resources: ResourceMap,
    remove_resources: Tuple[FrozenSet[str], FrozenSet[str]],
):
    def remove_resource(resource: Resource):
        if is_resource_in_entries(
            resource,
            remove_resources,
        ):
            return True

    removed_resources, _ = overlay_resources_process(
        resources,
        remove_resource,
        package=package,
    )

    return removed_resources


def fixup_resource_attrib(
    resource: XMLResource,
    package_resource: XMLResource,
):
    attrib: Optional[Dict[str | bytes, str | bytes]] = None

    def assign_attrib(name: str):
        nonlocal attrib

        package_attrib = package_resource.element.attrib.get(name)
        if resource.element.attrib.get(name) == package_attrib:
            return False

        if attrib is None:
            attrib = dict(resource.element.attrib)

        if package_attrib is None:
            attrib.pop(name)
        else:
            attrib[name] = package_attrib

        return True

    tag = None
    if resource.tag != package_resource.tag:
        tag = package_resource.tag

    assign_attrib('type')
    assign_attrib('format')

    return tag, attrib


def overlay_resources_remove_missing(
    package: str,
    resources: ResourceMap,
    package_resources: ResourceMap,
    manifest_tree: Optional[ElementTree],
    keep_resources: Tuple[FrozenSet[str], FrozenSet[str]],
):
    kept_resources: Set[Resource] = set()

    def remove_missing_resource(resource: Resource):
        if is_resource_in_entries(
            resource,
            keep_resources,
        ):
            kept_resources.add(resource)
            return

        matching_package_resources = package_resources.by_name(
            resource.name,
        )
        for package_resource in matching_package_resources:
            if package_resource.is_default:
                return

        if manifest_tree is not None:
            is_manifest_referencing = is_referenced_resource_element(
                resource.reference_name,
                manifest_tree.getroot(),
            )
            if is_manifest_referencing:
                return

        return True

    removed_resources, _ = overlay_resources_process(
        resources,
        remove_missing_resource,
        keep_if_referenced=True,
        package=package,
    )

    return removed_resources, kept_resources


def package_resource_sort_key(resource: Resource):
    assert is_xml_resource(resource)

    return (
        not resource.comments,
        not resource.is_default,
        bool(resource.product),
        resource.dir_name,
        resource.name,
        tuple(
            (
                # Longest length first
                -len(r.text if r.text is not None else ''),
                # Stable sort across text
                r.text if r.text is not None else '',
            )
            for r in resource.comments
        ),
    )


def overlay_resource_fixup_from_package(
    package: str,
    resources: ResourceMap,
    package_resources: ResourceMap,
):
    wrong_tag_resources: Set[Tuple[str, str]] = set()

    def fixup_resource_from_package(resource: Resource):
        if not is_xml_resource(resource):
            return

        matching_package_resources = package_resources.by_name(
            resource.name,
        )
        if not matching_package_resources:
            return

        matching_package_resources = sorted(
            matching_package_resources,
            key=package_resource_sort_key,
        )
        package_resource = matching_package_resources[0]

        assert isinstance(package_resource, XMLResource)
        tag, attrib = fixup_resource_attrib(resource, package_resource)
        index = package_resource.index
        comments = package_resource.comments
        file_name = package_resource.file_name
        res_dir = package_resource.res_dir

        new_resource = resource.copy(
            tag=tag,
            attrib=attrib,
            index=index,
            comments=comments,
            file_name=file_name,
            res_dir=res_dir,
        )

        if tag is not None or attrib is not None:
            wrong_tag_resources.add(
                (
                    resource.reference_name,
                    new_resource.reference_name,
                )
            )

        return resource, new_resource

    overlay_resources_process(
        resources,
        fixup_resource_from_package,
        package=package,
    )

    return wrong_tag_resources


def attrib_needs_aapt_raw(
    _attrib_key: str | bytes,
    attrib_value: str | bytes,
):
    if not len(attrib_value) > 1:
        return False

    if isinstance(attrib_value, bytes):
        return attrib_value.startswith(b'0')
    elif isinstance(attrib_value, str):
        return attrib_value.startswith('0')
    else:
        assert False


def raw_resource_need_aapt_raw(resource: RawResource):
    if not resource.name.endswith('.xml'):
        return False

    try:
        assert resource.data is not None
        if xml_attrib_matches(resource.data, attrib_needs_aapt_raw):
            return True
    except etree.XMLSyntaxError:
        pass

    return None


def write_xml_resources(
    xml_path: str,
    resources: List[XMLResource],
    preserved_prefix: Optional[bytes] = None,
):
    xml_dir_path = path.dirname(xml_path)
    os.makedirs(xml_dir_path, exist_ok=True)

    root = etree.Element(RESOURCES_TAG)
    tree = etree.ElementTree(root)

    # Only add default header when we're NOT preserving an existing prefix
    if preserved_prefix is None:
        root.addprevious(etree.Comment(XML_COMMENT_TEXT))

    next_line_spacing = '\n' + ' ' * 4
    root.text = next_line_spacing
    last_element = None

    for resource in resources:
        # Add a newline and indent between this element and the last element
        if last_element is not None:
            last_element.tail = '\n' + next_line_spacing

        for comment in resource.comments:
            # Only add comment if its parent is not root
            # If parent is root then comment was added for past entries
            if comment.getparent() != root:
                root.append(comment)
                last_element = comment

            assert last_element is not None
            last_element.tail = next_line_spacing

        root.append(resource.element)
        last_element = resource.element

    if last_element is not None:
        last_element.tail = '\n'

    xml_body = etree.tostring(
        tree,
        pretty_print=True,
        encoding='utf-8',
    )

    with open(xml_path, 'wb') as o:
        if preserved_prefix is not None:
            o.write(preserved_prefix)
        else:
            o.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        o.write(xml_body)


def write_resources(
    all_resources: ResourceMap,
    output_path: str,
    resources_dir: str,
    preserved_prefixes: Optional[Dict[str, bytes]],
):
    if preserved_prefixes is None:
        preserved_prefixes = {}

    aapt_raw_resource = None
    for rel_path, resources in all_resources.by_rel_path():
        xml_path = path.join(output_path, resources_dir, rel_path)
        preserved = preserved_prefixes.get(xml_path)

        if not resources:
            continue

        if is_by_rel_path_raw_resources(resources):
            assert len(resources) == 1
            resource = next(iter(resources))

            if aapt_raw_resource is None and raw_resource_need_aapt_raw(
                resource
            ):
                aapt_raw_resource = resource
            write_raw_resource(resource, output_path, resources_dir)
        elif is_by_rel_path_xml_resources(resources):
            sorted_resources = sorted(
                resources,
                key=lambda r: (r.index == -1, r.res_dir, r.index, r.name),
            )

            write_xml_resources(
                xml_path,
                sorted_resources,
                preserved_prefix=preserved,
            )
        else:
            assert False

    return aapt_raw_resource


def write_raw_resource(
    resource: RawResource,
    output_path: str,
    resources_dir: str,
):
    raw_path = path.join(output_path, resources_dir, resource.rel_path)
    raw_dir_path = path.dirname(raw_path)
    os.makedirs(raw_dir_path, exist_ok=True)
    with open(raw_path, 'wb') as raw:
        assert resource.data is not None
        raw.write(resource.data)


def read_xml_resources_prefix(
    all_resources: ResourceMap,
    output_path: str,
    extra_paths: List[str],
):
    rel_xml_paths: Set[str] = set()

    for rel_path, resources in all_resources.by_rel_path():
        if not is_by_rel_path_xml_resources(resources):
            continue

        rel_xml_paths.add(rel_path)

    rel_xml_paths.update(extra_paths)

    preserved_prefixes: Dict[str, bytes] = {}
    for rel_xml_path in rel_xml_paths:
        if rel_xml_path in preserved_prefixes:
            continue

        existing_xml_path = path.join(output_path, rel_xml_path)

        preserved = xml_read_prefix_before_tag(existing_xml_path, 'resources')
        if not preserved:
            continue

        preserved_prefixes[existing_xml_path] = preserved

    return preserved_prefixes
