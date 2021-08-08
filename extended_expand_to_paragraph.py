import sublime
import sublime_plugin

import itertools
import bisect

class ExtendedExpandSelectionToParagraphCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        regions = buf.find_all('\n\n\\s*')
        first, last = zip(*regions)
        for region in buf.sel():
            if region.empty():
                bisect_result = bisect.bisect(last, region.end())
                if bisect_result == 0:
                    reg_beg = 0
                    reg_end, _  = regions[bisect_result]
                elif bisect_result < len(regions):
                    _, reg_beg  = regions[bisect_result -1 ]
                    reg_end, _  = regions[bisect_result]
                elif bisect_result == len(regions):
                    _, reg_beg  = regions[bisect_result - 1]
                    reg_end = buf.size()
                reg = sublime.Region(reg_beg - 1, reg_end + 1)
                buf.sel().subtract(region)
                buf.sel().add(reg)
            else:
                bisect_result = bisect.bisect(last, region.end() - 1) + 1
                if bisect_result < len(regions):
                    reg_end, _  = regions[bisect_result]
                    reg = sublime.Region(region.end() - 1, reg_end + 1)
                    buf.sel().add(reg)
                elif bisect_result == len(regions):
                    reg_end = buf.size()
                    reg = sublime.Region(region.end() - 1, reg_end + 1)
                    buf.sel().add(reg)
        try:
            buf.show(reg_end, False)
        except UnboundLocalError:
            pass
