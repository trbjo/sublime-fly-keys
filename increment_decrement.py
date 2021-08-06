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
                i_pointer = column + i
                if cur_line[i_pointer].isdigit() or (not end_pos and cur_line[i_pointer] == '-' and cur_line[i_pointer + 1].isdigit()):

                    if not start_pos and first_char_is_digit == False:
                        start_pos = i_pointer

                    end_pos = i_pointer

                elif end_pos:
                    break

            if not start_pos:
                for j in range(to_the_left):
                    j_pointer = column - j
                    if cur_line[j_pointer].isdigit() or (cur_line[j_pointer] == '-' and cur_line[j_pointer + 1].isdigit()):

                        if not end_pos:
                            end_pos = j_pointer

                        start_pos = j_pointer

                    elif start_pos:
                        break

            if start_pos is not None and end_pos is not None:
                selection.subtract(region)
                selection.add(sublime.Region(buf.text_point(line, start_pos), buf.text_point(line, end_pos + 1)))

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
