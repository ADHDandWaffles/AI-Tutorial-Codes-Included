# app/graphagent/registry.py
from typing import Callable, Dict

NODE_REGISTRY: Dict[str, Callable] = {}

def register_node(name: str):
    """Decorator to register a node under a stable name."""
    def deco(fn: Callable):
        NODE_REGISTRY[name] = fn
        return fn
    return deco
