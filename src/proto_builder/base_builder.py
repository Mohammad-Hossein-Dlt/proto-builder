from .utils import BUILTIN_MODULES, COLLECTIONS, NONE_TYPE, PROTO, ProtoConfig
from .tree_structure import Node
from enum import Enum
import inspect
import types
import re
from typing import (
    get_args,
    get_origin,
    get_type_hints,
    Union,
    Literal,
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
        _type: type,
    ) -> str:
        return getattr(_type, "__name__", str(_type))

    def is_union(
        self,
        annotation: type,
    ) -> bool:
        
        origin = get_origin(annotation)
        return origin in (types.UnionType, Union) or annotation in (types.UnionType, Union)
    
    def is_optional(
        self,
        annotation: type,
    ) -> bool:
        
        args = get_args(annotation)        
        return self.is_union(annotation) and len(args) == 2 and NONE_TYPE in args

    def is_custom(
        self,
        annotation: type,
    ) -> bool:
    
        return (
            inspect.isclass(annotation)
            and annotation not in PROTO
            and not self.is_enum(annotation)
            and annotation.__module__ not in BUILTIN_MODULES
        )
        
    def is_enum(
        self,
        annotation: type,
    ) -> bool:
    
        return inspect.isclass(annotation) and issubclass(annotation, Enum)

    def is_collection(
        self,
        annotation: type,
    ) -> bool:
    
        return annotation in COLLECTIONS or get_origin(annotation) in COLLECTIONS

    def is_nested_collection(
        self,
        annotation: type,
    ) -> bool:
    
        origin = get_origin(annotation)
        args = get_args(annotation)

        if annotation in COLLECTIONS:
            return False

        if origin in (list, tuple, set):
            return bool(args) and self.is_collection(args[0])

        if origin is dict:
            if len(args) != 2:
                return True
            key_type, value_type = args
            return self.is_collection(key_type) or self.is_collection(value_type)

        return False
    
    def get_class_fields(
        self,
        cls: type,
    ) -> dict:
    
        return get_type_hints(cls, include_extras=True)

    def get_enum_params(
        self,
        enum_class: type[Enum],
    ) -> list[str]:
    
        return [item.name for item in enum_class]

    def create_path_str(
        self,
        *args: Node | str,
    ) -> str:
        
        return ".".join(
            n.name if isinstance(n, Node) else n
            for n in args
            if isinstance(n, (Node, str))
        )

    def resolve_is_removed(
        self,
        node: Node,
    ) -> bool:
        
        data_type = self.get_type_name(node.data.get("type"))
        
        # Exact
        remove_exact_include_self = self.config.get_remove("exact", "include")
        remove_exact_exclude_self = self.config.get_remove("exact", "exclude")
        
        # Scope
        remove_scope_include_self = self.config.get_remove("scope", "include")
        remove_scope_exclude_self = self.config.get_remove("scope", "exclude")
                
        path = self.path_variant(node)
        
        for i in remove_exact_include_self:
            if self.is_subpath(path, i.path) and (i.name == node.name or i.name == data_type):
                return True
            
        for i in remove_scope_include_self:
            if self.is_subpath(path, i.path):
                return True
                        
        path = self.path_variant(node, "exclude-self")
        
        for i in remove_exact_exclude_self:
            if self.is_subpath(path, i.path):
                return True
            
        for i in remove_scope_exclude_self:
            if self.is_subpath(path, i.path):
                return True
                
        return False

    def resolve_is_optional(
        self,
        node: Node,
    ) -> bool:
        
        
        if self.config.optional_all:
            return True
        
        data_type = self.get_type_name(node.data.get("type"))
        
        # Exact
        optional_exact_include_self = self.config.get_optional("exact", "include")
        
        # Scope
        optional_scope_include_self = self.config.get_optional("scope", "include")
        optional_scope_exclude_self = self.config.get_optional("scope", "exclude")
        
        path = self.path_variant(node)
        
        for i in optional_exact_include_self:
            if self.is_subpath(path, i.path) and (i.name == node.name or i.name == data_type):
                return True
            
        for i in optional_scope_include_self:
            if self.is_subpath(path, i.path):
                return True
                        
        path = self.path_variant(node, "exclude-self")
        for i in optional_scope_exclude_self:
            if self.is_subpath(path, i.path):
                return True
            
        return False

    def resolve_type(
        self,
        node: Node,
        annotation: type,
    ) -> type:
        
        override_fields = self.config.get_override()
                
        path = self.path_variant(node)
        for i in override_fields:
            if self.is_subpath(path, i.path) and i.name == node.name:
                return i.data.get("type", annotation)
                
        return annotation
    
    def is_subpath(
        self,
        path1: str,
        path2: str,
        must_end: bool = False,
    ) -> bool:
        parts1 = path1.split(".")
        parts2 = path2.split(".")

        indices = []
        j = 0

        for i, part in enumerate(parts1):
            if j < len(parts2) and part == parts2[j]:
                indices.append(i)
                j += 1

        if j != len(parts2):
            return False

        if must_end:
            return indices[-1] == len(parts1) - 1

        return True
    
    def path_variant(
        self,
        node: Node,
        mode: Literal["include-self", "exclude-self"] = "include-self",
    ) -> str:
        
        if mode == "include-self":
            nodes = node.path_to_root()
        elif mode == "exclude-self":
            nodes = node.path_to_root()[:-1]

        chains: list[str] = []
        
        for n in nodes:
            chains.append(n.name)
            data_type = n.data.get("type")
            if data_type:
                name = self.get_type_name(data_type)
                chains.append(name)
        
        return self.create_path_str(*chains)