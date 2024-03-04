from sublime_plugin import WindowCommand

MAX_NUM_GROUPS = 3
import re
import sys
import time
from enum import IntEnum
from typing import Optional, Union

import sublime
import sublime_plugin
from sublime import Selection, View, active_window
from sublime_api import view_cached_substr as substr  # pyright: ignore
from sublime_api import view_full_line_from_point as full_line  # pyright: ignore
from sublime_api import view_line_from_point as line  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore



class Action(IntEnum):
    DO_NOTHING = 0
    CHANGE_TO_BOL = 1
    EXTEND = 2


action: Action = Action.DO_NOTHING
first_view: Union[View, None] = None
old_pos: int = -1


revert_to_normal_mode = [
    "sneak",
    "repeat_sneak",
    "store_character",
    "revert_selection",
    "find_next",
    "find_prev",
    "go_to_nth_match",
]





class FocusViewCommand(WindowCommand):
    """
    The missing command for switching focus from side bar to view
    """

    def run(self) -> None:
        w = self.window
        active_group = w.active_group()
        if (sheet := w.active_sheet_in_group(active_group)) is None:
            return

        w.focus_sheet(sheet)




"""
Listeners start here
"""

def pre_command(v: Optional[View], command_name):
    if v is None:
        return

    if v.element() is not None:
        return

    v.erase_phantoms("Sneak")
    v.erase_regions("Sneak")
    v.erase_regions("copy_regions")
    v.erase_regions("Sneaks")

    if command_name not in revert_to_normal_mode:
        v.settings().set(key="has_stored_search", value=False)
        v.settings().set(key="needs_char", value=False)





class WindowListener(sublime_plugin.EventListener):
    def on_query_context(
        self, view, key, operator, operand, match_all
    ) -> Optional[bool]:
        if key == "search_in_selection":
            w = active_window()
            if setting := w.settings().get(key="search_in_selection"):
                w.settings().erase("search_in_selection")
            return setting == operand

    def on_window_command(self, window: sublime.Window, command_name, _):
        pre_command(window.active_view(), command_name)




class BufferListener(sublime_plugin.ViewEventListener):
    # thanks to Odatnurd from Sublime Discord
    # useful for relative line numbers, build_or_rebuild_ws_for_buffer

    regex = re.compile(r"^(\n|.\b)[\w]+(\b.|\n)$")

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        """
        :returns: Whether this listener should apply only to the primary view
                  for a file or all of its clones as well.
        """
        return False

    def on_query_context(self, key: str, operator: str, operand: bool, match_all: bool) ->Optional[bool]:
        view: View = self.view
        if view.element() is not None:
            return

        if key == "clipboard_newline":
            return (sublime.get_clipboard()[-1] == '\n') == operand

        if key == "word_boundary":
            reg = view.sel()[-1]
            a = reg.begin()
            b = reg.end()
            mysubstr: str = substr(view.id(), a - 1, b + 1)
            if a == 0:
                mysubstr = f"\a{mysubstr}"
            if b == view.size():
                mysubstr += "\a"
            return bool(self.regex.match(mysubstr)) == operand

        if key == "side_bar_visible":
            return active_window().is_sidebar_visible() == operand

        if key == "has_find_results":
            w = view.window()
            if w is None:
                return
            if (panelView:= w.find_output_panel("find_results")) is not None:
                return (panelView.size() > 0) == operand

        if key == "reversed_selection":
            if match_all:
                rhs = all([r.a > r.b for r in view.sel()])
            else:
                rhs = view.sel()[0].a > view.sel()[0].b
            return operator == sublime.OP_EQUAL and rhs == operand


    def on_activated(self):
        view: View = self.view
        if view.element() is not None:
            return

        global action
        if action == Action.DO_NOTHING:
            return

        for v in active_window().views():
            v.settings().set("relative_line_numbers", True)

        global first_view
        if first_view is None:
            return

        sels: Selection = view.sel()
        if sels[0].end() == old_pos:
            action = Action.DO_NOTHING
            return

        vid = view.id()

        if action == Action.EXTEND and vid == first_view.id():
            new_pos = view.sel()[0].b
            if new_pos > old_pos:
                start = line(vid, old_pos).begin()
                end = full_line(vid, new_pos).end()
            else:
                start = full_line(vid, old_pos).end()
                end = line(vid, new_pos).begin()
            sels.clear()
            add_region(vid, start, end, 0.0)
        else:
            next_res, _ = view.find(r"\S|^$|^\s+$", view.sel()[0].a)
            view.sel().clear()
            view.sel().add(next_res)

        action = Action.DO_NOTHING

    def on_modified(self):
        pre_command(self.view, "nonce")

    def on_text_command(self, command_name: str, args):
        pre_command(self.view, command_name)

