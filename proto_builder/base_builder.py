from .utils import BUILTIN_MODULES, COLLECTIONS, NONE_TYPE, PROTO, ProtoConfig, ProtoType
from tree_structure import PathNode, VariantMode
from enum import Enum
import inspect
import types
from typing import (
    get_args,
    get_origin,
    get_type_hints,
    Union,
    Iterator,
)


class BaseBuilder:
    
    def __init__(
        self,
        config: ProtoConfig | None = None,
    ):
    
        self.config = config or ProtoConfig()

    def format_proto_field(
        self,
        proto: ProtoType,
        index: int,
    ) -> str:
    
        if proto.optional:
            type_decl = f"optional {proto.p_type}"
        elif proto.repeated:
            type_decl = f"repeated {proto.p_type}"
        elif proto.p_type:
            type_decl = proto.p_type
        else:
            type_decl = None

        if type_decl:
            return f"    {type_decl} {proto.name} = {index};"
        return f"    {proto.name} = {index};"

    def is_enum(
        self,
        f_type: type,
    ) -> bool:
    
        return inspect.isclass(f_type) and issubclass(f_type, Enum)

    def is_union(
        self,
        f_type: type,
    ) -> bool:
    
        return f_type in (Union, types.UnionType)

    def is_custom(
        self,
        f_type: type,
    ) -> bool:
    
        return (
            inspect.isclass(f_type)
            and f_type not in PROTO
            and not self.is_enum(f_type)
            and f_type.__module__ not in BUILTIN_MODULES
        )

    def get_class_fields(
        self,
        cls: type,
    ) -> dict:
    
        return get_type_hints(cls, include_extras=True)

    def enum_params(
        self,
        enum_class: type[Enum],
    ) -> list[str]:
    
        return [item.name for item in enum_class]

    def is_collection(
        self,
        f_type: type,
    ) -> bool:
    
        return f_type in COLLECTIONS or get_origin(f_type) in COLLECTIONS

    def is_nested_collection(
        self,
        f_type: type,
    ) -> bool:
    
        origin = get_origin(f_type)
        args = get_args(f_type)

        if f_type in COLLECTIONS:
            return False

        if origin in (list, tuple, set):
            return bool(args) and self.is_collection(args[0])

        if origin is dict:
            if len(args) != 2:
                return True
            key_type, value_type = args
            return self.is_collection(key_type) or self.is_collection(value_type)

        return False

    # def collect_custom_types(
    #     self,
    #     f_type: type,
    # ):
    #     result = []
    #     stack = [f_type]

    #     while stack:
    #         current = stack.pop()
    #         origin = get_origin(current)
    #         args = get_args(current)

    #         if self.is_union(origin):
    #             stack.extend(arg for arg in args if arg is not NONE_TYPE)
    #             continue

    #         if self.is_collection(origin):
    #             stack.extend(arg for arg in args if arg is not NONE_TYPE)
    #             continue

    #         if self.is_custom(origin) or self.is_enum(origin):
    #             result.append(origin)
    #             continue

    #         if self.is_custom(current) or self.is_enum(current):
    #             result.append(current)

    #     return result

    def collect_custom_types(
        self,
        f_type: type,
    ):
        result = []
        stack = [f_type]

        while stack:
            current = stack.pop()
            origin = get_origin(current)
            args = get_args(current)
            
            if self.is_union(origin):
                stack.extend(arg for arg in reversed(args) if arg is not NONE_TYPE)
                continue

            if self.is_collection(origin):
                stack.extend(arg for arg in reversed(args) if arg is not NONE_TYPE)
                if origin not in result:
                    result.append(origin)
                continue
            
            if current not in result:
                result.append(current)

        return result

    def create_path_str(
        self,
        *args: PathNode | str,
    ) -> str:
        
        return ".".join(
            n.name if isinstance(n, PathNode) else n
            for n in args
            if isinstance(n, (PathNode, str))
        )

    def _variant_paths(
        self,
        node: PathNode,
        *,
        exact: bool,
        mode: VariantMode = "include-self",
    ) -> list[str]:
    
        return [
            self.create_path_str(*variant)
            for variant in node.path_variants_to_root(mode=mode)
        ]

    def _arg_names(
        self,
        node: PathNode,
    ) -> tuple[str]:
    
        custom_args = self.collect_custom_types(node.data.get("field_type"))
        return tuple(f_type.__name__ for f_type in custom_args if f_type is not None)

    def is_removed(
        self,
        node: PathNode,
    ) -> bool:
        
        arg_names = self._arg_names(node)
        
        # Exact
        remove_exact_include_self = self.config.get_remove("exact", "include")
        remove_exact_exclude_self = self.config.get_remove("exact", "exclude")
        
        # Scope
        remove_scope_include_self = self.config.get_remove("scope", "include")
        remove_scope_exclude_self = self.config.get_remove("scope", "exclude")
        
        # For absolute path like `Class1` | contains self
        if any(arg in remove_exact_include_self or arg in remove_scope_include_self for arg in arg_names):
            return True
        
        for variant in node.path_variants_to_root(mode="all"):
            
            # For relative path like Class1.Classs2, contains self
            if self.create_path_str(*variant) in remove_exact_include_self:
                return True

            if self.create_path_str(*variant) in remove_scope_include_self:
                return True
            
            
            # For relative path like Class1.var, contains self
            if any(self.create_path_str(*variant, arg) in remove_exact_include_self for arg in arg_names):
                return True
                    
            if any(self.create_path_str(*variant, arg) in remove_scope_include_self for arg in arg_names):
                return True
                      
        # For relative path like Class1.Classs2, exclude self
        for variant in node.path_variants_to_root(mode="exclude-self"):
            if self.create_path_str(*variant) in remove_exact_exclude_self:
                return True
            
            if self.create_path_str(*variant) in remove_scope_exclude_self:
                return True

        return False

    def is_optional(
        self,
        node: PathNode,
    ) -> bool:
        
        if self.config.optional_all:
            return True

        arg_names = self._arg_names(node)
        
        # Exact
        optional_exact_include_self = self.config.get_optional("exact", "include")
        
        # Scope
        optional_scope_include_self = self.config.get_optional("scope", "include")
        optional_scope_exclude_self = self.config.get_optional("scope", "exclude")
        
        # For absolute path like `Class1` | contains self
        if any(arg in optional_exact_include_self or arg in optional_scope_include_self for arg in arg_names):
            return True
        
        # Scope
        for variant in node.path_variants_to_root(mode="all"):
            
            # For relative path like Class1.Classs2, contains self
            if self.create_path_str(*variant) in optional_scope_include_self:
                return True
            
            # For relative path like Class1.var, contains self
            if any(self.create_path_str(*variant, arg) in optional_scope_include_self or arg in optional_scope_include_self for arg in arg_names):
                return True            
        
        for variant in node.path_variants_to_root(mode="exclude-self"):
            
            # Exact
            # For relative path like Class1.var, contains self
            if any(self.create_path_str(*variant, arg) in optional_exact_include_self for arg in arg_names):
                return True
            
            # Scope
            # For relative path like Class1.Classs2, exclude self
            if self.create_path_str(*variant) in optional_scope_exclude_self:
                return True
            
        # Exact
        for variant in node.path_variants_to_root(tags={"class"}, tag_mode="include", mode="include-self"):
            
            # For relative path like Class1.Classs2, contains self
            if self.create_path_str(*variant) in optional_exact_include_self:
                return True
                    
        return False

    def resolve_type(
        self,
        node: PathNode,
        f_type: type,
    ) -> type:

        arg_names = self._arg_names(node)
        
        # Exact
        override_exact_include_self = self.config.get_override("exact", "include")
        
        # Scope
        override_scope_include_self = self.config.get_override("scope", "include")
        override_scope_exclude_self = self.config.get_override("scope", "exclude")
        
        # For absolute path like `Class1`, contains self
        for arg in arg_names:
            
            if arg in override_exact_include_self:
                return override_exact_include_self.get(arg).type
                
            if arg in override_scope_include_self:
                return override_scope_include_self.get(arg).type
        
        # Scope
        for variant in node.path_variants_to_root(mode="all"):
            
            # For relative path like Class1.Classs2, contains self
            path = self.create_path_str(*variant)
            if path in override_scope_include_self:
                return override_scope_include_self.get(path).type

            for arg in arg_names:
                path = self.create_path_str(*variant, arg)
                if path in override_scope_include_self:
                    return override_scope_include_self.get(path).type          

        for variant in node.path_variants_to_root(mode="exclude-self"):

            # Exact
            # For relative path like Class1.var, contains self
            for arg in arg_names:
                path = self.create_path_str(*variant, arg)
                if path in override_exact_include_self:
                    return override_exact_include_self.get(path).type
            
            # Scope
            # For relative path like Class1.Classs2, exclude self
            path = self.create_path_str(*variant)
            if path in override_scope_exclude_self:
                return override_scope_exclude_self.get(path).type
            
        # Exact
        for variant in node.path_variants_to_root(tags={"class"}, tag_mode="include", mode="include-self"):
            
            # For relative path like Class1.Classs2, contains self
            path = self.create_path_str(*variant)
            if path in override_exact_include_self:
                return override_exact_include_self.get(path).type        
        
        return f_type