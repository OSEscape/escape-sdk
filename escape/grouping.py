import escape.timing as timing
from escape.constants import InterfaceID
from escape.gametab import GameTab, GameTabs
from escape.widget import WidgetFields, WidgetPanel


class Grouping(GameTabs):
    TAB_TYPE = GameTab.GROUPING

    def __init__(self):
        super().__init__()
        self.sub_tabs = WidgetPanel(
            InterfaceID.SIDE_CHANNELS,
            [
                InterfaceID.SideChannels.TAB_0,
                InterfaceID.SideChannels.TAB_1,
                InterfaceID.SideChannels.TAB_2,
                InterfaceID.SideChannels.TAB_3,
            ],
            get_children=False,
            use_actions=True,
        )

        for w in self.sub_tabs.buttons:
            w.enable(WidgetFields.get_on_op_listener)

        self.sub_tab_names = ["Chat-channel", "Your Clan", "View another clan", "Grouping"]

        self.dropdown_button = WidgetPanel(
            InterfaceID.GROUPING,
            [InterfaceID.Grouping.CURRENTGAME],
            get_children=False,
        )

        self.dropdown_selector = WidgetPanel(
            InterfaceID.GROUPING,
            [InterfaceID.Grouping.DROPDOWN_CONTENTS],
            get_children=True,
            menu_text="Select",
            scrollbox=InterfaceID.Grouping.DROPDOWN_CONTENTS,
        )

        self.teleport_button = WidgetPanel(
            InterfaceID.GROUPING,
            [InterfaceID.Grouping.TELEPORT_TEXT1],
            get_children=False,
            menu_text="Teleport",
        )

    def get_open_sub_tab(self) -> str | None:
        if not self.open():
            return None

        info = self.sub_tabs.get_widget_info()

        for i, w in enumerate(info):
            if len(w.get("on_op_listener", [])) == 3:
                return self.sub_tab_names[i]
        return None

    def open_sub_tab(self, sub_tab: str) -> bool:
        if not self.is_open():
            self.open()

        for name in self.sub_tab_names:
            if sub_tab.lower() in name.lower():
                if self.get_open_sub_tab() == name:
                    return True
                elif self.sub_tabs.interact(sub_tab):

                    def _tab_matches(n=name):
                        return self.get_open_sub_tab() == n

                    return timing.wait_until(_tab_matches, timeout=3.0)
        return False

    def get_selected_game(self) -> str | None:
        if not self.open() or not self.open_sub_tab("Grouping"):
            return None

        info = self.dropdown_button.get_widget_info()
        if not info:
            return None
        text = info[0].get("text", "")
        return text if text else None

    def is_game_selected(self, game_name: str) -> bool:
        selected_game = self.get_selected_game()
        return selected_game is not None and game_name.lower() in selected_game.lower()

    def dropdown_fully_loaded(self) -> bool:
        info = self.dropdown_selector.get_widget_info()
        return len(info) > 0 and info[-1].get("bounds")[0] >= 0

    def select_game(self, game_name: str) -> bool:
        if not self.open() or not self.open_sub_tab("Group"):
            return False

        current_game = self.get_selected_game()
        if current_game and game_name.lower() in current_game.lower():
            return True

        if len(self.dropdown_selector.get_widget_info()) == 0 and (
            not self.dropdown_button.interact("")
            or not timing.wait_until(self.dropdown_fully_loaded, timeout=3.0)
        ):
            return False
        if self.dropdown_selector.interact(game_name):
            return timing.wait_until(lambda: self.is_game_selected(game_name), timeout=3.0)

        return False

    def click_teleport(self) -> bool:
        if not self.open() or not self.open_sub_tab("Group"):
            return False

        return bool(self.teleport_button.interact("Teleport"))

    def teleport_to_minigame(self, game_name: str) -> bool:
        if not self.select_game(game_name):
            return False

        return self.click_teleport()
