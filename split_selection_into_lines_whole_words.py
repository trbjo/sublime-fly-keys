import sublime
import sublime_plugin

import re
WORDCHARS = r'[-\._\w]+'

class SplitSelectionIntoLinesWholeWordsCommand(sublime_plugin.TextCommand):
    def run(self, view):
        buf = self.view
        selections = buf.sel()
        for region in reversed(selections):
            if region.empty():
                continue

            contents = buf.substr(region)
            begin = region.begin()
            word_boundaries = [sublime.Region(m.start() + begin, m.end() + begin) for m in re.finditer(WORDCHARS, contents)]
            if word_boundaries != []:
                selections.subtract(region)
                selections.add_all(word_boundaries)

