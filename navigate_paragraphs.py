import time
from bisect import bisect
from typing import Dict, List, Tuple, Union

import sublime
from sublime import Region, View, active_window
from sublime_plugin import TextCommand, ViewEventListener, WindowCommand

interesting_regions: Dict[int, Dict[str, Tuple[int]]] = {}
timeouts: Dict[int, float] = {}


class RemoveBuildOutputCommand(WindowCommand):
    def run(self) -> None:
        view: Union[View, None] = active_window().active_view()
        if view is None:
            return
        view.erase_regions("exec")
        active_window().run_command("hide_panel")
        active_window().run_command("cancel_build")
        view.settings().set(key="needs_char", value=False)


def maybe_rebuild(view: View):

    if view.element() is not None:
        return

    global timeouts
    timeouts[view.buffer_id()] = time.time()
    sublime.set_timeout(lambda: build_or_rebuild_ws_for_buffer(view, False), 2000)


def build_or_rebuild_ws_for_buffer(view: View, now: bool):
    if view is None:
        return
    global timeouts
    buf_id = view.buffer_id()
    if now or (time.time() - timeouts.get(buf_id, 0) >= 2):
        global interesting_regions
        interesting_regions[buf_id] = {}
        try:
            whitespaces: List[Region] = view.find_all(r"\n[\t ]*\n[\t ]*\S")
            size = view.size() + 1
            (
                interesting_regions[buf_id]["first"],
                interesting_regions[buf_id]["last"],
            ) = zip(
                *[(-2, -1)]
                + [(first, last - 1) for first, last in whitespaces]
                + [(size, size)]
            )
        except ValueError:
            pass
        timeouts[view.buffer_id()] = time.time()


def get_regions(view: View, part: str, now: bool = False):
    global interesting_regions

    if now:
        build_or_rebuild_ws_for_buffer(view, now=True)
        myregs: Tuple[int] = interesting_regions[view.buffer_id()][part]
        return myregs

    try:
        myregs: Tuple[int] = interesting_regions[view.buffer_id()][part]
    except KeyError:
        build_or_rebuild_ws_for_buffer(view, now=True)
        myregs: Tuple[int] = interesting_regions[view.buffer_id()][part]
    return myregs


class ModifiedViewListener(ViewEventListener):
    def on_modified_async(self):
        view: View = self.view
        if view.element() is None:
            global interesting_regions
            interesting_regions[view.buffer_id()] = {}
            if view.settings().get("command_mode"):
                maybe_rebuild(view)

    def on_load_async(self):
        global interesting_regions
        view: View = self.view
        if view.buffer_id() not in interesting_regions and view.element() is None:
            build_or_rebuild_ws_for_buffer(view, now=True)


class NavigateByParagraphForwardCommand(TextCommand):
    def run(self, _) -> None:
        buf = self.view
        region = buf.sel()[-1].begin()
        try:
            myregs = get_regions(buf, "last")
            bisect_res = bisect(myregs, region)
            sel_end = myregs[bisect_res]
        except IndexError:
            myregs = get_regions(view=buf, part="last", now=True)
            bisect_res = bisect(myregs, region)
            sel_end = myregs[bisect_res]
        reg = Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg.b, True)


class NavigateByParagraphBackwardCommand(TextCommand):
    def run(self, _) -> None:
        buf = self.view
        region = buf.sel()[0].begin()
        try:
            myregs = get_regions(buf, "last")
            bisect_res = bisect(myregs, region - 1)
            sel_end: int = myregs[bisect_res - 1]
        except IndexError:
            myregs = get_regions(view=buf, part="last", now=True)
            bisect_res = bisect(myregs, region - 1)
            sel_end: int = myregs[bisect_res - 1]
        reg = Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)

        buf.show(reg.b, True)


class ExtendedExpandSelectionToParagraphForwardCommand(TextCommand):
    def run(self, _) -> None:
        buf = self.view
        regs_dict: Dict[int, int] = {}
        first = get_regions(buf, "first")
        for region in buf.sel():
            if region.b > region.a:
                bisect_res = bisect(first, region.b - 1)
                sel_begin = buf.full_line(region.a).a
                sel_end = first[bisect_res] + 2

            elif region.a > region.b:
                bisect_res = bisect(first, region.b)
                sel_end = first[bisect_res] + 2
                if region.a == sel_end or sel_end - 3 == region.a:
                    sel_end = region.a
                    sel_begin = region.b
                else:
                    sel_begin = region.a
                    buf.sel().subtract(region)

            elif region.a == region.b:
                bisect_res = bisect(first, region.b - 2)
                sel_begin = first[bisect_res - 1] + 2
                sel_end = first[bisect_res] + 2

            else:
                return

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all(Region(begin, end) for begin, end in regs_dict.items())
        buf.show(buf.sel()[-1].b, False)


class ExtendedExpandSelectionToParagraphBackwardCommand(TextCommand):
    def run(self, _) -> None:
        buf = self.view
        regs_dict: Dict[int, int] = {}
        first = get_regions(buf, "first")
        for region in buf.sel():
            if region.b > region.a:
                bisect_end = bisect(first, region.b - 3)
                sel_end = first[bisect_end - 1] + 2
                if region.a == sel_end:
                    sel_begin = region.b
                else:
                    sel_begin = buf.full_line(region.a).a
                    buf.sel().subtract(region)

            elif region.a > region.b:
                sel_begin = region.a
                bisect_end = bisect(first, region.b - 3)
                if bisect_end == 0:
                    sel_end = -1
                else:
                    sel_end = first[bisect_end - 1] + 2

            elif region.b == region.a:
                bisect_end = bisect(first, region.b - 2)
                sel_end = first[bisect_end - 1] + 2
                sel_begin = first[bisect_end] + 2

            else:
                return

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all(Region(begin, end) for begin, end in regs_dict.items())
        buf.show(buf.sel()[0].b, False)
