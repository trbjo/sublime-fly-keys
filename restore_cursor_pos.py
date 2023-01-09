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
        active_view = active_window().active_view()
        if active_view is None:
            return

        primary = active_view.buffer().primary_view()
        focus_after_close = False
        unique: Set[int] = set()
        for v in active_window().views_in_group(active_window().active_group()):
            if v.buffer_id() in unique and not v.is_primary():
                if active_view.id() == v.id():
                    focus_after_close = True
                v.close()
            unique.add(v.buffer_id())

        if focus_after_close:
            active_window().focus_view(primary)
