from dataclasses import dataclass
from enum import IntEnum

ItemIdentifier = int | str


class EntityType(IntEnum):
    NPC = 1
    OBJECT = 2
    ITEM = 3


@dataclass(frozen=True)
class Skill:
    name: str
    level: int
    xp: int
    boosted_level: int


@dataclass(frozen=True, slots=True)
class Item:
    id: int
    name: str
    quantity: int
    noted: bool

    def __repr__(self) -> str:
        fields = f"id={self.id}, name={self.name!r}, quantity={self.quantity}"
        if self.noted:
            fields += ", noted=True"
        return f"Item({fields})"

    def matches(self, identifier: ItemIdentifier) -> bool:
        if isinstance(identifier, int):
            return self.id == identifier
        return identifier in self.name


class ItemContainer:
    def __init__(
        self,
        container_id: int = -1,
        slot_count: int = -1,
        items: list[Item | None] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.container_id = container_id
        self.slot_count = slot_count
        self._items = items if items is not None else []
        self._quantity_by_id: dict[int, int] | None = None

    @property
    def items(self) -> list[Item | None]:
        return self._items

    @items.setter
    def items(self, value: list[Item | None]) -> None:
        self._items = value
        self._quantity_by_id = None

    @property
    def quantity_by_id(self) -> dict[int, int]:
        """Item ID to total quantity mapping, cached until items change."""
        if self._quantity_by_id is None:
            result: dict[int, int] = {}
            for item in self._items:
                if item is not None:
                    result[item.id] = result.get(item.id, 0) + item.quantity
            self._quantity_by_id = result
        return self._quantity_by_id

    def get_total_count(self) -> int:
        return sum(1 for item in self.items if item is not None)

    def get_total_quantity(self) -> int:
        return sum(item.quantity for item in self.items if item is not None)

    def count(self, identifier: ItemIdentifier) -> int:
        if isinstance(identifier, int):
            return sum(1 for item in self.items if item is not None and item.id == identifier)
        return sum(1 for item in self.items if item is not None and identifier in item.name)

    def get(self, identifier: ItemIdentifier) -> list[Item]:
        if isinstance(identifier, int):
            return [item for item in self.items if item is not None and item.id == identifier]
        return [item for item in self.items if item is not None and identifier in item.name]

    def get_slot(self, slot_index: int) -> Item | None:
        if 0 <= slot_index < len(self.items):
            return self.items[slot_index]
        return None

    def get_slots(self, slots: list[int]) -> list[Item | None]:
        result = []
        for slot_index in slots:
            if 0 <= slot_index < len(self.items):
                result.append(self.items[slot_index])
            else:
                result.append(None)
        return result

    def find_slot(self, identifier: ItemIdentifier) -> int | None:
        if isinstance(identifier, int):
            for index, item in enumerate(self.items):
                if item is not None and item.id == identifier:
                    return index
        else:
            for index, item in enumerate(self.items):
                if item is not None and identifier in item.name:
                    return index
        return None

    def find_slots(self, identifier: ItemIdentifier) -> list[int]:
        slots = []
        if isinstance(identifier, int):
            for index, item in enumerate(self.items):
                if item is not None and item.id == identifier:
                    slots.append(index)
        else:
            for index, item in enumerate(self.items):
                if item is not None and identifier in item.name:
                    slots.append(index)
        return slots

    def contains(self, identifier: ItemIdentifier) -> bool:
        if isinstance(identifier, int):
            return any(item is not None and item.id == identifier for item in self.items)
        return any(item is not None and identifier in item.name for item in self.items)

    def contains_all(self, identifiers: list[ItemIdentifier]) -> bool:
        return all(self.contains(identifier) for identifier in identifiers)

    def quantity(self, identifier: ItemIdentifier) -> int:
        if isinstance(identifier, int):
            return sum(
                item.quantity for item in self.items if item is not None and item.id == identifier
            )
        return sum(
            item.quantity for item in self.items if item is not None and identifier in item.name
        )

    def is_empty(self) -> bool:
        return all(item is None for item in self.items)

    def is_full(self) -> bool:
        if self.slot_count > 0:
            return self.get_total_count() >= self.slot_count
        return all(item is not None for item in self.items)

    def __repr__(self) -> str:
        count = self.get_total_count()
        return f"ItemContainer(id={self.container_id}, slots={self.slot_count}, items={count})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, ItemContainer):
            return False
        return (
            self.container_id == other.container_id
            and self.slot_count == other.slot_count
            and self.items == other.items
        )

    def clear(self) -> None:
        self.items = []
