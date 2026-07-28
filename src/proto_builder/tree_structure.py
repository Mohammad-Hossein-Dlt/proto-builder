from dataclasses import dataclass, field
from typing import Iterator, Literal

SearchPosition = Literal["first", "last"]

@dataclass
class Node:
    name: str
    parent: "Node | None" = None
    data: dict = field(default_factory=dict)
    children: dict[str, "Node"] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)

    @property
    def path(self) -> str:
        if self.parent and self.parent.path:
            return f"{self.parent.path}.{self.name}"
        return self.name

    @property
    def root(self) -> "Node":
        if self.parent is None:
            return self
        return self.parent.root
            
    def child(
        self,
        name: str,
        tags: set[str] = set(),
    ) -> "Node":
        
        key = name.lower()
        if key not in self.children:
            self.children[key] = Node(name=name, parent=self, tags=tags)
        return self.children[key]
    
    def node(
        self,
        _node: "Node",
    ) -> "Node":
        
        key = _node.name.lower()
        if key not in self.children:
            _node.parent = self
            self.children[key] = _node
        return self.children[key]
    
    def bulk(
        self,
        *parts: str,
        tags: set[str] = set(),
    ) -> "Node":
        
        for i in parts:
            self.child(i, tags=tags)
        return self
    
    def add(
        self,
        *parts: str,
    ) -> "Node":
        
        node = self        
        for i in parts:
            key = i.lower()
            node.children[key] = Node(name=i, parent=node)
            node = node.children[key]
        
        return node

    def iter_paths(
        self,
    ) -> Iterator[str]:
        
        yield self.path
        for child in self.children.values():
            yield from child.iter_paths()
    
    def next(
        self,
    ) -> "Node":
        
        if self.children:
            return next(iter(self.children.values()))
        
        return self
    
    def path_to_root(
        self,
        name: str | None = None,
    ) -> list["Node"]:
        
        if self.parent is None or self.name == name:
            return [self]
        return self.parent.path_to_root(name) + [self]
    
    def _iter_children(
        self,
        position: SearchPosition = "first",
    ) -> Iterator[Node]:
    
        if position == "first":
            return iter(self.children.values())
        elif position == "last":
            return reversed(self.children.values())

    def find_node(
        self,
        name: str,
        position: SearchPosition = "first",
    ) -> "Node | None":
        
        if self.name == name:
            return self
        
        for child in self._iter_children(position):
            found = child.find_node(name, position=position)
            if found:
                return found
        
        return None
    
    def find_node_by_contiguous_path(
        self,
        *parts: str,
        position: SearchPosition = "first",
    ) -> "Node | None":
        
        if not parts:
            return self

        def search_from(node: "Node", index: int) -> "Node | None":
            if index == len(parts):
                return node

            target = parts[index]

            for child in node._iter_children(position):
                if child.name == target:
                    found = search_from(child, index + 1)
                    if found:
                        return found
                    
            return None
        
        if self.name == parts[0]:
            found = search_from(self, 1)
            if found:
                return found

        for child in self._iter_children(position):
            found = child.find_node_by_contiguous_path(*parts, position=position)
            if found:
                return found
            
        return None

    def find_node_by_discontiguous_path(
        self,
        *parts: str,
        position: SearchPosition = "first",
    ) -> "Node | None":
        
        if not parts:
            return self
        
        def search_from(node: "Node", index: int) -> "Node | None":
            
            if index == len(parts):
                return node

            target = parts[index]

            for child in node._iter_children(position):
                if child.name == target:
                    found = search_from(child, index + 1)
                else:
                    found = search_from(child, index)
                if found:
                    return found
            
            return None

        if self.name == parts[0]:
            found = search_from(self, 1)
            if found:
                return found

        if position == "first":
            children = self.children.values()
        elif position == "last":
            children = reversed(self.children.values())

        for child in children:
            found = child.find_node_by_discontiguous_path(*parts)
            if found:
                return found

        return None
    
    def last_node(
        self,
    ) -> "Node":
        
        node = self
        while node.children:
            node = list(node.children.values())[-1]
        return node
    
    def same_as(self, other: "Node") -> bool:
        if self.name != other.name:
            return False

        if len(self.children) != len(other.children):
            return False

        for key, child in self.children.items():
            other_child = other.children.get(key)
            if other_child is None:
                return False
            if not child.same_as(other_child):
                return False

        return True

    def contains_subtree(self, other: "Node") -> bool:

        def _walk(node: "Node") -> bool:
            if node.same_as(other):
                return True

            return any(_walk(child) for child in node.children.values())

        return _walk(self)
    
    def find_nodes(
        self,
        name: str,
    ) -> list["Node"]:
    
        result = []

        if self.name == name:
            result.append(self)

        for child in self.children.values():
            result.extend(child.find_nodes(name))

        return result
    
    def find_nodes_by_tags(
        self,
        tags: set[str],
    ) -> list["Node"]:
        
        result = []
        if tags.issubset(self.tags):
            result.append(self)

        for child in self.children.values():
            result.extend(child.find_nodes_by_tags(tags))

        return result
    
    def leaves(
        self,
    ) -> list["Node"]:
        
        result = []
    
        if not self.children:
            return [self]
        
        for child in self.children.values():
            result.extend(child.leaves())
        
        return result