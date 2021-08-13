import sublime
import sublime_plugin

from re import finditer
from itertools import zip_longest

class DeselectLastSelectionAndRefocusCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        selection = buf.sel()
        selection_length = len(selection)

        if selection_length == 1:
            return

        l = []
        selected_word = buf.substr(selection[-1])
        for i in range(selection_length -2):
            if selected_word == buf.substr(selection[i+1]):
                l.append(selection[i])
                if i == selection_length -2:
                    l.append(selection[i+1])

        min_point, _ = selection[0]
        _, max_point = selection[-1]
        reg = sublime.Region(min_point, max_point)
        all_regs = [ min_point +  m.end() for m in finditer(selected_word, buf.substr(reg))]

        i = 0
        for region, word in zip_longest(selection, all_regs,fillvalue=(-1, -1)):
            if region.end() != word:
                selection.subtract(selection[i-1])
                if i == 1:
                    buf.show(selection[-1], True)
                else:
                    buf.show(selection[i-2], True)
                break
            i+=1
        else:
            selection.subtract(selection[-1])
            buf.show(selection[-1], True)
