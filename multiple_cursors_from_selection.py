import sublime
import sublime_plugin

import re

class MultipleCursorsFromSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        reg_list = []
        for region in buf.sel():
            reg_begin = region.begin() - 1
            reg_end = region.end() - 1
            buffer = buf.substr(sublime.Region(reg_begin, reg_end))
            if reg_begin > 1:
                reg_begin -= 1
            else:
                reg_list.append(-1)
            reg_list += [m.end() + reg_begin for m in re.finditer(r'\n *\S', buffer)]
        buf.sel().clear()
        buf.sel().add_all([sublime.Region(i) for i in reg_list])
