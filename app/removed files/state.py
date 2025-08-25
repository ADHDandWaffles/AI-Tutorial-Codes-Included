from dataclasses import dataclass, field
from typing import List

@dataclass
class State:
    task: str
    plan: str = ""
    scratch: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    result: str = ""
    step: int = 0
    done: bool = False
