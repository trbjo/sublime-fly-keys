import re
from bisect import bisect
from typing import Dict

import sublime_plugin
from sublime import Edit, FindFlags, Region
from sublime_api import view_add_regions  # pyright: ignore
from sublime_api import view_cached_substr as substr  # pyright: ignore
from sublime_api import view_find as vfind  # pyright: ignore
from sublime_api import view_selection_add_point as add_point  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_api import view_selection_subtract_region as subtract_region
from sublime_api import view_show_point as show_point  # pyright: ignore
from sublime_plugin import TextCommand

from .base import get_regions

normrgx = re.compile(r"^[-\w]+$")
wholergx = re.compile(r"^\S+$")


class BolCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit, extend=True):
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
            add_region(vid, r[0], r[1], 0.0)
            if r[1] < r[0] and extend
            else add_point(vid, r[1] if r[1] != -1 else r[0])
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
    def run(
        self, _, forward: bool = True, whole_words: bool = False, extend: bool = False
    ):
        rgx = r"\S+" if whole_words else r"[-\w]+"
        rrev = r"\s+" if whole_words else r"[^-\w]+"
        compiled_rgx = wholergx if whole_words else normrgx

        v = self.view
        s = v.sel()
        vi = v.id()
        if len(s) < 1:
            return
        vid = v.id()
        pts = []

        if forward:
            flag = FindFlags.NONE
            for r in s:
                pat = rgx
                pt = r.end()
                if r.a > r.b and not re.match(compiled_rgx, v.substr(r)):
                    pat = rrev if extend else rgx
                    pt = r.b
                pts.append((vfind(vi, pat, pt, flag), r))

        else:
            flag = FindFlags.REVERSE
            for r in s:
                pat = rgx
                pt = r.begin()
                if r.b > r.a and not re.match(compiled_rgx, v.substr(r)):
                    pat = rrev if extend else rgx
                    pt = r.b
                pts.append((vfind(vi, pat, pt, flag), r))

        if forward and extend:
            for r in pts:
                if r[1].a > r[1].b:
                    subtract_region(vi, r[1].b, r[0].b)
                    if r[0].b >= r[1].a:
                        add_region(vid, r[1].begin(), r[0].b, 0.0)
                else:
                    if r[0].a != -1:
                        add_region(vid, r[1].a, r[0].b, 0.0)
        elif not forward and extend:
            for r in pts:
                if r[1].a < r[1].b:
                    subtract_region(vi, r[1].b, r[0].a)
                    if r[0].a <= r[1].a:
                        add_region(vid, r[1].b, r[0].a, 0.0)
                else:
                    add_region(vid, r[1].a, r[0].a, 0.0)
        elif forward and not extend:
            if not (len(pts) == 1 and pts[0][0].a == -1):
                last = s[-1]
                save_last = False
                s.clear()
                for r in pts:
                    if r[0].a != -1:  # eof workaround
                        rg = r[1].b if r[1].a == r[0].a else r[0].a
                        add_region(vid, rg, r[0].b, 0.0)
                    else:
                        save_last = True
                if save_last:
                    add_region(vid, last.a, last.b, 0.0)

        elif not forward and not extend:
            if not (len(pts) == 1 and pts[0][0].a == -1):
                first = s[0]
                save_first = False
                s.clear()
                for r in pts:
                    if r[0].a != -1:  # bof workaround
                        rg = r[0].b if r[1].end() > r[0].b else r[1].end()
                        add_region(vid, rg, r[0].a, 0.0)
                    else:
                        save_first = True
                if save_first:
                    add_region(vid, *first, 0.0)

        show_point(vid, s[-1 if forward else 0].b, False, False, False)


class NavigateByParagraphForwardCommand(TextCommand):
    def run(self, _) -> None:
        v = self.view
        vi = v.id()
        pts = []
        for r in v.sel():
            region = r.begin()
            try:
                myregs = get_regions(v, "last")
                bisect_res = bisect(myregs, region)
                sel_end = myregs[bisect_res]
            except IndexError:
                myregs = get_regions(view=v, part="last", now=True)
                bisect_res = bisect(myregs, region)
                sel_end = myregs[bisect_res]
            pts.append(sel_end)

        v.sel().clear()
        [add_point(vi, p) for p in pts]
        v.show(v.sel()[-1].b, True)


class NavigateByParagraphBackwardCommand(TextCommand):
    def run(self, _) -> None:
        v = self.view

        vi = v.id()
        pts = []
        for r in v.sel():
            region = r.begin()
            try:
                myregs = get_regions(v, "last")
                bisect_res = bisect(myregs, region - 1)
                sel_end: int = myregs[bisect_res - 1]
            except IndexError:
                myregs = get_regions(view=v, part="last", now=True)
                bisect_res = bisect(myregs, region - 1)
                sel_end: int = myregs[bisect_res - 1]
            pts.append(sel_end)

        v.sel().clear()
        [add_point(vi, p) for p in pts]
        v.show(v.sel()[0].b, True)


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
    def find_pt(self, line: str, start: int, stop: int, forward: bool) -> int:
        for i in range(start, stop, 1 if forward else -1):
            if line[i].isalnum() or line[i] == "_":
                return i
        return stop

    def run(self, _) -> None:
        buf = self.view
        sel = buf.sel()
        for reg in sel:
            if not (line := buf.substr(buf.full_line(reg.b))):
                continue

            line_no, column = buf.rowcol(reg.b)

            left_pos = self.find_pt(line, column, -1, False)
            right_pos = self.find_pt(line, column, len(line), True)

            if left_pos == right_pos:
                continue
            elif right_pos != len(line) and left_pos == -1:
                pos = right_pos
            elif right_pos == len(line) and left_pos != -1:
                pos = left_pos + 1
            elif right_pos - column < column - left_pos:
                pos = right_pos
            else:
                pos = left_pos + 1

            pos = buf.text_point(line_no, pos)
            sel.subtract(reg)
            sel.add(Region(pos))
