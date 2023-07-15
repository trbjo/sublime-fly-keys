from typing import List, Optional, Tuple, Union

import sublime_plugin
from sublime import DRAW_NO_OUTLINE, LAYOUT_INLINE, Edit, Region, Selection, View
from sublime_api import view_add_phantom, view_add_regions  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_plugin import TextCommand

charlist = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
listen_for_char = {
    "search_string": "",
    "forward": True,
    "extend": False,
}
only_single_chars = "./()\"'-:,;<>~!@#$%^&*|+=[]{}`~?"


def set_chars(
    search_string: Optional[str] = None,
    forward: Optional[bool] = None,
    extend: Optional[bool] = None,
) -> None:
    global listen_for_char
    if search_string is not None:
        listen_for_char["search_string"] = search_string
    if forward is not None:
        listen_for_char["forward"] = forward
    if extend is not None:
        listen_for_char["extend"] = extend


class NextCharacterBaseCommand(sublime_plugin.TextCommand):
    def add_hl(self, color: str, regions, name: str) -> None:
        vid = self.view.id()
        view_add_regions(
            vid, name, regions, color, "", DRAW_NO_OUTLINE, [], "", None, None
        )

    def execute(
        self,
        search_string: str,
        forward: bool,
        extend: bool,
        special: bool,
    ) -> bool:
        v = self.view
        regs_to_add = []
        global matches

        s = v.sel()
        slen = len(search_string)
        diff = 0
        if forward:
            regb = s[0].b
            rega = s[0].a
            begin = rega if special else regb
            diff = abs(regb - rega) if special else 0
            mybuf = v.substr(Region(begin, v.size()))
        else:
            regb = s[-1].b
            rega = s[-1].a
            begin = rega + 1 if special else regb
            search_string = search_string[::-1]
            mybuf = v.substr(Region(0, begin))[::-1]
            diff = abs(regb - begin) if special else 0

        if search_string.islower():  # smartcase
            mybuf = mybuf.lower()

        try:
            for r in s:
                if forward:
                    ext_from = r.b if r.a > r.b else r.a
                    offset = r.b - begin - diff
                    pt: int = mybuf.index(search_string, offset) + begin
                else:
                    ext_from = r.b if r.a < r.b else r.a
                    offset = begin - r.b - diff
                    pt: int = begin - mybuf.index(search_string, offset)

                if extend:
                    r = (ext_from, pt + slen) if forward else (ext_from, pt - slen)
                    regs_to_add.append(r)
                else:
                    r = (pt, pt + slen) if forward else Region(pt, pt - slen)
                    regs_to_add.append(r)

        except ValueError:
            matches = []
            return False

        s.clear()
        vid = v.id()
        for region in regs_to_add:
            add_region(vid, *region, 0.0)
        v.show(s[-1].b, True)

        try:
            if len(s) > 1:
                light_hl: List[Region] = []
                regular_hl: List[Region] = []
                for i, region in enumerate(s):
                    if forward:
                        offset = region.b - begin
                        pt_end = begin + mybuf.index(search_string, offset + 1)
                        pt_beg = pt_end - slen
                    else:
                        offset = begin - region.b
                        pt_beg = begin - mybuf.index(search_string, offset + 1)
                        pt_end = pt_beg - slen

                    hl_reg = Region(pt_beg, pt_end)

                    try:
                        if hl_reg.intersects(s[i + 1 if forward else i - 1]):
                            light_hl.append(hl_reg)
                        else:
                            regular_hl.append(hl_reg)
                    except IndexError:
                        regular_hl.append(hl_reg)
                        break

                if regular_hl:
                    self.add_hl("accent", regular_hl, "Sneak")
                if light_hl:
                    self.add_hl("light", light_hl, "Sneaks")

            else:
                rel_pt = s[0].b - begin if forward else begin - s[0].b
                matches = []
                for i in range(10):
                    rel_pt = mybuf.index(search_string, rel_pt + 1)
                    abs_pt = begin + (rel_pt if forward else -rel_pt)
                    reg: Region = Region(abs_pt, abs_pt + (slen if forward else -slen))
                    matches.append(reg)
                    view_add_phantom(
                        vid,
                        "Sneak",
                        reg,
                        get_html(v).format(symbol=charlist[i]),
                        LAYOUT_INLINE,
                        None,
                    )

        except ValueError:
            pass

        return True


class ListenForCharacterCommand(TextCommand):
    def run(self, _, forward: bool, extend: bool = False) -> None:
        """
        Sets the buffer ready for search
        """
        set_chars("", forward, extend)
        arrow: str = "_❯" if forward else " ❮_"
        self.view.settings().set(key="needs_char", value=True)
        self.view.show_popup(
            get_html(self.view).format(symbol=arrow), location=self.view.sel()[-1].b
        )


class RepeatNextCharacterCommand(NextCharacterBaseCommand):
    def run(self, _, forward: bool) -> None:
        if not (search_string := listen_for_char["search_string"]):
            return

        val = self.execute(
            search_string,
            forward=forward,
            extend=listen_for_char["extend"],
            special=False,
        )

        if len(search_string) == 2 or search_string in only_single_chars:
            popup = f"{search_string}❯" if forward else f"❮{search_string}"
        else:
            popup = f"{search_string}_❯" if forward else f"❮{search_string}_"
        show_popup(popup, self.view, val)


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
        if listen_for_char["extend"]:
            pt = num.b
            start = region.a
            sels.clear()
            sels.add(Region(start, pt))
        else:
            sels.clear()
            sels.add(Region(num.a, num.b))
        v.show(sels[0].b, True)


def show_popup(popup, view: View, blue: bool = True) -> None:
    view.show_popup(
        get_html(view, blue=blue).format(symbol=popup),
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
        <div>{{symbol}}</div>
    </body>""".format(
        background=bg_color, color=fg_color
    )


class NextCharacterCommand(NextCharacterBaseCommand):
    def run(self, edit: Edit, character: str) -> None:
        global listen_for_char

        search_string = listen_for_char["search_string"] + character
        forward = listen_for_char["forward"]
        extend = listen_for_char["extend"]

        set_chars(search_string)
        self.view.settings().set(key="has_stored_search", value=True)
        val = self.execute(
            search_string=search_string,
            forward=forward,
            extend=extend,
            special=len(search_string) == 2 and not extend,
        )

        if len(search_string) == 2 or character in only_single_chars:
            self.view.settings().set(key="needs_char", value=False)
            popup = f"{search_string}❯" if forward else f"❮{search_string}"
        else:
            popup = f"{search_string}_❯" if forward else f"❮{search_string}_"
        show_popup(popup, self.view, val)
