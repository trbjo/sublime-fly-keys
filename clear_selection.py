import sublime
import sublime_plugin

class ClearSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        for region in buf.sel():
            buf.sel().subtract(region)
            buf.sel().add(region.end() - 1)
