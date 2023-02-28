from typing import Optional

import sublime
import sublime_plugin
from sublime import Edit, Region, Selection, View, active_window
from sublime_api import view_add_regions  # pyright: ignore
from sublime_api import view_erase  # pyright:ignore
from sublime_api import view_selection_add_region as add_reg  # pyright: ignore
from sublime_plugin import WindowCommand

from .base import Purpose, char_listener, maybe_rebuild


class CommandModeCommand(WindowCommand):
    def run(self) -> None:
        view: Optional[View] = active_window().active_view()
        active_window().run_command("hide_popup")
        if view is None:
            return
        view.settings().set(key="block_caret", value=True)
        view.settings().set(key="command_mode", value=True)
        view.settings().set(key="needs_char", value=False)
        maybe_rebuild(view)


class DeleteSingleCharCommand(sublime_plugin.TextCommand):
    def run(self, e: Edit, forward=False) -> None:
        s = self.view.sel()
        vi = self.view.id()
        pt = 1 if forward else -1
        [view_erase(vi, e.edit_token, Region(r.b, r.b + pt)) for r in s]


class SmartDeleteLineCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
        buf = self.view
        for region in reversed(buf.sel()):
            if region.empty():
                if region.a == buf.size():
                    reg = buf.full_line(region.begin() - 1)
                else:
                    reg = buf.full_line(region.begin())
            else:
                begin_line, _ = buf.rowcol(region.begin())
                end_line, col = buf.rowcol(region.end())
                if col != 0:
                    end_line += 1
                reg_beg = buf.text_point(begin_line, 0)
                reg_end = buf.text_point(end_line, 0) - 1
                reg = Region(reg_beg, reg_end + 1)
            buf.erase(edit, reg)


class InsertModeCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit, replace=False, before=False) -> None:
        buf = self.view
        if buf.is_read_only():
            sublime.status_message("Buffer is read only")
            return

        for region in reversed(buf.sel()):
            if region.empty():
                if replace:
                    buf.erase(edit, Region(region.a, region.b + 1))
            else:
                if replace:
                    buf.erase(edit, region)
                else:
                    buf.sel().subtract(region)
                    if before:
                        buf.sel().add(region.a)
                    else:
                        buf.sel().add(region.b)

        buf.settings().set(key="block_caret", value=False)
        buf.settings().set(key="command_mode", value=False)


class DeleteRestOfLineAndInsertModeCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
        buf = self.view
        if buf.is_read_only():
            sublime.status_message("Buffer is read only")
            return

        sels: Selection = buf.sel()
        for reg in reversed(sels):
            if reg.empty():
                line = buf.line(reg.begin())
                buf.erase(edit, Region(reg.begin(), line.end()))
            else:
                buf.erase(edit, reg)
        buf.settings().set(key="block_caret", value=False)
        buf.settings().set(key="command_mode", value=False)


class InsertBeforeOrAfterCommand(sublime_plugin.TextCommand):
    def run(self, _, after=False, plusone=False) -> None:
        if plusone == True:
            offset = 1
        else:
            offset = 0
        buf = self.view
        selections = buf.sel()
        for region in selections:
            if region.empty():
                if len(selections) == 1:
                    return
                selections.subtract(region)

            if after == True:
                reg = region.end() + offset
            else:
                reg = region.begin() - offset

            selections.subtract(region)
            selections.add(reg)

        buf.settings().set(key="block_caret", value=False)
        buf.settings().set(key="command_mode", value=False)


class InsertSingleChar(sublime_plugin.TextCommand):
    def run(self, edit: Edit, after=False):
        view: View = self.view
        vi = view.id()
        self.view.settings().set(key="block_caret", value=False)
        self.view.settings().set(key="command_mode", value=False)
        self.view.settings().set(key="needs_char", value=True)
        char_listener(purpose=Purpose.InsertChar)
        for r in view.sel():
            view.sel().subtract(r)
            pt = r.b + 1 if after and r.b == r.a else r.b
            view.insert(edit, pt, " ")
            add_reg(vi, pt, pt - 1 if pt < pt else pt + 1, 0.0)


class ReplaceSingleChar(sublime_plugin.TextCommand):
    def run(self, edit):
        view: View = self.view
        vi = view.id()
        self.view.settings().set(key="block_caret", value=False)
        self.view.settings().set(key="command_mode", value=False)
        self.view.settings().set(key="needs_char", value=True)
        char_listener(purpose=Purpose.InsertChar)

        for r in view.sel():
            add_reg(vi, r.a, r.a - 1 if r.b < r.a else r.a + 1, 0.0)
