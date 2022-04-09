from sublime import LAYOUT_INLINE, View, Region, Selection
import sublime
import sublime_plugin
from typing import List, Tuple, Union

# tuple of (char: str, forward: bool, extend: bool)
char_forward_tuple: Tuple[str, bool, bool] = ('', True, False)
matches : List[Region] = []
myhtml="""<body id="my-plugin-feature"><style>div.matcher{{padding: 0 2px 0 1px; margin: 0; border-radius:2px;background-color:{background};color:{color};}}</style><div class="matcher">{counter}</div></body>"""
charlist = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']

class FindNextCharacterBaseCommand(sublime_plugin.TextCommand):
    def set_single(self, forward: bool, extend: bool, search_string: str) -> None:
        view = self.view
        region = view.sel()[0]
        global matches
        matches = []
        bg_color = view.style()["accent"]
        fg_color = view.style()["background"]
        try:
            if forward:
                mybuf = self.view.substr(Region(region.b+1,view.size()))
                new_pt: int = mybuf.index(search_string) + 1
                pt = region.b + new_pt
                if region.a == region.b:
                    if extend:
                        view.sel().add(sublime.Region(region.a, pt + len(search_string)))
                    else:
                        view.sel().clear()
                        view.sel().add(pt)
                elif region.a < region.b:
                    view.sel().add(Region(region.b -1, pt + len(search_string)))
                elif region.a > region.b:
                    if pt > region.a:
                        view.sel().subtract(Region(region.a, region.b))
                        view.sel().add(region.a)
                    else:
                        view.sel().subtract(Region(region.b, pt))
                view.show(view.sel()[0], True)

                for i in range(10):
                    new_pt = mybuf.index(search_string, new_pt) + 1
                    mypt = region.b + new_pt
                    myreg: Region = Region(mypt, mypt+len(search_string))
                    matches.append(myreg)
                    self.view.add_phantom("Sneak", region=myreg, content=myhtml.format(counter=charlist[i], background=bg_color, color=fg_color), layout=LAYOUT_INLINE)
            else:
                offset = 1 if len(search_string) == 1 else 0
                mybuf = self.view.substr(Region(0, region.b-1))[::-1]
                char = search_string[::-1]
                new_pt = mybuf.index(char) + 2
                pt = region.b - new_pt

                if region.a == region.b:
                    if extend:
                        view.sel().add(sublime.Region(region.a, pt -1 + offset))
                    else:
                        view.sel().clear()
                        view.sel().add(pt-1+offset)
                elif region.a < region.b:
                    if pt < region.a:
                        view.sel().subtract(Region(region.b, region.a))
                        view.sel().add(region.a)
                    else:
                        view.sel().subtract(Region(region.b, pt+1))
                elif region.a > region.b:
                    view.sel().add(Region(region.a, pt -1 + offset))
                view.show(view.sel()[0], True)

                for i in range(10):
                    new_pt = mybuf.index(char, new_pt) + 2
                    mypt = region.b - new_pt + offset - 1
                    myreg: Region = Region(mypt, mypt+len(search_string))
                    matches.append(myreg)
                    self.view.add_phantom("Sneak", region=myreg, content=myhtml.format(counter=charlist[i], background=bg_color, color=fg_color), layout=LAYOUT_INLINE)
        except ValueError:
            return


    def set_multiple(self, forward: bool, extend: bool, search_string: str) -> None:
        view = self.view
        regs_to_add: List[Union[Region,int]] = []
        regs_to_subtract: List[Region] = []
        offset = 0

        light_hl: List[Region] = []
        regular_hl: List[Region] = []
        try:
            if forward:
                first_reg = view.sel()[0].b
                mybuf = self.view.substr(Region(first_reg+1,view.size()))
                for region in view.sel():
                    new_pt: int = mybuf.index(search_string, region.b - first_reg +1) + 1 + first_reg
                    if region.a == region.b:
                        if extend:
                            regs_to_add.append(sublime.Region(region.a, new_pt + len(search_string)))
                        else:
                            regs_to_subtract.append(region)
                            regs_to_add.append(new_pt)
                    elif region.a < region.b:
                        regs_to_add.append(Region(region.b -1, new_pt + len(search_string)))
                    elif region.a > region.b:
                        if new_pt > region.a:
                            regs_to_subtract.append(Region(region.a, region.b))
                            regs_to_add.append(region.a)
                        else:
                            regs_to_subtract.append(Region(region.b, new_pt))
                for reg in regs_to_subtract:
                    view.sel().subtract(reg)
                view.sel().add_all(regs_to_add)
                view.show(view.sel()[-1], True)

                offset = offset-1 if not forward else offset
                off_length = offset+len(search_string)
                for i,region in enumerate(view.sel()):
                    new_pt: int = mybuf.index(search_string, region.b - first_reg + 1) + first_reg + 1
                    try:
                        if new_pt == view.sel()[i+1].b:
                            light_hl.append(Region(new_pt+offset, new_pt+off_length))
                        else:
                            regular_hl.append(Region(new_pt+offset, new_pt+off_length))
                    except IndexError:
                        regular_hl.append(Region(new_pt+offset, new_pt+off_length))
                        break
            else:
                offset = 1 if len(search_string) == 1 else 0
                last_reg = view.sel()[-1].b
                mybuf = self.view.substr(Region(0, last_reg-1))[::-1]
                char = search_string[::-1]
                for region in view.sel():
                    pt: int =last_reg - mybuf.index(char, last_reg - region.b) - 2
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
                    view.show(view.sel()[0], True)

                for reg in regs_to_subtract:
                    view.sel().subtract(reg)
                view.sel().add_all(regs_to_add)
                view.show(view.sel()[-1], True)

                offset = offset-1 if not forward else offset
                off_length = offset+len(search_string)
                new_offset = 1 if not forward and len(search_string) == 2 else 0
                for i,region in enumerate(view.sel()):
                    pt: int = last_reg - mybuf.index(char, last_reg - region.b) - 2
                    try:
                        if pt == view.sel()[i-1].b + new_offset:
                            light_hl.append(Region(pt+offset, pt+off_length))
                        else:
                            regular_hl.append(Region(pt+offset, pt+off_length))
                    except IndexError:
                        regular_hl.append(Region(pt+offset, pt+off_length))
                        break

            if regular_hl:
                self.view.add_regions("Sneak", regular_hl, "accent", flags=sublime.DRAW_NO_OUTLINE)
            if light_hl:
                self.view.add_regions("Sneaks", light_hl, "light", flags=sublime.DRAW_NO_OUTLINE)

        except IndexError:
            return

    def execute(self, forward: bool, search_string: str, extend: bool) -> None:
        if len(self.view.sel()) == 1:
            self.set_single(forward, extend, search_string)
        else:
            self.set_multiple(forward, extend, search_string)

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
        view.show(sels[0], True)
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
