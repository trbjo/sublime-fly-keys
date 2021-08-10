import sublime_plugin

class ClearSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _, forward):
        buf = self.view
        for region in buf.sel():
            buf.sel().subtract(region)
            if forward == True:
                _, col = buf.rowcol(region.end())
                if col == 0:
                    reg = region.end() - 1
                else:
                    reg = region.end()
            else:
                reg = region.begin()
            buf.sel().add(reg)
            buf.show(reg, False)
