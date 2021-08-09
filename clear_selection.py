import sublime
import sublime_plugin

class ClearSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        for region in buf.sel():
            buf.sel().subtract(region)
            line, col = buf.rowcol(region.end())
            if col == 0:
                buf.sel().add(region.b - 1)
            else:
                buf.sel().add(region.b)
