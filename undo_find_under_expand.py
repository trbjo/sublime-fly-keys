import sublime
import sublime_plugin

from re import finditer

class UndoFindUnderExpandCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        selection = buf.sel()

        if len(selection) == 1:
            buf.show(selection[0], True)
            return

        selected_word = buf.substr(selection[-1])
        min_point = selection[0].begin()
        max_point = selection[-1].end()

        res = buf.find(selected_word, start_pt=max_point)
        if res.begin() != -1:
            selection.subtract(selection[-1])
            buf.show(selection[-1], True)
            return

        reg = sublime.Region(min_point, max_point)
        all_regs = [min_point +  m.end() for m in finditer(selected_word, buf.substr(reg))]

        i = 0
        for region in selection:
            if region.end() < all_regs[i]:
                # Consider a continue statement here instead.
                # Depends on what strategy works best
                selection.subtract(region)
                buf.show(selection[i-1], True)
                return
            elif region.end() > all_regs[i]:
                selection.subtract(selection[i-1])
                buf.show(selection[i-2], True)
                return
            i += 1

        selection.subtract(selection[-1])
        buf.show(selection[-1], True)
