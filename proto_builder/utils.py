from tree_structure import PathTree
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
        
    def get_override(
        self,
        condition: Literal["exact", "scope"] = "exact",
        mode: Literal["include", "exclude"] | None = None,
    ) -> dict[str, "OverrideConfig"]:
        
        if mode == "include":
            return {i.name: i for i in self.override if i.condition == condition and i.include_self}
        
        elif mode == "exclude":
            return {i.name: i for i in self.override if i.condition == condition and not i.include_self}
        
        return {i.name: i for i in self.override if i.condition == condition}
        
    def get_remove(
        self,
        condition: Literal["exact", "scope"] = "exact",
        mode: Literal["include", "exclude"] | None = None,
    ) -> set[str]:
        
        if mode == "include":
            return [i.name for i in self.remove if i.condition == condition and i.include_self]
        
        elif mode == "exclude":
            return [i.name for i in self.remove if i.condition == condition and not i.include_self]
        
        return [i.name for i in self.remove if i.condition == condition]
    
    def get_optional(
        self,
        condition: Literal["exact", "scope"] = "exact",
        mode: Literal["include", "exclude"] | None = None,
    ) -> set[str]:
                
        if mode == "include":
            return [i.name for i in self.optional if i.condition == condition and i.include_self]
        
        elif mode == "exclude":
            return [i.name for i in self.optional if i.condition == condition and not i.include_self]
        
        return [i.name for i in self.optional if i.condition == condition]
    
@dataclass
class OverrideConfig:
    name: str = field(default_factory=str)
    type: type = field(default_factory=type)
    condition: Literal["exact", "scope"] = field(default="exact")
    include_self: bool = False

@dataclass
class FieldConfig:
    name: str = field(default_factory=str)
    condition: Literal["exact", "scope"] = field(default="exact")
    include_self: bool = False

@dataclass(slots=True)
class ProtoType:
    optional: bool = False
    repeated: bool = False
    p_type: str = ""
    name: str | None = None
    contains_custom: bool = False


@dataclass(slots=True)
class Session:
    fn_name: str = ""
    request_name: str = ""
    response_name: str = ""
    input_params: dict[str, PathTree] = field(default_factory=dict)
    output_params: dict[str, PathTree] = field(default_factory=dict)

@dataclass(slots=True)
class NodeData:
    message_type: str | None = None
    message_name: str | None = None
    field_type: type | None = None
    is_custom: bool = False

@dataclass(slots=True)
class Message:
    text: str = field(default_factory=str)
    modules: list[str] = field(default_factory=list)
