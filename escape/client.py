"""Main Client class for the Escape SDK."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from escape._cache_manager import ensure_resources_loaded
from escape._logger import logger

# Initialize game resources (Varp/Varbit/Object definitions) on library load.
if not ensure_resources_loaded():
    logger.warning("Core game resources failed to load; SDK may be partially functional.")

if TYPE_CHECKING:
    from escape._cache.processed_cache import ProcessedCache
    from escape._tracking import ClickboxTracker
    from escape.bank import Bank
    from escape.camera import Camera
    from escape.dialog import Dialog
    from escape.drawing import Drawing
    from escape.equipment import Equipment
    from escape.events import EventBus
    from escape.fairy_ring import FairyRingInterface
    from escape.gametab import GameTab, GameTabs
    from escape.grouping import Grouping
    from escape.input import Keyboard, Mouse, RuneLite
    from escape.interfaces import Interfaces
    from escape.inventory import Inventory
    from escape.magic import Magic
    from escape.menu import Menu
    from escape.npcs import Npcs
    from escape.objects import Objects
    from escape.pathfinder import Pathfinder
    from escape.player import Player
    from escape.prayer import Prayer
    from escape.projection import Projection
    from escape.scene import Scene
    from escape.shop import Shop
    from escape.skills import Skills
    from escape.tile_items import TileItems
    from escape.walker import Walker


class Client:
    _instance: Client | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._connected = False

    def connect(self, wait_for_warmup: bool = True):
        if self._connected:
            return

        logger.info("Connecting to Bridge via Unix socket...")

        from escape._cache.consumer import EventConsumer
        from escape._cache.processed_cache import ProcessedCache
        from escape._services import Services
        from escape._tracking import ClickboxTracker
        from escape._transport import Transport
        from escape.drawing import Drawing
        from escape.input import Keyboard, Mouse, RuneLite
        from escape.menu import Menu
        from escape.widget import Widget

        self._stub = Transport().stub
        self._event_consumer = EventConsumer()
        self._event_cache = ProcessedCache(self._stub)
        self._event_consumer.start(self._event_cache, wait_for_warmup=wait_for_warmup)

        Widget._stub = self._stub

        runelite = RuneLite()
        mouse = Mouse(runelite, self._event_cache)
        keyboard = Keyboard(runelite)
        drawing = Drawing(self._stub)
        menu = Menu(self._event_cache, mouse)
        tracker = ClickboxTracker(self._stub, self._event_cache, menu, mouse)

        self._services = Services.init(
            stub=self._stub,
            cache=self._event_cache,
            mouse=mouse,
            keyboard=keyboard,
            menu=menu,
            tracker=tracker,
            drawing=drawing,
            runelite=runelite,
        )

        self._connected = True
        logger.success("Client connection established; services ready.")

    def disconnect(self):
        if not self._connected:
            return

        from escape._services import Services

        logger.info("Closing Bridge connection...")
        self._services.mouse.stop()
        self._event_consumer.stop()
        Services.reset()
        self._connected = False
        logger.info("Client disconnected.")

    # --- Core Services ---

    @property
    def stub(self):
        if not self._connected:
            raise RuntimeError("Client not connected - call connect() first")
        return self._stub

    @property
    def cache(self) -> ProcessedCache:
        if not self._connected:
            raise RuntimeError("Client not connected - call connect() first")
        return self._event_cache

    @property
    def mouse(self) -> Mouse:
        if not self._connected:
            raise RuntimeError("Client not connected")
        return self._services.mouse

    @property
    def keyboard(self) -> Keyboard:
        if not self._connected:
            raise RuntimeError("Client not connected")
        return self._services.keyboard

    @property
    def menu(self) -> Menu:
        if not self._connected:
            raise RuntimeError("Client not connected")
        return self._services.menu

    @property
    def drawing(self) -> Drawing:
        if not self._connected:
            raise RuntimeError("Client not connected")
        return self._services.drawing

    @property
    def tracker(self) -> ClickboxTracker:
        if not self._connected:
            raise RuntimeError("Client not connected")
        return self._services.tracker

    @property
    def runelite(self) -> RuneLite:
        if not self._connected:
            raise RuntimeError("Client not connected")
        return self._services.runelite

    @property
    def events(self) -> EventBus:
        if not self._connected:
            raise RuntimeError("Client not connected - call connect() first")
        return self._event_cache.events

    @property
    def tick(self) -> int | None:
        if not self._connected:
            raise RuntimeError("Client not connected - call connect() first")
        return self._event_cache.tick

    def wait_ticks(self, ticks: int, timeout: float | None = None):
        if not self._connected:
            raise RuntimeError("Client not connected - call connect() first")
        from escape.timing import wait_ticks

        wait_ticks(ticks, timeout)

    def get_varbit(self, varbit_id: int) -> int | None:
        if not self._connected:
            raise RuntimeError("Client not connected - call connect() first")
        from escape._resources import varps

        return varps.get_varbit(varbit_id)

    # --- Domain Modules ---

    @cached_property
    def camera(self) -> Camera:
        from escape.camera import Camera

        return Camera()

    @cached_property
    def projection(self) -> Projection:
        from escape.projection import Projection

        return Projection()

    @cached_property
    def skills(self) -> Skills:
        from escape.skills import Skills

        return Skills()

    @cached_property
    def npcs(self) -> Npcs:
        from escape.npcs import Npcs

        return Npcs()

    @cached_property
    def objects(self) -> Objects:
        from escape.objects import Objects

        return Objects()

    @cached_property
    def tile_items(self) -> TileItems:
        from escape.tile_items import TileItems

        return TileItems()

    @cached_property
    def player(self) -> Player:
        from escape.player import Player

        return Player(self.skills)

    @cached_property
    def scene(self) -> Scene:
        from escape.scene import Scene

        return Scene(self.projection)

    @cached_property
    def pathfinder(self) -> Pathfinder:
        from escape.pathfinder import Pathfinder

        return Pathfinder()

    @cached_property
    def walker(self) -> Walker:
        from escape.navigation.registry import default_registry
        from escape.walker import Walker

        return Walker(self.scene, self.pathfinder, default_registry())

    # --- Game Tabs ---

    @cached_property
    def inventory(self) -> Inventory:
        from escape.inventory import Inventory

        return Inventory()

    @cached_property
    def equipment(self) -> Equipment:
        from escape.equipment import Equipment

        return Equipment()

    @cached_property
    def prayer(self) -> Prayer:
        from escape.prayer import Prayer

        return Prayer(self.skills)

    @cached_property
    def magic(self) -> Magic:
        from escape.magic import Magic

        return Magic()

    @cached_property
    def grouping(self) -> Grouping:
        from escape.grouping import Grouping

        return Grouping()

    @cached_property
    def combat(self) -> GameTabs:
        from escape.gametab import GameTab, GameTabs

        return GameTabs(GameTab.COMBAT)

    @cached_property
    def account(self) -> GameTabs:
        from escape.gametab import GameTab, GameTabs

        return GameTabs(GameTab.ACCOUNT)

    @cached_property
    def emotes(self) -> GameTabs:
        from escape.gametab import GameTab, GameTabs

        return GameTabs(GameTab.EMOTES)

    @cached_property
    def friends(self) -> GameTabs:
        from escape.gametab import GameTab, GameTabs

        return GameTabs(GameTab.FRIENDS)

    @cached_property
    def logout(self) -> GameTabs:
        from escape.gametab import GameTab, GameTabs

        return GameTabs(GameTab.LOGOUT)

    @cached_property
    def music(self) -> GameTabs:
        from escape.gametab import GameTab, GameTabs

        return GameTabs(GameTab.MUSIC)

    @cached_property
    def progress(self) -> GameTabs:
        from escape.gametab import GameTab, GameTabs

        return GameTabs(GameTab.PROGRESS)

    @cached_property
    def settings(self) -> GameTabs:
        from escape.gametab import GameTab, GameTabs

        return GameTabs(GameTab.SETTINGS)

    def get_open_tab(self) -> GameTab | None:
        from escape.constants import VarClientID
        from escape.gametab import GameTab

        index = self.cache.get_varc(VarClientID.TOPLEVEL_PANEL)
        return GameTab(index) if index in GameTab._value2member_map_ else None

    # --- Interaction ---

    def interact(
        self,
        *,
        option: str | None = None,
        action: str | None = None,
        wait: bool = False,
    ) -> bool:
        """Interact with whatever is under the cursor."""
        from escape.interaction import interact

        return interact(option=option, action=action, wait=wait)

    # --- High-Level Interfaces ---

    @cached_property
    def interfaces(self) -> Interfaces:
        from escape.interfaces import Interfaces

        return Interfaces()

    @cached_property
    def dialog(self) -> Dialog:
        from escape.dialog import Dialog

        return Dialog()

    @cached_property
    def shop(self) -> Shop:
        from escape.shop import Shop

        return Shop()

    @cached_property
    def bank(self) -> Bank:
        from escape.bank import Bank

        return Bank()

    @cached_property
    def fairy_ring(self) -> FairyRingInterface:
        from escape.fairy_ring import FairyRingInterface

        return FairyRingInterface()

    def login(self, timeout: float = 30.0) -> bool:
        """Navigate login screens, enter credentials, and dismiss welcome screen."""
        from escape.login import login

        return login(timeout=timeout)
