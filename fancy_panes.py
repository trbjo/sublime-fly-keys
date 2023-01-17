import sublime
from sublime import Region, View, active_window
from sublime_plugin import WindowCommand

MAX_NUM_GROUPS = 3


class FancyClonePaneCommand(WindowCommand):
    def run(self) -> None:
        w = active_window()
        num_groups = w.num_groups()
        orig_view: View = w.active_view()
        next_group = w.active_group() + 1
        carets = list(orig_view.sel())
        if num_groups > next_group:
            for v in w.views_in_group(next_group):
                if orig_view.buffer_id() == v.buffer_id():
                    return  # only unique buffers per group
            w.run_command("clone_file")
            new_view = w.active_view()
            w.move_sheets_to_group(sheets=[new_view.sheet()], group=next_group)
        elif num_groups < MAX_NUM_GROUPS:
            w.run_command("clone_file")
            w.run_command("new_pane")

        new_view = w.active_view()
        if new_view is None:
            return
        new_view.sel().clear()
        new_view.sel().add_all(carets)
        new_view.show_at_center(carets[0].b)


class FancyMoveBufferToNextPaneCommand(WindowCommand):
    def run(self) -> None:
        w = active_window()
        if len(w.views_in_group(w.active_group())) < 2:
            return
        num_groups = w.num_groups()
        view: View = w.active_view()
        next_group = w.active_group() + 1
        if next_group >= MAX_NUM_GROUPS:
            return
        elif num_groups > next_group:
            for v in w.views_in_group(next_group):
                if view.buffer_id() == v.buffer_id():
                    return  # only unique buffers per group
            w.move_sheets_to_group(sheets=[view.sheet()], group=next_group)
        else:
            w.run_command("new_pane")


class FancyMoveBufferToPrevPaneCommand(WindowCommand):
    def run(self, close: bool = False) -> None:
        w = active_window()
        if w.num_groups() < 2:
            return

        active_view = w.active_view()
        if active_view is None:
            return

        active_group = w.active_group()
        if close or len(w.views_in_group(active_group)) < 2 or active_group == 0:
            w.run_command("close_pane")
        else:
            prev_group = w.active_group() - 1
            w.move_sheets_to_group(sheets=[active_view.sheet()], group=prev_group)

        active_view = w.active_view()
        if active_view is None:
            return

        buffers = {active_view.buffer_id()}
        scratch_buffers = set()
        for v in w.views_in_group(w.active_group()):
            if active_view.id() != v.id() and v.buffer_id() in buffers:
                if not v.is_scratch() and v.is_dirty():
                    scratch_buffers.add(v.buffer())
                    v.set_scratch(True)
                v.close()
            else:
                buffers.add(v.buffer_id())

        for b in scratch_buffers:
            b.primary_view().set_scratch(False)
