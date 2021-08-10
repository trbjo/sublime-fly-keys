import sublime
import sublime_plugin

class DeleteSelectionAndInsertCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        for region in reversed(buf.sel()):
            if region.empty():
                continue
            buf.erase(edit, region)
        buf.settings().set(key="block_caret", value=False)






