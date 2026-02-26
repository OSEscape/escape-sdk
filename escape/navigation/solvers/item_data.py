"""Mapping from transport display_info names to item teleport click options.

Manually maintained. Keys are the `display_info` strings from TELEPORTATION_ITEM
transports in the graph data. Values are the right-click menu option to use.

The solver tries inventory first, then equipment. The option string is the same
for both containers (e.g. "Edgeville" works on a glory in inventory or equipped).

Tablets always use "Break". Teleport scrolls always use "Teleport".
Jewelry and multi-destination items use the destination name as the option.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ItemTeleportInfo:
    option: str


# -- Tablets (Break) -----------------------------------------------------------

_TABLETS: dict[str, ItemTeleportInfo] = {
    "Annakarl tablet": ItemTeleportInfo("Break"),
    "Ape Atoll tablet": ItemTeleportInfo("Break"),
    "Arceuus Library tablet": ItemTeleportInfo("Break"),
    "Ardougne tablet": ItemTeleportInfo("Break"),
    "Barbarian tablet": ItemTeleportInfo("Break"),
    "Barrows tablet": ItemTeleportInfo("Break"),
    "Battlefront tablet": ItemTeleportInfo("Break"),
    "Brimhaven tablet": ItemTeleportInfo("Break"),
    "Camelot tablet": ItemTeleportInfo("Break"),
    "Carrallanger tablet": ItemTeleportInfo("Break"),
    "Catherby tablet": ItemTeleportInfo("Break"),
    "Cemetery tablet": ItemTeleportInfo("Break"),
    "Dareeyak tablet": ItemTeleportInfo("Break"),
    "Draynor Manor tablet": ItemTeleportInfo("Break"),
    "Falador tablet": ItemTeleportInfo("Break"),
    "Fenkenstrain's Castle tablet": ItemTeleportInfo("Break"),
    "Fishing guild tablet": ItemTeleportInfo("Break"),
    "Ghorrock tablet": ItemTeleportInfo("Break"),
    "Harmony Island tablet": ItemTeleportInfo("Break"),
    "Hosidius tablet": ItemTeleportInfo("Break"),
    "Ice plateau tablet": ItemTeleportInfo("Break"),
    "Kharyrll tablet": ItemTeleportInfo("Break"),
    "Khazard tablet": ItemTeleportInfo("Break"),
    "Lassar tablet": ItemTeleportInfo("Break"),
    "Lumbridge tablet": ItemTeleportInfo("Break"),
    "Mind Altar tablet": ItemTeleportInfo("Break"),
    "Moonclan tablet": ItemTeleportInfo("Break"),
    "Ourania tablet": ItemTeleportInfo("Break"),
    "Paddewwa tablet": ItemTeleportInfo("Break"),
    "Pollnivneach tablet": ItemTeleportInfo("Break"),
    "Prifddinas tablet": ItemTeleportInfo("Break"),
    "Rellekka tablet": ItemTeleportInfo("Break"),
    "Rimmington tablet": ItemTeleportInfo("Break"),
    "Salve Graveyard tablet": ItemTeleportInfo("Break"),
    "Senntisten tablet": ItemTeleportInfo("Break"),
    "Taverley tablet": ItemTeleportInfo("Break"),
    "Teleport to House": ItemTeleportInfo("Break"),
    "Teleport to House tablet": ItemTeleportInfo("Break"),
    "Trollheim tablet": ItemTeleportInfo("Break"),
    "Varrock tablet": ItemTeleportInfo("Break"),
    "Varrock tablet: GE": ItemTeleportInfo("Grand Exchange"),
    "Volcanic Mine tablet": ItemTeleportInfo("Break"),
    "Watchtower tablet": ItemTeleportInfo("Break"),
    "Watchtower tablet: Yanille": ItemTeleportInfo("Yanille"),
    "Waterbirth tablet": ItemTeleportInfo("Break"),
    "West Ardougne tablet": ItemTeleportInfo("Break"),
    "Wilderness Crabs tablet": ItemTeleportInfo("Break"),
    "Yanille tablet": ItemTeleportInfo("Break"),
}

# -- Teleport scrolls (Teleport) -----------------------------------------------

_SCROLLS: dict[str, ItemTeleportInfo] = {
    "Digsite teleport": ItemTeleportInfo("Teleport"),
    "Feldip hills teleport": ItemTeleportInfo("Teleport"),
    "Iorwerth camp teleport": ItemTeleportInfo("Teleport"),
    "Key master teleport": ItemTeleportInfo("Teleport"),
    "Lumberyard teleport": ItemTeleportInfo("Teleport"),
    "Lunar isle teleport": ItemTeleportInfo("Teleport"),
    "Mort'ton teleport": ItemTeleportInfo("Teleport"),
    "Mos le'harmless teleport": ItemTeleportInfo("Teleport"),
    "Nardah teleport": ItemTeleportInfo("Teleport"),
    "Pest control teleport": ItemTeleportInfo("Teleport"),
    "Piscatoris teleport": ItemTeleportInfo("Teleport"),
    "Revenant cave teleport": ItemTeleportInfo("Teleport"),
    "Tai bwo wannai teleport": ItemTeleportInfo("Teleport"),
    "Watson teleport": ItemTeleportInfo("Teleport"),
    "Zul-andra teleport": ItemTeleportInfo("Teleport"),
}

# -- Master scroll book ---------------------------------------------------------
# Right-click option on the book matches the scroll name.

_MASTER_SCROLL_BOOK: dict[str, ItemTeleportInfo] = {
    "Master scroll book: Digsite teleport": ItemTeleportInfo("Digsite Teleport"),
    "Master scroll book: Feldip hills teleport": ItemTeleportInfo("Feldip Hills Teleport"),
    "Master scroll book: Iorwerth camp teleport": ItemTeleportInfo("Iorwerth Camp Teleport"),
    "Master scroll book: Key master teleport": ItemTeleportInfo("Key Master Teleport"),
    "Master scroll book: Lumberyard teleport": ItemTeleportInfo("Lumberyard Teleport"),
    "Master scroll book: Lunar isle teleport": ItemTeleportInfo("Lunar Isle Teleport"),
    "Master scroll book: Mort'ton teleport": ItemTeleportInfo("Mort'ton Teleport"),
    "Master scroll book: Mos le'harmless teleport": ItemTeleportInfo("Mos Le'Harmless Teleport"),
    "Master scroll book: Nardah teleport": ItemTeleportInfo("Nardah Teleport"),
    "Master scroll book: Pest control teleport": ItemTeleportInfo("Pest Control Teleport"),
    "Master scroll book: Piscatoris teleport": ItemTeleportInfo("Piscatoris Teleport"),
    "Master scroll book: Revenant cave teleport": ItemTeleportInfo("Revenant Cave Teleport"),
    "Master scroll book: Tai bwo wannai teleport": ItemTeleportInfo("Tai Bwo Wannai Teleport"),
    "Master scroll book: Watson teleport": ItemTeleportInfo("Watson Teleport"),
    "Master scroll book: Zul-andra teleport": ItemTeleportInfo("Zul-Andra Teleport"),
}

# -- Jewelry (destination name as right-click option) ---------------------------

_JEWELRY: dict[str, ItemTeleportInfo] = {
    # Amulet of glory
    "Amulet of glory: Al Kharid": ItemTeleportInfo("Al Kharid"),
    "Amulet of glory: Draynor Village": ItemTeleportInfo("Draynor Village"),
    "Amulet of glory: Edgeville": ItemTeleportInfo("Edgeville"),
    "Amulet of glory: Karamja": ItemTeleportInfo("Karamja"),
    # Burning amulet
    "Burning amulet: Bandit Camp": ItemTeleportInfo("Bandit Camp"),
    "Burning amulet: Chaos Temple": ItemTeleportInfo("Chaos Temple"),
    "Burning amulet: Lava Maze": ItemTeleportInfo("Lava Maze"),
    # Combat bracelet
    "Combat bracelet: Champions' Guild": ItemTeleportInfo("Champions' Guild"),
    "Combat bracelet: Monastery": ItemTeleportInfo("Monastery"),
    "Combat bracelet: Ranging Guild": ItemTeleportInfo("Ranging Guild"),
    "Combat bracelet: Warriors' Guild": ItemTeleportInfo("Warriors' Guild"),
    # Digsite pendant
    "Digsite pendant: Digsite": ItemTeleportInfo("Digsite"),
    "Digsite pendant: Fossil Island": ItemTeleportInfo("Fossil Island"),
    "Digsite pendant: Lithkren": ItemTeleportInfo("Lithkren"),
    # Games necklace
    "Games necklace: Barbarian Outpost": ItemTeleportInfo("Barbarian Outpost"),
    "Games necklace: Burthorpe": ItemTeleportInfo("Burthorpe"),
    "Games necklace: Corporeal Beast": ItemTeleportInfo("Corporeal Beast"),
    "Games necklace: Tears of Guthix": ItemTeleportInfo("Tears of Guthix"),
    "Games necklace: Wintertodt": ItemTeleportInfo("Wintertodt"),
    # Necklace of passage
    "Necklace of passage: Eagle's Eyrie": ItemTeleportInfo("Eagle's Eyrie"),
    "Necklace of passage: The Outpost": ItemTeleportInfo("The Outpost"),
    "Necklace of passage: Wizards' Tower": ItemTeleportInfo("Wizards' Tower"),
    # Ring of dueling
    "Ring of dueling: Castle Wars": ItemTeleportInfo("Castle Wars"),
    "Ring of dueling: Emir's Arena": ItemTeleportInfo("Emir's Arena"),
    "Ring of dueling: Ferox Enclave": ItemTeleportInfo("Ferox Enclave"),
    "Ring of dueling: Fortis Colosseum": ItemTeleportInfo("Fortis Colosseum"),
    # Ring of shadows
    "Ring of shadows: Ancient Vault": ItemTeleportInfo("Ancient Vault"),
    "Ring of shadows: Ghorrock Dungeon": ItemTeleportInfo("Ghorrock Dungeon"),
    "Ring of shadows: Lassar Undercity": ItemTeleportInfo("Lassar Undercity"),
    "Ring of shadows: The Scar": ItemTeleportInfo("The Scar"),
    "Ring of shadows: The Stranglewood": ItemTeleportInfo("The Stranglewood"),
    # Ring of the elements
    "Ring of the elements: Air": ItemTeleportInfo("Air Altar"),
    "Ring of the elements: Earth": ItemTeleportInfo("Earth Altar"),
    "Ring of the elements: Fire": ItemTeleportInfo("Fire Altar"),
    "Ring of the elements: Water": ItemTeleportInfo("Water Altar"),
    # Ring of wealth
    "Ring of wealth: Dondakan": ItemTeleportInfo("Dondakan"),
    "Ring of wealth: Falador Park": ItemTeleportInfo("Falador Park"),
    "Ring of wealth: Grand Exchange": ItemTeleportInfo("Grand Exchange"),
    "Ring of wealth: Miscellania": ItemTeleportInfo("Miscellania"),
    # Skills necklace
    "Skills necklace: Cooks' Guild": ItemTeleportInfo("Cooking Guild"),
    "Skills necklace: Crafting Guild": ItemTeleportInfo("Crafting Guild"),
    "Skills necklace: Farming Guild": ItemTeleportInfo("Farming Guild"),
    "Skills necklace: Fishing Guild": ItemTeleportInfo("Fishing Guild"),
    "Skills necklace: Mining Guild": ItemTeleportInfo("Mining Guild"),
    "Skills necklace: Woodcutting Guild": ItemTeleportInfo("Woodcutting Guild"),
    # Slayer ring
    "Slayer ring: Dark Beasts": ItemTeleportInfo("Dark Beasts"),
    "Slayer ring: Fremennik": ItemTeleportInfo("Fremennik Dungeon"),
    "Slayer ring: Slayer Tower": ItemTeleportInfo("Slayer Tower"),
    "Slayer ring: Stronghold": ItemTeleportInfo("Stronghold"),
    "Slayer ring: Tarn's Lair": ItemTeleportInfo("Tarn's Lair"),
}

# -- Multi-destination items ----------------------------------------------------

_MULTI_DEST: dict[str, ItemTeleportInfo] = {
    # Camulet
    "Camulet: Bandit Camp Quarry": ItemTeleportInfo("Enakhra's Temple Entrance"),
    "Camulet: Enakhra's Temple": ItemTeleportInfo("Enakhra's Temple"),
    # Drakan's medallion
    "Drakan's medallion: Darkmeyer": ItemTeleportInfo("Darkmeyer"),
    "Drakan's medallion: Slepe": ItemTeleportInfo("Slepe"),
    "Drakan's medallion: Ver Sinhaza": ItemTeleportInfo("Ver Sinhaza"),
    # Enchanted lyre
    "Enchanted lyre: Jatizso": ItemTeleportInfo("Jatiszo"),
    "Enchanted lyre: Neitiznot": ItemTeleportInfo("Neitiznot"),
    "Enchanted lyre: Rellekka": ItemTeleportInfo("Rellekka"),
    "Enchanted lyre: Waterbirth Island": ItemTeleportInfo("Waterbirth Island"),
    "Enchanted lyre (i): Jatizso": ItemTeleportInfo("Jatiszo"),
    "Enchanted lyre (i): Neitiznot": ItemTeleportInfo("Neitiznot"),
    "Enchanted lyre (i): Rellekka": ItemTeleportInfo("Rellekka"),
    "Enchanted lyre (i): Waterbirth Island": ItemTeleportInfo("Waterbirth Island"),
    # Teleport crystal / Eternal
    "Teleport crystal: Lletya": ItemTeleportInfo("Lletya"),
    "Teleport crystal: Prifddinas": ItemTeleportInfo("Prifddinas"),
    "Eternal teleport crystal: Lletya": ItemTeleportInfo("Lletya"),
    "Eternal teleport crystal: Prifddinas": ItemTeleportInfo("Prifddinas"),
    # Giantsoul amulet
    "Giantsoul amulet: 1. Bryophyta": ItemTeleportInfo("Bryophyta"),
    "Giantsoul amulet: 2. Obor": ItemTeleportInfo("Obor"),
    "Giantsoul amulet: 3. Branda and Eldric": ItemTeleportInfo("Branda and Eldric"),
    # Kharedst's memoirs
    "Kharedst's memoirs: A Dark Disposition": ItemTeleportInfo("A Dark Disposition"),
    "Kharedst's memoirs: History and Hearsay": ItemTeleportInfo("History and Hearsay"),
    "Kharedst's memoirs: Jewelry of Jubilation": ItemTeleportInfo("Jewelry of Jubilation"),
    "Kharedst's memoirs: Lunch by the Lancalliums": ItemTeleportInfo("Lunch by the Lancalliums"),
    "Kharedst's memoirs: The Fisher's Flute": ItemTeleportInfo("The Fisher's Flute"),
    # Pendant of ates
    "Pendant of ates: 1. The Darkfrost": ItemTeleportInfo("Darkfrost"),
    "Pendant of ates: 2. Twilight Temple": ItemTeleportInfo("Twilight Temple"),
    "Pendant of ates: 3. Ralos' Rise": ItemTeleportInfo("Ralos' Rise"),
    "Pendant of ates: 4. North Aldarin": ItemTeleportInfo("North Aldarin"),
    # Pharaoh's sceptre
    "Pharaoh's sceptre: Jaldraocht": ItemTeleportInfo("Jaldraocht"),
    "Pharaoh's sceptre: Jaleustrophos": ItemTeleportInfo("Jaleustrophos"),
    "Pharaoh's sceptre: Jalsavrah": ItemTeleportInfo("Jalsavrah"),
    "Pharaoh's sceptre: Jaltevas": ItemTeleportInfo("Jaltevas"),
    # Sailors' amulet
    "Sailors' amulet: Deepfin Point": ItemTeleportInfo("Deepfin Point"),
    "Sailors' amulet: Port Roberts": ItemTeleportInfo("Port Roberts"),
    "Sailors' amulet: The Pandemonium": ItemTeleportInfo("The Pandemonium"),
    # Xeric's talisman
    "Xeric's talisman: 1. Xeric's Lookout": ItemTeleportInfo("Xeric's Lookout"),
    "Xeric's talisman: 2. Xeric's Glade": ItemTeleportInfo("Xeric's Glade"),
    "Xeric's talisman: 3. Xeric's Inferno": ItemTeleportInfo("Xeric's Inferno"),
    "Xeric's talisman: 4. Xeric's Heart": ItemTeleportInfo("Xeric's Heart"),
    "Xeric's talisman: 5. Xeric's Honour": ItemTeleportInfo("Xeric's Honour"),
}

# -- Special items (unique options) ---------------------------------------------

_SPECIAL: dict[str, ItemTeleportInfo] = {
    "Amulet of the eye": ItemTeleportInfo("Teleport"),
    "Chronicle": ItemTeleportInfo("Teleport"),
    "Ectophial": ItemTeleportInfo("Empty"),
    "Grand seed pod": ItemTeleportInfo("Commune"),
    "Hallowed crystal shard": ItemTeleportInfo("Teleport"),
    "Icy basalt": ItemTeleportInfo("Teleport"),
    "Quetzal whistle": ItemTeleportInfo("Whistle"),
    "Royal seed pod": ItemTeleportInfo("Commune"),
    "Skull sceptre": ItemTeleportInfo("Invoke"),
    "Stony basalt": ItemTeleportInfo("Troll Stronghold entrance"),
    "Stony basalt: Roof": ItemTeleportInfo("Troll Stronghold roof"),
}

# -- Diary items ----------------------------------------------------------------

_DIARY: dict[str, ItemTeleportInfo] = {
    # Ardougne cloak
    "Ardougne cloak: Kandarin Monastery": ItemTeleportInfo("Kandarin Monastery"),
    "Ardougne cloak: Ardougne Farm": ItemTeleportInfo("Ardougne Farm"),
    # Desert amulet
    "Desert amulet 3: Teleport": ItemTeleportInfo("Teleport"),
    "Desert amulet 4: Nardah": ItemTeleportInfo("Nardah"),
    "Desert amulet 4: Kalphite cave": ItemTeleportInfo("Kalphite cave"),
    # Explorer's ring
    "Explorer's ring: Teleport": ItemTeleportInfo("Teleport"),
    "Explorer's ring 2: Teleport": ItemTeleportInfo("Teleport"),
    # Fremennik sea boots
    "Fremennik sea boots: Teleport": ItemTeleportInfo("Teleport"),
    # Kandarin headgear
    "Kandarin headgear 3: Teleport": ItemTeleportInfo("Teleport"),
    "Kandarin headgear 4: Teleport": ItemTeleportInfo("Teleport"),
    # Karamja gloves
    "Karamja gloves: Gem Mine": ItemTeleportInfo("Gem Mine"),
    "Karamja gloves 4: Slayer Master": ItemTeleportInfo("Slayer Master"),
    # Morytania legs
    "Morytania legs: Burgh de Rott": ItemTeleportInfo("Burgh de Rott"),
    "Morytania legs: Slime Pit": ItemTeleportInfo("Slime Pit"),
    # Rada's blessing
    "Rada's blessing: Kourend Woodland": ItemTeleportInfo("Kourend Woodland"),
    "Rada's blessing: Mount Karuulm": ItemTeleportInfo("Mount Karuulm"),
    # Western banner
    "Western banner 3: Teleport": ItemTeleportInfo("Teleport"),
    "Western banner 4: Teleport": ItemTeleportInfo("Teleport"),
    # Wilderness sword
    "Wilderness sword 3: Teleport": ItemTeleportInfo("Teleport"),
    "Wilderness sword 4: Teleport": ItemTeleportInfo("Teleport"),
}

# -- Capes ----------------------------------------------------------------------

_CAPES: dict[str, ItemTeleportInfo] = {
    # Achievement diary cape — numbered NPC destinations
    "Achievement diary cape: 1. Two-pints": ItemTeleportInfo("1. Two-pints"),
    "Achievement diary cape: 2. Jarr": ItemTeleportInfo("2. Jarr"),
    "Achievement diary cape: 3. Sir Rebral": ItemTeleportInfo("3. Sir Rebral"),
    "Achievement diary cape: 4. Thorodin": ItemTeleportInfo("4. Thorodin"),
    "Achievement diary cape: 5. Flax keeper": ItemTeleportInfo("5. Flax keeper"),
    "Achievement diary cape: 6. Pirate Jackie the Fruit": ItemTeleportInfo("6. Pirate Jackie the Fruit"),
    "Achievement diary cape: 7. Kaleb Paramaya": ItemTeleportInfo("7. Kaleb Paramaya"),
    "Achievement diary cape: 8. Jungle forester": ItemTeleportInfo("8. Jungle forester"),
    "Achievement diary cape: 9. TzHaar-Mej": ItemTeleportInfo("9. TzHaar-Mej"),
    "Achievement diary cape: A. Elise": ItemTeleportInfo("A. Elise"),
    "Achievement diary cape: B. Hatius Cosaintus": ItemTeleportInfo("B. Hatius Cosaintus"),
    "Achievement diary cape: C. Le-sabrè": ItemTeleportInfo("C. Le-sabrè"),
    "Achievement diary cape: D. Toby": ItemTeleportInfo("D. Toby"),
    "Achievement diary cape: E. Lesser Fanatic": ItemTeleportInfo("E. Lesser Fanatic"),
    "Achievement diary cape: F. Elder Gnome child": ItemTeleportInfo("F. Elder Gnome child"),
    "Achievement diary cape: G. Twiggy O'Korn": ItemTeleportInfo("G. Twiggy O'Korn"),
    # Construction cape
    "Construction cape: Brimhaven": ItemTeleportInfo("Brimhaven"),
    "Construction cape: Home": ItemTeleportInfo("Tele to POH"),
    "Construction cape: Hosidius": ItemTeleportInfo("Hosidius"),
    "Construction cape: Pollnivneach": ItemTeleportInfo("Pollnivneach"),
    "Construction cape: Prifddinas": ItemTeleportInfo("Prifddinas"),
    "Construction cape: Rellekka": ItemTeleportInfo("Rellekka"),
    "Construction cape: Rimmington": ItemTeleportInfo("Rimmington"),
    "Construction cape: Taverley": ItemTeleportInfo("Taverley"),
    "Construction cape: Tele to POH": ItemTeleportInfo("Tele to POH"),
    "Construction cape: Yanille": ItemTeleportInfo("Yanille"),
    # Other capes
    "Crafting cape: Teleport": ItemTeleportInfo("Teleport"),
    "Farming cape: Teleport": ItemTeleportInfo("Teleport"),
    "Fishing cape: Fishing Guild": ItemTeleportInfo("Fishing Guild"),
    "Fishing cape: Otto's Grotto": ItemTeleportInfo("Otto's Grotto"),
    "Hunter cape: Black chinchompa": ItemTeleportInfo("Teleport"),
    "Hunter cape: Feldip Hills": ItemTeleportInfo("Teleport"),
    "Hunter cape: Hunter Guild": ItemTeleportInfo("Teleport"),
    "Music cape: Teleport": ItemTeleportInfo("Teleport"),
    "Mythical cape": ItemTeleportInfo("Teleport"),
    "Quest point cape: Teleport": ItemTeleportInfo("Teleport"),
    "Strength cape: Teleport": ItemTeleportInfo("Teleport"),
    # Max cape
    "Max cape: Crafting Guild": ItemTeleportInfo("Crafting Guild"),
    "Max cape: Fishing Teleports: Fishing Guild": ItemTeleportInfo("Fishing Guild"),
    "Max cape: Fishing Teleports: Otto's Grotto": ItemTeleportInfo("Otto's Grotto"),
    "Max cape: Other Teleports: Black chinchompa": ItemTeleportInfo("Black chinchompa"),
    "Max cape: Other Teleports: Farming Guild": ItemTeleportInfo("Farming Guild"),
    "Max cape: Other Teleports: Feldip Hills": ItemTeleportInfo("Feldip Hills"),
    "Max cape: Other Teleports: Hunter Guild": ItemTeleportInfo("Hunter Guild"),
    "Max cape: Other Teleports: The Pandemonium": ItemTeleportInfo("The Pandemonium"),
    "Max cape: POH Portals: Brimhaven": ItemTeleportInfo("Brimhaven"),
    "Max cape: POH Portals: Hosidius": ItemTeleportInfo("Hosidius"),
    "Max cape: POH Portals: Pollnivneach": ItemTeleportInfo("Pollnivneach"),
    "Max cape: POH Portals: Prifddinas": ItemTeleportInfo("Prifddinas"),
    "Max cape: POH Portals: Rellekka": ItemTeleportInfo("Rellekka"),
    "Max cape: POH Portals: Rimmington": ItemTeleportInfo("Rimmington"),
    "Max cape: POH Portals: Taverley": ItemTeleportInfo("Taverley"),
    "Max cape: POH Portals: Yanille": ItemTeleportInfo("Yanille"),
    "Max cape: Tele to POH": ItemTeleportInfo("Tele to POH"),
    "Max cape: Warriors' Guild": ItemTeleportInfo("Warriors' Guild"),
}

# -- Combined lookup ------------------------------------------------------------

_BY_NAME: dict[str, ItemTeleportInfo] = {
    **_TABLETS,
    **_SCROLLS,
    **_MASTER_SCROLL_BOOK,
    **_JEWELRY,
    **_MULTI_DEST,
    **_SPECIAL,
    **_DIARY,
    **_CAPES,
}


def lookup_item_teleport(display_info: str) -> ItemTeleportInfo | None:
    """Look up item teleport info by transport display_info string."""
    return _BY_NAME.get(display_info)
