from sublime_plugin import WindowCommand

MAX_NUM_GROUPS = 3


class FancyClonePaneCommand(WindowCommand):
    def run(self) -> None:

        w = self.window

        num_groups = w.num_groups()
        next_group = w.active_group() + 1

        view = w.active_view()
        v_bid = view.buffer_id()

        carets = list(view.sel()) or [0]

        if num_groups > next_group:
            for v in w.views_in_group(next_group):
                if v_bid == v.buffer_id():
                    return  # only unique buffers per group

            w.run_command("clone_file")

            new_view = w.active_view()
            if new_view is None:
                return

            w.move_sheets_to_group(sheets=[new_view.sheet()], group=next_group)

            sels = new_view.sel()
            sels.clear()
            [sels.add(c) for c in carets]
            new_view.show_at_center(carets[0])

        elif num_groups < MAX_NUM_GROUPS:
            w.run_command("clone_file")
            w.run_command("new_pane")

            new_view = w.active_view()
            if new_view is None:
                return

            sels = new_view.sel()
            sels.clear()
            [sels.add(c) for c in carets]
            new_view.show_at_center(carets[0])


class FancyMoveBufferToNextPaneCommand(WindowCommand):
    def run(self) -> None:
        w = self.window

        if len(w.views_in_group(w.active_group())) < 2:
            return

        num_groups = w.num_groups()
        next_group = w.active_group() + 1

        view = w.active_view()
        v_bid = view.buffer_id()

        if num_groups > next_group:
            for v in w.views_in_group(next_group):
                if v_bid == v.buffer_id():
                    return  # only unique buffers per group

            w.move_sheets_to_group(sheets=[view.sheet()], group=next_group)

        elif num_groups < MAX_NUM_GROUPS:
            w.run_command("new_pane")


class FancyMoveBufferToPrevPaneCommand(WindowCommand):
    def run(self) -> None:
        w = self.window
        if w.num_groups() < 2:
            return

        view = w.active_view()
        if view is None:
            return

        active_group = w.active_group()
        if len(w.views_in_group(active_group)) < 2 or active_group == 0:
            w.run_command("close_pane")
        else:
            prev_group = w.active_group() - 1
            w.move_sheets_to_group(sheets=[view.sheet()], group=prev_group)

        view = w.active_view()
        if view is None:
            return
        v_id = view.id()

        buffers = {view.buffer_id()}
        scratch_buffers = set()
        for v in w.views_in_group(w.active_group()):
            if v_id != v.id() and v.buffer_id() in buffers:
                if not v.is_scratch() and v.is_dirty():
                    scratch_buffers.add(v.buffer())
                    v.set_scratch(True)
                v.close()
            else:
                buffers.add(v.buffer_id())

        for b in scratch_buffers:
            b.primary_view().set_scratch(False)
