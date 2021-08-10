import sublime
import sublime_plugin

import datetime
import bisect

timeout = datetime.datetime.now()
interesting_regions = {}

def build_or_rebuild_ws_for_view(view, immediate: bool):
    global interesting_regions
    global timeout
    res = (datetime.datetime.now()-timeout).total_seconds()
    if res > 2 or immediate == True:
        interesting_regions[view] = {}
        try:
            whitespaces = view.find_all(r'\n\n *\S')
            first, last = zip(*[(-2, -1)] + [(first, last -1) for first, last in whitespaces] + [(view.size() + 1, view.size() + 1)])
            interesting_regions[view]['first'] = first
            interesting_regions[view]['last'] = last
        except ValueError:
            interesting_regions[view]['first'] = []
            interesting_regions[view]['last'] = []
    timeout = datetime.datetime.now()


class HejSampleListener(sublime_plugin.EventListener):
    def on_modified_async(self, view):
        global interesting_regions
        if view.element() is None:
            try:
                del interesting_regions[view]
            except KeyError:
                pass
            sublime.set_timeout(lambda: build_or_rebuild_ws_for_view(view, immediate=False), 2000)

    def on_activated_async(self, view):
        global interesting_regions
        if view not in interesting_regions and view.element() is None:
            build_or_rebuild_ws_for_view(view, immediate=False)

class NavigateByParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        region = buf.sel()[-1].begin()
        try:
            myregs = interesting_regions[buf]['last']
        except KeyError:
            build_or_rebuild_ws_for_view(buf, immediate=True)
            myregs = interesting_regions[buf]['last']
        bisect_res = bisect.bisect(myregs, region)
        sel_end = myregs[bisect_res]
        reg = sublime.Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, False)


class NavigateByParagraphBackwardCommand(sublime_plugin.TextCommand):
    def run(self, _):
        global interesting_regions
        buf = self.view
        region = buf.sel()[0].begin()
        try:
            myregs = interesting_regions[buf]['last']
        except KeyError:
            build_or_rebuild_ws_for_view(buf, immediate=True)
            myregs = interesting_regions[buf]['last']
        bisect_res = bisect.bisect(myregs, region - 1)
        sel_end = myregs[bisect_res -1 ]
        reg = sublime.Region(sel_end, sel_end)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, False)


class ExtendedExpandSelectionToParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        regs_dict = {}
        for region in buf.sel():
            try:
                first = interesting_regions[buf]['first']
            except KeyError:
                build_or_rebuild_ws_for_view(buf, immediate=True)
                first = interesting_regions[buf]['first']
            if region.empty():
                bisect_begin = bisect.bisect(first, region.begin() -2)
                sel_begin = first[bisect_begin -1 ] + 2
            else:
                sel_begin = region.begin()
            bisect_end = bisect.bisect(first, region.end() -1)
            sel_end = first[bisect_end] + 3

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all([sublime.Region(begin,end -1) for begin,end in regs_dict.items()])
        buf.show(buf.sel()[-1], False)
