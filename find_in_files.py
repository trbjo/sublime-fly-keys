import re
from os import getenv, path
from typing import List

import sublime
from sublime import NewFileFlags
from sublime_api import view_cached_substr as view_substr
from sublime_plugin import TextCommand, WindowCommand

from .navigate_paragraphs import build_or_rebuild_ws_for_buffer

VIEWPORT_MARGIN = 2


class NavigateForwardFindInFilesCommand(TextCommand):
    def run(self, _):
        v = self.view
        reg = self.view.sel()[0]
        match = v.find(r"\n\n.+:\n", reg.a)
        if match.a == -1:
            return
        v.sel().clear()
        v.sel().add(match.a + 2)


class NavigateBackwardFindInFilesCommand(TextCommand):
    def run(self, _):
        v = self.view
        reg = self.view.sel()[0]
        buffer = view_substr(v.id(), 0, reg.b)[::-1]
        if match := re.search(r"\n:.+\S\n\n", buffer):
            v.sel().add(reg.b - match.end() + 2)
            v.sel().subtract(reg)


class LineDownFindInFilesCommand(TextCommand):
    def run(self, _):
        v = self.view
        if len(v.sel()) == 1:
            reg = v.sel()[0]
            s = v.sel()
            line = v.line(v.line(reg.b + 1).b + 1)
            while line.end() + 1 < v.size():
                if line.empty():
                    line = v.line(line.b + 1)
                    continue
                s.clear()
                s.add(line.a)
                v.show(line.a)
                return


class LineUpFindInFilesCommand(TextCommand):
    def run(self, _):
        v = self.view
        if len(v.sel()) == 1:
            reg = v.sel()[0]
            s = v.sel()
            line = v.line(v.line(reg.a - 1).a)
            while line.begin() > 1:
                if line.empty():
                    line = v.line(line.a - 1)
                    continue
                s.clear()
                s.add(line.a)
                v.show(line.a)
                return


class CloseTransientViewCommand(WindowCommand):
    def run(self):
        self.window.run_command("hide_panel", {"cancel": True})

        group = self.window.active_group()
        if (transient := self.window.transient_view_in_group(group)) is not None:
            views: List[int] = self.window.settings().get("views_before_search", [])
            if transient.id() not in views:
                transient.close()
            else:
                if (
                    focus_view := self.window.settings().get("view_before_search")
                ) is not None:
                    for v in self.window.views():
                        if v.id() == focus_view:
                            self.window.focus_view(v)
                            return


class ScrollToTopOfViewportCommand(TextCommand):
    def run(self, _):
        reg = self.view.sel()[0]
        text_point = self.view.text_to_layout(reg.a)
        target_viewpoint = (0.0, text_point[1])
        self.view.set_viewport_position(target_viewpoint)


class FocusPanelCommand(WindowCommand):
    """
    Focus the given output panel, optionally also ensuring that it is open.
    """

    def run(self, panel, show=True):
        if show:
            self.window.run_command("show_panel", {"panel": f"output.{panel}"})

        if view := self.window.find_output_panel(panel):
            self.window.focus_view(view)


class OpenFindResultsCommand(WindowCommand):
    def run(self, show=True):
        views = [v.id() for v in self.window.views()]
        self.window.settings().set(key="views_before_search", value=views)
        view_before_search = self.window.active_view()
        self.window.settings().set(
            key="view_before_search", value=view_before_search.id()
        )

        if show:
            self.window.run_command("show_panel", {"panel": "output.find_results"})

        if view := self.window.find_output_panel("find_results"):
            build_or_rebuild_ws_for_buffer(view=view, immediate=True)
            view.set_read_only(True)
            if sublime.ui_info()["theme"]["style"] == "dark":
                view.settings().set("color_scheme", "dark.sublime-color-scheme")
            else:
                view.settings().set("color_scheme", "Light_dim.sublime-color-scheme")
            self.window.focus_view(view)


class FindInFilesGotoCommand(TextCommand):
    def run(self, _, preview=False, new_tab=False) -> None:

        if (view := self.view) is None:
            return

        if (window := view.window()) is None:
            return

        if view != window.find_output_panel("find_results"):
            return

        line_no = self.get_line_no()
        file_name, target_line = self.get_file()

        if file_name is None:
            group = window.active_group()
            if (transient := window.transient_view_in_group(group)) is not None:
                views: List[int] = window.settings().get("views_before_search", [])
                if transient.id() not in views:
                    transient.close()
            if not preview:
                self.view.window().run_command("hide_panel", {"cancel": True})
            return None

        if line_no is not None and file_name is not None:
            caretpos = view.sel()[0].begin()
            (_, col) = view.rowcol(caretpos)
            file_loc = "%s:%s:%s" % (file_name, line_no, col - 6)
        elif file_name is not None:
            file_loc = "%s:%s:%s" % (file_name, 1, 1)

        params = sublime.ENCODED_POSITION
        if preview:
            params += NewFileFlags.TRANSIENT

        if new_tab:
            params += NewFileFlags.FORCE_CLONE

        window.open_file(fname=file_loc, flags=params)  # type: ignore

        if new_tab:
            window.run_command("new_pane")

        if not preview:
            self.view.window().run_command("hide_panel", {"cancel": True})

        elif target_line is not None:
            target_tp = self.view.text_to_layout(target_line.a)[1]
            cursor_tp = self.view.text_to_layout(view.sel()[0].a)[1]
            padding = view.line_height()
            if cursor_tp + padding - target_tp < view.viewport_extent()[1]:
                target_viewpoint = (0.0, target_tp - VIEWPORT_MARGIN)
                self.view.set_viewport_position(target_viewpoint)

    def get_line_no(self):
        view = self.view
        if len(view.sel()) == 1:
            line_text = view.substr(view.line(view.sel()[0]))
            match = re.match(r"\s*(\d+):.+", line_text)
            if match:
                return match.group(1)
        return None

    def get_file(self):
        view = self.view
        if len(view.sel()) == 1:
            line = view.line(view.sel()[0])
            if line.empty() or line.b + 1 == self.view.size() or line.a == 1:
                return None, None
            while line.begin() > 0:
                line_text = view.substr(line)
                match = re.match(r"^(\S.+):$", line_text)
                if match:
                    normalized_path = match.group(1).replace("~", getenv("HOME"))
                    if path.exists(normalized_path):
                        return normalized_path, line
                line = view.line(line.begin() - 1)
        return None, None
