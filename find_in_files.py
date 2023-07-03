import re
from os import getenv, path
from typing import Dict, List, Optional, Tuple

import sublime
import sublime_plugin
from sublime import NewFileFlags, View, active_window, set_clipboard
from sublime_api import settings_get_default  # pyright: ignore
from sublime_api import view_cached_substr as view_substr  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_api import view_set_viewport_position as set_vp  # pyright: ignore
from sublime_plugin import TextCommand, WindowCommand

VIEWPORT_MARGIN = 2
HOME: str = getenv("HOME")  # pyright: ignore


class CopyInFindInFilesCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        v: View = self.view
        sel = v.sel()
        line = v.line(sel[0])
        line_content = v.substr(line)

        if not line_content.startswith(" "):
            set_clipboard(line_content[:-1])
        elif line_match := re.match(r"^\s+\d+", line_content):
            offset = line_match.end() + 2
            set_clipboard(line_content[offset:])


class FindInFilesListener(sublime_plugin.EventListener):
    def on_activated(self, view: View):
        if view.element() == "find_in_files:output":
            views = active_window().views()
            v_n_s = {str(v.id()): [tuple(reg) for reg in v.sel()] for v in views}
            vps = {str(v.id()): v.viewport_position() for v in views}
            active_window().settings().set(key="ViewsBeforeSearch", value=v_n_s)
            active_window().settings().set(key="viewport_positions", value=vps)


class CloseTransientViewCommand(WindowCommand):
    def run(self):
        w = self.window
        w.run_command("hide_panel", {"cancel": True})

        group = w.active_group()
        if (transient := w.transient_view_in_group(group)) is None:
            return

        views: Dict[str, List[List[int]]] = w.settings().get(
            "ViewsBeforeSearch", {}
        )  # pyright: ignore
        viewport_pos: Dict[str, Tuple[float, float]] = w.settings().get(
            "viewport_positions", {}
        )  # pyright: ignore
        if str(transient.id()) not in views.keys():
            transient.close()
        prior_vs: List[int] = w.settings().get("views_before_search", [])
        active_group: int = w.settings().get("active_group", 0)
        for v in w.views():
            v.sel().clear()
            [add_region(v.id(), reg[0], reg[1], 0.0) for reg in views[str(v.id())]]
            set_vp(v.id(), viewport_pos[str(v.id())], False)
            if v.id() in prior_vs:
                self.window.focus_view(v)

        w.focus_group(active_group)


class OpenFindResultsCommand(WindowCommand):
    def run(self, panel):
        w = self.window
        vs = []
        if (v := w.active_view()) is not None:
            # do not run the rest if "show in buffer" is set
            if v.name() == "Find Results":
                return

        for num in range(w.num_groups()):
            if (v := w.active_view_in_group(num)) is not None:
                vs.append(v.id())
        w.settings().set(key="views_before_search", value=vs)
        w.settings().set(key="active_group", value=w.active_group())

        if panel == "find_results":
            w.run_command("show_panel", {"panel": f"output.{panel}"})

        if view := w.find_output_panel(panel):
            if panel == "diagnostics":
                view.settings().set("font_face", "sans-serif")
                view.settings().set("font_size", 9.5)
            view.set_read_only(True)
            view.settings().set("command_mode", True)
            view.settings().set("block_caret", True)
            if sublime.ui_info()["theme"]["style"] == "dark":
                view.settings().set("color_scheme", "dark.sublime-color-scheme")
            else:
                view.settings().set("color_scheme", "Light_dim.sublime-color-scheme")
            s = view.sel()
            if len(s) == 0:
                view.sel().add(0)
            w.focus_view(view)


class OutputPanelNavigateCommand(TextCommand):
    def run(self, _, new_tab=False, show=None) -> None:
        if (view := self.view) is None:
            return
        if (window := view.window()) is None:
            return

        # if view != window.find_output_panel("find_results"):
        #     return

        if (next_position := self.get_next_pos(show)) == -1:
            return None  # no matches were found
        elif next_position > 0:
            view.sel().clear()
            view.sel().add(next_position)
            view.show(next_position)

        if show and view.name() == "Find Results":
            # do not run the rest if "show in buffer" is set
            return

        line_no = self.get_line_no()
        file_name, target_line = self.get_file()

        if line_no is not None and file_name is not None:
            caretpos = view.sel()[0].b
            col = view.rowcol(caretpos)[1] - 6
            if col < 1:
                col = 1
            file_loc = f"{file_name}:{line_no}:{col}"
        elif file_name is not None:
            file_loc = f"{file_name}:1:1"
        else:
            return None

        params = sublime.ENCODED_POSITION
        if new_tab:
            params += NewFileFlags.FORCE_CLONE

        if show:
            params += NewFileFlags.TRANSIENT

            target_tp = view.text_to_layout(target_line.a)[1]
            cursor_tp = view.text_to_layout(view.sel()[0].a)[1]
            padding = view.line_height()
            if cursor_tp + padding - target_tp < view.viewport_extent()[1]:
                target_viewpoint = (0.0, target_tp - VIEWPORT_MARGIN)
                view.set_viewport_position(target_viewpoint)

        elif not view.name() == "Find Results":
            views: Dict[str, List[List[int]]] = window.settings().get(
                "ViewsBeforeSearch", {}
            )  # pyright: ignore
            viewport_pos: Dict[str, Tuple[float, float]] = window.settings().get(
                "viewport_positions", {}
            )  # pyright: ignore

            for v in window.views():
                v.sel().clear()
                [add_region(v.id(), reg[0], reg[1], 0.0) for reg in views[str(v.id())]]
                set_vp(v.id(), viewport_pos[str(v.id())], False)
            window.run_command("hide_panel")

        window.open_file(fname=file_loc, flags=params)  # pyright: ignore

        if new_tab:
            window.run_command("new_pane")

    def get_line_no(self):
        v = self.view
        line_text = v.substr(v.line(v.sel()[0]))
        match = re.match(r"\s*(\d+):.+", line_text)
        if match:
            return match.group(1)
        return None

    def get_file(self):
        v = self.view
        line = v.line(v.sel()[0])
        if line.empty() or line.b + 1 == v.size() or line.a == 1:
            return None, None
        while line.begin() > 1:
            line_text = v.substr(line)
            match = re.match(r"^(\S.+):$", line_text)
            if match:
                normalized_path = match.group(1).replace("~", HOME)
                if path.exists(normalized_path):
                    return normalized_path, line
            line = v.line(line.begin() - 1)
        return None, None

    def get_next_pos(self, show: Optional[str]) -> int:
        v = self.view
        reg = v.sel()[0]
        if show == "prev_line":
            line = v.line(v.line(reg.b - 1).a)
            while line.begin() > 1:
                if line.empty() or re.match(r"^(\S.+):$", v.substr(line)):
                    line = v.line(line.a - 1)
                    continue
                return line.a
        elif show == "next_line":
            line = v.line(v.line(reg.b + 1).b + 1)
            while line.end() + 1 < v.size():
                if line.empty() or re.match(r"^(\S.+):$", v.substr(line)):
                    line = v.line(line.b + 1)
                    continue
                return line.a
        elif show == "next_paragraph":
            if (match := v.find(r"\n\n.+:\n", reg.b).a) != -1:
                return match + 2
        elif show == "prev_paragraph":
            buffer = view_substr(v.id(), 0, reg.b)[::-1]
            if match := re.search(r"\n:.+\S\n\n", buffer):
                return reg.b - match.end() + 2
        else:
            return 0

        return -1
