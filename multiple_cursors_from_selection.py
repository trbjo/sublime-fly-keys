import sublime
import sublime_plugin

class MultipleCursorsFromSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        lines = []
        for region in buf.sel():
            line_begin, _ = buf.rowcol(region.begin())
            line_end, _ = buf.rowcol(region.end())
            for line in range(line_end - line_begin):
                line_in_point, _ = sublime.Region(buf.text_point(line_begin + line, 0),0)
                lines.append((buf.find(r'\S', line_in_point).begin()))
        buf.sel().clear()
        buf.sel().add_all(lines)
