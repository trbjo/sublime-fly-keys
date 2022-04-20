from sublime import View
import sublime
from sublime_plugin import TextCommand, EventListener

from typing import Union
from os import path, getenv
import re

class SetReadOnly(EventListener):
    def on_new_async(self, view: View):
        if view.element() == "find_in_files:output":
            view.set_read_only(True)

class FindInFilesGotoCommand(TextCommand):
    def run(self, _) -> None:
        view = self.view
        if view is None:
            return
        window: Union[sublime.Window,None] = view.window()
        if window is None:
            return
        if view.name() == "Find Results":
            line_no = self.get_line_no()
            file_name = self.get_file()
            if line_no is not None and file_name is not None:
                caretpos = view.sel()[0].begin()
                (_,col) = view.rowcol(caretpos)
                file_loc = "%s:%s:%s" % (file_name, line_no, col -6)
                window.open_file(file_loc, sublime.ENCODED_POSITION)
            elif file_name is not None:
                window.open_file(file_name)

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
                    normalized_path = match.group(1).replace('~', getenv("HOME"))
                    if path.exists(normalized_path):
                        return normalized_path
                line = view.line(line.begin() - 1)
        return None


