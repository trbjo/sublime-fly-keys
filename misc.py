from typing import Union

import sublime_plugin
from sublime import Edit, FindFlags, Region, View, Window, active_window
from sublime_api import view_cached_substr as substr  # pyright: ignore
from sublime_api import view_find  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_plugin import WindowCommand


class ClearSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _, forward: bool = True) -> None:
        buf = self.view
        for region in buf.sel():
            pt = region.b if forward else region.a
            buf.sel().subtract(region)
            buf.sel().add(pt)
            buf.show(pt, False)


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


class EofCommand(WindowCommand):
    def run(self):
        w = self.window
        view: Union[View, None] = w.active_view()
        if view is None:
            return
        w.focus_view(view)
        view.run_command(cmd="move_to", args={"to": "eof", "extend": False} )
