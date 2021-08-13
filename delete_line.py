import sublime
import sublime_plugin

class DeleteSmartCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        for region in reversed(buf.sel()):
            if region.empty():
                if region.a == buf.size():
                    reg = buf.full_line(region.begin() -1)
                else:
                    reg = buf.full_line(region.begin())
            else:
                begin_line, _ = buf.rowcol(region.begin())
                end_line, col = buf.rowcol(region.end())
                if col != 0:
                    end_line += 1
                reg_beg = buf.text_point(begin_line, 0)
                reg_end = buf.text_point(end_line, 0) - 1
                reg = sublime.Region(reg_beg, reg_end + 1)
            buf.erase(edit, reg)
