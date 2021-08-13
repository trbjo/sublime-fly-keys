import sublime
import sublime_plugin

class SingleSelectionLastCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        reg = buf.sel()[-1]
        buf.sel().clear()
        buf.sel().add(reg)
