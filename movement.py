import re
from bisect import bisect
from typing import Dict, List

import sublime_plugin
from sublime import Edit, FindFlags, Region
from sublime_api import view_add_regions  # pyright: ignore
from sublime_api import view_find  # pyright: ignore
from sublime_api import view_cached_substr as substr  # pyright: ignore
from sublime_api import view_selection_add_point as add_point  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_api import view_show_point as show_point  # pyright: ignore
from sublime_plugin import TextCommand

from .base import get_regions


class BolCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit):
        v = self.view
        s = v.sel()
        vid = v.id()
        pat = r"\s*(?=\S)"
        pts = [
            (r.a if r.a > r.b else r.b, v.find(pat, v.line(r.begin()).begin()).b)
            for r in s
        ]
        s.clear()
        [
            add_region(vid, r[0], r[1], 0.0) if r[1] < r[0] else add_point(vid, r[1])
            for r in pts
        ]
        show_point(vid, s[0].b, False, False, False)


class EolCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit):
        v = self.view
        s = v.sel()
        vid = v.id()
        pts = [(r.a if r.a < r.b else r.b, v.line(r.end()).b) for r in s]
        s.clear()
        [add_region(vid, r[0], r[1], 0.0) for r in pts]
        show_point(vid, s[-1].b, False, False, False)


class NavigateWordCommand(TextCommand):
    regex = r"[-<>\w]+"

    def run(self, _, forward: bool = True):
        v = self.view
        s = v.sel()
        vi = v.id()
        if len(s) < 1:
            return
        vid = v.id()

        if forward:
            pts = [view_find(vi, self.regex, r.b, FindFlags.NONE) for r in s]
            if not (len(pts) == 1 and pts[0].a == -1):
                s.clear()
                [add_region(vid, r.a, r.b, 0.0) for r in pts if r.a != -1]
            show_point(vid, s[-1].b, False, False, False)
        else:
            most_recent = v.size() + 1
            last = s[-1].b
            myiter = re.finditer(self.regex, substr(vid, 0, last)[::-1])
            pts = [] if s[0].b != 0 else [(s[0].a, s[0].b)]
            for r in reversed(s):
                for m in myiter:
                    if r.b > last - m.end():
                        if r.b < most_recent:
                            most_recent = last - m.end()
                            pts.append((min(r.b, last - m.start()), last - m.end()))
                        break
            if pts:
                s.clear()
                [add_region(vid, a[0], a[1], 0.0) for a in pts]
            show_point(vid, s[0].b, False, False, False)


class NavigateByParagraphForwardCommand(TextCommand):
    def run(self, _) -> None:
        v = self.view
        region = v.sel()[-1].begin()
        try:
            myregs = get_regions(v, "last")
            bisect_res = bisect(myregs, region)
            sel_end = myregs[bisect_res]
        except IndexError:
            myregs = get_regions(view=v, part="last", now=True)
            bisect_res = bisect(myregs, region)
            sel_end = myregs[bisect_res]
        reg = Region(sel_end)
        v.sel().clear()
        v.sel().add(reg)
        v.show(reg.b, True)


class NavigateByParagraphBackwardCommand(TextCommand):
    def run(self, _) -> None:
        buf = self.view
        region = buf.sel()[0].begin()
        try:
            myregs = get_regions(buf, "last")
            bisect_res = bisect(myregs, region - 1)
            sel_end: int = myregs[bisect_res - 1]
        except IndexError:
            myregs = get_regions(view=buf, part="last", now=True)
            bisect_res = bisect(myregs, region - 1)
            sel_end: int = myregs[bisect_res - 1]
        reg = Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)

        buf.show(reg.b, True)


class ExtendedExpandSelectionToParagraphForwardCommand(TextCommand):
    def run(self, _) -> None:
        buf = self.view
        regs_dict: Dict[int, int] = {}
        first = get_regions(buf, "first")
        for region in buf.sel():
            if region.b > region.a:
                bisect_res = bisect(first, region.b - 1)
                sel_begin = buf.full_line(region.a).a
                sel_end = first[bisect_res] + 2

            elif region.a > region.b:
                bisect_res = bisect(first, region.b)
                sel_end = first[bisect_res] + 2
                if region.a == sel_end or sel_end - 3 == region.a:
                    sel_end = region.a
                    sel_begin = region.b
                else:
                    sel_begin = region.a
                    buf.sel().subtract(region)

            elif region.a == region.b:
                bisect_res = bisect(first, region.b - 2)
                sel_begin = first[bisect_res - 1] + 2
                sel_end = first[bisect_res] + 2

            else:
                return

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all(Region(begin, end) for begin, end in regs_dict.items())
        buf.show(buf.sel()[-1].b, False)


class ExtendedExpandSelectionToParagraphBackwardCommand(TextCommand):
    def run(self, _) -> None:
        buf = self.view
        regs_dict: Dict[int, int] = {}
        first = get_regions(buf, "first")
        for region in buf.sel():
            if region.b > region.a:
                bisect_end = bisect(first, region.b - 3)
                sel_end = first[bisect_end - 1] + 2
                if region.a == sel_end:
                    sel_begin = region.b
                else:
                    sel_begin = buf.full_line(region.a).a
                    buf.sel().subtract(region)

            elif region.a > region.b:
                sel_begin = region.a
                bisect_end = bisect(first, region.b - 3)
                if bisect_end == 0:
                    sel_end = -1
                else:
                    sel_end = first[bisect_end - 1] + 2

            elif region.b == region.a:
                bisect_end = bisect(first, region.b - 2)
                sel_end = first[bisect_end - 1] + 2
                sel_begin = first[bisect_end] + 2

            else:
                return

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all(Region(begin, end) for begin, end in regs_dict.items())
        buf.show(buf.sel()[0].b, False)


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
