from dataclasses import dataclass, field
from typing import Iterator, Literal

SearchPosition = Literal["first", "last"]

@dataclass
class Node:
    name: str
    parent: "Node | None" = None
    data: dict = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
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
    
    def get_child(
        self,
        name: str,
    ) -> Node:
        return next((i for i in self.children if i.name == name))
    
    def drop_child(
        self,
        name: str,
    ):
        index = next((i for i, child in enumerate(self.children) if child.name == name))
        del self.children[index]    

    def replace_child(
        self,
        old: str | "Node",
        new: str | "Node",
    ):
        name = old if isinstance(old, str) else old.name
        index = next((i for i, child in enumerate(self.children) if child.name == name))
        if isinstance(new, str):
            new = Node(name=new)        
        new.parent = self
            
        del self.children[index]
        self.children.insert(index, new)
        
        return new
        
    def child(
        self,
        name: str,
        tags: set[str] = set(),
    ) -> "Node":
        
        if all(i.name != name for i in self.children):
            self.children.append(
                Node(name=name, parent=self, tags=tags),
            )
            
                
        return self.get_child(name)
    
    def node(
        self,
        n: "Node",
    ) -> "Node":
        
        if all(i.name != n.name for i in self.children):
            n.parent = self
            self.children.append(n)
            
        return self.get_child(n.name)
    
    def bulk(
        self,
        *parts: str,
        tags: set[str] = set(),
    ) -> "Node":
        
        for i in parts:
            self.child(i, tags=tags)
        return self
    
    def set_parent(self, parent: "Node") -> "Node":

        if parent.same_as(self):
            raise ValueError("Cannot set a node as parent of itself or its descendant.")

        if self.parent is not None:
            self.parent.children.pop(self.name.lower(), None)

        self.parent = parent
        parent.children[self.name.lower()] = self

        return self
    
    def insert_parent(
        self,
        name: str,
    ) -> "Node":

        old_parent = self.parent

        new_parent = Node(name=name, parent=old_parent)
        new_parent.children.append(self)
        self.parent = new_parent
        
        if old_parent:
            old_parent.replace_child(self, new_parent)

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
        for child in self.children:
            yield from child.iter_paths()
    
    def next(
        self,
    ) -> "Node":
        
        if self.children:
            return next(iter(self.children))
        
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
            return iter(self.children)
        elif position == "last":
            return reversed(self.children)

    def find_node(
        self,
        *name: str,
        position: SearchPosition = "first",
    ) -> "Node | None":
        
        if self.name in name:
            return self
        
        for child in self._iter_children(position):
            found = child.find_node(*name, position=position)
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
            children = self.children
        elif position == "last":
            children = reversed(self.children)

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
            node = list(node.children)[-1]
        return node
    
    def same_as(self, other: "Node") -> bool:
        if self.name != other.name:
            return False

        if len(self.children) != len(other.children):
            return False

        for child in self.children:
            other_child = other.get_child(child.name)
            if other_child is None:
                return False
            if not child.same_as(other_child):
                return False

        return True

    def contains_subtree(self, other: "Node") -> bool:

        def _walk(node: "Node") -> bool:
            if node.same_as(other):
                return True

            return any(_walk(child) for child in node.children)

        return _walk(self)
    
    def find_nodes(
        self,
        name: str,
    ) -> list["Node"]:
    
        result = []

        if self.name == name:
            result.append(self)

        for child in self.children:
            result.extend(child.find_nodes(name))

        return result
    
    def find_nodes_by_tags(
        self,
        tags: set[str],
    ) -> list["Node"]:
        
        result = []
        if tags.issubset(self.tags):
            result.append(self)

        for child in self.children:
            result.extend(child.find_nodes_by_tags(tags))

        return result
    
    def leaves(
        self,
    ) -> list["Node"]:
        
        result = []
    
        if not self.children:
            return [self]
        
        for child in self.children:
            result.extend(child.leaves())
        
        return result
    
    def copy(
        self,
        parent: "Node | None" = None,
    ) -> "Node":
        new_node = Node(
            name=self.name,
            parent=parent,
            data=self.data.copy(),
            tags=self.tags.copy(),
        )

        for child in self.children:
            child_copy = child.copy(parent=new_node)
            new_node.children.append(child_copy)

        return new_node