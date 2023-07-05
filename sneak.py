from typing import List, Union

import sublime
import sublime_plugin
from sublime import DRAW_NO_OUTLINE, LAYOUT_INLINE, Edit, Region, Selection, View
from sublime_api import view_add_phantom, view_add_regions
from sublime_api import view_selection_add_point as add_point
from sublime_api import view_selection_subtract_region as subtract_region

from .base import char_listener, charlist, listen_for_char


class NextCharacterBaseCommand(sublime_plugin.TextCommand):
    def add_hl(self, color: str, regions, name: str) -> None:
        vid = self.view.id()
        view_add_regions(
            vid, name, regions, color, "", DRAW_NO_OUTLINE, [], "", None, None
        )

    def execute(
        self,
        search_string: str,
        start_pt: int,
        forward: bool,
        extend: bool,
    ) -> None:
        view = self.view
        regs_to_add: List[Union[Region, int]] = []
        regs_to_subtract: List[Region] = []
        s = view.sel()
        slength = len(search_string)
        try:
            if forward:
                mybuf = self.view.substr(Region(start_pt, view.size()))
                if search_string.islower():  # smartcase
                    mybuf = mybuf.lower()

                for region in s:
                    offset = region.end() - start_pt - slength + 1
                    pt: int = mybuf.index(search_string, offset) + start_pt
                    if extend:
                        regs_to_add.append(sublime.Region(region.a, pt + slength))
                    else:
                        regs_to_subtract.append(region)
                        regs_to_add.append(Region(pt, pt + slength))
            else:
                search_string = search_string[::-1]
                mybuf = self.view.substr(Region(0, start_pt))[::-1]
                if search_string.islower():  # smartcase
                    mybuf = mybuf.lower()

                for region in s:
                    offset = abs(start_pt - region.end() - 1)
                    pt: int = start_pt - mybuf.index(search_string, offset)
                    if extend:
                        regs_to_add.append(sublime.Region(region.a, pt - slength))
                    else:
                        regs_to_subtract.append(region)
                        regs_to_add.append(Region(pt, pt - slength))

        except ValueError:
            arrow = search_string + "❯" if forward else "❮" + search_string[::-1]
            html = self.get_html(error=True).format(symbol=arrow)
            self.view.show_popup(html, location=s[-1].b)
            return

        for reg in regs_to_subtract:
            s.subtract(reg)
        s.add_all(regs_to_add)
        view.show(s[-1].b, True)
        vid = self.view.id()

        try:
            if len(s) > 1:
                light_hl: List[Region] = []
                regular_hl: List[Region] = []
                for i, region in enumerate(s):
                    if forward:
                        offset = region.b - start_pt
                        pt_beg: int = mybuf.index(search_string, offset + 1) + start_pt
                        pt_end = pt_beg + slength
                    else:
                        offset = start_pt - region.b
                        pt_beg: int = start_pt - mybuf.index(search_string, offset)
                        pt_end = pt_beg - slength

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
                if forward:
                    rel_pt: int = s[0].b - start_pt
                else:
                    rel_pt: int = start_pt - s[0].b

                html = self.get_html()
                global matches
                matches = []
                for i in range(10):
                    rel_pt = mybuf.index(search_string, rel_pt + 1)
                    if forward:
                        abs_pt: int = rel_pt + start_pt
                    else:
                        abs_pt: int = start_pt - rel_pt - slength

                    reg: Region = Region(abs_pt, abs_pt + slength)
                    matches.append(reg)
                    view_add_phantom(
                        vid,
                        "Sneak",
                        reg,
                        html.format(symbol=charlist[i]),
                        LAYOUT_INLINE,
                        None,
                    )

        except ValueError:
            pass

        if slength == 1:
            popup = f"{search_string}_❯" if forward else f"❮{search_string[::-1]}_"
        else:
            popup = f"{search_string}❯" if forward else f"❮{search_string[::-1]}"

        self.view.show_popup(
            self.get_html(error=False).format(symbol=popup),
            location=self.view.sel()[-1].b,
        )

    def get_html(self, error=False) -> str:
        if error:
            bg_color = self.view.style()["redish"]
        else:
            bg_color = self.view.style()["accent"]
        fg_color = self.view.style()["background"]
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


class ListenForCharacterCommand(NextCharacterBaseCommand):
    def run(
        self,
        _,
        forward: bool,
        extend: bool = False,
    ) -> None:
        """
        Sets the buffer ready for search
        """

        char_listener(
            "",
            forward,
            extend,
        )

        arrow: str = "_❯" if forward else " ❮_"
        self.view.settings().set(key="needs_char", value=True)
        self.view.show_popup(
            self.get_html().format(symbol=arrow), location=self.view.sel()[-1].b
        )


class RepeatNextCharacterCommand(NextCharacterBaseCommand):
    def run(self, _, **kwargs: bool) -> None:
        if not (search_string := listen_for_char["search_string"]):
            return
        if bool(kwargs):
            forward = kwargs["forward"]
        else:
            forward = listen_for_char["forward"]
        self.view.settings().set(key="has_stored_search", value=True)

        if forward:
            start_pt = self.view.sel()[0].begin()
        else:
            start_pt = self.view.sel()[-1].end()

        self.execute(
            search_string,
            start_pt=start_pt,
            forward=forward,
            extend=listen_for_char["extend"],
        )


class GoToNthMatchCommand(NextCharacterBaseCommand):
    def run(self, _, **kwargs: int) -> None:
        self.view.settings().set(key="has_stored_search", value=False)
        self.view.settings().set(key="needs_char", value=False)
        if bool(kwargs):
            number: int = kwargs["number"]
        else:
            return
        view = self.view
        sels: Selection = view.sel()
        region = sels[0]
        if len(sels) != 1:
            return

        extend = listen_for_char["extend"]

        if len(matches) < number:
            return
        mymatch: Region = matches[number - 1]
        if extend:
            pt = mymatch.b if region.a < region.b else mymatch.a
            start = sels[0].a
            sels.clear()
            sels.add(Region(start, pt))
        else:
            sels.clear()
            sels.add(Region(mymatch.a, mymatch.b))
        view.show(sels[0].b, True)
        return


class NextCharacterCommand(NextCharacterBaseCommand):
    def run(self, edit: Edit, character: str) -> None:
        global listen_for_char

        search_string = listen_for_char["search_string"]
        forward = listen_for_char["forward"]
        extend = listen_for_char["extend"]

        search_string += character

        self.view.settings().set(key="has_stored_search", value=True)

        if len(search_string) == 2:
            self.view.settings().set(key="needs_char", value=False)

        if forward:
            start_pt = self.view.sel()[0].begin()
        else:
            start_pt = self.view.sel()[-1].end() + len(search_string) - 1

        self.execute(
            search_string=search_string,
            start_pt=start_pt,
            forward=forward,
            extend=extend,
        )
        char_listener(search_string)
