import sublime
import sublime_plugin
import bisect
import itertools

import re

class ExtendedExpandSelectionToParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        whitespaces = None
        regs_dict = {}
        for region in buf.sel():

            if region.empty():
                if whitespaces is None:
                    whitespaces = buf.find_all(r'\n\n *')
                    first, last = zip(*whitespaces)

                bisect_end = bisect.bisect(first, region.end() -1)
                if bisect_end >= len(whitespaces):
                    sel_end = buf.size() + 1
                else:
                    sel_end, _ = whitespaces[bisect_end]
                    sel_end += 2

                bisect_begin = bisect.bisect(whitespaces, region) - 1
                if bisect_begin == -1:
                    beginning = -1
                else:
                    beginning, _ = whitespaces[bisect_begin]
                    beginning += 1

            else:

                beginning = region.begin()
                if whitespaces is None:
                    _, sel_end = buf.find(r'\S\n\n', region.end() - 1)
                    if sel_end == -1:
                        sel_end = buf.size() + 1
                else:
                    if bisect_end >= len(whitespaces) - 1:
                        sel_end = buf.size() + 1
                    else:
                        sel_end, _ = whitespaces[bisect_end + 1]
                        sel_end += 2

            regs_dict[beginning] = sel_end

        buf.sel().add_all([sublime.Region(begin,end -1) for begin,end in regs_dict.items()])
        buf.show(buf.sel()[-1], False)
