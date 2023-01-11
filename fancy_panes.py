from typing import Dict, List, Set, Tuple, Union

import sublime
from sublime import Region, View, active_window
from sublime_plugin import TextCommand, ViewEventListener, WindowCommand


class FancyOpenPaneCommand(WindowCommand):
    def run(self) -> None:

        orig_view: Union[View, None] = active_window().active_view()
        active_window().run_command("clone_file")
        active_window().run_command("new_pane")
        if orig_view is None:
            return
        carets = orig_view.sel()
        new_view: View = active_window().active_view()
        new_view.sel().clear()
        new_view.sel().add_all(carets)
        new_view.show_at_center(carets[0].b)


class FancyClosePaneCommand(WindowCommand):
    def run(self) -> None:

        if active_window().num_groups() < 2:
            return

        active_view = active_window().active_view()
        if active_view is None:
            active_window().run_command("close_pane")
            return

        if active_view.is_dirty():
            active_view.set_scratch(True)

        active_window().run_command("close_pane")

        buffers = {active_view.buffer_id()}
        for v in active_window().views_in_group(active_window().active_group()):
            if active_view.id() != v.id() and v.buffer_id() in buffers:
                v.close()
            else:
                buffers.add(v.buffer_id())

        if active_view.is_scratch():
            active_view.set_scratch(False)
