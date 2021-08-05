import sublime
import sublime_plugin

class NumberCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        buf = self.view
        selection = buf.sel()
        for region in selection:
            if region.begin() != region.end():
                continue

            line, column = buf.rowcol(region.begin())
            cur_line = buf.substr(buf.full_line(buf.text_point(line,0)))
            line_length = len(cur_line)
            start_pos = None
            end_pos = None
            to_the_right = line_length - column
            to_the_left = line_length - (line_length - column) + 1

            if cur_line[column].isdigit() or (cur_line[column] == '-' and cur_line[column + 1].isdigit()):
                first_char_is_digit = True
            else:
                first_char_is_digit = False

            for i in range(to_the_right):
                if cur_line[column + i].isdigit() or (cur_line[column + i] == '-' and cur_line[column + i + 1].isdigit()):

                    if not start_pos and first_char_is_digit == False:
                        start_pos = column + i

                    if not end_pos:
                        end_pos = column + i + 1
                    else:
                        end_pos += 1

                elif end_pos:
                    break

            if not start_pos:
                for j in range(to_the_left):
                    if cur_line[column - j].isdigit() or (cur_line[column - j] == '-' and cur_line[column - j + 1].isdigit()):

                        if not end_pos:
                            end_pos = column - j + 1

                        if not start_pos:
                            start_pos = column - j
                        else:
                            start_pos -= 1

                    elif start_pos:
                        break

            if start_pos is not None and end_pos is not None:
                buf.sel().subtract(region)
                buf.sel().add(sublime.Region(buf.text_point(line, start_pos), buf.text_point(line, end_pos)))

        for region in selection:
            try:
                value = int(buf.substr(region))
                buf.replace(edit, region, str(self.op(value)))
            except ValueError:
                    pass


class IncrementCommand(NumberCommand):
    def op(self, value):
          return value + 1

class DecrementCommand(NumberCommand):
    def op(self, value):
          return value - 1
