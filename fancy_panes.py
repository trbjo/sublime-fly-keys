import sublime
from sublime import Region, View, active_window
from sublime_plugin import WindowCommand


class FancyOpenPaneCommand(WindowCommand):
    def run(self) -> None:
        w = active_window()
        orig_view = w.active_view()
        w.run_command("clone_file")
        w.run_command("new_pane")
        if orig_view is None:
            return
        carets = orig_view.sel()
        new_view: View = w.active_view()
        new_view.sel().clear()
        new_view.sel().add_all(carets)
        new_view.show_at_center(carets[0].b)


class FancyClosePaneCommand(WindowCommand):
    def run(self) -> None:
        w = active_window()
        if w.num_groups() < 2:
            return

        active_view = w.active_view()
        if active_view is None:
            return

        if active_view.is_dirty():
            active_view.set_scratch(True)

        w.run_command("close_pane")

        buffers = {active_view.buffer_id()}
        for v in w.views_in_group(w.active_group()):
            if active_view.id() != v.id() and v.buffer_id() in buffers:
                v.close()
            else:
                buffers.add(v.buffer_id())

        if active_view.is_scratch():
            active_view.set_scratch(False)
