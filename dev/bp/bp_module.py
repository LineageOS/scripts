from typing import List, NotRequired, TypedDict


class BpModule(TypedDict):
    name: str
    module: str


class SoongConfigModuleTypeModule(BpModule):
    module_type: str


class FilegroupModule(BpModule):
    srcs: List[str]


class AppModule(BpModule):
    manifest: NotRequired[str]
    additional_manifests: NotRequired[List[str]]
    defaults: NotRequired[List[str]]
    static_libs: NotRequired[List[str]]
    resource_dirs: NotRequired[List[str]]


class RROModule(BpModule):
    manifest: NotRequired[str]
    resource_dirs: NotRequired[List[str]]
