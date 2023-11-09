from copy import deepcopy

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

if sys.version_info[:2] == (3, 3):
    import traceback

    importer = "unknown"
    for entry in reversed(traceback.extract_stack()[:-1]):
        if entry[0].startswith("<frozen importlib"):
            continue
        importer = entry[0]
        break
    print('error: Default.history_list was imported on Python 3.3 by "%s"' % importer)


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


class JumpRecord:
    __slots__ = ["key", "view", "sheets"]

    def __init__(self, key, view, selections, sheets):
        # The View.get_regions() key to retrieve the selections
        self.key = key
        # The sublime.View to focus
        self.view = view
        # A set of sublime.Sheet objects to be selected
        self.sheets = sheets

        view.add_regions(key, selections)

    def __repr__(self):
        return "JumpRecord(%r, %r, %r, %r)" % (
            self.key,
            self.view,
            self.selections,
            self.sheets,
        )

    def __del__(self):
        self.view.erase_regions(self.key)

    def update(self, view, selections, sheets):
        """
        Update the record with new details

        :param view:
            The new sublime.View for the record

        :param selections:
            A list of sublime.Region objects to set the selections to

        :param sheets:
            A set of sublime.Sheet objects for the selected sheets
        """

        view.add_regions(self.key, selections)
        if self.view != view:
            self.view.erase_regions(self.key)
            self.view = view
        self.sheets = sheets

    @property
    def selections(self):
        """
        The selections are not stored in this object since modifications to
        the view will cause the regions to be moved. By storing the regions in
        the text buffer, it will deal with shifting them around.

        :return:
            A list of sublime.Region objects representing the selections
        """

        return self.view.get_regions(self.key)


def _log(message):
    """
    Prints a log to the console, prefixed by the plugin name

    :param message:
        A str of the message to print
    """

    print("history_list: %s" % message)


class JumpHistory:
    """
    Stores the current jump history
    """

    LOG = False
    LIST_LIMIT = 120
    TIME_BETWEEN_RECORDING = 1
    TIME_AFTER_ACTIVATE = 0.1

    def __init__(self):
        # A stack of JumpRecord objects
        self.history_list = []

        # The string name of the command the user most recently executed
        self.current_command = ""
        # If self.current_command was different from the preceeding command
        self.different_command = False

        # A float unix timestamp of when self.history_list was last modified
        self.last_change_time = 0
        # If the last modification to self.history_list was from on_activated()
        self.last_was_activation = False

        # A negative integer index in self.history_list of where the user is
        # located. This allows them to jump forward and backward.
        self.current_item = -1

        # Used to generate the region names where the selection is stored
        self.key_counter = 0

    def push_selection(self, view, selection=None, is_activation=False):
        """
        Possibly records the current selections in the view to the history.
        Will skip recording if the current state of the view would result in
        history entries the user would find confusing.

        :param view:
            A sublime.View object

        :param selection:
            None to use the view's current selection, otherwise a list of
            sublime.Region objects to use as the selections to record

        :param is_activation:
            A bool - if the push event is triggered by on_activated()
        """

        if (
            self.current_command == "jump_back"
            or self.current_command == "jump_forward"
            or self.current_command == "soft_undo"
            or self.current_command == "soft_redo"
            or self.current_command == "undo"
            or self.current_command == "redo_or_repeat"
            or self.current_command == "redo"
            or self.current_command == "smart_find_word"
            or self.current_command == "show_panel"  # find typing
        ):
            self.current_command = ":empty"
            return

        if view.settings().get("multiplier") is not None:
            return

        if view.settings().get("search_in_selection") is not None:
            return

        # We need the view to be loaded in order to interact with regions
        # and the selection
        if view.is_loading():
            kwargs = {"selection": selection, "is_activation": is_activation}
            sublime.set_timeout(lambda: self.push_selection(view, **kwargs), 100)
            return

        if selection is not None:
            cur_sel = selection

        else:
            cur_sel = list(view.sel())
            to_ignore = view.get_regions("jump_ignore_selection")
            if to_ignore:
                view.erase_regions("jump_ignore_selection")
            if to_ignore == cur_sel:
                if self.LOG:
                    _log("ignoring selection %r" % cur_sel)
                return

        sheets = set()
        window = view.window()
        if window:
            sheets = set(window.selected_sheets())

        temp_item = self.current_item
        if self.history_list != []:
            while True:
                record = self.history_list[temp_item]
                prev_sel = record.selections
                if prev_sel or temp_item <= -len(self.history_list):
                    break
                temp_item -= 1

            # Don't record duplicate history records
            if prev_sel and record.view == view and prev_sel == cur_sel:
                return

            # There are two situations in which we overwrite the previous
            # record:
            #  1. When a command is repeated in quick succession. This
            #     prevents lots of records when editing.
            #  2. When the last item was from on_activate, we don't want to
            #     mark that as a real record, otherwise things like
            #     Goto Definition result in two records the user has to jump
            #     back through.
            change = time.time() - self.last_change_time

            just_activated = (
                change <= self.TIME_AFTER_ACTIVATE and self.last_was_activation
            )
            duplicate_command = (
                change <= self.TIME_BETWEEN_RECORDING
                and not self.different_command
                and record.view == view
            )

            if self.current_command in [
                "smarter_find_under_expand",
                "find_under_expand",
            ]:
                record.update(view, cur_sel, sheets)
            elif just_activated or duplicate_command:
                record.update(view, cur_sel, sheets)
                if self.LOG:
                    _log("updated record %d to %r" % (temp_item, record))
                self.last_change_time = time.time()
                self.last_was_activation = False if just_activated else is_activation
                return

            # we are searching, don't record every selection change
            if (
                len(prev_sel) == 1 == len(cur_sel)
                and cur_sel[0].b - 1 == prev_sel[0].b
                and cur_sel[0].a == prev_sel[0].a
            ):
                del self.history_list[temp_item]
                return

        if self.current_item != -1:
            delete_index = self.current_item + 1
            del self.history_list[delete_index:]
            self.current_item = -1
            if self.LOG:
                _log("removed newest %d records, pointer = -1" % abs(delete_index))

        key = self.generate_key()
        self.history_list.append(JumpRecord(key, view, cur_sel, sheets))
        if self.LOG:
            _log("adding %r" % self.history_list[-1])

        if len(self.history_list) > self.LIST_LIMIT:
            # We remove more than one at a time so we don't call this every time
            old_len = len(self.history_list)
            new_len = old_len - int(self.LIST_LIMIT / 3)
            if self.LOG:
                _log(
                    "removed oldest %d records, pointer = %d"
                    % (old_len - new_len, self.current_item)
                )
            del self.history_list[:new_len]

        self.last_change_time = time.time()
        self.last_was_activation = is_activation

        # This ensures the start of a drag_select gets a unique entry, but
        # then all subsequent selections get merged into a single entry
        if self.current_command == "post:drag_select":
            self.different_command = False
        elif self.current_command == "drag_select":
            self.current_command = "post:drag_select"
            self.different_command = True

    def jump_back(self, in_widget):
        """
        Returns info about where the user should jump back to, modifying the
        index of the current item.

        :param in_widget:
            A bool indicating if the focus is currently on a widget. In this
            case we don't move the current_item, just jump to it.

        :return:
            A 3-element tuple:
            0: sublime.View - the view to focus on
            1: a list of sublime.Region objects to use as the selection
            2: a set of sublime.Sheet objects that should be selected
        """

        temp_item = self.current_item

        cur_record = self.history_list[temp_item]
        cur_sel = cur_record.selections

        while True:
            if temp_item == -len(self.history_list):
                return None, [], []

            if not in_widget:
                temp_item -= 1
            record = self.history_list[temp_item]
            record_sel = record.selections
            if in_widget:
                break

            if record_sel and (cur_record.view != record.view or cur_sel != record_sel):
                if not cur_sel:
                    cur_sel = record_sel
                else:
                    break

        self.current_item = temp_item
        if self.LOG:
            _log("setting pointer = %d" % self.current_item)

        return record.view, record_sel, record.sheets

    def jump_forward(self, in_widget):
        """
        Returns info about where the user should jump forward to, modifying
        the index of the current item.

        :param in_widget:
            A bool indicating if the focus is currently on a widget. In this
            case we don't move the current_item, just jump to it.

        :return:
            A 3-element tuple:
            0: sublime.View - the view to focus on
            1: a list of sublime.Region objects to use as the selection
            2: a set of sublime.Sheet objects that should be selected
        """

        temp_item = self.current_item

        cur_record = self.history_list[temp_item]
        cur_sel = cur_record.selections

        while True:
            if temp_item == -1:
                return None, [], []

            if not in_widget:
                temp_item += 1
            record = self.history_list[temp_item]
            record_sel = record.selections
            if in_widget:
                break

            if record_sel and (cur_record.view != record.view or cur_sel != record_sel):
                if not cur_sel:
                    cur_sel = record_sel
                else:
                    break

        self.current_item = temp_item
        if self.LOG:
            _log("setting pointer = %d" % self.current_item)

        return record.view, record_sel, record.sheets

    def set_current_item(self, index):
        """
        Modifies the index of the current item in the history list

        :param index:
            A negative integer, with -1 being the last item
        """

        self.current_item = index
        if self.LOG:
            _log("setting pointer = %d" % self.current_item)

    def record_command(self, command):
        """
        Records a command being run, used to determine when changes to the
        selection should be recorded

        :param command:
            A string of the command that was run. The string ":text_modified"
            should be passed when the buffer is modified. This is used in
            combination with the last command to ignore recording undo/redo
            changes.
        """

        self.different_command = self.current_command != command

        # We don't track text modifications when they occur due to
        # the undo/redo stack. Otherwise we'd end up pusing new
        # selections, and undo/redo is handled by
        # JumpHistoryUpdater.on_post_text_command().
        if command == ":text_modified" and (
            self.current_command == "soft_undo"
            or self.current_command == "soft_redo"
            or self.current_command == "undo"
            or self.current_command == "redo_or_repeat"
            or self.current_command == "redo"
        ):
            return

        self.current_command = command

    def reorient_current_item(self, view):
        """
        Find the index of the item in the history list that matches the
        current view state, and update the current_item with that

        :param view:
            The sublime.View object to use when finding the correct current
            item in the history list
        """

        cur_sel = list(view.sel())
        for i in range(-1, -len(self.history_list) - 1, -1):
            while True:
                record = self.history_list[i]
                record_sel = record.selections
                if record_sel or i <= -len(self.history_list):
                    break
                i -= 1

            if record_sel and record.view == view and record_sel == cur_sel:
                self.current_item = i
                if self.LOG:
                    _log("set pointer = %d" % self.current_item)
                return

    def remove_view(self, view):
        """
        Purges all history list items referring to a specific view

        :param view:
            The sublime.View being removed
        """

        sheet = view.sheet()
        removed = 0
        for i in range(-len(self.history_list), 0):
            record = self.history_list[i]
            if record.view == view:
                del self.history_list[i]
                removed += 1
                if self.current_item < i:
                    self.current_item += 1
            elif sheet in record.sheets:
                record.sheets.remove(sheet)
        if self.LOG:
            _log(
                "removed %r including %d records, pointer = %d"
                % (view, removed, self.current_item)
            )

    def generate_key(self):
        """
        Creates a key to be used with sublime.View.add_regions()

        :return:
            A string key to use when storing and retrieving regions
        """

        # generate enough keys for 5 times the jump history limit
        # this can still cause clashes as new history can be erased when we jump
        # back several steps and jump again.
        self.key_counter += 1
        self.key_counter %= self.LIST_LIMIT * 5
        return "jump_key_" + hex(self.key_counter)


# dict from window id to JumpHistory
jump_history_dict = {}


def _history_for_view(view: Optional[View]):
    """
    Fetches the JumpHistory object for the view

    :param view:
        A sublime.Window object

    :return:
        A JumpHistory object
    """

    global jump_history_dict

    if not view:
        return JumpHistory()
    else:
        return jump_history_dict.setdefault(view.id(), JumpHistory())


# Compatibility shim to not raise ImportError with Anaconda and other plugins
# that manipulated the JumpHistory in ST3
get_jump_history_for_window = _history_for_view


class JumpHistoryUpdater(sublime_plugin.EventListener):
    """
    Listens on the sublime text events and push the navigation history into the
    JumpHistory object
    """

    def _valid_view(self, view):
        """
        Determines if we want to track the history for a view

        :param view:
            A sublime.View object

        :return:
            A bool if we should track the view
        """

        return view is not None and not view.settings().get("is_widget")

    def on_modified(self, view):
        if not self._valid_view(view):
            return

        history = _history_for_view(view)
        if history.LOG:
            _log("%r was modified" % view)
        history.record_command(":text_modified")

    def on_selection_modified(self, view):
        if not self._valid_view(view):
            return

        history = _history_for_view(view)
        if history.LOG:
            _log("%r selection was changed" % view)
        history.push_selection(view)

    def on_activated(self, view):
        if not self._valid_view(view):
            return

        history = _history_for_view(view)
        if history.LOG:
            _log("%r was activated" % view)
        history.push_selection(view, is_activation=True)

    def on_text_command(self, view, name, args):
        if not self._valid_view(view):
            return

        history = _history_for_view(view)
        if history.LOG:
            _log("%r is about to run text command %r" % (view, name))
        history.record_command(name)

    def on_post_text_command(self, view, name, args):
        if not self._valid_view(view):
            return

        if name == "undo" or name == "redo_or_repeat" or name == "redo":
            _history_for_view(view).reorient_current_item(view)

        if name == "soft_redo":
            _history_for_view(view).set_current_item(-1)

    def on_window_command(self, window, name, args):
        view = window.active_view()
        if not self._valid_view(view):
            return

        history = _history_for_view(view)
        if history.LOG:
            _log("%r is about to run window command %r" % (view, name))
        history.record_command(name)

    # TODO: We need an on_pre_closed_sheet in the future since we currently
    # leave stale ImageSheet() and HtmlSheet() references in the JumpHistory.
    def on_pre_close(self, view):
        if not self._valid_view(view):
            return

        _history_for_view(view).remove_view(view)


class _JumpCommand(sublime_plugin.TextCommand):
    VALID_WIDGETS = {
        "find:input",
        "incremental_find:input",
        "replace:input:find",
        "replace:input:replace",
        "find_in_files:input:find",
        "find_in_files:input:location",
        "find_in_files:input:replace",
        "find_in_files:output",
    }

    def _get_window(self):
        """
        Returns the (non-widget) view to get the history for

        :return:
            None or a sublime.Window to get the history from
        """

        if (
            not self.view.settings().get("is_widget")
            or self.view.element() in self.VALID_WIDGETS
        ):
            return self.view.window()

        return None

    def _perform_jump(self, window, view, selections, sheets, clear):
        """
        Restores the window to the state where the view has the selections

        :param window:
            The sublime.Window containing the view

        :param view:
            The sublime.View to focus

        :param selections:
            A list of sublime.Region objects to set the selection to

        :param sheets:
            A list of sublime.Sheet objects that should be (minimally)
            selected. If the currently selected sheets is a superset of these,
            then no sheet selection changes will be made.
        """

        # Reduce churn by only selecting sheets when one is not visible
        if set(sheets) - set(window.selected_sheets()):
            window.select_sheets(sheets)
        window.focus_view(view)

        if clear:
            view.sel().clear()
        view.sel().add_all(selections)
        view.show(selections[0], True)

        sublime.status_message("")

    def is_enabled(self):
        return self._get_window() is not None


class JumpBackCommand(_JumpCommand):
    def run(self, edit, clear: bool = True):
        window = self._get_window()
        view = self.view
        jump_history = _history_for_view(view)

        is_widget = self.view.settings().get("is_widget")
        _, selections, sheets = jump_history.jump_back(is_widget)
        if not selections:
            sublime.status_message("Already at the earliest position")
            return

        if jump_history.LOG:
            _log("jumping back to %r, %r, %r" % (view, selections, sheets))
        self._perform_jump(window, view, selections, sheets, clear)


class JumpForwardCommand(_JumpCommand):
    def run(self, edit, clear: bool = True):
        window = self._get_window()
        view = self.view
        jump_history = _history_for_view(view)

        is_widget = self.view.settings().get("is_widget")
        view, selections, sheets = jump_history.jump_forward(is_widget)
        if not selections:
            sublime.status_message("Already at the newest position")
            return

        if jump_history.LOG:
            _log("jumping forward to %r, %r, %r" % (view, selections, sheets))
        self._perform_jump(window, view, selections, sheets, clear)


def _2_int_list(value):
    """
    :param value:
        The value to check

    :return:
        A bool is the value is a list with 2 ints
    """

    if not isinstance(value, list):
        return False

    if len(value) != 2:
        return False

    if not isinstance(value[0], int):
        return False

    return isinstance(value[1], int)


class AddJumpRecordCommand(sublime_plugin.TextCommand):
    """
    Allows packages to add a jump point without changing the selection
    """

    def run(self, edit, selection):
        if not self.view.settings().get("is_widget"):
            view = self.view
        else:
            view = self.view.window().active_view()

        regions = []
        type_error = False

        if isinstance(selection, int):
            regions.append(sublime.Region(selection, selection))

        elif isinstance(selection, list):
            if _2_int_list(selection):
                regions.append(sublime.Region(selection[0], selection[1]))
            else:
                for s in selection:
                    if _2_int_list(s):
                        regions.append(sublime.Region(s[0], s[1]))
                    elif isinstance(s, int):
                        regions.append(sublime.Region(s, s))
                    else:
                        type_error = True
                        break
        else:
            type_error = True

        if type_error:
            raise TypeError(
                "selection must be an int, 2-int list, " "or list of 2-int lists"
            )

        jump_history = _history_for_view(view)
        jump_history.push_selection(view, selection=regions)


def plugin_unloaded():
    # Clean up the View region side-effects of the JumpRecord objects
    jump_history_dict.clear()


class FancyClonePaneCommand(WindowCommand):
    def run(self) -> None:
        w = self.window

        num_groups = w.num_groups()
        next_group = w.active_group() + 1

        view = w.active_view()
        if view is None:
            return
        old_id = view.id()
        v_bid = view.buffer_id()

        carets = list(view.sel()) or [0]

        global jump_history_dict
        if num_groups > next_group:
            for v in w.views_in_group(next_group):
                if v_bid == v.buffer_id():
                    return  # only unique buffers per group

            w.run_command("clone_file")

            new_view = w.active_view()
            if new_view is None:
                return

            w.move_sheets_to_group(sheets=[new_view.sheet()], group=next_group)

            sels = new_view.sel()
            sels.clear()
            [sels.add(c) for c in carets]
            new_view.show_at_center(carets[0])
            jump_history_dict[new_view.id()] = deepcopy(jump_history_dict[old_id])

        elif num_groups < MAX_NUM_GROUPS:
            w.run_command("clone_file")
            w.run_command("new_pane")

            new_view = w.active_view()
            if new_view is None:
                return

            sels = new_view.sel()
            sels.clear()
            [sels.add(c) for c in carets]
            new_view.show_at_center(carets[0])

            jump_history_dict[new_view.id()] = deepcopy(jump_history_dict[old_id])


class FancyMoveBufferToNextPaneCommand(WindowCommand):
    def run(self) -> None:
        w = self.window

        if len(w.views_in_group(w.active_group())) < 2:
            return

        num_groups = w.num_groups()
        next_group = w.active_group() + 1

        if (view := w.active_view()) is None:
            return
        v_bid = view.buffer_id()
        change_scratch_status = False
        if num_groups > next_group:
            for v in w.views_in_group(next_group):
                if v_bid == v.buffer_id():
                    if v.is_dirty():
                        change_scratch_status = True
                        v.set_scratch(True)
                    v.close()
                    break

            w.move_sheets_to_group(sheets=[view.sheet()], group=next_group)
            if change_scratch_status:
                view.set_scratch(False)

        elif num_groups < MAX_NUM_GROUPS:
            w.run_command("new_pane")


class FancyMoveBufferToPrevPaneCommand(WindowCommand):
    def run(self) -> None:
        w = self.window
        if w.num_groups() < 2:
            return

        view = w.active_view()
        if view is None:
            return

        global jump_history_dict
        active_group = w.active_group()
        if len(w.views_in_group(active_group)) < 2 or active_group == 0:
            w.run_command("close_pane")
        else:
            prev_group = w.active_group() - 1
            w.move_sheets_to_group(sheets=[view.sheet()], group=prev_group)

        view = w.active_view()
        if view is None:
            return
        v_id = view.id()

        buffers = {view.buffer_id()}
        scratch_buffers = set()
        for v in w.views_in_group(w.active_group()):
            if v_id != v.id() and v.buffer_id() in buffers:
                if not v.is_scratch() and v.is_dirty():
                    scratch_buffers.add(v.buffer())
                    v.set_scratch(True)

                mit_id = v.id()
                v.close()
                jump_history_dict.pop(mit_id)
            else:
                buffers.add(v.buffer_id())

        for b in scratch_buffers:
            b.primary_view().set_scratch(False)


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


class NewPaneCommand(sublime_plugin.WindowCommand):
    def new_pane(self, window, move_sheet, max_columns):
        cur_sheet = window.active_sheet()

        layout = window.get_layout()
        num_panes = len(layout["cells"])

        cur_index = window.active_group()

        rows = layout["rows"]
        cols = layout["cols"]
        cells = layout["cells"]

        if cells != assign_cells(num_panes, max_columns):
            # Current layout doesn't follow the automatic method, reset everyting
            num_rows, num_cols = rows_cols_for_panes(num_panes + 1, max_columns)
            rows = create_splits(num_rows)
            cols = create_splits(num_cols)
            cells = assign_cells(num_panes + 1, max_columns)
        else:
            # Adjust the current layout, keeping the user selected column widths
            # where possible
            num_cols = len(cols) - 1
            num_rows = len(rows) - 1

            # determine row or coloumn from screen width:
            view = self.window.active_view()
            if num_panes == 1 and view is not None:
                width, height = view.viewport_extent()
                if height > width:
                    num_rows += 1
                    rows = create_splits(num_rows)
                    max_columns = 1
                else:
                    num_cols += 1
                    cols = create_splits(num_cols)

            # insert a new row or a new col
            elif num_cols < max_columns:
                num_cols += 1
                cols = create_splits(num_cols)
            else:
                num_rows += 1
                rows = create_splits(num_rows)

            cells = assign_cells(num_panes + 1, max_columns)

        window.set_layout({"cells": cells, "rows": rows, "cols": cols})
        window.settings().set("last_automatic_layout", cells)

        # Move all the sheets so the new pane is created in the correct location
        for i in reversed(range(0, num_panes - cur_index - 1)):
            current_selection = window.selected_sheets_in_group(cur_index + i + 1)
            window.move_sheets_to_group(
                window.sheets_in_group(cur_index + i + 1),
                cur_index + i + 2,
                select=False,
            )
            window.select_sheets(current_selection)

        if move_sheet:
            transient = window.transient_sheet_in_group(cur_index)
            if transient is not None and cur_sheet.sheet_id == transient.sheet_id:
                # transient sheets may only be moved to index -1
                window.set_sheet_index(cur_sheet, cur_index + 1, -1)
            else:
                selected_sheets = window.selected_sheets_in_group(cur_index)
                window.move_sheets_to_group(selected_sheets, cur_index + 1)
                window.focus_sheet(cur_sheet)
        else:
            window.focus_group(cur_index)

    def run(self, move=True):
        max_columns = self.window.template_settings().get("max_columns", MAX_COLUMNS)
        self.new_pane(self.window, move, max_columns)


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
    # v.run_command("hide_popup")

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
            return
        w.focus_group(new_idx)

    def on_init(self, views):
        for v in views:
            if v.element() is not None:
                continue

            if v.settings().get(key="command_mode"):
                v.settings().set(key="block_caret", value=True)


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

    def on_query_context(self, key: str, operator, operand, match_all: bool):
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
            old_pos = view.sel()[0].b
            action = Action.CHANGE_TO_BOL
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
