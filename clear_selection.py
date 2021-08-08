import sublime
import sublime_plugin

class ClearSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        for region in buf.sel():
            buf.sel().subtract(region)
            if region.a > region.b:
                buf.sel().add(region.b)
            else:
                buf.sel().add(region.b - 1)
