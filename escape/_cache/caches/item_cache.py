"""Cache for storing item containers (inventory, bank, equipment)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape._proto.bridge.v1.bridge_pb2 import (  # pyright: ignore[reportMissingImports]
        ItemContainerChanged,
    )

from escape._models import Item, ItemContainer


class ItemContainerCache:
    """Cache for item containers (inventory, equipment, bank)."""

    INVENTORY_ID = 93
    EQUIPMENT_ID = 94
    BANK_ID = 95

    def __init__(self):
        self.inventory = ItemContainer(container_id=self.INVENTORY_ID, slot_count=28)
        self.equipment = ItemContainer(container_id=self.EQUIPMENT_ID, slot_count=14)
        self.bank = ItemContainer(container_id=self.BANK_ID)

        # Store other containers that might be tracked
        self._other_containers: dict[int, ItemContainer] = {}

    def get_container(self, container_id: int) -> ItemContainer | None:
        """Get container by ID."""
        if container_id == self.INVENTORY_ID:
            return self.inventory
        elif container_id == self.EQUIPMENT_ID:
            return self.equipment
        elif container_id == self.BANK_ID:
            return self.bank
        elif container_id in self._other_containers:
            return self._other_containers[container_id]
        return None

    def add_container(self, container_id: int, container: ItemContainer) -> None:
        self._other_containers[container_id] = container

    def _proto_items_to_items(self, proto_items) -> list[Item | None]:
        if not proto_items:
            return []
        size = max(pi.slot for pi in proto_items) + 1
        items: list[Item | None] = [None] * size
        for proto_item in proto_items:
            items[proto_item.slot] = Item(
                id=proto_item.id,
                name=proto_item.name,
                quantity=proto_item.quantity,
                noted=proto_item.noted,
            )
        return items

    def process_change(self, change: ItemContainerChanged) -> None:
        """Process item container change event."""
        container_id = change.container_id

        # Get or create container
        if container_id == self.INVENTORY_ID:
            container = self.inventory
        elif container_id == self.EQUIPMENT_ID:
            container = self.equipment
        elif container_id == self.BANK_ID:
            container = self.bank
        else:
            # Create other container if it doesn't exist
            if container_id not in self._other_containers:
                self._other_containers[container_id] = ItemContainer(container_id=container_id)
            container = self._other_containers[container_id]

        # Update items using protobuf data
        container.items = self._proto_items_to_items(change.items)
