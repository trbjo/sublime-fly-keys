from sublime import View, Region
import sublime
import sublime_plugin

from typing import List, Tuple, Dict
from bisect import bisect
import datetime

interesting_regions: Dict[View, Dict[str, Tuple[int]]] = {}
timeout = datetime.datetime.now()

def build_or_rebuild_ws_for_view(view: View, immediate: bool):
    if view is None:
        return
    global interesting_regions
    global timeout
    if (datetime.datetime.now() - timeout).total_seconds() > 2 or immediate == True:
        interesting_regions[view] = dict()
        try:
            whitespaces: List[Region] = view.find_all(r'\n[\t ]*\n[\t ]*\S')
            size = view.size() + 1
            first, last = zip(*[(-2, -1)] + [(first, last -1) for first, last in whitespaces] + [(size, size)])
            interesting_regions[view]['first'] = first
            interesting_regions[view]['last'] = last
        except ValueError:
            pass
    timeout = datetime.datetime.now()


class ModifiedViewListener(sublime_plugin.ViewEventListener):
    def on_modified_async(self):
        view: View = self.view
        if view.element() is None:
            try:
                global interesting_regions
                del interesting_regions[view]
            except KeyError:
                pass
            print(view.file_name())
            sublime.set_timeout(lambda: build_or_rebuild_ws_for_view(view, immediate=False), 2000)

    def on_load_async(self):
        view: View = self.view
        if view not in interesting_regions and view.element() is None:
            build_or_rebuild_ws_for_view(view, immediate=True)


class NavigateByParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        region = buf.sel()[-1].begin()
        try:
            myregs: Tuple[int] = interesting_regions[buf]['last']
        except KeyError:
            build_or_rebuild_ws_for_view(buf, immediate=True)
            myregs: Tuple[int] = interesting_regions[buf]['last']
        bisect_res = bisect(myregs, region)
        sel_end = myregs[bisect_res]
        reg = Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, True)


class NavigateByParagraphBackwardCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        region = buf.sel()[0].begin()
        try:
            myregs: Tuple[int] = interesting_regions[buf]['last']
        except KeyError:
            build_or_rebuild_ws_for_view(buf, immediate=True)
            myregs: Tuple[int] = interesting_regions[buf]['last']
        bisect_res = bisect(myregs, region - 1)
        sel_end: int = myregs[bisect_res -1 ]
        reg = Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)

        buf.show(reg, True)

class ExtendedExpandSelectionToParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        regs_dict: Dict[int, int] = dict()
        for region in buf.sel():

            try:
                first: Tuple[int] = interesting_regions[buf]['first']
            except KeyError:
                build_or_rebuild_ws_for_view(buf, immediate=True)
                first: Tuple[int] = interesting_regions[buf]['first']

            if region.b > region.a:
                bisect_res = bisect(first, region.b -1)
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
                bisect_res = bisect(first, region.b -2)
                sel_begin = first[bisect_res -1] + 2
                sel_end = first[bisect_res] + 2

            else:
                return

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all(Region(begin,end) for begin,end in regs_dict.items())
        buf.show(buf.sel()[-1], False)


class ExtendedExpandSelectionToParagraphBackwardCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        regs_dict: Dict[int, int] = dict()
        for region in buf.sel():

            try:
                first: Tuple[int] = interesting_regions[buf]['first']
            except KeyError:
                build_or_rebuild_ws_for_view(buf, immediate=True)
                first: Tuple[int] = interesting_regions[buf]['first']

            if region.b > region.a:
                bisect_end = bisect(first, region.b - 3)
                sel_end = first[bisect_end -1] + 2
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
                    sel_end = first[bisect_end -1] + 2

            elif region.b == region.a:
                bisect_end = bisect(first, region.b - 2)
                sel_end = first[bisect_end -1] + 2
                sel_begin = first[bisect_end] + 2

            else:
                return

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all(Region(begin, end) for begin,end in regs_dict.items())
        buf.show(buf.sel()[0], False)
