from .utils import PROTO, OTHER, NONE_TYPE, ProtoConfig, ProtoType, NodeData, Message
from .base_builder import BaseBuilder
from .tree_structure import Node
from dataclasses import asdict
from typing import (
    get_origin,
    get_args,
)

class SessionBuilder(BaseBuilder):
    
    def __init__(
        self,
        config: ProtoConfig | None = None,
    ):
        super().__init__(config)

    @staticmethod
    def _is_value(
        args: tuple,
    ) -> bool:
        return all(a in [int, float, str, bool, list, tuple, set, dict] for a in args) and len(args) == 2

    @staticmethod
    def _is_optional_union(
        args: tuple,
    ) -> bool:
        return NONE_TYPE in args and len(args) == 2

    @staticmethod
    def _is_optional_union_many(
        args: tuple,
    ) -> bool:
        return NONE_TYPE in args and len(args) > 2

    def type_detector(
        self,
        f_type: type,
    ) -> ProtoType:
    
        origin = get_origin(f_type)
        args = get_args(f_type)

        if self.is_union(origin) and self._is_optional_union_many(args):

            non_none_args = [arg for arg in args if arg is not NONE_TYPE]

            if any(self.is_custom(arg) or self.is_enum(arg) for arg in non_none_args):
                return ProtoType(optional=True, repeated=False, p_type=OTHER["any"])
            
            # if dict in non_none_args:
            #     return ProtoType(optional=True, repeated=False, p_type=OTHER["value"])
            
            if all(
                arg in (list, tuple, set) or get_origin(arg) in (list, tuple, set)
                for arg in non_none_args
            ):
                return ProtoType(optional=True, repeated=False, p_type=OTHER["listvalue"])
            
            return ProtoType(optional=True, repeated=False, p_type=OTHER["value"])

        if self.is_union(origin) and self._is_optional_union(args):

            inner = next(arg for arg in args if arg is not NONE_TYPE)

            if self.is_custom(inner) or self.is_enum(inner):
                return ProtoType(optional=True, repeated=False, p_type=inner.__name__, contains_custom=True)
            
            if inner is dict or get_origin(inner) is dict:
                inner_proto = self.type_detector(inner)
                return ProtoType(optional=True, repeated=False, p_type=inner_proto.p_type, contains_custom=inner_proto.contains_custom)
            
            if inner in (list, tuple, set) or get_origin(inner) in (list, tuple, set):
                return ProtoType(optional=True, repeated=False, p_type=OTHER["listvalue"])
            
            return ProtoType(optional=True, repeated=False, p_type=PROTO.get(inner, OTHER["any"]))
        
        if self.is_union(origin) and self._is_value(args):
            return ProtoType(optional=False, repeated=False, p_type=OTHER["value"])
        
        if origin in (list, tuple, set):
            
            if not args or self.is_nested_collection(f_type):
                return ProtoType(optional=False, repeated=False, p_type=OTHER["listvalue"])

            inner_proto = self.type_detector(args[0])
            return ProtoType(optional=False, repeated=True, p_type=inner_proto.p_type, contains_custom=inner_proto.contains_custom)

        if origin is dict:
            
            if len(args) != 2 or self.is_nested_collection(f_type):
                return ProtoType(optional=False, repeated=False, p_type=f"{OTHER['struct']}")

            key_proto = self.type_detector(args[0])
            value_proto = self.type_detector(args[1])
            return ProtoType(
                optional=False,
                repeated=False,
                p_type=f"map<{key_proto.p_type}, {value_proto.p_type}>",
                contains_custom=key_proto.contains_custom or value_proto.contains_custom,
            )

        if f_type in (list, tuple, set):
            return ProtoType(optional=False, repeated=False, p_type=f"{OTHER['listvalue']}")

        if f_type is dict:
            return ProtoType(optional=False, repeated=False, p_type=f"{OTHER['struct']}")

        if self.is_enum(f_type) or self.is_custom(f_type):
            return ProtoType(optional=False, repeated=False, p_type=f_type.__name__, contains_custom=True)
        
        return ProtoType(optional=False, repeated=False, p_type=PROTO.get(f_type, OTHER["any"]))

    def proto_type(
        self,
        node: Node,
    ) -> ProtoType:
    
        resolved_type = self.resolve_type(node, node.data.get("field_type"))
        proto = self.type_detector(resolved_type)
        proto.optional = proto.optional or (self.is_optional(node) and not proto.repeated)
        return proto

    def _node_by_path(
        self,
        tree: Node,
        path: str,
    ) -> Node:
    
        if not path:
            return tree.root
        node = tree.root.find_node_by_contiguous_path(*path.split("."))
        
        return node or tree.root

    def create_node(
        self,
        tree: Node,
        annotation: type,
        path: str = "",
    ):
    
        parent = self._node_by_path(tree, path)
        child = parent if not path else parent.child(annotation.__name__, tags={"class"})

        if self.is_enum(annotation):
            child.data.update(
                asdict(
                    NodeData(
                        message_type="enum",
                        message_name=annotation.__name__,
                        field_type=annotation,
                        is_custom=True,
                    )
                )
            )
            child.bulk(*self.enum_params(annotation))
            
        elif self.is_custom(annotation):
            child.data.update(
                asdict(
                    NodeData(
                        message_type="message",
                        message_name=annotation.__name__,
                        field_type=annotation,
                        is_custom=True,
                    )
                )
            )
            self.model_to_proto(annotation, tree, f"{path}.{annotation.__name__}" if path else annotation.__name__)
        else:
            child.data.update(asdict(NodeData(field_type=annotation)))
            
    def collect_nested_defs(
        self,
        tree: Node,
        annotation: type,
        path: str = "",
    ):
    
        origin = get_origin(annotation)
        args = get_args(annotation)
        node = self._node_by_path(tree, path)

        if self.is_union(origin) or self.is_collection(origin):
            
            node.data.update(asdict(NodeData(field_type=annotation)))

            if self._is_optional_union(args):
                inner = next(arg for arg in args if arg is not NONE_TYPE)
                if inner is dict or get_origin(inner) is dict:
                    inner_args = get_args(inner)
                    for arg in inner_args:
                        if self.is_custom(arg) or self.is_enum(arg):
                            self.create_node(tree, arg, path)
                else:
                    if self.is_custom(inner) or self.is_enum(inner):
                        self.create_node(tree, inner, path)
                            
            elif self.is_collection(origin):
                for arg in args:
                    if self.is_custom(arg) or self.is_enum(arg):
                        self.create_node(tree, arg, path)

            # for arg in args:
                
            #     if arg is NONE_TYPE:
            #         continue

            #     arg_origin = get_origin(arg)
            #     if self.is_union(arg_origin) or self.is_collection(arg_origin):
            #         self.collect_nested_defs(tree, arg, path)
            #     else:
            #         self.create_node(tree, arg, path)
                    
        elif self.is_enum(annotation):
            node.data.update(asdict(NodeData(field_type=annotation)))
            self.create_node(tree, annotation, path)

        elif self.is_custom(annotation):
            node.data.update(asdict(NodeData(field_type=annotation)))
            self.create_node(tree, annotation, path)
        
        else:
            node.data.update(asdict(NodeData(message_type="message", field_type=annotation)))

    def model_to_proto(
        self,
        model: type,
        tree: Node | None = None,
        prefix: str | None = None,
    ) -> Node:
        
        if tree is None:
            tree = Node(model.__name__)
            self.create_node(tree, model)

        if self.is_custom(model):
            
            fields = self.get_class_fields(model)
            prefix_parts = prefix.split(".") if prefix else []
            prefix_parent = tree.root.find_node_by_contiguous_path(*prefix_parts) or tree.root
            
            for name, annotation in fields.items():
                prefix_parent.child(name)
                self.collect_nested_defs(tree, annotation, f"{prefix}.{name}" if prefix else name)
        
        elif self.is_enum(model):
            self.create_node(tree, model, prefix or "")

        return tree.root

    def build_tree(
        self,
        _type: type,
        node: Node | None = None,
        name: str | None = None,
    ) -> Node:
    
        if self.is_union(type(_type)) or self.is_union(_type):
            tree = Node(name or _type.__name__) if not node else node
            self.collect_nested_defs(tree, _type, name or _type.__name__)
            return tree.root
        
        return self.model_to_proto(_type, node)

    def node_to_message(
        self,
        node: Node,
        visited: set[str] | None = None,
    ) -> list[Message]:
        
        visited = set() if visited is None else visited
        
        node_name = node.data.get("message_name")
        node_type = node.data.get("message_type")
        if self.is_removed(node) or node_name is None or node_name in visited:
            return []

        visited.add(node_name)
        messages_list: list[Message] = []
        message: Message = Message()
        lines = [f"{node_type} {node_name} {{"]
        
        start_index = 1 if node_type == "message" else 0
        for idx, child in enumerate(node.children.values(), start_index):
            
            if self.is_removed(child):
                continue

            proto = self.proto_type(child)
            proto.name = child.name
            if node_type != "message":
                proto.p_type = None

            if proto.contains_custom and not child.data.get("message_name") and child.children:
                for grandchild in child.children.values():
                    messages_list.extend(self.node_to_message(grandchild, visited))

            if child.children:
                messages_list.extend(self.node_to_message(child, visited))

            lines.append(self.format_proto_field(proto, idx))
            message.modules.append(proto.p_type)

        lines.append("}")
        if len(lines) > 2:
            message.text = "\n".join(lines)
            messages_list.append(message)
        
        return messages_list
        
    def build(
        self,
        model: type,
    ) -> str:
    
        tree = self.build_tree(model)
        messages = self.node_to_message(tree, tree.root)
        return "\n\n".join([msg.text for msg in messages])
