from sublime import LAYOUT_INLINE, LITERAL, View, Region, Selection
import sublime
import sublime_plugin

from typing import List, Tuple, Union

# tuple of (char: str, forward: bool, extend: bool)
char_forward_tuple: Tuple[str, bool, bool] = ('', True, False)
matches : List[Region] = []
class FindNextCharacterBaseCommand(sublime_plugin.TextCommand):
    def find_next(self, forward: bool, char: str, pt: int, num_matches: int) -> List[int]:
        buf = self.view
        pts: List[int] = []
        if forward:
            mybuf = self.view.substr(Region(pt+1,buf.size()))
        else:
            mybuf = self.view.substr(Region(0, pt-1))[::-1]
            char = char[::-1]
        new_pt: int = 0
        for _ in range(num_matches):
            if forward:
                try:
                    new_pt = mybuf.index(char, new_pt) + 1
                    pts.append(pt + new_pt)
                except ValueError:
                    return pts
            else:
                try:
                    new_pt = mybuf.index(char, new_pt) + 2
                    pts.append(pt - new_pt)
                except ValueError:
                    return pts
        return pts


    myhtml="""<body id="my-plugin-feature"><style>div.matcher{{padding: 0 2px 0 1px; margin: 0; border-radius:2px;background-color:{background};color:{color};}}</style><div class="matcher">{counter}</div></body>"""
    charlist = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']
    def execute(self, forward: bool, search_string: str, extend: bool) -> None:
        buf = self.view
        sels: Selection = buf.sel()
        regs_to_add: List[Union[Region,int]] = []
        regs_to_subtract: List[Region] = []
        offset = 1 if not forward and len(search_string) == 1 else 0
        for region in sels:
            pts = self.find_next(forward, search_string, region.b, 1)
            if not pts:
                return
            pt = pts[0]
            if region.a == region.b:
                if extend:
                    tp = pt + len(search_string) if forward else pt -1
                    regs_to_add.append(sublime.Region(region.a, tp))
                else:
                    tp = pt if forward else pt -1
                    regs_to_subtract.append(region)
                    regs_to_add.append(tp + offset)
                # normal sel
            elif region.a < region.b:
                if forward:
                    regs_to_add.append(Region(region.b -1, pt + len(search_string)))
                else:
                    if pt < region.a:
                        regs_to_subtract.append(Region(region.b, region.a))
                        regs_to_add.append(Region(region.a))
                    else:
                        regs_to_subtract.append(Region(region.b, pt+1))
                # reverse sel
            elif region.a > region.b:
                if forward:
                    if pt > region.a:
                        regs_to_subtract.append(Region(region.a, region.b))
                        regs_to_add.append(Region(region.a))
                    else:
                        regs_to_subtract.append(Region(region.b, pt))
                else:
                    regs_to_add.append(Region(region.a, pt -1 + offset))

        for reg in regs_to_subtract:
            sels.subtract(reg)
        sels.add_all(regs_to_add)
        buf.show(buf.sel()[-1], True)

        # now we look for highlights
        global matches
        matches = []
        offset = offset-1 if not forward else offset
        off_length = offset+len(search_string)
        # we use phantoms if we have one match, regions, if more
        if len(sels) > 1:
            new_offset = 1 if not forward and len(search_string) == 2 else 0
            light_hl: List[Region] = []
            for i,region in enumerate(sels):
                new_pt = self.find_next(forward, search_string, region.b, 1)[0]
                try:
                    if new_pt == sels[i+1 if forward else i-1].b + new_offset:
                        light_hl.append(Region(new_pt+offset, new_pt+off_length))
                        continue
                    matches.append(Region(new_pt+offset, new_pt+off_length))
                except IndexError:
                    matches.append(Region(new_pt+offset, new_pt+off_length))
                    break
            if matches:
                self.view.add_regions("Sneak", matches, "accent", flags=sublime.DRAW_NO_OUTLINE)
                matches = []
            if light_hl:
                self.view.add_regions("Sneaks", light_hl, "light", flags=sublime.DRAW_NO_OUTLINE)
        else:
            bg_color = buf.style()["accent"]
            fg_color = buf.style()["background"]
            matches = [Region(pt+offset, pt+off_length) for pt in self.find_next(forward, search_string, sels[0].b, 10)]
            for i,match in enumerate(matches):
                self.view.add_phantom("Sneak", region=match, content=self.myhtml.format(counter=self.charlist[i], background=bg_color, color=fg_color), layout=LAYOUT_INLINE)


class StoreCharacterCommand(FindNextCharacterBaseCommand):
    def run(self, _, forward: bool, character: str='', extend: bool=False) -> None:
        self.view.settings().set(key="waiting_for_char", value=True)
        global char_forward_tuple
        char_forward_tuple = (character, forward, extend)

class RepeatFindNextCharacterCommand(FindNextCharacterBaseCommand):
    def run(self, _, **kwargs: bool) -> None:
        search_string, forward, extend = char_forward_tuple
        if not search_string:
            return
        if bool(kwargs):
            forward = kwargs['forward']
        self.view.settings().set(key="has_stored_search", value=True)
        self.execute(forward, search_string, extend)

class GoToNthMatchCommand(FindNextCharacterBaseCommand):
    def run(self, _, **kwargs: int) -> None:
        if bool(kwargs):
            number: int = kwargs['number']
        else:
            return
        buf = self.view
        sels: Selection = buf.sel()
        region = sels[0]
        if len(sels) != 1:
            return
        _, _, extend = char_forward_tuple
        if region.a != region.b:
            extend = True

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
            sels.add(mymatch.a)
        buf.show(sels[0], True)
        return

class FindNextCharacterCommand(FindNextCharacterBaseCommand):
    def run(self, _, **kwargs: str) -> None:
        self.view.settings().set(key="has_stored_search", value=True)
        self.view.settings().set(key="sneak_override_find_keybinding", value=True)
        self.view.settings().set(key="waiting_for_char", value=False)
        if bool(kwargs):
            mychar = kwargs['character']
        else:
            mychar = ''
        global char_forward_tuple
        character, forward, extend = char_forward_tuple
        search_string: str = character + mychar
        char_forward_tuple = (search_string, forward, extend)
        self.execute(forward, search_string, extend)


class FindNextCharacterListener(sublime_plugin.EventListener):
    def on_window_command(self, window: sublime.Window, _, __):
        view: Union[View,None] = window.active_view()
        if view is None:
            return
        view.erase_phantoms("Sneak")
        view.erase_regions("Sneak")
        view.erase_regions("Sneaks")
        view.settings().set(key="waiting_for_char", value=False)
        view.settings().set(key="has_stored_search", value=False)

    def on_text_command(self, view: View, command_name: str, _):
        view.erase_regions("Sneak")
        view.erase_regions("Sneaks")
        view.erase_phantoms("Sneak")
        if (command_name != "find_next_character" and command_name != "repeat_find_next_character"
        and command_name != "store_character" and command_name != "revert_selection"):
            view.settings().set(key="has_stored_search", value=False)
            view.settings().set(key="waiting_for_char", value=False)
