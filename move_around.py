import sublime
import sublime_plugin

import re
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
        if view.element() is None:
            sublime.set_timeout(lambda: build_or_rebuild_ws_for_view(view, immediate=False), 2000)

    def on_activated_async(self, view):
        global interesting_regions
        if view not in interesting_regions and view.element() is None:
            build_or_rebuild_ws_for_view(view, immediate=False)

class NavigateByParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        region = buf.sel()[-1].begin()
        try:
            myregs = interesting_regions[buf]['last']
            bisect_res = bisect.bisect(myregs, region)
            sel_end = myregs[bisect_res]
        except KeyError:
            build_or_rebuild_ws_for_view(buf, immediate=True)
            _, sel_end = buf.find(r'\n\n\s*', region)
            if sel_end == -1:
                sel_end = buf.size()
        reg = sublime.Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, False)


class NavigateByParagraphBackwardCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global interesting_regions
        buf = self.view
        region = buf.sel()[0].begin()
        try:
            myregs = interesting_regions[buf]['last']
            bisect_res = bisect.bisect(myregs, region - 1)
            sel_end = myregs[bisect_res -1 ]
        except KeyError:
            build_or_rebuild_ws_for_view(buf, immediate=True)
            buffer_rev = buf.substr(sublime.Region(-1, region - 1))[::-1]
            for m in re.finditer(r'\S *\n\n', buffer_rev):
                sel_end = region - m.start() - 2
                break
            else:
                sel_end = -1
        reg = sublime.Region(sel_end, sel_end)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, False)


class ExtendedExpandSelectionToParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        myregs = None
        regs_dict = {}
        for region in buf.sel():
            try:
                first = interesting_regions[buf]['first']
                if region.empty():
                    bisect_begin = bisect.bisect(first, region.begin() -2)
                    sel_begin = first[bisect_begin -1 ] + 2
                else:
                    sel_begin = region.begin()
                bisect_end = bisect.bisect(first, region.end() -1)
                sel_end = first[bisect_end] + 3
            except KeyError:
                build_or_rebuild_ws_for_view(buf, immediate=True)
                if region.empty():
                    if myregs is None:
                        myregs = buf.find_all(r'\n\n *\S')
                        try:
                            first, last = zip(*myregs)
                        except ValueError:
                            first, last = [2], [0]

                    bisect_end = bisect.bisect(first, region.end() - 2)
                    if bisect_end >= len(myregs):
                        sel_end = buf.size() + 1
                    else:
                        sel_end, _ = myregs[bisect_end]
                        sel_end += 3

                    bisect_begin = bisect.bisect(first, region.begin() -2 )
                    if bisect_begin == 0:
                        sel_begin = -1
                    else:
                        sel_begin, _ = myregs[bisect_begin -1 ]
                        sel_begin += 2

                else:

                    sel_begin = region.begin()

                    if myregs is None:
                        sel_end, _ = buf.find(r'\n\n *\S', region.end() + 2)
                        if sel_end == -1:
                            sel_end = buf.size()

                    else:

                        bisect_end = bisect.bisect(first, region.end() - 2)
                        if bisect_end >= len(myregs):
                            sel_end = buf.size()
                        else:
                            sel_end, _ = myregs[bisect_end]

                    sel_end += 3

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all([sublime.Region(begin,end -1) for begin,end in regs_dict.items()])
        buf.show(buf.sel()[-1], False)
