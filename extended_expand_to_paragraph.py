import sublime
import sublime_plugin

import bisect

class ExtendedExpandSelectionToParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        whitespaces = None
        regs_dict = {}
        for region in buf.sel():

            if region.empty():
                if whitespaces is None:
                    whitespaces = buf.find_all(r'\n\n *\S')
                    try:
                        first, last = zip(*whitespaces)
                    except ValueError:
                        first, last = [2], [0]

                bisect_end = bisect.bisect(first, region.end() - 2)
                if bisect_end >= len(whitespaces):
                    sel_end = buf.size() + 1
                else:
                    sel_end, _ = whitespaces[bisect_end]
                    sel_end += 3

                bisect_begin = bisect.bisect(first, region.begin() -2 )
                if bisect_begin <= 1:
                    sel_begin = -1
                else:
                    sel_begin, _ = whitespaces[bisect_begin -1 ]
                    sel_begin += 2

            else:

                sel_begin = region.begin()

                if whitespaces is None:
                    sel_end, _ = buf.find(r'\n\n *\S', region.end() + 2)
                    if sel_end == -1:
                        sel_end = buf.size()

                else:

                    bisect_end = bisect.bisect(first, region.end() - 2)
                    if bisect_end >= len(whitespaces):
                        sel_end = buf.size()
                    else:
                        sel_end, _ = whitespaces[bisect_end]

                sel_end += 3

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all([sublime.Region(begin,end -1) for begin,end in regs_dict.items()])
        buf.show(buf.sel()[-1], False)
