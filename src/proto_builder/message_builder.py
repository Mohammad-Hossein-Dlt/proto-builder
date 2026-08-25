from .utils import PROTO, LIST_TYPES, COLLECTION_TYPES, VALUE_TYPES, OTHER, ProtoConfig, MessageField, Message
from .base_builder import BaseBuilder
from .tree_structure import Node
from typing import get_args

class MessageBuilder(BaseBuilder):

    def __init__(
        self,
        config: ProtoConfig | None = None,
    ):
        super().__init__(config)

    def build_tree(
        self,
        annotation: object,
        name: str | None = None,
        *,
        main: Node | None = None,
    ) -> Node:

        def walk(
            ann: object,
            name: str | None = None,
            *,
            node: Node | None = None,
        ):
            scoped = True if node else False
            args = get_args(ann)

            if node is None:
                node = Node(self.get_node_name(ann))
            else:
                if name:
                    node = node.child(name)
                    node.data.update({"label": "field"})
                field_name = self.get_node_name(ann)
                node = node.child(field_name)

            if self.is_union(ann) or self.is_collection(ann):
                for arg in args:
                    walk(arg, node=node)

            elif self.is_enum(ann):
                node.data.update({"label": "enum"})
                if scoped:
                    node.data.update({"type": ann})
                else:
                    for name, f in self.get_enum_params(ann):
                        walk(type(f), name, node=node)

            elif self.is_custom(ann):
                node.data.update({"label": "message"})
                if scoped:
                    node.data.update({"type": ann})
                else:
                    for name, f in self.get_class_fields(ann).items():
                        walk(f, name, node=node)

            return node

        if main:
            message_node = walk(annotation, name, node=main)
            return message_node
        else:
            message_node = walk(annotation, name)
            return message_node.root

    def node_to_message(
        self,
        node: Node,
    ) -> list[Message]:
                
        messages: list[Message] = []
        
        def walk(
            n: Node,
            prefix: str = "",
        ):
                   
            if self.is_nested_collection(n.path):
                return None

            if self.resolve_is_removed(n, prefix):
                return None

            resolve_type = self.resolve_type(n, prefix)
            if resolve_type:
                
                node_name = self.get_node_name(resolve_type)
                
                if any(i for i in messages if i.name == node_name):
                    n = Node(name=node_name)
                    n.data.update({"label": True})
                else:
                    prefix = prefix + "." + n.parent.path if prefix else n.parent.path
                    if n.data.get("label") == "field":
                        n.children.clear()
                        self.build_tree(resolve_type, main=n)
                    else:
                        n = self.build_tree(resolve_type)
                    
                    # print(n.last_node().path)
            
            obj = n.data.get("type")
            if obj:
                
                node_name = self.get_node_name(obj)
                
                if any(i for i in messages if i.name == node_name):
                    n = Node(name=node_name)
                    n.data.update({"label": True})
                else:
                    prefix = prefix + "." + n.parent.path if prefix else n.parent.path
                    n = self.build_tree(obj)

            fields: list[MessageField] = []
            current = MessageField(type=n.name, name=n.name, is_message=n.data.get("label") in ("message", "enum"))

            for i, child in enumerate(n.children):
                if n.name == "dict" and i == 0:
                    if child.name in COLLECTION_TYPES:
                        continue

                entity = walk(child, prefix)
                if entity:
                    fields.append(entity)
                    
            if n.name in LIST_TYPES:
                
                if len(fields) == 1:

                    other_field = next(iter(fields))
                    
                    if other_field.label == "oneof" or other_field.type == "Union":
                        current.type = OTHER["listvalue"]
                        current.fields = fields
                    
                    elif other_field.label == "repeated" or other_field.type == OTHER["value"]:
                        current.type = OTHER["listvalue"]
                    
                    else:
                        current.label = "repeated"
                        current.type = other_field.type
                        current.fields = other_field.fields
                        current.name = other_field.name

                else:
                    current.type = OTHER["listvalue"]
                    current.fields = fields

            elif n.name == "dict":

                if 0 < len(fields) <= 2:

                    key, value = (fields[0], fields[0]) if len(fields) == 1 else fields

                    if value.label == "repeated" or value.type in ("map", OTHER["struct"], OTHER["listvalue"]):
                        value.type = OTHER["value"]

                    if key.type in PROTO:
                        current.type = "map"
                        current.fields = [key, value]
                    else:
                        current.type = OTHER["struct"]
                        
                else:
                    current.type = OTHER["struct"]

            elif n.name == "Union":
                
                if len(fields) == 2 and any(f.name == "NoneType" for f in fields):
                    
                    other_field = next(f for f in fields if f.name != "NoneType")
                    current.label = "optional"
                    
                    if other_field.label == "repeated":
                        current.type = OTHER["listvalue"]
                    
                    else:
                        current.type = other_field.type
                    
                    current.fields = other_field.fields
                    current.name = other_field.name
                
                elif all(child.name in VALUE_TYPES for child in n.children):
                    current.type = OTHER["value"]
                
                else:
                    current.label = "oneof"
                    current.fields = [f for f in fields if f.name != "NoneType"]

            elif not current.is_message:
                if fields: current = next(iter(fields))
                current.is_message = False
            
            current.name = n.name

            if not current.is_message and current.label != "repeated" and self.resolve_is_optional(n, prefix):
                if current.label == "oneof":
                    for i in current.fields:
                        if i.label != "repeated":
                            i.label = "optional"
                else:
                    current.label = "optional"

            if current.is_message and fields:
                
                f = next(iter(fields))
                                
                if len(f.fields) > 1 and (f.label == "repeated" or f.type == OTHER["listvalue"]) and n.data.get("split_collection"):
                    message: Message = Message(label=n.data.get("label"), name=n.name, fields=f.fields)
                
                else:
                    message: Message = Message(label=n.data.get("label"), name=n.name, fields=fields)

                messages.append(message)

            return current

        walk(node)

        return messages

    def build(
        self,
        model: object,
    ) -> str:

        tree = self.build_tree(model)
        messages = self.node_to_message(tree)
        return "\n\n".join([msg.text for msg in messages])
