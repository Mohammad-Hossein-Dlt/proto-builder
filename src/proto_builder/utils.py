from .tree_structure import Node
from dataclasses import dataclass, field
import re

PROTO = {
    "int": "int32",
    "float": "float",
    "bool": "bool",
    "str": "string",
    "bytes": "bytes",
    "datetime": "google.protobuf.Timestamp",
}

LIST_TYPES = ("list", "tuple", "set")
COLLECTION_TYPES = ("list", "tuple", "set", "dict")
VALUE_TYPES = ("str", "int", "float", "bool", "NoneType", "list" , "tuple", "set", "dict")

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
        override: list[dict[str, object]] | None = None,
        remove: list[str] | None = None,
        optional: list[str] | None = None,
        optional_all: bool = False,
    ):

        self.override: list[dict[str, object]] = override or []
        self.remove: list[str] = remove or []
        self.optional: list[str] = optional or []
        self.optional_all: bool = optional_all
        
@dataclass(slots=True)
class MessageField:
    label: str | None = field(default_factory=str)
    type: str = field(default_factory=str)
    name: str = field(default_factory=str)
    fields: list[MessageField] = field(default_factory=list)
    is_message: bool = field(default_factory=bool)

@dataclass(slots=True)
class Message:
    label: str = field(default_factory=str)
    name: str = field(default_factory=str)
    fields: list[MessageField] = field(default_factory=list)

    @property
    def text(self) -> str:
        content = [f"{self.label} {self.name} {{"]

        start_index = 1 if self.label == "message" else 0
        idx = start_index
        for f in self.fields:

            if f.label != "oneof":
                if self.label == "enum":
                    content.append(f"    {f.name} = {idx};")
                elif f.label:
                    content.append(f"    {f.label} {self.resolve_type_name(f)} {self.get_field_name(f.name)} = {idx};")
                else:
                    content.append(f"    {self.resolve_type_name(f)} {self.get_field_name(f.name)} = {idx};")

                idx += 1

            else:
                content.append(f"    oneof {self.get_field_name(f.name)} {{")
                for oneof_field in f.fields:
                    if oneof_field.label:
                        content.append(f"        {oneof_field.label} {self.resolve_type_name(oneof_field)} {self.get_field_name(oneof_field.name)} = {idx};")
                    else:
                        content.append(f"        {self.resolve_type_name(oneof_field)} {self.get_field_name(oneof_field.name)} = {idx};")

                    idx += 1

                content.append("    }")


        content.append("}")

        return "\n".join(content)
    
    @property
    def modules(self) -> list[str]:
        result = []
        for f in self.fields:
            mdl = MODULES.get(self.resolve_type_name(f))
            if mdl:
                result.append(mdl)
                
        return result

    def resolve_type_name(
        self,
        message_field: MessageField,
    ):

        type_name = message_field.type
        if type_name == "map":
            key, value = message_field.fields
            return f"{type_name}<{self.resolve_type_name(key)}, {self.resolve_type_name(value)}>"
        
        elif type_name in PROTO:
            return PROTO.get(type_name)

        elif type_name in OTHER:
            return OTHER.get(type_name)

        return type_name

    def to_snake_case(
        self,
        name: str,
    ) -> str:
        name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
        name = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', name)
        return name.lower()

    def get_field_name(
        self,
        name: str,
    ):
        if name in (*VALUE_TYPES, "Union"):
            return name.lower() + "_var"

        return self.to_snake_case(name)
