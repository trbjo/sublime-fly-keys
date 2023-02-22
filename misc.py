from typing import Optional, Union

import sublime_api
import sublime_plugin
from sublime import Edit, Region, View, active_window
from sublime_api import view_add_regions  # pyright: ignore
from sublime_api import view_selection_add_region as add_reg  # pyright: ignore
from sublime_plugin import WindowCommand

from .base import backward, forward


class ClearSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _, forward: Optional[bool] = None, cursor=False) -> None:
        buf = self.view
        for region in buf.sel():
            buf.sel().subtract(region)
            if cursor:
                reg = region.b
                if not forward:
                    reg -= 1
            elif forward == True:
                _, col = buf.rowcol(region.end())
                if col == 0:
                    reg = region.end() - 1
                else:
                    reg = region.end()
            else:
                reg = region.begin()
            buf.sel().add(reg)
            buf.show(reg, False)


class CreateRegionFromSelectionsCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        sel = buf.sel()
        line_beg = buf.full_line(sel[0]).begin()
        line_end = buf.full_line(sel[-1]).end()
        sel.clear()
        sel.add(Region(line_beg, line_end))


class PoorMansDebuggingCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
        buf = self.view
        if buf.is_read_only():
            return
        selections = buf.sel()

        for region in reversed(selections):
            if region.empty():
                continue

            cur_line_num = buf.line(region.end())
            indent = (
                cur_line_num.b - cur_line_num.a - len(buf.substr(cur_line_num).lstrip())
            )
            content = "\n" + indent * " " + "print(f'{" + buf.substr(region) + "=}')"
            _, insert_pos = buf.line(region.end())
            sel_beg_pos = cur_line_num.b + indent + 10
            sel_beg_end = sel_beg_pos + region.end() - region.begin()
            buf.insert(edit, insert_pos, content)
            selections.subtract(region)
            new_reg = Region(sel_beg_pos, sel_beg_end)

            selections.add(new_reg)


class RemoveBuildOutputCommand(WindowCommand):
    def run(self) -> None:
        view: Union[View, None] = active_window().active_view()
        if view is None:
            return
        view.erase_regions("exec")
        active_window().run_command("hide_panel")
        active_window().run_command("cancel_build")
        view.settings().set(key="needs_char", value=False)


class SmarterSoftUndoCommand(sublime_plugin.TextCommand):
    def run(self, _):
        vi = self.view.id()
        s = self.view.sel()

        global forward
        global backward

        if len(backward[vi]) == 1:
            prev_sel = backward[vi][0]
        else:
            prev_sel = backward[vi].pop()
            forward[vi].append(prev_sel)

        s.clear()
        [add_reg(vi, r.a, r.b, 0.0) for r in prev_sel]
        self.view.show(s)


class SetNumberCommand(sublime_plugin.TextCommand):
    def run(self, _, value=None):
        size = self.view.rowcol(self.view.size())[0]
        if value is None:
            self.view.settings().erase("lolol")
            if (multiplier := self.view.settings().get("multiplier")) is not None:
                self.view.settings().erase("multiplier")
                multiplier -= 1
                if size < multiplier:
                    multiplier = size
                elif multiplier == -1:
                    multiplier = size
                hej = self.view.text_point_utf8(multiplier, 0)
                next_res, _ = self.view.find(r"\S|^$|^\s+$", hej)
                self.view.sel().clear()
                self.view.sel().add(next_res)
                self.view.show(next_res)
        else:
            if (multiplier := self.view.settings().get("multiplier")) is not None:
                multiplier = int(f"{str(multiplier)}{str(value)}")
            else:
                multiplier = value

            self.view.settings().set("multiplier", min(multiplier, min(size, 9999)))
            self.view.settings().set("lolol", True)
