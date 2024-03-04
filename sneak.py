import re
from re import IGNORECASE
from typing import List, Optional

import sublime_plugin
from sublime import DRAW_NO_OUTLINE, Edit, PopupFlags, Region, Selection, View
from sublime_api import view_add_phantom, view_add_regions  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_plugin import TextCommand

from .base import buffer_slice

charlist = "1234567890"
only_single_chars = charlist + "_\\./()\"'-:,;<>~!@#$%^&*|+=[]{}`~?/"

_search_string = ""
_forward = True
_extend = False
matches = []


def set_chars(
    search_string: Optional[str] = None,
    forward: Optional[bool] = None,
    extend: Optional[bool] = None,
) -> None:
    global _search_string
    global _forward
    global _extend
    if search_string is not None:
        _search_string = search_string
    if forward is not None:
        _forward = forward
    if extend is not None:
        _extend = extend


class NextCharacterBaseCommand(sublime_plugin.TextCommand):
    def add_hl(self, color: str, regions, name: str) -> None:
        vid = self.view.id()
        view_add_regions(
            vid, name, regions, color, "", DRAW_NO_OUTLINE, [], "", None, None
        )

    def execute(
        self, search_string: str, forward: bool, extend: bool, special: bool
    ) -> bool:
        v = self.view
        global matches
        matches = []

        s = v.sel()
        if forward:
            offset = -1 if special else 0
        else:
            search_string = search_string[::-1]
            offset = 2 if special else 0

        flags = 0
        if search_string.islower():  # smartcase
            flags += IGNORECASE
        rgx = re.compile(re.escape(search_string), flags)

        vid = v.id()
        bufind = buffer_slice(v, forward)
        bufind.send(None)
        cursors = []
        seen = set()
        for _, end in s if forward else reversed(s):
            while m := bufind.send((end + offset, rgx)):
                _, end = m
                if end not in seen:
                    seen.add(end)
                    cursors.append(m)
                    break

        if not cursors:
            return False

        if forward and extend:
            cursors = [(r.begin(), b) for r, (_, b) in zip(s, cursors)]
        elif not forward and extend:
            cursors = [(r.end(), b) for r, (_, b) in zip(s, cursors)]

        s.clear()
        for cursor in cursors:
            add_region(vid, *cursor, 0.0)
        v.show(s[-1].b, True)

        hls = []
        iterations = len(charlist) if len(s) == 1 else 1
        for reg in s if forward else reversed(s):
            while (reg := bufind.send((*reg, rgx))) and len(hls) < iterations:
                hls.append(reg)

        if len(s) == 1:
            matches = [Region(*reg) for reg in hls]
            for m, c in zip(matches, charlist):
                view_add_phantom(vid, "Sneak", m, get_html(v).format(char=c), 0, None)
        else:
            light_hl: List[Region] = []
            regular_hl: List[Region] = []
            cursors = {b for _, b in cursors}
            for res_a, res_b in hls:
                reg = Region(res_a, res_b)
                (light_hl if res_b in cursors else regular_hl).append(reg)

            if light_hl:
                self.add_hl("light", light_hl, "Sneaks")
            if regular_hl:
                self.add_hl("accent", regular_hl, "Sneak")

        return True


class GoToNthMatchCommand(TextCommand):
    def run(self, _, number: int) -> None:
        v = self.view
        v.settings().set(key="has_stored_search", value=False)
        v.settings().set(key="needs_char", value=False)
        sels: Selection = v.sel()

        if len(sels) != 1:
            return

        if len(matches) < number:
            return

        region = sels[0]
        num: Region = matches[number - 1]
        if _extend:
            pt = num.b
            start = region.a
            sels.clear()
            sels.add(Region(start, pt))
        else:
            sels.clear()
            sels.add(Region(num.a, num.b))
        v.show(sels[0].b, True)


class SneakListenCommand(TextCommand):
    def run(self, _, forward: bool, extend: bool = False) -> None:
        """
        Sets the buffer ready for search
        """
        set_chars("", forward, extend)
        arrow: str = "_❯" if forward else " ❮_"
        self.view.settings().set(key="needs_char", value=True)
        format_search_arrow(arrow, self.view)


def format_search_arrow(arrow, view: View, blue: bool = True) -> None:
    view.show_popup(
        get_html(view, blue=blue).format(char=arrow),
        flags=PopupFlags.HIDE_ON_CHARACTER_EVENT,
        location=view.sel()[-1].b,
    )


def get_html(view: View, blue=True) -> str:
    if blue:
        bg_color = view.style()["accent"]
    else:
        bg_color = view.style()["redish"]
    fg_color = view.style()["background"]
    return """<body
        style="
            padding: 0 2px 0 1px;
            margin: 0;
            border-radius:2px;
            background-color:{background};
            color:{color};
        ">
        <div>{{char}}</div>
    </body>""".format(
        background=bg_color, color=fg_color
    )


class SneakCommand(NextCharacterBaseCommand):
    def run(self, edit: Edit, character: str) -> None:
        global matches
        search_string = _search_string + character
        v = self.view
        sels: Selection = v.sel()

        if len(sels) < 1:
            return

        if (
            len(search_string) == 2
            and matches
            and (idx := charlist.find(character)) != -1
        ):
            v.settings().set(key="has_stored_search", value=False)
            v.settings().set(key="needs_char", value=False)
            region = sels[0]
            num: Region = matches[idx]
            if _extend:
                pt = num.b
                start = region.a
                sels.clear()
                sels.add(Region(start, pt))
            else:
                sels.clear()
                sels.add(Region(num.a, num.b))
            v.show(sels[0].b, True)
            return

        set_chars(search_string)

        val = self.execute(
            search_string=search_string,
            forward=_forward,
            extend=_extend,
            special=len(search_string) == 2,
        )

        self.view.settings().set(key="has_stored_search", value=val)

        if len(search_string) == 2 or character in only_single_chars or not val:
            self.view.settings().set(key="needs_char", value=False)
            arrow = f"{search_string}❯" if _forward else f"❮{search_string}"
        else:
            arrow = f"{search_string}_❯" if _forward else f"❮{search_string}_"

        format_search_arrow(arrow, self.view, val)


class SneakRepeatCommand(NextCharacterBaseCommand):
    def run(self, _, forward: bool) -> None:
        if not _search_string:
            return

        val = self.execute(
            _search_string, forward=forward, extend=_extend, special=False
        )
        self.view.settings().set(key="has_stored_search", value=val)

        if len(_search_string) == 2 or _search_string in only_single_chars:
            arrow = f"{_search_string}❯" if forward else f"❮{_search_string}"
        else:
            arrow = f"{_search_string}_❯" if forward else f"❮{_search_string}_"

        format_search_arrow(arrow, self.view, val)
