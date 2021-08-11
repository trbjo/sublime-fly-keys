import sublime
import sublime_plugin

import re

class MultipleCursorsFromSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        reg_list = []
        for region in buf.sel():
            reg_begin = region.begin() - 1
            buffer = buf.substr(sublime.Region(reg_begin, region.end()))
            if reg_begin <= 1:
                reg_begin += 1
                reg_list.append(-2)
            reg_list += [sublime.Region(m.start() + reg_begin) for m in re.finditer(r'\S.+\n', buffer)]
        buf.sel().clear()
        buf.sel().add_all(reg_list)
