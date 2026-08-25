from .utils import OTHER, ProtoConfig, Message
from .base_builder import BaseBuilder
from .message_builder import MessageBuilder
from .tree_structure import Node
import inspect
from typing import (
    get_type_hints,
    Callable,
)

class ServiceBuilder(BaseBuilder):
    
    def __init__(
        self,
        config: ProtoConfig,
    ):
    
        super().__init__(config)
        self.message_builder = MessageBuilder(config)

    def build_session(
        self,
        node: Node,
        fn: Callable,
    ):

        fn_name = self.get_node_name(fn)
        
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)

        params = {
            pname: hints.get(pname, param.annotation)
            for pname, param in sig.parameters.items()
        }
        ret = hints.get("return")

        base_name = fn_name.title().replace("_", "")
        request_name = f"{base_name}Request"
        response_name = f"{base_name}Response"
        
        node = node.child(fn_name)
        
        input_node = node.child(request_name)        
        input_node.data.update({"label": "message"})
        
        output_node = node.child(response_name)
        output_node.data.update({"label": "message", "split_collection": True})
        
        for param_name, param_type in params.items():
            if param_name != "self":
                self.message_builder.build_tree(param_type, name=param_name, main=input_node),
        
        if ret:
            self.message_builder.build_tree(ret, main=output_node),

    def build(
        self,
        service_cls: object,
        package_name: str = "generated",
    ) -> str:
        
        cls_name = self.get_node_name(service_cls)
        methods = [
            fn
            for _, fn in service_cls.__dict__.items()
            if inspect.isfunction(fn) and getattr(fn, "__isabstractmethod__", False)
        ]
        
        main = Node(cls_name)
        for fn in methods:
            self.build_session(main, fn)

        header = [
            'syntax = "proto3";',
            f"package {package_name};",
        ]

        modules: list[str] = []
        service: list[str] = []
        messages: list[Message] = self.message_builder.node_to_message(main)
        messages.sort(key=lambda m: m.name.endswith("Request") or m.name.endswith("Response"))
        
        for fn_node in main.children:
            
            request_node, response_node = fn_node.children
            
            request_name = request_node.name if request_node.children else OTHER["empty"]
            response_name = response_node.name if response_node.children else OTHER["empty"]
            
            if not (request_node.children and response_node.children):
                modules.append(OTHER["empty"])
                
            request_message = next((m for m in messages if m.name == request_name), None)
            response_message = next((m for m in messages if m.name == response_name), None)
            if request_message and len(request_message.fields) == 1 and request_message.fields[0].is_message:
                request_name = request_message.fields[0].name
                messages.remove(request_message)
            if response_message and len(response_message.fields) == 1 and response_message.fields[0].is_message:
                response_name = response_message.fields[0].name
                messages.remove(response_message)
            
            service.append(f"    rpc {fn_node.name} ({request_name}) returns ({response_name});")
        
        modules = modules + [mdl for m in messages for mdl in m.modules]
        
        imports: list[str] = []
        for mdl in modules:
            imp = f'import "{mdl}";'
            if imp not in imports:
                imports.append(imp)

        content: list[str] = []

        content.append("\n".join(header))
        if imports:
            content.append("\n\n")
            content.append("\n".join(imports))
        if service:
            content.append("\n\n")
            content.append("\n".join([f"service {cls_name} {{"] + service + ["}"]))
        if messages:
            content.append("\n\n")
            content.append("\n\n".join([i.text for i in messages]))

        return "".join(content)