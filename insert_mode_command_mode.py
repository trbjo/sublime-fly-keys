import sublime_plugin

class InsertModeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        for region in reversed(buf.sel()):
            if region.empty():
                continue
            buf.erase(edit, region)
        buf.settings().set(key="block_caret", value=False)
        buf.settings().set(key="command_mode", value=False)


class CommandModeCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        buf.settings().set(key="block_caret", value=True)
        buf.settings().set(key="command_mode", value=True)


class InsertBeforeOrAfterCommand(sublime_plugin.TextCommand):
    def run(self, _, after=False):
        buf = self.view
        selections = buf.sel()
        for region in selections:

            if region.empty():
                continue

            if after == True:
                reg = region.end() + 1
            else:
                reg = region.begin() - 1

            selections.subtract(region)
            selections.add(reg)

        buf.settings().set(key="block_caret", value=False)
        buf.settings().set(key="command_mode", value=False)

