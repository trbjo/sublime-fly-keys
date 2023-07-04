from typing import List, Union

import sublime
import sublime_plugin
from sublime import DRAW_NO_OUTLINE, LAYOUT_INLINE, Edit, Region, Selection, View
from sublime_api import view_add_phantom, view_add_regions
from sublime_api import view_selection_add_point as add_point
from sublime_api import view_selection_subtract_region as subtract_region

from .base import char_listener, charlist, listen_for_char


class NextCharacterBaseCommand(sublime_plugin.TextCommand):
    def execute(
        self,
        search_string: str,
        start_pt: int,
        forward: bool,
        extend: bool,
    ) -> None:
        view = self.view
        global matches
        matches = []
        regs_to_add: List[Union[Region, int]] = []
        regs_to_subtract: List[Region] = []
        try:
            if forward:
                mybuf = self.view.substr(Region(start_pt, view.size()))
                for region in view.sel():
                    pt: int = mybuf.index(search_string) + start_pt
                    if extend:
                        regs_to_add.append(
                            sublime.Region(region.a, pt + len(search_string))
                        )
                    else:
                        regs_to_subtract.append(region)
                        regs_to_add.append(Region(pt, pt + len(search_string)))
            else:
                search_string = search_string[::-1]
                mybuf = self.view.substr(Region(0, start_pt))[::-1]
                for region in view.sel():
                    pt: int = start_pt - mybuf.index(search_string)
                    if extend:
                        regs_to_add.append(
                            sublime.Region(region.a, pt - len(search_string))
                        )
                    else:
                        regs_to_subtract.append(region)
                        regs_to_add.append(Region(pt, pt - len(search_string)))

        except ValueError:
            self.view.show_popup(
                self.get_html(error=True).format(
                    symbol=search_string + "❯" if forward else "❮" + search_string[::-1]
                ),
                location=self.view.sel()[-1].b,
            )
            return

        for reg in regs_to_subtract:
            view.sel().subtract(reg)
        view.sel().add_all(regs_to_add)
        view.show(view.sel()[-1].b, True)
        view_id = self.view.id()

        try:
            if len(view.sel()) > 1:
                light_hl: List[Region] = []
                regular_hl: List[Region] = []
                offset = offset - 1 if not forward else offset
                off_length = offset + len(search_string)
                new_offset = 1 if not forward and len(search_string) == 2 else 0
                for i, region in enumerate(view.sel()):
                    if forward:
                        pt: int = (
                            mybuf.index(search_string, region.b - start_pt + 1)
                            + start_pt
                            + 1
                        )
                    else:
                        pt: int = (
                            start_pt
                            - mybuf.index(search_string, start_pt - region.b)
                            - 2
                        )
                    try:
                        if pt == view.sel()[i + 1 if forward else i - 1].b + new_offset:
                            light_hl.append(Region(pt + offset, pt + off_length))
                        else:
                            regular_hl.append(Region(pt + offset, pt + off_length))
                    except IndexError:
                        regular_hl.append(Region(pt + offset, pt + off_length))
                        break

                if regular_hl:
                    view_add_regions(
                        view_id,
                        "Sneak",
                        regular_hl,
                        "accent",
                        "",
                        DRAW_NO_OUTLINE,
                        [],
                        "",
                        None,
                        None,
                    )
                if light_hl:
                    view_add_regions(
                        view_id,
                        "Sneak",
                        light_hl,
                        "light",
                        "",
                        DRAW_NO_OUTLINE,
                        [],
                        "",
                        None,
                        None,
                    )
            else:
                if forward:
                    rel_pt: int = view.sel()[0].b - start_pt
                else:
                    rel_pt: int = start_pt - view.sel()[0].b

                html = self.get_html()
                for i in range(10):
                    rel_pt = mybuf.index(search_string, rel_pt + 1)
                    if forward:
                        abs_pt: int = rel_pt + start_pt
                    else:
                        abs_pt: int = start_pt - rel_pt - len(search_string)

                    reg: Region = Region(abs_pt, abs_pt + len(search_string))
                    matches.append(reg)
                    view_add_phantom(
                        view_id,
                        "Sneak",
                        reg,
                        html.format(symbol=charlist[i]),
                        LAYOUT_INLINE,
                        None,
                    )

        except ValueError:
            pass
        if len(search_string) == 1:
            signifier = (
                f"{search_string}_❯" if forward else "❮" + search_string[::-1] + "_"
            )
        else:
            signifier = f"{search_string}❯" if forward else "❮" + search_string[::-1]

        self.view.show_popup(
            self.get_html(error=False).format(symbol=signifier),
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
        if not listen_for_char["search_string"]:
            return
        if bool(kwargs):
            forward = kwargs["forward"]
        else:
            forward = listen_for_char["forward"]
        self.view.settings().set(key="has_stored_search", value=True)
        start_pt = self.view.sel()[0].end() if forward else self.view.sel()[-1].b
        self.execute(
            listen_for_char["search_string"],
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
        v = self.view
        global listen_for_char

        search_string = listen_for_char["search_string"]
        forward = listen_for_char["forward"]
        extend = listen_for_char["extend"]

        search_string += character

        self.view.settings().set(key="has_stored_search", value=True)
        if len(search_string) == 2:
            self.view.settings().set(key="needs_char", value=False)

        start_pt = self.view.sel()[0].begin() if forward else self.view.sel()[-1].b
        self.execute(
            search_string=search_string,
            start_pt=start_pt,
            forward=forward,
            extend=extend,
        )
        char_listener(search_string)
