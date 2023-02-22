from enum import IntEnum
from typing import List, Optional, Union

import sublime
import sublime_plugin
from sublime import Region, Selection, View, active_window
from sublime_api import view_full_line_from_point as full_line
from sublime_api import view_line_from_point as line
from sublime_api import view_selection_add_region as add_region

from .base import (
    backward,
    build_or_rebuild_ws_for_buffer,
    interesting_regions,
    maybe_rebuild,
)


class Action(IntEnum):
    DO_NOTHING = 0
    CHANGE_TO_BOL = 1
    EXTEND = 2


action: Action = Action.DO_NOTHING
first_view: Union[View, None] = None
old_pos: int = -1


MIN_LINE_THRESHOLD = 5
undo_no_track_cmds = [
    "navigate_word",
    "bol",
    "eol",
    "navigate_by_paragraph_forward",
    "navigate_by_paragraph_backward",
    "expand_selection_to_next",
]


revert_to_normal_mode = [
    "next_character",
    "repeat_next_character",
    "store_character",
    "revert_selection",
    "find_next",
    "find_prev",
    "go_to_nth_match",
]


class BlockCursorOnStartupListener(sublime_plugin.EventListener):
    def on_init(self, views):
        global backward
        for v in views:
            vid = v.id()
            backward[vid].append(list(v.sel()))
            command_mode = v.settings().get(key="command_mode")
            if command_mode:
                v.settings().set(key="block_caret", value=True)


class ModifiedViewListener(sublime_plugin.ViewEventListener):
    def on_modified_async(self):
        view: View = self.view
        if view.element() is None:
            global interesting_regions
            interesting_regions[view.buffer_id()] = {}
            if view.settings().get("command_mode"):
                maybe_rebuild(view)

    def on_load_async(self):
        global interesting_regions
        view: View = self.view
        if view.buffer_id() not in interesting_regions and view.element() is None:
            build_or_rebuild_ws_for_buffer(view, now=True)


class GotoInputListener(sublime_plugin.ViewEventListener):
    def on_query_context(self, key: str, _, __: bool, ___):
        if key != "can_expand":
            return None
        view: View = self.view
        view.settings().set("relative_line_numbers", False)
        global first_view
        global action
        first_view = view
        global old_pos
        if view.sel()[0].empty():
            old_pos = view.sel()[0].b
            action = Action.CHANGE_TO_BOL
        else:
            old_pos = view.sel()[0].a
            action = Action.EXTEND
        return True

    def on_activated(self):
        view: View = self.view
        view.settings().set("relative_line_numbers", True)
        global action
        if action == Action.DO_NOTHING:
            return
        if view.element() is not None:
            return
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


class ReverseSelectionListener(sublime_plugin.EventListener):
    def on_query_context(self, view, key, operator, operand, match_all):
        if key != "reversed_selection":
            return None

        lhs = operand
        if match_all:
            rhs = all([r.a > r.b for r in view.sel()])
        else:
            rhs = view.sel()[0].a > view.sel()[0].b

        return True if operator == sublime.OP_EQUAL and rhs == lhs else False


class NumGroupsListener(sublime_plugin.EventListener):
    def on_query_context(self, view, key, operator, operand, match_all):
        if key != "num_groups":
            return None
        if active_window().num_groups() == 1:
            return True
        return False


class NextCharacterTextListener(sublime_plugin.ViewEventListener):
    # todo: need to clone the queue when view is cloned
    sels_before_cmd = [Region(1)]

    def on_text_command(self, command_name: str, args):
        v = self.view
        vi = self.view.id()

        current_sel = list(self.view.sel())
        if command_name != "smarter_soft_undo":
            if self.should_add(command_name, current_sel, self.sels_before_cmd):
                global backward
                backward[vi].append(current_sel)
        self.sels_before_cmd = current_sel

        if command_name == "set_number":
            pre_command(v, command_name)
            return

        if multiplier := v.settings().get("multiplier"):
            for _ in range(multiplier - 1):
                v.run_command(command_name, args)
            v.settings().erase("multiplier")
            v.settings().erase("lolol")
        pre_command(v, command_name)

    def should_add(
        self,
        cmd_name: str,
        current_sel: List[Region],
        sels_before_cmd: List[Region],
    ) -> bool:
        if cmd_name in undo_no_track_cmds:
            return False

        if len(current_sel) != len(sels_before_cmd):
            return True

        if any(
            reg_a.a != reg_b.a or reg_a.b != reg_b.b
            for reg_a, reg_b in zip(current_sel, sels_before_cmd)
        ) and any(not r.empty() for r in current_sel):
            return True

        current_pos = self.view.rowcol(current_sel[0].b)[0]
        pos_before_cmd = self.view.rowcol(sels_before_cmd[0].b)[0]
        if abs(current_pos - pos_before_cmd) > MIN_LINE_THRESHOLD:
            return True
        return False

    # thanks to Odatnurd from Sublime Discord
    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        """
        :returns: Whether this listener should apply only to the primary view
                  for a file or all of its clones as well.
        """
        return False


class NextCharacterWindowListener(sublime_plugin.EventListener):
    def on_window_command(self, window: sublime.Window, command_name, _):
        pre_command(window.active_view(), command_name)


def pre_command(v: Optional[View], command_name):
    if v is None:
        return

    if v.element() is not None:
        return

    v.erase_phantoms("Sneak")
    v.erase_regions("Sneak")
    v.erase_regions("Sneaks")

    if command_name not in revert_to_normal_mode:
        v.settings().set(key="has_stored_search", value=False)
        v.settings().set(key="needs_char", value=False)
