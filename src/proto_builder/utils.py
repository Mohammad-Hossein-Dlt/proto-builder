from .tree_structure import Node
from dataclasses import dataclass, field
from typing import Literal
from datetime import datetime

PROTO = {
    int: "int32",
    float: "float",
    bool: "bool",
    str: "string",
    bytes: "bytes",
    datetime: "google.protobuf.Timestamp",
}

OTHER = {
    "any": "google.protobuf.Any",
    "timestamp": "google.protobuf.Timestamp",
    "duration": "google.protobuf.Duration",
    "empty": "google.protobuf.Empty",
    "struct": "google.protobuf.Struct",
    "value": "google.protobuf.Value",
    "listvalue": "google.protobuf.ListValue",
}

MODULES = {
    "google.protobuf.Empty": "google/protobuf/empty.proto",
    "google.protobuf.Any": "google/protobuf/any.proto",
    "google.protobuf.Timestamp": "google/protobuf/timestamp.proto",
    "google.protobuf.Duration": "google/protobuf/duration.proto",
    "google.protobuf.Struct": "google/protobuf/struct.proto",
    "google.protobuf.Value": "google/protobuf/struct.proto",
    "google.protobuf.ListValue": "google/protobuf/struct.proto",
    
    "google.protobuf.DoubleValue": "google/protobuf/wrappers.proto",
    "google.protobuf.FloatValue": "google/protobuf/wrappers.proto",
    "google.protobuf.Int64Value": "google/protobuf/wrappers.proto",
    "google.protobuf.UInt64Value": "google/protobuf/wrappers.proto",
    "google.protobuf.Int32Value": "google/protobuf/wrappers.proto",
    "google.protobuf.UInt32Value": "google/protobuf/wrappers.proto",
    "google.protobuf.BoolValue": "google/protobuf/wrappers.proto",
    "google.protobuf.StringValue": "google/protobuf/wrappers.proto",
    "google.protobuf.BytesValue": "google/protobuf/wrappers.proto",
}

COLLECTIONS = (list, tuple, set, dict)
VALUES = [int, float, str, bool, list, tuple, set, dict]
BUILTIN_MODULES = {"builtins", "typing", "types", "collections", "collections.abc", "inspect"}
NONE_TYPE = type(None)


class ProtoConfig:
    
    def __init__(
        self,
        override: list["OverrideConfig"] = [],
        remove: list["FieldConfig"] = [],
        optional: list["FieldConfig"] = [],
        optional_all: bool = False,
    ):
        
        self.override = override
        self.remove = remove
        self.optional = optional
        self.optional_all = optional_all
        
    def build_tree(
        self,
        path: str,
    ) -> Node:
        root, *body = path.split(".")
        return Node(root).add(*body)
        
    def get_override(
        self,
    ) -> list[Node]:
        
        result = []
        
        for i in self.override:
            tree = self.build_tree(i.name)
            tree.data.update({"type": i.type})
            result.append(tree)
                
        return result
        
    def get_remove(
        self,
        condition: Literal["exact", "scope"] = "exact",
        mode: Literal["include", "exclude"] | None = None,
    ) -> list[Node]:
        
        if mode == "include":
            return [self.build_tree(i.name) for i in self.remove if i.condition == condition and i.include_self]
        
        elif mode == "exclude":
            return [self.build_tree(i.name) for i in self.remove if i.condition == condition and not i.include_self]
        
        return [self.build_tree(i.name) for i in self.remove if i.condition == condition]
    
    def get_optional(
        self,
        condition: Literal["exact", "scope"] = "exact",
        mode: Literal["include", "exclude"] | None = None,
    ) -> list[Node]:
                
        if mode == "include":
            return [self.build_tree(i.name) for i in self.optional if i.condition == condition and i.include_self]
        
        elif mode == "exclude":
            return [self.build_tree(i.name) for i in self.optional if i.condition == condition and not i.include_self]
        
        return [self.build_tree(i.name) for i in self.optional if i.condition == condition]
    
@dataclass
class OverrideConfig:
    name: str = field(default_factory=str)
    type: type = field(default_factory=type)

@dataclass
class FieldConfig:
    name: str = field(default_factory=str)
    condition: Literal["exact", "scope"] = field(default="exact")
    include_self: bool = False

@dataclass(slots=True)
class ProtoType:
    label: Literal["repeated", "optional"] | None = None
    type: str = ""
    process_type: bool = True
    
@dataclass(slots=True)
class Session:
    name: str = ""
    input_node: Node = field(default_factory=Node)
    output_node: Node = field(default=Node)

@dataclass(slots=True)
class NodeData:
    label: str | None = None
    name: str | None = None
    type: type | None = None
    
@dataclass(slots=True)
class Message:
    label: str = field(default_factory=str)
    name: str = field(default_factory=str)
    fields: list[MessageField | OneOf] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    
    @property
    def text(self) -> str:
        content = [f"{self.label} {self.name} {{"]
        
        start_index = 1 if self.label == "message" else 0
        idx = start_index
        for f in self.fields:

            if isinstance(f, MessageField):
                if self.label == "enum":
                    content.append(f"    {f.name} = {idx};")  
                elif f.label:
                    content.append(f"    {f.label} {f.type} {f.name} = {idx};")
                else:
                    content.append(f"    {f.type} {f.name} = {idx};")
                
                idx += 1
            
            elif isinstance(f, OneOf):
                content.append(f"    oneof {f.name} {{")
                for oneof_field in f.fields:
                    if oneof_field.label:
                        content.append(f"        {oneof_field.label} {oneof_field.type} {oneof_field.name} = {idx};")
                    else:
                        content.append(f"        {oneof_field.type} {oneof_field.name} = {idx};")
                    
                    idx += 1
                    
                content.append("    }")
                
        
        content.append("}")
        
        return "\n".join(content)
    
    
    def is_empty(self):
        
        if not self.fields:
            return True
        
        for message_field in self.fields:
            if isinstance(message_field, OneOf):
                if message_field.fields:
                    return False
                
            elif isinstance(message_field, MessageField):
                return False
                
        return True
    
@dataclass(slots=True)
class MessageField:
    label: str | None = field(default_factory=str)
    type: str = field(default_factory=str)
    name: str = field(default_factory=str)
    
@dataclass
class OneOf:
    name: str
    fields: list[MessageField]