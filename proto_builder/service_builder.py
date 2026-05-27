from .utils import OTHER, MODULES, NONE_TYPE, ProtoConfig, Session, NodeData, Message
from .base_builder import BaseBuilder
from .session_builder import SessionBuilder
from tree_structure import PathTree
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
        self.trees: list[PathTree] = []

    def should_generate_message(
        self,
        params: dict[str, PathTree],
    ) -> bool:
        
        if not params:
            return False
        
        if len(params) > 1:
            return True

        tree = next(iter(params.values()))
        if tree.root.data.get("is_custom"):
            
            if tree.root.data.get("message_type") == "enum":
                return True
            
            for t in self.trees:
                
                if t.root.same_as(tree.root):
                    return False
                
                if t.root.contains_subtree(tree.root):
                    return False
        
        return True

    def merge_model(
        self,
        tree: PathTree,
    ) -> None:
    
        if not any(
            t.root.contains_subtree(tree.root)
            for t in self.trees
        ):
            self.trees.append(tree)

    def method_models(
        self,
        fn: Callable,
        cls_name: str,
    ):
    
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)
        method_node = PathTree(cls_name).root.child(fn.__name__)

        def add_model(cls: type):
            if cls and (self.is_custom(cls) or self.is_enum(cls)):
                tree = self.session_builder.build_tree(cls)
                
                if self.is_removed(tree.root):
                    return
                
                self.merge_model(tree)

        def add_type(
            tp,
            name: str | None = None,
        ):
        
            node = method_node.child(name or "")
            resolved = self.resolve_type(node, tp)
            origin = get_origin(resolved)
            if self.is_union(origin):
                for arg in get_args(resolved):
                    if arg is not NONE_TYPE:
                        add_model(arg)
            else:
                add_model(resolved)

        for param in sig.parameters.values():
            add_type(hints.get(param.name, param.annotation), param.name)

        add_type(hints.get("return"))

    def build_session(
        self,
        name: str,
        fn: Callable,
        cls_name: str,
    ) -> Session:
    
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)
        method_node = PathTree(cls_name).root.child(fn.__name__)

        params = {
            pname: hints.get(pname, param.annotation)
            for pname, param in sig.parameters.items()
        }
        ret = hints.get("return")

        base_name = name.title().replace("_", "")
        request_name = f"{base_name}Request"
        response_name = f"{base_name}Response"
        input_params: dict[str, PathTree] = {}
        output_params: dict[str, PathTree] = {}

        for param_name, param_type in params.items():
            node = method_node.child(param_name)
            node.data.update(asdict(NodeData(message_name=param_type.__name__, field_type=param_type)))
            if self.is_removed(node):
                continue
            resolved_type = self.resolve_type(node, param_type)
            input_params[param_name] = self.session_builder.build_tree(resolved_type)
        
        if not input_params:
            request_name = OTHER["empty"]
        
        elif len(input_params) == 1:
            name, tree = next(iter(input_params.items()))
            f_type = tree.root.data.get("field_type")
            if self.is_custom(f_type) and any(t.root.contains_subtree(tree.root) for t in self.trees):
                request_name = resolved_type.__name__
        
        if ret:
            f_type = method_node.data.get("field_type")
            resolved_type = self.resolve_type(method_node, ret)
            tree = self.session_builder.build_tree(resolved_type, name="return")
            output_params = {"return_value": tree}
            
        if not output_params:
            response_name = OTHER["empty"]
            
        elif len(output_params) == 1:
            name, tree = next(iter(output_params.items()))
            f_type = tree.root.data.get("field_type")
            if self.is_custom(f_type) and any(t.root.contains_subtree(tree.root) for t in self.trees):
                response_name = resolved_type.__name__

        return Session(fn.__name__, request_name, response_name, input_params, output_params)

    def message_from_fields(
        self,
        fn_name: str,
        name: str,
        fields: dict[str, PathTree],
        cls_name: str,
    ) -> Message:
        
        message: Message = Message()
        lines = [f"message {name} {{"]
        method_node = PathTree(cls_name).root.child(fn_name)

        idx = 1
        for field_name, tree in fields.items():
            
            node = method_node.node(tree.root)
            
            if self.is_removed(node):
                continue

            proto = self.session_builder.proto_type(node)
            proto.name = field_name
            lines.append(self.format_proto_field(proto, idx))
            message.modules.append(proto.p_type)
            idx += 1

        lines.append("}")
        if len(lines) > 2:
            message.text = "\n".join(lines)

        return message

    def build(
        self,
        service_cls: type,
        package_name: str = "generated",
    ) -> str:
        
        self.trees = []
    
        cls_name = service_cls.__name__
        methods = {
            name: fn
            for name, fn in service_cls.__dict__.items()
            if inspect.isfunction(fn) and getattr(fn, "__isabstractmethod__", False)
        }

        for fn in methods.values():
            self.method_models(fn, cls_name)

        sessions = {
            name: self.build_session(name, fn, cls_name)
            for name, fn in methods.items()
        }

        header = [
            'syntax = "proto3";',
            f"package {package_name};",
        ]

        service = [f"service {cls_name} {{"]
        for name, session in sessions.items():
            service.append(f"    rpc {name} ({session.request_name}) returns ({session.response_name});")
        service.append("}")

        messages: list[str] = []
        modules: list[str] = []
        for tree in self.trees:
            msg_list: list[Message] = self.session_builder.node_to_message(tree, tree.root)
            for msg in msg_list:
                messages.append(msg.text)
                modules.extend(msg.modules)
        
        for session in sessions.values():
            
            if self.should_generate_message(session.input_params):
                msg = self.message_from_fields(session.fn_name, session.request_name, session.input_params, cls_name)
                messages.append(msg.text)
                modules.extend(msg.modules)
            
            if self.should_generate_message(session.output_params):
                msg = self.message_from_fields(session.fn_name, session.response_name, session.output_params, cls_name)
                messages.append(msg.text)
                modules.extend(msg.modules)
                
            if not session.input_params or not session.output_params:
                modules.append(OTHER["empty"])
            
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
            content.append("\n".join(service))
        if messages:
            content.append("\n\n")
            content.append("\n\n".join(messages))

        return "".join(content)