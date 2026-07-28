from .utils import OTHER, MODULES, NONE_TYPE, ProtoConfig, Session, NodeData, Message
from .base_builder import BaseBuilder
from .session_builder import SessionBuilder
from .tree_structure import Node
import inspect
from dataclasses import asdict
from typing import (
    get_origin,
    get_args,
    get_type_hints,
    Callable,
)    

class ServiceBuilder(BaseBuilder):
    
    def __init__(
        self,
        config: ProtoConfig,
    ):
    
        super().__init__(config)
        self.session_builder = SessionBuilder(config)

    def build_session(
        self,
        name: str,
        fn: Callable,
        cls_name: str,
    ) -> Session:
        
        fn_name = self.get_type_name(fn)
        
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)

        params = {
            pname: hints.get(pname, param.annotation)
            for pname, param in sig.parameters.items()
        }
        ret = hints.get("return")

        base_name = name.title().replace("_", "")
        request_name = f"{base_name}Request"
        response_name = f"{base_name}Response"
        
        input_node: Node = Node(cls_name).child(fn_name).child("arg")
        input_node.data.update(asdict(NodeData(label="message", name=request_name)))
        
        output_node: Node = Node(cls_name).child(fn_name).child("return")
        output_node.data.update(asdict(NodeData(label="message", name=response_name)))
        
        for param_name, param_type in params.items():
            node = input_node.child(param_name)
            self.session_builder.build_tree(param_type, node)
        
        if ret:

            ret_origin = get_origin(ret)
            ret_args = get_args(ret)
            
            if ret_origin is tuple:
                for arg in ret_args:
                    
                    if self.is_optional(arg):
                        inner = next(a for a in get_args(arg) if a is not NONE_TYPE)
                        name = self.to_snake_case(self.get_type_name(inner))
                        if not (self.is_custom(inner) or self.is_enum(inner)):
                            name += "_var"
                    else:
                        name = self.to_snake_case(self.get_type_name(arg)) + "_var"
                    
                    node = output_node.child(name)
                    self.session_builder.build_tree(arg, node)
            else:
                if self.is_optional(ret):
                    inner = next(a for a in get_args(ret) if a is not NONE_TYPE)
                    name = self.to_snake_case(self.get_type_name(inner))
                    if not (self.is_custom(inner) or self.is_enum(inner)):
                        name += "_var"
                else:
                    name = self.to_snake_case(self.get_type_name(ret)) + "_var"
                node = output_node.child(name)
                self.session_builder.build_tree(ret, node)
                
        return Session(fn_name, input_node.root, output_node.root)
    
    def _typed_node(self, node: Node) -> Node | None:
        
        if node.data.get("label") == "enum":
            return node
        
        else: 
            for child in node.children.values():
                    
                if child.data.get("type"):
                    return child
                else:
                    return self._typed_node(child)
                    
        return None
    
    def resolve_service_name(
        self,
        node: Node,
    ):
                
        if not node.children:
            return OTHER["empty"]

        if len(node.children) > 1:
            return node.data.get("name")
        
        child = self._typed_node(node)
        
        if child:
            f_type = child.data.get("type")
            if self.is_custom(f_type):
                return self.get_type_name(f_type)
        
        return node.data.get("name")

    def message_from_fields(
        self,
        node: Node,
    ) -> list[Message]:
        
        messages_list: list[Message] = []            
        msg = self.session_builder.node_to_message(node)
        messages_list.extend(msg)
        return messages_list

    def build(
        self,
        service_cls: type,
        package_name: str = "generated",
    ) -> str:
        
        cls_name = self.get_type_name(service_cls)
        methods = {
            name: fn
            for name, fn in service_cls.__dict__.items()
            if inspect.isfunction(fn) and getattr(fn, "__isabstractmethod__", False)
        }

        sessions = [self.build_session(name, fn, cls_name) for name, fn in methods.items()]

        header = [
            'syntax = "proto3";',
            f"package {package_name};",
        ]

        modules: list[str] = []
        service: list[str] = []
        messages: list[str] = []
        
        for session in sessions:
            
            input_node = session.input_node.find_node("arg", "first")
            output_node = session.output_node.find_node("return", "first")
            
            request_name = self.resolve_service_name(input_node)
            response_name = self.resolve_service_name(output_node)
            
            if request_name == OTHER["empty"] or response_name == OTHER["empty"]:
                modules.append(OTHER["empty"])
            
            msgs = self.message_from_fields(input_node)            
            for msg in msgs:
         
                if input_node.data.get("name") != request_name and msg.name == input_node.data.get("name"):
                    continue
         
                if msg.text and msg.text not in messages:
                    messages.append(msg.text)
                modules.extend(msg.modules)
                
            if not any(msg.name == input_node.data.get("name") or msg.name == request_name for msg in msgs):
                request_name = OTHER["empty"]
                
            msgs = self.message_from_fields(output_node)
            for msg in msgs:

                if output_node.data.get("name") != response_name and msg.name == output_node.data.get("name"):
                    continue

                if msg.text and msg.text not in messages:
                    messages.append(msg.text)
                modules.extend(msg.modules)
                
            if not any(msg.name == output_node.data.get("name") or msg.name == response_name for msg in msgs):
                response_name = OTHER["empty"]
                                 
            service.append(f"    rpc {session.name} ({request_name}) returns ({response_name});")
        
        imports: list[str] = []
        for mdl in modules:
            if mdl in MODULES:
                imp = f'import "{MODULES[mdl]}";'
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
            content.append("\n\n".join(messages))

        return "".join(content)