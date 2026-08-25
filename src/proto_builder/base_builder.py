from .utils import PROTO, LIST_TYPES, COLLECTIONS, BUILTIN_MODULES, NONE_TYPE, ProtoConfig
from .tree_structure import Node
from enum import Enum
import inspect
import types
import re
from typing import (
    get_origin,
    get_type_hints,
    Union,
)

class BaseBuilder:

    def __init__(
        self,
        config: ProtoConfig | None = None,
    ):

        self.config = config or ProtoConfig()

    def to_snake_case(
        self,
        name: str,
    ) -> str:
        name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
        name = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', name)
        return name.lower()

    def get_type_name(
        self,
        _type: object,
    ) -> str:
        return getattr(_type, "__name__", str(_type))

    def get_node_name(
        self,
        annotation: object,
    ) -> str:

        if self.is_union(annotation):
            return "Union"

        if annotation is NONE_TYPE:
            return "NoneType"

        origin = get_origin(annotation)
        if origin in COLLECTIONS:
            return origin.__name__

        if annotation in COLLECTIONS:
            return annotation.__name__

        return self.get_type_name(annotation)

    def is_union(
        self,
        annotation: object,
    ) -> bool:

        origin = get_origin(annotation)
        return origin in (types.UnionType, Union) or annotation in (types.UnionType, Union)

    def is_custom(
        self,
        annotation: object,
    ) -> bool:

        return (
            inspect.isclass(annotation)
            and annotation not in PROTO
            and not self.is_enum(annotation)
            and annotation.__module__ not in BUILTIN_MODULES
            and self.get_type_name(annotation) not in PROTO
        )

    def is_enum(
        self,
        annotation: object,
    ) -> bool:

        return inspect.isclass(annotation) and issubclass(annotation, Enum)

    def is_collection(
        self,
        annotation: object,
    ) -> bool:

        return annotation in COLLECTIONS or get_origin(annotation) in COLLECTIONS

    def get_class_fields(
        self,
        cls: object,
    ) -> dict:

        return get_type_hints(cls, include_extras=True)

    def get_enum_params(
        self,
        enum_class: type[Enum],
    ) -> list[str]:

        return [(item.name, item.value) for item in enum_class]
    
    def is_nested_collection(
        self,
        path: str,
    ) -> bool:
        
        items = path.split(".")
        
        counter = 0
        for i in items:

            if i in LIST_TYPES:
                counter += 1
            else:
                if counter:
                    if counter and i == "dict":
                        return True
                    elif counter > 1 and i == "Union":
                        return True
                counter = 0

            if counter > 1:
                return True

        return False

    def resolve_is_removed(
        self,
        node: Node,
        prefix: str = "",
    ) -> bool:

        prefix = prefix + "." if prefix else prefix
        path = prefix + node.path
        
        is_field = node.data.get("label") == "field"
        next_path = prefix + node.next().path
        
        for i in self.config.remove:
            
            if self.is_subpath(path, i):
                return True
            
            elif is_field and self.is_subpath(next_path, i):
                return True
            
        return False

    def resolve_is_optional(
        self,
        node: Node,
        prefix: str = "",
    ) -> bool:

        prefix = prefix + "." if prefix else prefix
        path = prefix + node.path

        for i in self.config.optional:
            
            if node.parent and i.split(".")[-1] == node.parent.name:
                return True
            
            elif i.split(".")[-1] == node.name and self.is_subpath(path, i):
                return True

        return False

    def resolve_type(
        self,
        node: Node,
        prefix: str = "",
    ) -> type:

        prefix = prefix + "." if prefix else prefix
        path = prefix + node.path

        for i in self.config.override:
            
            k, v = list(i.items())[0]
            
            if self.get_type_name(v) not in path and self.is_subpath(path, k, must_end=True):
                return v

    def ordered_combinations(
        selfm,
        items: list,
    ):
        if len(items) < 2:
            yield items
            return

        first = items[0]
        last = items[-1]
        middle = items[1:-1]

        def helper(start=0, current=None):
            if current is None:
                current = []

            for i in range(start, len(middle)):
                new_current = current + [middle[i]]
                yield [first] + new_current + [last]
                yield from helper(i + 1, new_current)

        yield [first, last]
        yield from helper()

    def is_subpath(
        self,
        path1: str,
        path2: str,
        must_end: bool = False,
    ) -> bool:

        parts1 = path1.split(".")
        parts2 = path2.split(".")

        for i in self.ordered_combinations(parts2):
            check_path = all(p2 in parts1 for p2 in i)
            if must_end:
                if check_path and parts1[-1] == i[-1]:
                    return True
            else:
                if check_path:
                    return True
