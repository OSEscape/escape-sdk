from dataclasses import dataclass, field
from typing import Any


@dataclass
class Blackboard:
    _data: dict[str, Any] = field(init=False, default_factory=dict, repr=False)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._data
