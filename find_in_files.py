import re
from os import getenv, path
from typing import Union

import sublime
from sublime import Region, View, active_window
from sublime_plugin import EventListener, TextCommand, WindowCommand

from .navigate_paragraphs import build_or_rebuild_ws_for_buffer


class ScrollToTopOfViewportCommand(TextCommand):
    def run(self, _):
        reg = self.view.sel()[0]
        text_point = self.view.text_to_layout(reg.a)
        target_viewpoint = (0.0, text_point[1])
        self.view.set_viewport_position(target_viewpoint)


class SetReadOnly(EventListener):
    def on_new_async(self, view: View):
        if view.element() == "find_in_files:output":
            view.set_read_only(True)


class FocusPanelCommand(WindowCommand):
    """
    Focus the given output panel, optionally also ensuring that it is open.
    """

    def run(self, panel, show=True):
        if show:
            self.window.run_command("show_panel", {"panel": f"output.{panel}"})

        view = self.window.find_output_panel(panel)
        if view:
            build_or_rebuild_ws_for_buffer(view=view, immediate=True)
            view.set_read_only(True)
            if sublime.ui_info()["theme"]["style"] == "dark":
                view.settings().set("color_scheme", "dark.sublime-color-scheme")
            else:
                view.settings().set("color_scheme", "Light_dim.sublime-color-scheme")
            self.window.focus_view(view)
            hej = view.viewport_position()
            vp = (400.0, 500.0)
            view.set_viewport_position(vp)
            print(f"{hej=}")


class FindInFilesGotoCommand(TextCommand):
    def run(self, _) -> None:
        view = self.view
        if view is None:
            return
        window: Union[sublime.Window, None] = view.window()
        if window is None:
            return
        line_no = self.get_line_no()
        file_name = self.get_file()
        if line_no is not None and file_name is not None:
            caretpos = view.sel()[0].begin()
            (_, col) = view.rowcol(caretpos)
            file_loc = "%s:%s:%s" % (file_name, line_no, col - 6)
            new_view = window.open_file(file_loc, sublime.ENCODED_POSITION)
        elif file_name is not None:
            new_view = window.open_file(file_name)

    def get_line_no(self):
        view = self.view
        if len(view.sel()) == 1:
            line_text = view.substr(view.line(view.sel()[0]))
            match = re.match(r"\s*(\d+).+", line_text)
            if match:
                return match.group(1)
        return None

    def get_file(self):
        view = self.view
        if len(view.sel()) == 1:
            line = view.line(view.sel()[0])
            while line.begin() > 0:
                line_text = view.substr(line)
                match = re.match(r"(.+):$", line_text)
                if match:
                    normalized_path = match.group(1).replace("~", getenv("HOME"))
                    if path.exists(normalized_path):
                        return normalized_path
                line = view.line(line.begin() - 1)
        return None
