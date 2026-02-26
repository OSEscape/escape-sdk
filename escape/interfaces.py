"""Overlay windows - bank, GE, shop, dialogue, etc."""

from escape.constants import InterfaceID  # pyright: ignore[reportMissingImports]
from escape.widget import Widget, WidgetPanel

# Lazy-loaded reverse lookup: group_id -> name
_interface_id_to_name: dict[int, str] | None = None


def _get_interface_id_to_name_map() -> dict[int, str]:
    """Build and cache a reverse lookup map from interface group ID to name."""
    global _interface_id_to_name

    if _interface_id_to_name is not None:
        return _interface_id_to_name

    _interface_id_to_name = {}

    try:
        from escape.constants import InterfaceID  # pyright: ignore[reportMissingImports]

        for name in dir(InterfaceID):
            if name.startswith("_") and not name.startswith("__"):
                value = getattr(InterfaceID, name)
                if isinstance(value, int):
                    _interface_id_to_name[value] = name[1:]
            elif not name.startswith("_") and name.isupper():
                value = getattr(InterfaceID, name)
                if isinstance(value, int):
                    _interface_id_to_name[value] = name
    except ImportError:
        pass

    return _interface_id_to_name


def get_interface_name(group_id: int) -> str | None:
    """Get the interface name for a group ID."""
    return _get_interface_id_to_name_map().get(group_id)


class ScrollInterface(WidgetPanel):
    """Interface for scroll-type overlays."""

    def __init__(self):
        super().__init__(
            InterfaceID.MENU,
            [InterfaceID.Menu.LJ_LAYER1],
            get_children=False,
            menu_text="Continue",
            scrollbox=InterfaceID.Menu.LJ_LAYER1,
        )


class GliderInterface(WidgetPanel):
    """Interface for the gnome glider map."""

    def __init__(self):
        super().__init__(
            InterfaceID.GLIDERMAP,
            [
                InterfaceID.Glidermap.GRANDTREE_BUTTON,
                InterfaceID.Glidermap.WHITEWOLFMOUNTAIN_BUTTON,
                InterfaceID.Glidermap.VARROCK_BUTTON,
                InterfaceID.Glidermap.ALKHARID_BUTTON,
                InterfaceID.Glidermap.KARAMJA_BUTTON,
                InterfaceID.Glidermap.OGREAREA_BUTTON,
                InterfaceID.Glidermap.APEATOLL_BUTTON,
            ],
            get_children=False,
        )

        self.names = [
            "Ta Quir Priw",
            "Sindarpos",
            "Lemanto Andra",
            "Kar-Hewo",
            "Gandius",
            "Lemantolly Undri",
            "Ookookolly Undri",
        ]

    def get_widget_info(self) -> list[dict]:
        res = Widget.get_batch(self.buttons)

        for i in range(len(res)):
            res[i]["text"] = self.names[i]
        return res

    def is_right_option(self, widget_info, option_text=""):
        b = widget_info.get("bounds", "")
        text = widget_info.get("text", "")
        if option_text:
            return option_text in text and isinstance(b, dict) and b.get("x", -1) >= 0


class Interfaces:
    """Overlay interfaces: bank, fairy ring, spirit tree, etc."""

    def __init__(self):
        from escape._services import Services

        s = Services.get()
        self._cache = s.cache
        self.spirit_tree = ScrollInterface()
        self.mushtree = WidgetPanel(
            InterfaceID.FOSSIL_MUSHTREES,
            [
                InterfaceID.FossilMushtrees.TREE1,
                InterfaceID.FossilMushtrees.TREE2,
                InterfaceID.FossilMushtrees.TREE3,
                InterfaceID.FossilMushtrees.TREE4,
            ],
            get_children=False,
            wrong_text="Not yet",
            menu_text="Continue",
        )
        self.zeah_minecart = ScrollInterface()
        self.jewellery_box = WidgetPanel(
            InterfaceID.POH_JEWELLERY_BOX,
            [
                InterfaceID.PohJewelleryBox.DUELING,
                InterfaceID.PohJewelleryBox.GAMING,
                InterfaceID.PohJewelleryBox.COMBAT,
                InterfaceID.PohJewelleryBox.SKILLS,
                InterfaceID.PohJewelleryBox.WEALTH,
                InterfaceID.PohJewelleryBox.GLORY,
            ],
            get_children=True,
            wrong_text="</str>",
        )
        self.gnome_glider = GliderInterface()
        self.charter_ship = WidgetPanel(
            InterfaceID.CHARTERING_MENU_SIDE,
            [InterfaceID.CharteringMenuSide.LIST_CONTENT],
            get_children=True,
            scrollbox=InterfaceID.CharteringMenuSide.LIST_CONTENT,
        )
        self.quetzal = WidgetPanel(
            InterfaceID.QUETZAL_MENU,
            [InterfaceID.QuetzalMenu.ICONS],
            get_children=True,
            use_actions=True,
        )

    def get_open_interfaces(self) -> list[int]:
        """Return the group IDs of all currently open interfaces."""
        return self._cache.active_interfaces

    def get_open_interface_names(self) -> list[str]:
        """Get a list of currently open interface names."""
        names = []
        for group_id in self.get_open_interfaces():
            name = get_interface_name(group_id)
            if name:
                names.append(name)
            else:
                names.append(f"UNKNOWN_{group_id}")
        return names


__all__ = ["Interfaces", "get_interface_name"]
