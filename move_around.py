import sublime
import sublime_plugin

import re

class NavigateByParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        region = buf.sel()[-1]
        _, next_res = buf.find(r'\n\n\s*', region.begin())
        if next_res == -1:
            next_res = buf.size()
        reg = sublime.Region(next_res, next_res)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, False)


class NavigateByParagraphBackwardCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        region = buf.sel()[0]
        buffer_rev = buf.substr(sublime.Region(-1, region.begin() - 1))[::-1]
        for m in re.finditer(r'\S *\n\n', buffer_rev):
            next_res = region.begin() - m.start() - 2
            break
        else:
            next_res = -1
        reg = sublime.Region(next_res, next_res)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, False)
