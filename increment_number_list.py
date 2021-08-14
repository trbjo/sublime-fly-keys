import sublime
import sublime_plugin

class IncrementNumberListCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        selections = buf.sel()
        for region in reversed(selections):
            cur_line_num, _ = buf.rowcol(region.end())
            cur_line = buf.substr(buf.line(region))
            num = ''
            for char in cur_line:
                if char.isdigit():
                    num+=char
                else:
                    break
            num = int(num) + 1
            buf.insert(edit, region.end(), f'\n{num}. ')

            next_line_num_offset = cur_line_num + 1
            continue_while = True
            while continue_while == True:
                next_line_num_offset += 1
                next_line_begin_in_points = buf.text_point(next_line_num_offset, 0)
                next_line_content = buf.substr(buf.line(next_line_begin_in_points))

                if len(next_line_content) < 1:
                    continue_while = False
                    break
                if not next_line_content[0].isdigit():
                    continue_while = False
                    break

                next_num = next_line_content[0]
                for char in next_line_content[1:]:
                    if char.isdigit():
                        next_num+=char
                    else:
                        offset = len(next_num)
                        next_num = int(next_num) + 1
                        buf.erase(edit,sublime.Region(next_line_begin_in_points, next_line_begin_in_points+offset))
                        buf.insert(edit, next_line_begin_in_points, f'{next_num}')
                        break

