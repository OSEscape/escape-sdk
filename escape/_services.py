"""Singleton service locator for core infrastructure objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape._cache.processed_cache import ProcessedCache
    from escape._proto.bridge.v1.bridge_pb2_grpc import BridgeServiceStub
    from escape._tracking import ClickboxTracker
    from escape.drawing import Drawing
    from escape.input import Keyboard, Mouse, RuneLite
    from escape.menu import Menu


class Services:
    _instance: Services | None = None

    __slots__ = ("cache", "drawing", "keyboard", "menu", "mouse", "runelite", "stub", "tracker")

    def __init__(
        self,
        *,
        stub: BridgeServiceStub,
        cache: ProcessedCache,
        mouse: Mouse,
        keyboard: Keyboard,
        menu: Menu,
        tracker: ClickboxTracker,
        drawing: Drawing,
        runelite: RuneLite,
    ) -> None:
        self.stub = stub
        self.cache = cache
        self.mouse = mouse
        self.keyboard = keyboard
        self.menu = menu
        self.tracker = tracker
        self.drawing = drawing
        self.runelite = runelite

    @classmethod
    def init(
        cls,
        *,
        stub: BridgeServiceStub,
        cache: ProcessedCache,
        mouse: Mouse,
        keyboard: Keyboard,
        menu: Menu,
        tracker: ClickboxTracker,
        drawing: Drawing,
        runelite: RuneLite,
    ) -> Services:
        cls._instance = cls(
            stub=stub,
            cache=cache,
            mouse=mouse,
            keyboard=keyboard,
            menu=menu,
            tracker=tracker,
            drawing=drawing,
            runelite=runelite,
        )
        return cls._instance

    @classmethod
    def get(cls) -> Services:
        if cls._instance is None:
            raise RuntimeError("Services not initialized — call Client.connect() first")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
