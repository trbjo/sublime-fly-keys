from typing import Optional, Union

import sublime_plugin
from sublime import Edit, FindFlags, Region, View, active_window
from sublime_api import view_add_regions  # pyright: ignore
from sublime_api import view_find  # pyright: ignore
from sublime_api import view_cached_substr as substr  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_plugin import TextCommand, TextInputHandler, WindowCommand


class ClearSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _, forward: Optional[bool] = None, after=True) -> None:
        buf = self.view
        for region in buf.sel():
            buf.sel().subtract(region)
            reg = region.end() if forward else region.begin()
            if not after:
                reg -= 1
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
    regex = r"[-<>\w]+"

    def run(self, edit: Edit) -> None:
        v = self.view
        vi = v.id()
        if v.is_read_only():
            return
        s = v.sel()
        for r in s:
            if r.empty():
                right = view_find(vi, self.regex, r.b, FindFlags.NONE)
                s.subtract(r)
                if substr(vi, r.a, r.b + 1).isspace():
                    add_region(vi, right.a, right.b, 0.0)
                else:
                    line_content_rev: str = substr(vi, v.line(r.b).a, r.b)[::-1]
                    if (boundary := line_content_rev.find(" ")) == -1:
                        boundary = 0
                    add_region(vi, r.a - boundary, right.b, 0.0)

        for r in s:
            cur_line_num = v.line(r.end())
            indent = (
                cur_line_num.b - cur_line_num.a - len(v.substr(cur_line_num).lstrip())
            )
            content = "\n" + indent * " " + "print(f'{" + v.substr(r) + "=}')"
            _, insert_pos = v.line(r.end())
            sel_beg_pos = cur_line_num.b + indent + 10
            sel_beg_end = sel_beg_pos + r.end() - r.begin()
            v.insert(edit, insert_pos, content)
            s.subtract(r)
            new_reg = Region(sel_beg_pos, sel_beg_end)

            s.add(new_reg)


class RemoveBuildOutputCommand(WindowCommand):
    def run(self) -> None:
        view: Union[View, None] = active_window().active_view()
        if view is None:
            return
        view.erase_regions("exec")
        active_window().run_command("hide_panel")
        active_window().run_command("cancel_build")
        view.settings().set(key="needs_char", value=False)


class SetNumberCommand(sublime_plugin.TextCommand):
    def run(self, _, value=None):
        lines = self.view.rowcol(self.view.size())[0]
        if value is None:
            self.view.settings().erase("set_number")
            if (multiplier := self.view.settings().get("multiplier")) is not None:
                self.view.settings().erase("multiplier")
                multiplier -= 1
                if lines < multiplier:
                    multiplier = lines
                elif multiplier == -1:
                    multiplier = lines
                tp = self.view.text_point_utf8(multiplier, 0)
                next_res, _ = self.view.find(r"\S|^$|^\s+$", tp)
                self.view.sel().clear()
                self.view.sel().add(next_res)
                self.view.show(next_res)
        else:
            if (multiplier := self.view.settings().get("multiplier")) is not None:
                multiplier = int(f"{str(multiplier)}{str(value)}")
            else:
                multiplier = value

            self.view.settings().set("multiplier", min(multiplier, min(lines, 9999)))
            self.view.settings().set("set_number", True)
