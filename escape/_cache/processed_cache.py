from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from escape._cache.caches import (
    AnimationCache,
    CameraState,
    ChatCache,
    GameStateCache,
    GroundItem,
    GroundItemCache,
    Item,
    ItemContainer,
    ItemContainerCache,
    MenuOptionClick,
    MenuOptionClickCache,
    Npc,
    NpcCache,
    SceneObject,
    SceneObjectCache,
    Skill,
    SkillCache,
    VarcCache,
    VarpCache,
)
from escape.events import ChatMessageReceived, EventBus, InventoryChanged, TickEvent

if TYPE_CHECKING:
    from escape._proto.bridge.v1.bridge_pb2 import (  # pyright: ignore[reportMissingImports]
        ActiveInterfacesUpdate,
        ClickboxUpdate,
        MenuOpenUpdate,
        SelectedWidgetUpdate,
        WorldEntityUpdate,
        WorldViewLoad,
    )


@dataclass(frozen=True, slots=True)
class SubMenuSort:
    parent_index: int
    options: tuple[str, ...]
    targets: tuple[str, ...]
    menu_actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MenuSort:
    options: tuple[str, ...]
    targets: tuple[str, ...]
    menu_actions: tuple[str, ...]
    sub_menus: tuple[SubMenuSort, ...] = ()


class ProcessedCache:
    def __init__(self, stub):
        self._stub = stub
        self._containers_initialized: set[int] = set()
        self.events = EventBus()

        # Domain caches
        self._varps = VarpCache()
        self._varcs = VarcCache()
        self._skills = SkillCache()
        self._items = ItemContainerCache()
        self._chat = ChatCache()
        self._game_state = GameStateCache()
        self._ground_items = GroundItemCache()
        self._scene_objects = SceneObjectCache()
        self._npcs = NpcCache()
        self._menu_option_clicks = MenuOptionClickCache()
        self._animations = AnimationCache()

        # Wire stubs to entity caches for subscribe-as-you-go RPCs
        self._npcs.set_stub(stub)
        self._scene_objects.set_stub(stub)
        self._ground_items.set_stub(stub)

        # World view derived data
        self._collision_flags: np.ndarray | None = None
        self._instance_template_chunks: np.ndarray | None = None
        self._is_instance: bool = False
        self._world_view_version: int = 0
        self._camera_version: int = 0

        # Raw protobuf storage
        self._world_view: WorldViewLoad | None = None
        self._menu_open: MenuOpenUpdate | None = None
        self._selected_widget: SelectedWidgetUpdate | None = None
        self._active_interfaces: ActiveInterfacesUpdate | None = None
        self._world_entity: WorldEntityUpdate | None = None
        self._post_menu_sort: MenuSort | None = None
        self._clickbox_update: ClickboxUpdate | None = None

    # --- Event Routing ---

    def _process_snapshot(self, field_name: str, proto_obj: Any) -> None:
        if field_name == "snapshot":
            self._varps.process_snapshot(proto_obj)
        elif field_name == "chat_snapshot":
            self._chat.process_snapshot(proto_obj)
        elif field_name == "stat_snapshot":
            self._skills.process_snapshot(proto_obj)
        elif field_name == "varc_int_snapshot":
            self._varcs.process_snapshot_int(proto_obj)
        elif field_name == "varc_str_snapshot":
            self._varcs.process_snapshot_str(proto_obj)
        elif field_name == "interface_snapshot":
            self._active_interfaces = proto_obj

    def _process_stream_event(self, field_name: str, proto_obj: Any) -> None:
        if field_name == "game_tick_update":
            self._game_state.process_tick(proto_obj)
        elif field_name == "camera_changed":
            self._game_state.process_camera(proto_obj)
            self._camera_version += 1
        elif field_name == "game_state_change":
            self._game_state.process_game_state(proto_obj)
        elif field_name == "varbit_changed":
            self._varps.process_change(proto_obj)
        elif field_name == "varc_int_changed":
            self._varcs.process_change_int(proto_obj)
        elif field_name == "varc_str_changed":
            self._varcs.process_change_str(proto_obj)
        elif field_name == "stat_changed":
            self._skills.process_change(proto_obj)
        elif field_name == "item_container_changed":
            self._items.process_change(proto_obj)
        elif field_name == "chat_changed":
            self._chat.process_change(proto_obj)
        elif field_name == "ground_items_update":
            self._ground_items.process_update(proto_obj)
        elif field_name == "scene_objects_update":
            self._scene_objects.process_update(proto_obj)
        elif field_name == "npc_update":
            self._npcs.process_update(proto_obj)
        elif field_name == "menu_option_click_update":
            self._menu_option_clicks.process_click(proto_obj)
        elif field_name == "animation_changed":
            self._animations.process_change(proto_obj)
        elif field_name == "world_view_load":
            self._world_view = proto_obj
            self._world_view_version += 1
            wv = proto_obj
            num_planes = len(wv.tile_heights) // (wv.size_x * wv.size_y) if wv.size_x and wv.size_y else 0
            if wv.collision_flags and num_planes:
                # Collision is per-tile (size-1 x size-1), not per-vertex like heights
                col_x = wv.size_x - 1
                col_y = wv.size_y - 1
                self._collision_flags = np.array(wv.collision_flags, dtype=np.int32).reshape(num_planes, col_x, col_y)
            else:
                self._collision_flags = None
            self._is_instance = wv.is_instance
            if wv.is_instance and wv.instance_template_chunks and num_planes:
                chunks_x = wv.size_x // 8
                self._instance_template_chunks = np.array(wv.instance_template_chunks, dtype=np.int32).reshape(num_planes, chunks_x, -1)
            else:
                self._instance_template_chunks = None
        elif field_name == "menu_open_update":
            self._menu_open = proto_obj
        elif field_name == "selected_widget_update":
            self._selected_widget = proto_obj
        elif field_name == "active_interfaces_update":
            self._active_interfaces = proto_obj
        elif field_name == "world_entity_update":
            self._world_entity = proto_obj
        elif field_name == "post_menu_sort_update":
            if proto_obj and hasattr(proto_obj, "options"):
                n = len(proto_obj.options)
                sub_menus: list[SubMenuSort] = []
                for sm in proto_obj.sub_menus:
                    sub_menus.append(SubMenuSort(
                        parent_index=n - 1 - sm.parent_index,
                        options=tuple(reversed(sm.options)),
                        targets=tuple(reversed(sm.targets)),
                        menu_actions=tuple(reversed(sm.menu_actions)),
                    ))
                self._post_menu_sort = MenuSort(
                    options=tuple(reversed(proto_obj.options)),
                    targets=tuple(reversed(proto_obj.targets)),
                    menu_actions=tuple(reversed(proto_obj.menu_actions)),
                    sub_menus=tuple(sub_menus),
                )
            else:
                self._post_menu_sort = None
        elif field_name == "collision_update":
            if self._collision_flags is not None and proto_obj.indices:
                indices = np.array(proto_obj.indices, dtype=np.intp)
                flags = np.array(proto_obj.flags, dtype=np.int32)
                self._collision_flags.flat[indices] = flags
        elif field_name == "clickbox_update":
            self._clickbox_update = proto_obj

    def process_event(self, field_name: str, proto_obj: Any) -> None:
        if field_name.endswith("_snapshot") or field_name == "snapshot":
            self._process_snapshot(field_name, proto_obj)
        else:
            self._process_stream_event(field_name, proto_obj)

            if field_name == "item_container_changed":
                self._containers_initialized.add(proto_obj.container_id)
                self.events.emit(InventoryChanged(container_id=proto_obj.container_id))

            if field_name == "game_tick_update":
                self.events.emit(TickEvent(tick=proto_obj.tick))

            if field_name == "chat_changed":
                self.events.emit(
                    ChatMessageReceived(
                        sender=proto_obj.message.sender,
                        message=proto_obj.message.message,
                        type=proto_obj.message.type,
                    )
                )

    # --- Varp / Varc Access ---

    def get_varp(self, varp_id: int) -> int:
        return self._varps.get_varp(varp_id)

    def get_varc(self, varc_id: int) -> Any | None:
        return self._varcs.get_varc(varc_id)

    # --- Skill / Stats Access ---

    def get_skill(self, skill_name: str) -> Skill | None:
        return self._skills.get_skill(skill_name)

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills.skills.copy()

    # --- Item Container Management ---

    def _populate_container_if_needed(self, container_id: int) -> None:
        if container_id in self._containers_initialized:
            return

        container = self._items.get_container(container_id)
        if container and container.items:
            self._containers_initialized.add(container_id)
            return

        from escape._proto.bridge.v1 import bridge_pb2

        request = bridge_pb2.GetItemContainerRequest(container_id=container_id)
        response = self._stub.GetItemContainer(request)

        if response.items:
            size = max(p.slot for p in response.items) + 1
            items: list[Item | None] = [None] * size
            for p in response.items:
                items[p.slot] = Item(id=p.id, name=p.name, quantity=p.quantity, noted=p.noted)
        else:
            items = []

        if container:
            container.items = items
        else:
            from escape._models import ItemContainer

            new_container = ItemContainer(container_id=container_id, slot_count=len(items))
            new_container.items = items
            self._items.add_container(container_id, new_container)

        self._containers_initialized.add(container_id)

    def _copy_container(self, container: ItemContainer) -> ItemContainer:
        copy = ItemContainer(container.container_id)
        copy.items = container.items.copy()
        return copy

    @property
    def inventory(self) -> ItemContainer:
        self._populate_container_if_needed(ItemContainerCache.INVENTORY_ID)
        return self._copy_container(self._items.inventory)

    @property
    def equipment(self) -> ItemContainer:
        self._populate_container_if_needed(ItemContainerCache.EQUIPMENT_ID)
        return self._copy_container(self._items.equipment)

    @property
    def bank(self) -> ItemContainer:
        return self._copy_container(self._items.bank)

    def get_item_container(self, container_id: int) -> ItemContainer | None:
        self._populate_container_if_needed(container_id)
        container = self._items.get_container(container_id)
        if container:
            return self._copy_container(container)
        return None

    # --- Game State Properties ---

    @property
    def game_state(self) -> str | None:
        return self._game_state.game_state

    @property
    def game_state_str(self) -> str | None:
        return self.game_state

    @property
    def tick(self) -> int | None:
        return self._game_state.game_tick.tick if self._game_state.game_tick else None

    @property
    def energy(self) -> int | None:
        return self._game_state.game_tick.energy if self._game_state.game_tick else None

    @property
    def position(self) -> tuple[int, int] | None:
        if self._game_state.game_tick:
            t = self._game_state.game_tick
            return (t.scene_x, t.scene_y)
        return None

    @property
    def target_position(self) -> tuple[int, int] | None:
        if self._game_state.game_tick:
            t = self._game_state.game_tick
            return (t.target_x, t.target_y)
        return None

    @property
    def world_position(self) -> tuple[int, int, int]:
        tick = self._game_state.game_tick
        if tick and self._world_view:
            return (
                self._world_view.base_x + tick.scene_x,
                self._world_view.base_y + tick.scene_y,
                tick.plane,
            )
        return (0, 0, 0)

    @property
    def camera(self) -> CameraState | None:
        return self._game_state.camera

    @property
    def camera_version(self) -> int:
        return self._camera_version

    @property
    def world_entity(self) -> WorldEntityUpdate | None:
        return self._world_entity

    @property
    def world_view(self) -> WorldViewLoad | None:
        return self._world_view

    @property
    def world_view_version(self) -> int:
        return self._world_view_version

    @property
    def collision_flags(self) -> np.ndarray | None:
        return self._collision_flags

    @property
    def instance_template_chunks(self) -> np.ndarray | None:
        return self._instance_template_chunks

    @property
    def is_instance(self) -> bool:
        return self._is_instance

    @property
    def canvas_offset(self) -> tuple[int, int]:
        if self._game_state.game_tick:
            t = self._game_state.game_tick
            return (t.canvas_offset_x, t.canvas_offset_y)
        return (0, 0)

    @property
    def plane(self) -> int | None:
        tick = self._game_state.game_tick
        return tick.plane if tick else None

    # --- Scene Entities ---

    @property
    def npcs(self) -> list[Npc]:
        return self._npcs.get_all_npcs()

    @property
    def ground_items(self) -> list[GroundItem]:
        return self._ground_items.items.copy()

    @property
    def scene_objects(self) -> list[SceneObject]:
        return self._scene_objects.objects.copy()

    # --- Metadata & Interactions ---

    @property
    def menu_open_state(self) -> MenuOpenUpdate | None:
        return self._menu_open

    @property
    def menu_options(self) -> MenuSort | None:
        return self._post_menu_sort

    @property
    def active_interfaces(self) -> list[int]:
        return list(self._active_interfaces.active_interfaces) if self._active_interfaces else []

    @property
    def clickbox_update(self) -> ClickboxUpdate | None:
        return self._clickbox_update

    @property
    def selected_widget(self) -> SelectedWidgetUpdate | None:
        return self._selected_widget

    @property
    def latest_menu_click(self) -> MenuOptionClick | None:
        return self._menu_option_clicks.get_latest_click()

    @property
    def menu_click_fresh(self) -> bool:
        return self._menu_option_clicks.is_fresh()

    def clear_menu_click_fresh(self) -> None:
        self._menu_option_clicks.clear_fresh()

    def consume_menu_click(self) -> None:
        self.clear_menu_click_fresh()

    def get_npc_by_index(self, index: int) -> Npc | None:
        return self._npcs.npcs.get(index)

    def get_actor_animation(self, actor_name: str) -> int:
        return self._animations.get_animation(actor_name)

    @property
    def interacting_npc(self) -> Npc | None:
        tick = self._game_state.game_tick
        if tick and tick.interacting_index >= 0:
            return self.get_npc_by_index(tick.interacting_index)
        return None

    # --- Subscribe-as-you-go ---

    def ensure_npcs_streamed(
        self,
        ids: list[int] | None = None,
        names: list[str] | None = None,
    ) -> None:
        self._npcs.ensure_streamed(ids, names)

    def ensure_objects_streamed(
        self,
        ids: list[int] | None = None,
        names: list[str] | None = None,
    ) -> None:
        self._scene_objects.ensure_streamed(ids, names)

    def ensure_all_npcs_streamed(self) -> None:
        self._npcs.ensure_stream_all()

    def ensure_all_objects_streamed(self) -> None:
        self._scene_objects.ensure_stream_all()

    def ensure_ground_items_enabled(self) -> None:
        self._ground_items.ensure_enabled()

    def clear_entity_subscriptions(self) -> None:
        self._npcs.clear_subscriptions()
        self._scene_objects.clear_subscriptions()
        self._ground_items.clear_subscriptions()
