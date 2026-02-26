from escape.constants import InterfaceID, SpriteID
from escape.gametab import GameTab, GameTabs
from escape.geometry import Box
from escape.widget import Widget, WidgetFields


class Magic(GameTabs):
    TAB_TYPE = GameTab.MAGIC

    def __init__(self):
        super().__init__()

        magic_on_classes = [
            SpriteID.Magicon,
            SpriteID._2XStandardSpellsOn,
            SpriteID.Magicon2,
            SpriteID._2XAncientSpellsOn,
            SpriteID._2XLunarSpellsOn,
            SpriteID.LunarMagicOn,
            SpriteID.MagicNecroOn,
            SpriteID._2XNecroSpellsOn,
        ]

        magic_off_classes = [
            SpriteID.Magicoff,
            SpriteID._2XStandardSpellsOff,
            SpriteID.Magicoff2,
            SpriteID._2XAncientSpellsOff,
            SpriteID._2XLunarSpellsOff,
            SpriteID.LunarMagicOff,
            SpriteID.MagicNecroOff,
            SpriteID._2XNecroSpellsOff,
        ]

        self.on_sprites = {
            v for cls in magic_on_classes for v in vars(cls).values() if isinstance(v, int)
        }
        self.off_sprites = {
            v for cls in magic_off_classes for v in vars(cls).values() if isinstance(v, int)
        }

        self.spells = InterfaceID.MagicSpellbook

        self._allSpellWidgets: list[Widget] = []
        for i in range(
            InterfaceID.MagicSpellbook.SPELLLAYER + 1,
            InterfaceID.MagicSpellbook.INFOLAYER,
        ):
            w = Widget(i)
            w.enable(WidgetFields.get_sprite_id)
            self._allSpellWidgets.append(w)

    def _get_info(self, spell: int) -> dict:
        w = Widget(spell)
        w.enable(WidgetFields.get_bounds)
        w.enable(WidgetFields.is_hidden)
        w.enable(WidgetFields.get_sprite_id)
        return w.get()

    def _get_all_visible_sprites(self) -> list[int]:
        res = Widget.get_batch(self._allSpellWidgets)
        return [w["sprite_id"] for w in res]

    def get_castable_spell_ids(self) -> set[int]:
        vis = self._get_all_visible_sprites()
        return set(vis).intersection(self.on_sprites)

    def _can_cast_spell(self, sprite_id: int) -> bool:
        return sprite_id in self.get_castable_spell_ids()

    def cast_spell(self, spell: int, option: str = "Cast") -> bool:
        if not self.open():
            return False

        w = self._get_info(spell)
        if "sprite_id" not in w:
            return False
        if self._can_cast_spell(w["sprite_id"]) and not w["is_hidden"]:
            bounds = w["bounds"]
            box = Box(bounds["x"], bounds["y"], bounds["width"], bounds["height"])
            return box.interact(option=option)

        return False
