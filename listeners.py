import re
from enum import IntEnum
from typing import Optional, Union

import sublime
import sublime_plugin
from sublime import Selection, View, active_window
from sublime_api import view_cached_substr as substr  # pyright: ignore
from sublime_api import view_full_line_from_point as full_line  # pyright: ignore
from sublime_api import view_line_from_point as line  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore

from .base import build_or_rebuild_ws_for_buffer, interesting_regions, maybe_rebuild


class Action(IntEnum):
    DO_NOTHING = 0
    CHANGE_TO_BOL = 1
    EXTEND = 2


action: Action = Action.DO_NOTHING
first_view: Union[View, None] = None
old_pos: int = -1


revert_to_normal_mode = [
    "next_character",
    "repeat_next_character",
    "store_character",
    "revert_selection",
    "find_next",
    "find_prev",
    "go_to_nth_match",
]


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


def assign_cells(num_panes, max_columns):
    num_rows, num_cols = rows_cols_for_panes(num_panes, max_columns)

    cells = []
    for i in range(0, num_panes):
        if i < (max_columns - 1):
            cells.append([i, 0, i + 1, num_rows])
        else:
            row = i - (max_columns - 1)
            cells.append([num_cols - 1, row, num_cols, row + 1])
    return cells


def create_splits(num_splits):
    return [0.0] + [1.0 / num_splits * i for i in range(1, num_splits)] + [1.0]


def rows_cols_for_panes(num_panes, max_columns):
    if num_panes > max_columns:
        num_cols = max_columns
        num_rows = num_panes - num_cols + 1
    else:
        num_cols = num_panes
        num_rows = 1
    return num_rows, num_cols


MAX_COLUMNS = 2


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

    def on_close(self, view: View):
        w = active_window()
        max_columns = w.template_settings().get("max_columns", MAX_COLUMNS)
        if len(w.sheets_in_group(w.active_group())) > 0:
            return

        idx = w.active_group()
        layout = w.get_layout()
        num_panes = len(layout["cells"])

        if num_panes == 1:
            return

        for i in range(idx, w.num_groups()):
            current_selection = w.selected_sheets_in_group(i)
            w.move_sheets_to_group(w.sheets_in_group(i), i - 1)
            w.select_sheets(current_selection)

        rows = layout["rows"]
        cols = layout["cols"]
        cells = layout["cells"]

        if layout["cells"] != assign_cells(num_panes, max_columns):
            num_rows, num_cols = rows_cols_for_panes(num_panes - 1, max_columns)
            rows = create_splits(num_rows)
            cols = create_splits(num_cols)
            cells = assign_cells(num_panes - 1, max_columns)
        else:
            num_cols = len(cols) - 1
            num_rows = len(rows) - 1

            if num_rows > 1:
                num_rows -= 1
                rows = create_splits(num_rows)
            else:
                num_cols -= 1
                cols = create_splits(num_cols)

            cells = assign_cells(num_panes - 1, max_columns)

        w.set_layout({"cells": cells, "rows": rows, "cols": cols})
        w.settings().set("last_automatic_layout", cells)

        new_idx = idx - 1
        if new_idx < 0:
            new_idx = 0
        w.focus_group(new_idx)

    def on_init(self, views):
        for v in views:
            if v.element() is not None:
                continue

            if v.settings().get(key="command_mode"):
                v.settings().set(key="block_caret", value=True)

            global interesting_regions
            if v.buffer_id() not in interesting_regions:
                build_or_rebuild_ws_for_buffer(v, now=True)


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

    def on_query_context(self, key: str, operator, operand: bool, match_all: bool):
        view: View = self.view
        if view.element() is not None:
            return

        if key == "word_boundary":
            reg = view.sel()[-1]
            a = reg.begin()
            b = reg.end()
            mysubstr = substr(view.id(), a - 1, b + 1)
            if a == 0:
                mysubstr = f"\a{mysubstr}"
            if b == view.size():
                mysubstr += "\a"
            return bool(self.regex.match(mysubstr)) == operand

        if key == "side_bar_visible":
            return active_window().is_sidebar_visible() == operand

        if key == "num_groups":
            return active_window().num_groups() == operand

        if key == "reversed_selection":
            if match_all:
                rhs = all([r.a > r.b for r in view.sel()])
            else:
                rhs = view.sel()[0].a > view.sel()[0].b
            return operator == sublime.OP_EQUAL and rhs == operand

        if key == "can_expand":
            for v in active_window().views():
                v.settings().set("relative_line_numbers", False)
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

    def on_text_command(self, command_name: str, args):
        special_cmds = ["expand_selection_to_next", "insert_mode"]
        v = self.view
        if v.element() is not None:
            return

        if command_name in special_cmds:
            pre_command(v, command_name)
            return

        if command_name != "set_number" and (
            multiplier := v.settings().get("multiplier")
        ):
            for _ in range(multiplier - 1):
                v.run_command(command_name, args)
            v.settings().erase("multiplier")
            v.settings().erase("set_number")
        pre_command(v, command_name)
