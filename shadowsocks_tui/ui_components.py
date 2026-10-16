"""Custom TUI components extending uibuilder elements.
Provides enhanced inputs with password masking, clean navigation,
styled action buttons, and background decorative frames.
"""

from typing import Callable, Optional
from uibuilder import Border, Button, Element, Event, Input, Label, UIBuilder


class FormInput(Input):
    """Enhanced Input element with password masking, text editing, and key navigation."""

    def __init__(
        self,
        ui: UIBuilder,
        x: int,
        y: int,
        size: int = 20,
        placeholder: str = "",
        is_password: bool = False,
        on_enter_next: Optional[Callable[["FormInput"], None]] = None,
    ):
        super().__init__(ui, x, y, size=size)
        self.placeholder = placeholder
        self.is_password = is_password
        self.on_enter_next = on_enter_next
        self.border_type = Border.LIGHT
        self.name = "FormInput"

    @property
    def value(self) -> str:
        return "".join(self.input_buffer)

    @value.setter
    def value(self, val: str) -> None:
        self.input_buffer = list(str(val))
        self.where_to_place = len(self.input_buffer)

    def on_enter(self) -> None:
        if (
            self.ui.current_event.type == Event.KEY_PRESS
            and self.ui.current_event.value == "ENTER"
            and self.focus
        ):
            if self.on_enter_next:
                self.on_enter_next(self)
            elif self.enter_func:
                self.enter_func(self)

    def capture_input(self) -> None:
        if self.ui.current_event.type != Event.KEY_PRESS:
            return

        char = self.ui.current_event.value

        if char == "BACK":
            if self.where_to_place > 0 and self.input_buffer:
                self.input_buffer.pop(self.where_to_place - 1)
                self.where_to_place -= 1
        elif char == "DELETE":
            if self.where_to_place < len(self.input_buffer):
                self.input_buffer.pop(self.where_to_place)
        elif char == "LEFT":
            self.where_to_place = max(0, self.where_to_place - 1)
        elif char == "RIGHT":
            self.where_to_place = min(len(self.input_buffer), self.where_to_place + 1)
        elif char == "HOME":
            self.where_to_place = 0
        elif char == "END":
            self.where_to_place = len(self.input_buffer)
        elif isinstance(char, str) and len(char) == 1 and char.isprintable():
            if self.where_to_place == len(self.input_buffer):
                self.input_buffer.append(char)
            else:
                self.input_buffer.insert(self.where_to_place, char)
            self.where_to_place += 1

    def on_focus(self) -> None:
        super().on_focus()
        if self.is_password and self.input_buffer:
            # Mask characters in rendered buffer
            for i in range(len(self.to_render)):
                ch = self.to_render[i]
                if "\033[7m" in ch:
                    self.to_render[i] = "\033[7m*"
                elif ch != " ":
                    self.to_render[i] = "*"


class ActionButton(Button):
    """Button element with support for dynamic text updating and uniform width."""

    def __init__(
        self,
        ui: UIBuilder,
        x: int,
        y: int,
        text: str,
        on_click: Callable[["ActionButton"], None],
        width: Optional[int] = None,
    ):
        self.fixed_width = width or len(text)
        padded_text = text.center(self.fixed_width)
        super().__init__(ui, x, y, padded_text, on_click)
        self.border_type = Border.ROUND
        self.name = "ActionButton"
        self._current_raw_text = text

    def set_label(self, new_text: str) -> None:
        """Update button label smoothly without erasing active focus highlight."""
        if self._current_raw_text == new_text:
            return
        self._current_raw_text = new_text
        self.text = new_text.center(self.fixed_width)
        self.on_focus()

    def on_focus(self) -> None:
        if self.focus:
            self.render_text()
            to_render = UIBuilder.deepcopy(self.grid)
            for row in range(1, len(self.grid) - 1):
                for ch in range(1, len(self.grid[row]) - 1):
                    self.grid[row][ch] = f"\033[1;7m{to_render[row][ch]}"
        else:
            self.render_text()


class BackgroundFrame(Element):
    """Draws full application window frame, titles, and section dividers."""

    def __init__(self, ui: UIBuilder):
        super().__init__(ui, 0, 0)
        self.name = "BackgroundFrame"

    def add_to_grid(self) -> None:
        w = self.ui.grid_size_x
        h = self.ui.grid_size_y

        # 1. Top and bottom outer border
        self.ui.grid[0] = list("╭" + "─" * (w - 2) + "╮")
        for y in range(1, h - 1):
            self.ui.grid[y] = list("│" + " " * (w - 2) + "│")
        self.ui.grid[h - 1] = list("╰" + "─" * (w - 2) + "╯")

        # 2. Dividers
        for div_y in (2, 4, 14, 18, 21):
            if div_y < h:
                self.ui.grid[div_y] = list("├" + "─" * (w - 2) + "┤")

        # 3. Static Section Headers
        self._write_at(5, 4, "[ SERVER CONFIGURATION ]")

    def _write_at(self, y: int, x: int, text: str) -> None:
        if 0 <= y < self.ui.grid_size_y:
            for i, ch in enumerate(text):
                if x + i < self.ui.grid_size_x - 1:
                    self.ui.grid[y][x + i] = ch
