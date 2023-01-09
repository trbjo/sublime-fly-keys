import re
import string
from typing import List, Union

import sublime
import sublime_plugin
from sublime import Edit, Region, Selection, View, active_window, load_binary_resource

WORDCHARS = r"[-\._\w]+"


class SmartFindBoundaryCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        sel = buf.sel()
        for reg in sel:
            line_indices: Region = buf.full_line(reg)
            line_contents = buf.substr(line_indices)

            if len(line_contents) <= 1:
                continue

            cursor_begin: int = reg.a - line_indices.a

            if reg.a == reg.b or not line_contents[cursor_begin].isspace():
                # handle situation where cursor is at the end of the line:
                if reg.b == line_indices.b - 1:
                    cursor_begin -= 1

                # we find out if the cursor is already at a word
                while line_contents[cursor_begin].isspace() and cursor_begin < len(
                    line_contents
                ):
                    cursor_begin += 1

            if reg.empty():
                cursor_end: int = cursor_begin
            else:
                cursor_end: int = reg.b - line_indices.a

                if reg.b != line_indices.b - 1:
                    cursor_end += 1

                while (
                    line_contents[cursor_end].isspace()
                    and cursor_end < len(line_contents) - 1
                ):
                    cursor_end += 1

            while not line_contents[cursor_end].isspace() and cursor_end < len(
                line_contents
            ):
                cursor_end += 1

            left_offset: int = 0
            for i in range(cursor_begin + 1):
                if line_contents[cursor_begin::-1][i].isspace():
                    left_offset = i - 1
                    break
            else:
                # match until beginning of line:
                left_offset = i

            left_abs_pos = line_indices.a + cursor_begin - left_offset
            right_abs_pos = line_indices.a + cursor_end

            if reg.empty():
                sel.subtract(reg)

            sel.add(Region(left_abs_pos, right_abs_pos))


class SmartFindWordCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        sel = buf.sel()
        positions: List[int] = []
        for reg in sel:
            if not reg.empty():
                end_pos = reg.end()
                sel.subtract(reg)
                sel.add(end_pos)

            str_after_cur = buf.substr(reg.begin())
            if str_after_cur.isalnum() or str_after_cur == "_":
                if len(sel) > 1:
                    positions.append(reg.a)
                    continue
                else:
                    return

            str_before_cur = buf.substr(reg.begin() - 1)
            if str_before_cur.isalnum() or str_before_cur == "_":
                if len(sel) > 1:
                    positions.append(reg.a)
                    continue
                else:
                    return

            cur_line_in_points_beg, cur_line_in_points_end = buf.line(reg)

            rev_reg = Region(cur_line_in_points_beg, reg.begin())
            rev_reg_str = buf.substr(rev_reg)
            i = 0
            rev_beg = -1
            for char in reversed(rev_reg_str):
                if rev_beg == -1:
                    if char.isalnum() or char == "_":
                        rev_beg = i
                        break
                i += 1

            forw_reg_str = ""
            if rev_beg > 1 or rev_beg == -1:
                forw_reg = Region(cur_line_in_points_end, reg.begin())
                forw_reg_str = buf.substr(forw_reg)
            if len(forw_reg_str) > 0:
                j = 0
                forw_beg = -1
                for char in forw_reg_str:
                    if forw_beg == -1:
                        if char.isalnum() or char == "_":
                            forw_beg = j
                            break
                    j += 1

                if forw_beg != -1 and rev_beg == -1:
                    positions.append(reg.a + forw_beg)
                elif forw_beg < rev_beg:
                    positions.append(reg.a + forw_beg)
                elif rev_beg != -1:
                    positions.append(reg.a - rev_beg)
                else:
                    positions.append(reg.a)
                    continue
            else:
                positions.append(reg.a - rev_beg)

        sel.clear()
        buf.sel().add_all(positions)
