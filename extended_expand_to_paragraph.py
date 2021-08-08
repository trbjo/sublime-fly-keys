import sublime
import sublime_plugin

import re

class ExtendedExpandSelectionToParagraphCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        buffer_rev = None
        for region in buf.sel():
            if region.empty():
                # selection is empty, we need to look behind:
                if buffer_rev is None:
                    buffer_rev = buf.substr(sublime.Region(-1, buf.sel()[-1].begin() + 1))[::-1]
                for m in re.finditer(r'\S *\n\n', buffer_rev):
                    beginning = region.begin() - m.start()
                    break
                else:
                    beginning = -1
            else:
                beginning = region.begin()

            _, next_res = buf.find(r'\S\n\n', region.end() - 1)
            if next_res == -1:
                next_res = buf.size() + 1

            reg = sublime.Region(beginning, next_res - 1)
            buf.sel().add(reg)
        try:
            buf.show(reg, False)
        except UnboundLocalError:
            pass
