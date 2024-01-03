from typing import Optional

import sublime
import sublime_plugin
from sublime import Edit, Region, Selection, View, active_window
from sublime_api import view_add_regions  # pyright: ignore
from sublime_api import view_erase  # pyright:ignore
from sublime_api import view_selection_add_point as add_pt  # pyright: ignore
from sublime_api import view_selection_add_region as add_reg  # pyright: ignore
from sublime_plugin import WindowCommand


class CommandModeCommand(WindowCommand):
    def run(self) -> None:
        view: Optional[View] = active_window().active_view()
        if view is None:
            return
        view.settings().set(key="block_caret", value=True)
        view.settings().set(key="command_mode", value=True)
        view.settings().set(key="needs_char", value=False)
        view.run_command("hide_popup")


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


class CallbackCommand(sublime_plugin.TextCommand):
    def run(self, edit, cmd, args):
        callback = {"cmd": cmd, "args": args}
        self.view.settings().set("callback", callback)


class InsertModeCommand(sublime_plugin.TextCommand):
    def change_case(self) -> bool:
        v = self.view

        if (multiplier := self.view.settings().get("multiplier")) is not None:
            if multiplier == 1:
                v.run_command("upper_case")
            elif multiplier == 2:
                v.run_command("lower_case")
            elif multiplier == 3:
                v.run_command("title_case")
            elif multiplier == 4:
                v.run_command("convert_to_snake")
            elif multiplier == 5:
                v.run_command("convert_to_pascal")
            else:
                return False

            return True
        return False

    def run(self, edit: Edit, after=False, before=False) -> None:
        v = self.view
        if v.settings().get("set_number") is not None:
            v.settings().erase("set_number")
            if before and not after:
                self.change_case()
            elif not before and after:
                if (multiplier := v.settings().get("multiplier")) is not None:
                    if multiplier == 1:
                        v.run_command("transpose")
                    elif multiplier == 2:
                        v.run_command("toggle_true_false")
            v.settings().erase("multiplier")
            return

        if v.is_read_only():
            sublime.status_message("Buffer is read only")
            return

        for r in reversed(v.sel()):
            begin = r.begin()
            end = r.end()
            if r.empty():
                end += 1

            start = end if after else begin
            stop = begin if before else end

            v.sel().subtract(r)
            new_region = Region(stop, start) if r.a > r.b else Region(start, stop)
            v.sel().add(new_region)
            if before and after:
                v.erase(edit, new_region)

        v.settings().set(key="block_caret", value=False)
        v.settings().set(key="command_mode", value=False)


class DeleteRestOfLineAndInsertModeCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
        v = self.view
        if v.is_read_only():
            sublime.status_message("Buffer is read only")
            return

        sels: Selection = v.sel()
        for reg in reversed(sels):
            if reg.empty():
                line = v.line(reg.begin())
                v.erase(edit, Region(reg.begin(), line.end()))
            else:
                v.erase(edit, reg)
        v.settings().set(key="block_caret", value=False)
        v.settings().set(key="command_mode", value=False)


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


class InsertSpaceCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit):
        view: View = self.view
        vi = view.id()
        for r in view.sel():
            view.sel().subtract(r)
            view.insert(edit, r.b, " ")
            add_pt(vi, r.b if r.b < r.a else r.b + 1, 0.0)


class ReplaceSingleChar(sublime_plugin.TextCommand):
    def run(self, edit, character):
        view: View = self.view
        for r in view.sel():
            if r.empty():
                view.replace(edit, Region(r.a, r.a + 1), character)
            else:
                view.replace(edit, r, character)
