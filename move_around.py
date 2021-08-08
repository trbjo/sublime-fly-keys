import sublime
import sublime_plugin
import bisect
import re

class NavigateByParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        for region in buf.sel():
            _, next_res = buf.find('\n\n\\s*', region.begin())
            if next_res == -1:
                next_res = buf.size()
            reg = sublime.Region(next_res, next_res)
            buf.sel().subtract(region)
            buf.sel().add(reg)

        buf.show(reg, False)


class NavigateByParagraphBackwardCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        region = buf.sel()[0]
        buffer_rev = buf.substr(sublime.Region(-1, region.begin() - 1))[::-1]
        for m in re.finditer(r'\S *\n\n', buffer_rev):
            end = region.begin() - m.start()
            break
        else:
            end = -1
        reg = sublime.Region(end - 2, end - 2)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, False)
