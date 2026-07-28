from .utils import PROTO, OTHER, NONE_TYPE, ProtoConfig, ProtoType, NodeData, Message, MessageField, OneOf
from .base_builder import BaseBuilder
from .tree_structure import Node
from dataclasses import asdict
from typing import (
    get_origin,
    get_args,
    Literal,
)

class SessionBuilder(BaseBuilder):
    
    def __init__(
        self,
        config: ProtoConfig | None = None,
    ):
        super().__init__(config)
        
    def type_detector(
        self,
        annotation: type,
    ) -> ProtoType | None:
    
        origin = get_origin(annotation)
        args = get_args(annotation)
        
        if self.is_optional(annotation):
            
            inner = next(arg for arg in args if arg is not NONE_TYPE)
            inner_proto = self.type_detector(inner)
            
            if inner_proto.label == "repeated":
                return ProtoType(label="optional", type=OTHER["listvalue"], process_type=False)
            
            return ProtoType(label="optional", type=inner_proto.type, process_type=inner_proto.process_type)
        
        elif self.is_union(annotation):
            return None            
        
        elif origin in (list, tuple, set):
            
            if not args or self.is_nested_collection(annotation):
                return ProtoType(label="repeated", type=OTHER["listvalue"], process_type=False)
            
            inner = next(arg for arg in args if arg is not NONE_TYPE)
            inner_proto = self.type_detector(inner)
            
            if inner_proto:
                return ProtoType(label="repeated", type=inner_proto.type, process_type=inner_proto.process_type)
            
            return ProtoType(label="repeated", type=OTHER["listvalue"], process_type=False)

        elif origin is dict:
            
            if len(args) != 2 or self.is_nested_collection(annotation):
                return ProtoType(type=OTHER['struct'], process_type=False)
            
            inner = iter(args)
            key_proto = self.type_detector(next(inner))
            value_proto = self.type_detector(next(inner))
            
            if key_proto and value_proto:
                return ProtoType(
                    type=f"map<{key_proto.type}, {value_proto.type}>",
                    process_type=key_proto.process_type or value_proto.process_type,
                )

            return ProtoType(type=OTHER["struct"], process_type=False)

        elif annotation in (list, tuple, set):
            return ProtoType(type=OTHER['listvalue'])

        elif annotation is dict:
            return ProtoType(type=OTHER['struct'])

        elif self.is_enum(annotation) or self.is_custom(annotation):
            return ProtoType(type=self.get_type_name(annotation))
        
        return ProtoType(type=PROTO.get(annotation, OTHER["any"]))

    def proto_type(
        self,
        node: Node,
    ) -> ProtoType | None:
        
        data_type = node.data.get("type")
        
        resolved_type = self.resolve_type(node, data_type)
        
        if resolved_type != data_type:
            path = node.path.split(".")
            node.children.clear()
            node = self.build_tree(resolved_type, node).find_node_by_contiguous_path(*path)

        if self.resolve_is_removed(node):
            return None
        
        optional = self.resolve_is_optional(node)
        
        proto = self.type_detector(resolved_type)
        
        if optional and proto.label != "repeated":
            proto.label = "optional"
            
        return proto
    
    def create_data(
        self,
        annotation: type,
        node: Node,
        mode: Literal["union", "enum", "custom", "primitive"] = "primitive",
    ):
        
        name = self.get_type_name(annotation)
        
        if mode == "union":
            node.data.update(
                asdict(
                    NodeData(
                        label="oneof", name=name, type=annotation,
                    ),
                ),
            )
            
        elif mode == "enum":
            node.data.update(
                asdict(
                    NodeData(label="enum", name=name, type=annotation)
                )
            )
            node.bulk(*self.get_enum_params(annotation))
            
        elif mode == "custom":
            node.data.update(
                asdict(
                    NodeData(label="message", name=name, type=annotation)
                )
            )
        
        elif mode == "primitive":
            node.data.update(asdict(NodeData(name=name, type=annotation)))

    def build_tree(
        self,
        annotation: type,
        node: Node | None = None,
    ) -> Node:
                
        if node is None:
            node = Node(self.get_type_name(annotation))
            self.create_data(annotation, node)
                
        args = get_args(annotation)
        
        if self.is_optional(annotation):
            inner = next(arg for arg in args if arg is not NONE_TYPE)
            self.create_data(annotation, node, "primitive")      
            field_name = self.to_snake_case(self.get_type_name(inner))
            if not (self.is_custom(inner) or self.is_enum(inner)):
                field_name += "_var"
            child = node.child(field_name)
            self.build_tree(inner, child)
                
        elif self.is_union(annotation):
            self.create_data(annotation, node, "union")
            for arg in args:
                
                if arg is NONE_TYPE:
                    continue
                
                field_name = node.name + "_" + self.get_type_name(arg)
                
                # field_name = self.to_snake_case(self.get_type_name(arg))
                # if not (self.is_custom(arg) or self.is_enum(arg)):
                #     field_name += "_var"
                child = node.child(field_name)
                self.build_tree(arg, child)
            
        elif self.is_collection(annotation):
            self.create_data(annotation, node, "primitive")
            for arg in args:
                field_name = self.to_snake_case(self.get_type_name(arg))
                if not (self.is_custom(arg) or self.is_enum(arg)):
                    field_name += "_var"
                child = node.child(field_name)
                self.build_tree(arg, child)
                    
        elif self.is_enum(annotation):
            self.create_data(annotation, node, "enum")

        elif self.is_custom(annotation):
            self.create_data(annotation, node, "custom")
            fields = self.get_class_fields(annotation)
            for name, f in fields.items():
                child = node.child(name)
                self.build_tree(f, child)
            
        else:
            self.create_data(annotation, node, "primitive")
            
        return node.root
       
    def build_oneof(
        self,
        node: Node,
        message: Message,
    ):
        fields = []
        for child in node.children.values():
            proto = self.proto_type(child)
            if proto:
                fields.append(MessageField(label=proto.label, type=proto.type, name=child.name))
                message.modules.append(proto.type)
                        
        message.fields.append(
            OneOf(
                name=node.name,
                fields=fields,
            )
        )  
        
    def node_to_message(
        self,
        node: Node,
    ) -> list[Message]:
        
        label = node.data.get("label")
        name = node.data.get("name")
        
        message = Message(label=label, name=name)
        messages: list[Message] = []

        for child in node.children.values():
                        
            if child.data.get("label") == "oneof":
                if self.resolve_is_removed(child):
                    continue
                self.build_oneof(child, message)
                for grandchild in child.children.values():
                    messages.extend(self.node_to_message(grandchild))
                continue
            
            proto = self.proto_type(child)
            if proto:
                message.modules.append(proto.type)
                message.fields.append(MessageField(label=proto.label, type=proto.type, name=child.name))
                if proto.process_type:
                    messages.extend(self.node_to_message(child))
            
        if message.label and message.name:
            if not message.is_empty():
                messages.append(message)

        return messages
        
    def build(
        self,
        model: type,
    ) -> str:
    
        tree = self.build_tree(model)
        messages = self.node_to_message(tree)
        return "\n\n".join([msg.text for msg in messages])
