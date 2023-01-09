from typing import Dict, List, Set, Tuple, Union

import sublime
from sublime import Region, View, active_window
from sublime_plugin import TextCommand, ViewEventListener, WindowCommand


class FancyOpenPaneCommand(WindowCommand):
    def run(self) -> None:

        view: Union[View, None] = active_window().active_view()
        active_window().run_command("clone_file")
        active_window().run_command("new_pane")
        if view is None:
            return
        old_pointer = view.sel()[0].b
        view: Union[View, None] = active_window().active_view()
        view.sel().clear()
        view.sel().add(old_pointer)
        view.show_at_center(old_pointer)


class FancyClosePaneCommand(WindowCommand):
    def run(self) -> None:
        active_window().run_command("close_pane")
        if active_window().active_view() is None:
            return
        unique: Set[int] = set()
        for v in active_window().views():
            if v.buffer_id() in unique:
                v.close()
            unique.add(v.buffer_id())
