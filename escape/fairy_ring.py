import escape.timing as timing
from escape._logger import logger
from escape._resources import varps
from escape._services import Services
from escape.constants import InterfaceID, VarPlayerID
from escape.geometry import Box
from escape.widget import Widget, WidgetFields

_DIAL_LETTERS = ("ADCB", "ILKJ", "PSRQ")


class FairyRingInterface:
    def __init__(self):
        self.group = InterfaceID.FAIRYRINGS
        self.abcd_button = Widget(InterfaceID.Fairyrings.ROOT_MODEL3).enable(
            WidgetFields.get_rotation_y
        )
        self.ijlk_button = Widget(InterfaceID.Fairyrings.ROOT_MODEL4).enable(
            WidgetFields.get_rotation_y
        )
        self.pqrs_button = Widget(InterfaceID.Fairyrings.ROOT_MODEL5).enable(
            WidgetFields.get_rotation_y
        )

        self.abcd_clockwise = Widget(InterfaceID.Fairyrings._1_CLOCKWISE).enable(
            WidgetFields.get_bounds
        )
        self.ijlk_clockwise = Widget(InterfaceID.Fairyrings._2_CLOCKWISE).enable(
            WidgetFields.get_bounds
        )
        self.pqrs_clockwise = Widget(InterfaceID.Fairyrings._3_CLOCKWISE).enable(
            WidgetFields.get_bounds
        )

        self.abcd_anti_clockwise = Widget(InterfaceID.Fairyrings._1_ANTICLOCKWISE).enable(
            WidgetFields.get_bounds
        )
        self.ijlk_anti_clockwise = Widget(InterfaceID.Fairyrings._2_ANTICLOCKWISE).enable(
            WidgetFields.get_bounds
        )
        self.pqrs_anti_clockwise = Widget(InterfaceID.Fairyrings._3_ANTICLOCKWISE).enable(
            WidgetFields.get_bounds
        )

        self.destination_button = Widget(InterfaceID.Fairyrings.CONFIRM).enable(
            WidgetFields.get_bounds
        )

        self.buttons = [
            self.abcd_button,
            self.ijlk_button,
            self.pqrs_button,
            self.abcd_clockwise,
            self.ijlk_clockwise,
            self.pqrs_clockwise,
            self.abcd_anti_clockwise,
            self.ijlk_anti_clockwise,
            self.pqrs_anti_clockwise,
            self.destination_button,
        ]

        self.letter_strings = ["ABCD", "IJKL", "PQRS"]

        self.cached_info: list[dict] = []

    def is_open(self) -> bool:
        return self.group in Services.get().cache.active_interfaces

    def _rotation_to_letter(self, rotation_y: int, index: int) -> str:
        letters = self.letter_strings[index]
        if rotation_y == 0:
            return letters[0]
        elif rotation_y == 512:
            return letters[1]
        elif rotation_y == 1024:
            return letters[2]
        elif rotation_y == 1536:
            return letters[3]
        return "Z"

    def _get_all_info(self) -> list[dict]:
        return Widget.get_batch(self.buttons)

    def get_current_code(self) -> str:
        info = self.cached_info
        code = ""
        for i in range(3):
            rotation_y = info[i].get("rotation_y", -1)
            code += self._rotation_to_letter(rotation_y, i)
        return code

    def _from_letter_to_letter(self, letter: str, target: str) -> int:
        for i in range(3):
            letters = self.letter_strings[i]
            if letter in letters and target in letters:
                break
        current_index = letters.index(letter)
        target_index = letters.index(target)

        anticlockwise_steps = (target_index - current_index) % 4
        clockwise_steps = (current_index - target_index) % 4

        return clockwise_steps if clockwise_steps <= anticlockwise_steps else -anticlockwise_steps

    def _check_index_to_target(self, index: int, target: str) -> bool:
        self.cached_info = self._get_all_info()
        current_code = self.get_current_code()
        return current_code[index] == target

    def _next_letter(self, letter: str, clockwise: bool, index: int) -> str:
        letters = self.letter_strings[index]
        current_index = letters.index(letter)
        next_index = (current_index - 1) % 4 if clockwise else (current_index + 1) % 4
        return letters[next_index]

    def _rotate_to_sequence(self, target_code: str) -> bool:
        all_info = self.cached_info
        current_code = self.get_current_code()
        logger.info(f"Current code: {current_code}, Target code: {target_code}")
        if "Z" in current_code:
            logger.error("Invalid current code detected")
            return False

        for i in range(3):
            current_letter = current_code[i]
            target_letter = target_code[i]
            steps = self._from_letter_to_letter(current_letter, target_letter)
            for _ in range(abs(steps)):
                current_letter = self.get_current_code()[i]
                if steps > 0:
                    button = all_info[i + 3].get(
                        "bounds", {"x": 0, "y": 0, "width": 0, "height": 0}
                    )
                    next_letter = self._next_letter(current_letter, True, i)
                else:
                    button = all_info[i + 6].get(
                        "bounds", {"x": 0, "y": 0, "width": 0, "height": 0}
                    )
                    next_letter = self._next_letter(current_letter, False, i)
                box = Box(button["x"], button["y"], button["width"], button["height"])
                s = "Rotate clockwise" if steps > 0 else "Rotate counter-clockwise"
                if box.interact(option=s):
                    timing.wait_until(
                        lambda i=i, nl=next_letter: self._check_index_to_target(i, nl),
                        timeout=5,
                    )
                else:
                    return False
        self.cached_info = self._get_all_info()
        return self.get_current_code() == target_code

    @staticmethod
    def _varp_to_code(value: int) -> str:
        d1 = value // 100
        d2 = (value % 100) // 10
        d3 = value % 10
        return _DIAL_LETTERS[0][d1] + _DIAL_LETTERS[1][d2] + _DIAL_LETTERS[2][d3]

    def is_last_destination(self, code: str) -> bool:
        value = varps.get_varp_value(VarPlayerID.FAIRYRING_DESTINATION1)
        if value is None:
            return False
        return self._varp_to_code(value) == code.upper()

    def interact(self, target_code: str) -> bool:
        self.cached_info = self._get_all_info()
        if self._rotate_to_sequence(target_code):
            dest_button_bounds = self.cached_info[9].get(
                "bounds", {"x": 0, "y": 0, "width": 0, "height": 0}
            )
            box = Box(
                dest_button_bounds["x"],
                dest_button_bounds["y"],
                dest_button_bounds["width"],
                dest_button_bounds["height"],
            )
            box.interact(option="Confirm")
            return True
        return False
