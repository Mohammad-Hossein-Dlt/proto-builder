from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterator, Literal

TagMode = Literal["all", "include", "exclude"]
SearchPosition = Literal["first", "last"]
VariantMode = Literal["include-self", "exclude-self", "all"]

@dataclass
class PathTree:
    
    root: PathNode = field(default_factory="PathNode")
    
    def __init__(
        self,
        name: str,
        tags: set[str] = set(),
    ):
        self.root = PathNode(name, tags=tags)
    
    def child(
        self,
        name: str,
        tags: set[str] = set(),
    ) -> PathNode:
        return self.root.child(name, tags)
    
    def add(
        self,
        *parts: str,
    ) -> PathNode:
        if not parts:
            raise ValueError("parts cannot be empty")
        node = self.root
        for part in parts:
            node = node.child(part)
        return node    

    def iter_paths(
        self,
    ) -> Iterator[str]:
        yield self.root.path
        for root in self.root.children.values():
            yield from root.iter_paths()

@dataclass
class PathNode:
    name: str
    parent: "PathNode | None" = None
    data: dict = field(default_factory=dict)
    children: dict[str, "PathNode"] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)

    @property
    def path(self) -> str:
        if self.parent and self.parent.path:
            return f"{self.parent.path}.{self.name}"
        return self.name

    @property
    def root(self) -> "PathNode":
        if self.parent is None:
            return self
        return self.parent.root

    def _iter_children(
        self,
        position: SearchPosition = "first",
    ) -> Iterator[PathNode]:
    
        if position == "first":
            return iter(self.children.values())
        elif position == "last":
            return reversed(self.children.values())
            
    def child(
        self,
        name: str,
        tags: set[str] = set(),
    ) -> "PathNode":
        
        key = name.lower()
        if key not in self.children:
            self.children[key] = PathNode(name=name, parent=self, tags=tags)
        return self.children[key]
    
    def node(
        self,
        _node: "PathNode",
    ) -> "PathNode":
        
        key = _node.name.lower()
        if key not in self.children:
            self.children[key] = _node
        return self.children[key]
    
    def add(
        self,
        name: str,
        *parts: str,
    ) -> "PathNode":
        
        root = PathNode(name=name, parent=self)
        node = root        
        for i in parts:
            key = i.lower()
            node.children[key] = PathNode(name=i, parent=node)
            node = node.children[key]
        self.children[name] = root
        
    def bulk(
        self,
        *parts: str,
        tags: set[str] = set(),
    ) -> "PathNode":
        
        for i in parts:
            self.child(i, tags=tags)
        return self

    def iter_paths(
        self,
    ) -> Iterator[str]:
        
        yield self.path
        for child in self.children.values():
            yield from child.iter_paths()
    
    def path_by_criteria(
        self,
        tags: set[str] = set(),
        tag_mode: TagMode = "all",
    ) -> list["PathNode"]:
        
        path = self.path_to_root()
        
        if tag_mode == "include":
            nodes = [node for node in path if node.tags.issuperset(tags)]
        
        elif tag_mode == "exclude":
            nodes = [node for node in path if not node.tags.issuperset(tags)]
        
        elif tag_mode == "all":
            nodes = [node for node in path]
            
        return nodes

    def find_nodes_by_tags( #
        self,
        tags: set[str],
    ) -> list["PathNode"]:
        
        result = []
        if tags.issubset(self.tags):
            result.append(self)

        for child in self.children.values():
            result.extend(child.find_nodes_by_tags(tags))

        return result
            
    def find_node(
        self,
        name: str,
        position: SearchPosition = "first",
    ) -> "PathNode | None":
        
        if self.name == name:
            return self
        
        for child in self._iter_children(position):
            found = child.find_node(name, position=position)
            if found:
                return found
        
        return None

    def find_all_nodes( #
        self,
        name: str,
    ) -> list["PathNode"]:
    
        result = []

        if self.name == name:
            result.append(self)

        for child in self.children.values():
            result.extend(child.find_all_nodes(name))

        return result

    def find_node_by_contiguous_path(
        self,
        *parts: str,
        position: SearchPosition = "first",
    ) -> "PathNode | None":
        
        if not parts:
            return self

        def search_from(node: "PathNode", index: int) -> "PathNode | None":
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
    ) -> "PathNode | None":
        
        if not parts:
            return self
        
        def search_from(node: "PathNode", index: int) -> "PathNode | None":
            
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
    
    def find_all_nodes_by_contiguous_path( #
        self,
        *parts: str,
    ) -> list["PathNode"]:
    
        if not parts:
            return [self]

        target = parts[0]
        results: list[PathNode] = []

        def _walk(node: "PathNode", remaining: tuple[str, ...]) -> None:
            if not remaining:
                results.append(node)
                return

            head = remaining[0]
            for child in node.children.values():
                if child.name == head:
                    _walk(child, remaining[1:])

        if self.name == target:
            if len(parts) == 1:
                results.append(self)
            else:
                _walk(self, parts[1:])

        for child in self.children.values():
            results.extend(child.find_all_nodes_by_contiguous_path(*parts))

        return results
    
    def find_all_nodes_by_discontiguous_path( #
        self,
        *parts: str,
    ) -> list[list[str]]:
    
        result = []
        
        def _walk(node: "PathNode", idx: int = 0) -> None:
            if idx == len(parts):
                result.append(node)
                return

            target = parts[idx]

            for child in node.children.values():
                if child.name == target:
                    _walk(child, idx + 1)
                else:
                    _walk(child, idx)

        _walk(self)
        return result
    
    def leaves( #
        self,
    ) -> list["PathNode"]:
        
        result = []
    
        if not self.children:
            return [self]
        
        for child in self.children.values():
            result.extend(child.leaves())
        
        return result
    
    def path_to_root(
        self,
        name: str | None = None,
    ) -> list["PathNode"]:
        
        if self.parent is None or self.name == name:
            return [self]
        return self.parent.path_to_root(name) + [self]

    def path_variants_to_root(
        self,
        tags: set[str] = set(),
        tag_mode: Literal["include", "exclude"] = "include",
        mode: VariantMode = "include-self", 
    ) -> Iterator[list["PathNode"]]:
        
        def is_match(node: "PathNode") -> bool:
            
            if not tags:
                return True
            
            if tag_mode == "include":
                return node.tags.issuperset(tags)
            if tag_mode == "exclude":
                return not node.tags.issuperset(tags)
            
            return False 
        
        path = self.path_to_root()[:-1]    
        tagged_idxs = [i for i, n in enumerate(path) if is_match(n)]
        
        for r in range(len(tagged_idxs) + 1):
            for removed in combinations(tagged_idxs, r):
                removed = set(removed)
                
                if len(removed) == len(path):
                    continue
                
                if mode == "all":
                    yield [n for i, n in enumerate(path) if i not in removed] + [self]
                    yield [n for i, n in enumerate(path) if i not in removed]
                
                elif mode == "include-self":
                    yield [n for i, n in enumerate(path) if i not in removed] + [self]
                
                elif mode == "exclude-self":
                    yield [n for i, n in enumerate(path) if i not in removed]
        
        if mode != "exclude-self":
            yield [self]
                
    def last_node(
        self,
    ) -> "PathNode":
        
        node = self
        while node.children:
            node = list(node.children.values())[-1]
        return node
    
    def same_as(self, other: "PathNode") -> bool:
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

    def contains_subtree(self, other: "PathNode") -> bool:

        def _walk(node: "PathNode") -> bool:
            if node.same_as(other):
                return True

            return any(_walk(child) for child in node.children.values())

        return _walk(self)
        

if __name__ == "__main__":
    
    tree = PathTree("a")
    
    child_B = tree.root.child("b")
    
    child_D = child_B.child("d", tags={"tag-1"})
    child_B.child("e")
    
    child_D.child("h", tags={"tag-1"})
    child_D.child("i")    
    
    child_C = tree.root.child("c")
    
    child_F = child_C.child("f")
    child_C.child("g")
    
    child_F.child("j", tags={"tag-1"})
    child_F.child("k")
    
    child_B = tree.root.find_node("b")
    child_K = tree.root.find_node("k")
    
    # child_I = child_C.child("d", tags={"tag-1"}).child("h").child("i")
    child_I = tree.root.find_node("i")
