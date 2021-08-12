import sublime
import sublime_plugin

class SmartPasteCommand(sublime_plugin.TextCommand):

    def find_indent(self, cur_line_num, cur_line) -> int:
        buf = self.view
        clipboard = sublime.get_clipboard()
        if len(cur_line) == 0 and clipboard.startswith(' '):
            lines_above, _ = buf.line(cur_line_num.begin())
            for line in range(lines_above):
                line += 1
                prev_line = buf.substr(buf.line(cur_line_num.begin() - line))
                if prev_line.startswith(' '):
                    break
            indent = len(prev_line) - len(prev_line.lstrip())
        else:
            indent = len(cur_line) - len(cur_line.lstrip())
        return indent


    def run(self, edit):
        buf = self.view
        selections = buf.sel()
        clipboard = sublime.get_clipboard()
        clips = clipboard.splitlines()

        if clipboard.endswith('\n'):
            has_final_newline = True
        else:
            has_final_newline = False

        if len(clips) == len(selections):
            for region, cliplet in zip(reversed(selections), reversed(clips)):

                cur_line_num = buf.line(region.begin())
                cur_line = buf.substr(cur_line_num)

                if has_final_newline:
                    insert_pos, _ = buf.line(region.begin())
                else:
                    insert_pos = region.begin()

                if has_final_newline:
                    indent = self.find_indent(cur_line_num, cur_line)
                    insert_string = " " * indent + cliplet.lstrip() + '\n'
                else:
                    insert_string = cliplet

                if region.empty() == False:
                    buf.erase(edit, region)

                buf.insert(edit, insert_pos, insert_string)

        else:
            for region in reversed(selections):
                cur_line_num = buf.line(region.begin())
                cur_line = buf.substr(cur_line_num)

                if has_final_newline:
                    insert_pos, _ = buf.line(region.begin())
                else:
                    insert_pos = region.begin()


                if has_final_newline:
                    above_indent = self.find_indent(cur_line_num, cur_line)
                    insert_string = ''
                    initial_indent = None
                    for line in clips:
                        deindented_line = line.lstrip().rstrip()
                        cur_indent = len(line) - len(deindented_line)
                        if initial_indent == None:
                            initial_indent = cur_indent
                        this_indent = above_indent + cur_indent - initial_indent
                        insert_string += " " * this_indent  + deindented_line + '\n'
                else:
                    insert_string = clipboard

                if region.empty() == False:
                    buf.erase(edit, region)

                buf.insert(edit, insert_pos, insert_string)


