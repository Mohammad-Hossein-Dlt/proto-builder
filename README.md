# Proto Builder

## 📦 Installation

Install the package with:

```bash
pip install proto-builder
```

A simple compiler that converts an abstract class to Protocol Buffers (`.proto`), built with Python.

It can also convert Python `dataclass` or Pydantic models to protobuf messages using a tree-based structure.

## 📚 Contents

### Getting Started

- [Overview](#overview)
- [Example Models](#example-models)

### Service Generation

- [Build a Protobuf Service](#build-a-protobuf-service)
- [Generated Service Output](#generated-service-output)

### Message Generation

- [Convert a Dataclass or Pydantic Model](#convert-a-dataclass-or-pydantic-model)
- [Generated Message Output](#generated-message-output)

### Configuration

- [Configuration Options](#configuration-options)
- [Override](#override)
- [Remove](#remove)
- [Optional](#optional)
- [Optional All](#optional-all)
- [Configuration Paths](#configuration-paths)
- [Configuration Example](#configuration-example)
- [Configured Output](#configured-output)

## Overview

A simple compiler that converts an abstract class to protobuf, built with Python.

It is also used to convert data classes or Pydantic classes to protobuf messages using a tree structure.

## Example Models

Suppose we have this abstract class along with data classes or Pydantic models (here we've used data classes).

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass
class Location:
    city: str
    country: str


@dataclass
class Address:
    street: str
    postal_code: str
    location: Location


@dataclass
class Employee:
    id: int
    name: str
    status: Status
    address: Address


@dataclass
class Department:
    name: str
    manager: Employee


@dataclass
class Company:
    name: str
    founded: datetime
    department: Department


class CompanyService(ABC):

    @abstractmethod
    def get_company(self, company_id: int) -> Company:
        pass

    @abstractmethod
    def get_employee(self, employee_id: int) -> Employee | None:
        pass

    @abstractmethod
    def find(self, name: str) -> Company | Department | Employee | Status | None:
        pass

    @abstractmethod
    def summary(self, employee_id: int) -> tuple[Employee | Status | None, str]:
        pass

    @abstractmethod
    def update(
        self,
        company: Company,
        employees: list[Employee],
        metadata: dict[str, str],
        tags: set[str],
    ) -> list[Department]:
        pass
```

## Build a Protobuf Service

This is how the protobuf service is generated from the abstract class.

```python
from proto_builder.utils import ProtoConfig
from proto_builder.service_builder import ServiceBuilder

config = ProtoConfig()
service_builder = ServiceBuilder(config)

proto = service_builder.build(CompanyService, "company_service")

print(proto)
```

## Generated Service Output

```protobuf
syntax = "proto3";
package company_service;

import "google/protobuf/timestamp.proto";

service CompanyService {
    rpc get_company (GetCompanyRequest) returns (Company);
    rpc get_employee (GetEmployeeRequest) returns (GetEmployeeResponse);
    rpc find (FindRequest) returns (FindResponse);
    rpc summary (SummaryRequest) returns (SummaryResponse);
    rpc update (UpdateRequest) returns (UpdateResponse);
}

enum Status {
    ACTIVE = 0;
    INACTIVE = 1;
}

message Location {
    string city = 1;
    string country = 2;
}

message Address {
    string street = 1;
    string postal_code = 2;
    Location location = 3;
}

message Employee {
    int32 id = 1;
    string name = 2;
    Status status = 3;
    Address address = 4;
}

message Department {
    string name = 1;
    Employee manager = 2;
}

message Company {
    string name = 1;
    google.protobuf.Timestamp founded = 2;
    Department department = 3;
}

message GetCompanyRequest {
    int32 company_id = 1;
}

message GetEmployeeRequest {
    int32 employee_id = 1;
}

message GetEmployeeResponse {
    optional Employee employee = 1;
}

message FindRequest {
    string name = 1;
}

message FindResponse {
    oneof union_var {
        Company company = 1;
        Department department = 2;
        Employee employee = 3;
        Status status = 4;
    }
}

message SummaryRequest {
    int32 employee_id = 1;
}

message SummaryResponse {
    oneof union_var {
        Employee employee = 1;
        Status status = 2;
    }
    string str_var = 3;
}

message UpdateRequest {
    Company company = 1;
    repeated Employee employees = 2;
    map<string, string> metadata = 3;
    repeated string tags = 4;
}

message UpdateResponse {
    repeated Department department = 1;
}
```

## Convert a Dataclass or Pydantic Model

Converting a dataclass or Pydantic model to protobuf messages is done using this way.

```python
from proto_builder.utils import ProtoConfig
from proto_builder.message_builder import MessageBuilder

config = ProtoConfig()
message_builder = MessageBuilder(config)

proto = message_builder.build(Company)

print(proto)
```

## Generated Message Output

```protobuf
enum Status {
    ACTIVE = 0;
    INACTIVE = 1;
}

message Location {
    string city = 1;
    string country = 2;
}

message Address {
    string street = 1;
    string postal_code = 2;
    Location location = 3;
}

message Employee {
    int32 id = 1;
    string name = 2;
    Status status = 3;
    Address address = 4;
}

message Department {
    string name = 1;
    Employee manager = 2;
}

message Company {
    string name = 1;
    google.protobuf.Timestamp founded = 2;
    Department department = 3;
}
```

## Configuration Options

The changes we can make via configuration:

```python
config = ProtoConfig(
    override=[
        ...
    ],
    remove=[
        ...
    ],
    optional=[
        ...
    ],
    optional_all=True or False,
)
```

### Override

Replace a type or a field's type with another type.

### Remove

Remove a type or a field's type.

### Optional

Make a field or its type optional (i.e., making its assignment optional).

### Optional All

`optional_all` makes the assignment of all fields or field types optional.

### Configuration Paths

The paths used in the config can be either relative or absolute.

### Configuration Example

```python
config = ProtoConfig(
    override=[
        {"Department.manager": list[Employee]},
        # It can be:
        # {"...Department.manager": list[Employee]},
        # or
        # {"...manager": list[Employee]},

        {"str": int},
    ],
    remove=[
        "Employee.address",
        # It can be:
        # "...Employee.address",
        # or
        # "...address",
        # or
        # "...Address",
    ],
    optional=[
        "Company",
        # It can be:
        # "...Company",

        "Employee.status",
        # It can be:
        # "...Employee.status",
        # or
        # "...status",
    ],
    # optional_all=True,
)
```

## Configured Output

```protobuf
enum Status {
    ACTIVE = 0;
    INACTIVE = 1;
}

message Employee {
    int32 id = 1;
    int32 name = 2;
    optional Status status = 3;
}

message Department {
    int32 name = 1;
    repeated Employee manager = 2;
}

message Company {
    optional int32 name = 1;
    optional google.protobuf.Timestamp founded = 2;
    optional Department department = 3;
}
```
