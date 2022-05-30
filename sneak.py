from sublime import LAYOUT_INLINE, View, Region, Selection, DRAW_NO_OUTLINE, Edit
import sublime
from sublime_api import view_add_phantom, view_add_regions
import sublime_plugin
from typing import List, Tuple, Union

# tuple of (search_string: str, forward: bool, extend: bool)
char_forward_tuple: Tuple[str, bool, bool] = ('', True, False)
matches: List[Region] = []
charlist = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']

class FindNextCharacterBaseCommand(sublime_plugin.TextCommand):
    def execute(self, forward: bool, search_string: str, extend: bool) -> None:
        view = self.view
        global matches
        matches = []
        regs_to_add: List[Union[Region,int]] = []
        regs_to_subtract: List[Region] = []
        try:
            if forward:
                offset = 0
                first_pt = view.sel()[0].b
                mybuf = self.view.substr(Region(first_pt+1,view.size()))
                for region in view.sel():
                    pt: int = mybuf.index(search_string, region.b - first_pt +1) + 1 + first_pt
                    if region.a == region.b:
                        if extend:
                            regs_to_add.append(sublime.Region(region.a, pt + len(search_string)))
                        else:
                            regs_to_subtract.append(region)
                            regs_to_add.append(pt)
                    elif region.a < region.b:
                        regs_to_add.append(Region(region.b -1, pt + len(search_string)))
                    elif region.a > region.b:
                        if pt > region.a:
                            regs_to_subtract.append(Region(region.a, region.b))
                            regs_to_add.append(region.a)
                        else:
                            regs_to_subtract.append(Region(region.b, pt))
            else:
                search_string = search_string[::-1]
                offset = 1 if len(search_string) == 1 else 0
                last_pt = view.sel()[-1].b
                mybuf = self.view.substr(Region(0, last_pt-1))[::-1]
                for region in view.sel():
                    pt: int = last_pt - mybuf.index(search_string, last_pt - region.b) - 2
                    if region.a == region.b:
                        if extend:
                            regs_to_add.append(sublime.Region(region.a, pt -1 + offset))
                        else:
                            regs_to_subtract.append(region)
                            regs_to_add.append(pt-1+offset)
                    elif region.a < region.b:
                        if pt < region.a:
                            regs_to_subtract.append(Region(region.b, region.a))
                            regs_to_add.append(region.a)
                        else:
                            regs_to_subtract.append(Region(region.b, pt+1))
                    elif region.a > region.b:
                        regs_to_add.append(Region(region.a, pt -1 + offset))

        except ValueError:
            self.view.show_popup(self.get_html(error=True).format(symbol=search_string+'❯' if forward else '❮'+search_string[::-1]),location=self.view.sel()[-1].b)
            return

        for reg in regs_to_subtract:
            view.sel().subtract(reg)
        view.sel().add_all(regs_to_add)
        view.show(view.sel()[-1].end(), True)
        view_id = self.view.id()
        try:
            if len(view.sel()) > 1:
                light_hl: List[Region] = []
                regular_hl: List[Region] = []
                offset = offset-1 if not forward else offset
                off_length = offset+len(search_string)
                new_offset = 1 if not forward and len(search_string) == 2 else 0
                for i,region in enumerate(view.sel()):
                    if forward:
                        pt: int = mybuf.index(search_string, region.b - first_pt + 1) + first_pt + 1
                    else:
                        pt: int = last_pt - mybuf.index(search_string, last_pt - region.b) - 2
                    try:
                        if pt == view.sel()[i+1 if forward else i-1].b + new_offset:
                            light_hl.append(Region(pt+offset, pt+off_length))
                        else:
                            regular_hl.append(Region(pt+offset, pt+off_length))
                    except IndexError:
                        regular_hl.append(Region(pt+offset, pt+off_length))
                        break

                if regular_hl:
                    view_add_regions(view_id, "Sneak", regular_hl, "accent", "", DRAW_NO_OUTLINE, [], "", None, None)
                if light_hl:
                    view_add_regions(view_id, "Sneaks", light_hl, "light", "", DRAW_NO_OUTLINE, [], "", None, None)
            else:
                if forward:
                    rel_pt: int = view.sel()[0].b - first_pt
                else:
                    rel_pt: int = last_pt - view.sel()[0].b

                html = self.get_html()
                for i in range(10):
                    rel_pt = mybuf.index(search_string, rel_pt) + 1
                    if forward:
                        abs_pt: int = rel_pt + first_pt
                    else:
                        abs_pt: int = last_pt - rel_pt - len(search_string)

                    reg: Region = Region(abs_pt, abs_pt+len(search_string))
                    matches.append(reg)
                    view_add_phantom(view_id, "Sneak", reg, html.format(symbol=charlist[i]), LAYOUT_INLINE, None)
        except ValueError:
            return


    def get_html(self, error=False) -> str:
        if error:
            bg_color = self.view.style()["redish"]
        else:
            bg_color = self.view.style()["accent"]
        fg_color = self.view.style()["background"]
        return """<body style="padding: 0 2px 0 1px; margin: 0; border-radius:2px;background-color:{background};color:{color};"><div>{{symbol}}</div></body>""".format(background=bg_color, color=fg_color)

class ListenForCharacterCommand(FindNextCharacterBaseCommand):
    def run(self, _, forward: bool, extend: bool=False, single: bool=False) -> None:
        self.view.settings().set(key="needs_char", value=True)
        if single:
            arrow: str = '_❯' if forward else ' ❮_'
            self.view.settings().set(key="sneak_ready_to_search", value=True)
            self.view.show_popup(self.get_html().format(symbol=arrow),location=self.view.sel()[-1].b)
        else:
            arrow: str = '__❯' if forward else ' ❮__'
            self.view.show_popup(self.get_html().format(symbol=arrow),location=self.view.sel()[-1].b)
            self.view.settings().set(key="sneak_ready_to_search", value=False)

        global char_forward_tuple
        char_forward_tuple = ('', forward, extend)

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
        view = self.view
        sels: Selection = view.sel()
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
        view.show(sels[0].end(), True)
        return

class InsertSingleChar(sublime_plugin.TextCommand):
    def run(self, _):
        self.view.settings().set(key="insert_single_char", value=True)
        self.view.settings().set(key="block_caret", value=False)
        self.view.settings().set(key="command_mode", value=False)
        self.view.settings().set(key="needs_char", value=True)


class FindNextCharacterCommand(FindNextCharacterBaseCommand):
    def run(self, edit: Edit, character: str) -> None:
        if self.view.settings().get("insert_single_char", False):
            self.view.settings().set(key="command_mode", value=True)
            self.view.settings().set(key="block_caret", value=True)
            self.view.settings().set("insert_single_char", False)
            self.view.settings().set(key="needs_char", value=False)
            for reg in reversed(self.view.sel()):
                if reg.empty():
                    self.view.insert(edit, reg.a, character)
                else:
                    self.view.replace(edit, reg, character)
            return

        global char_forward_tuple
        sneak_ready_to_search: bool = self.view.settings().get(key="sneak_ready_to_search", default=False)
        stored_char, forward, extend = char_forward_tuple

        if sneak_ready_to_search:
            self.view.settings().set(key="sneak_ready_to_search", value=False)
            search_string = stored_char+character
            char_forward_tuple = (search_string, forward, extend)
            self.execute(forward, search_string, extend)
            self.view.settings().set(key="has_stored_search", value=True)
            self.view.settings().set(key="sneak_override_find_keybinding", value=True)
            self.view.settings().set(key="needs_char", value=False)
        else:
            self.view.settings().set(key="sneak_ready_to_search", value=True)
            arrow: str = f'{character}_❯' if forward else f'❮{character}_'
            self.view.show_popup(self.get_html().format(symbol=arrow),location=self.view.sel()[-1].b)
            char_forward_tuple = character, forward, extend


class FindNextCharacterListener(sublime_plugin.EventListener):
    def on_window_command(self, window: sublime.Window, _, __):
        view: Union[View,None] = window.active_view()
        if view is None:
            return
        view.erase_phantoms("Sneak")
        view.erase_regions("Sneak")
        view.erase_regions("Sneaks")
        view.settings().set(key="needs_char", value=False)
        view.settings().set(key="has_stored_search", value=False)

    def on_text_command(self, view: View, command_name: str, _):
        view.erase_regions("Sneak")
        view.erase_regions("Sneaks")
        view.erase_phantoms("Sneak")
        if (command_name != "find_next_character" and command_name != "repeat_find_next_character"
        and command_name != "store_character" and command_name != "revert_selection"):
            view.settings().set(key="has_stored_search", value=False)
            view.settings().set(key="needs_char", value=False)
