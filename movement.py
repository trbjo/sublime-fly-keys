import re
import time

import sublime_plugin
from sublime import Region
from sublime_api import view_selection_add_point as add_point  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_api import view_show_point as show_point  # pyright: ignore
from sublime_plugin import TextCommand

from .base import buffer_slice

then = time.time()

normrgx = re.compile(r"[-\w]+")
wholergx = re.compile(r"\S+")


class NavigateWordCommand(TextCommand):
    def run(
        self, _, forward: bool = True, whole_words: bool = False, extend: bool = False
    ):
        v = self.view
        s = v.sel()
        if len(s) < 1:
            return

        vid = v.id()
        pts = []
        rgx = wholergx if whole_words else normrgx

        bufind = buffer_slice(v, forward)
        bufind.send(None)
        for a, b in s if forward else reversed(s):
            mend = b
            while match := bufind.send((mend, rgx)):
                mstart, mend = match
                if mstart == b and (mend == a or (extend and forward is (a > mend))):
                    continue

                shrink = a != b and forward is (a > b)
                if extend:
                    a = b if shrink and (forward is (mstart > a) or b == mstart) else a
                    b = mstart if shrink and a != b else mend
                else:
                    a = mstart if b != mstart or shrink else a
                    b = mend

                break
            pts.append((a, b))

        s.clear()
        for start, end in pts:
            add_region(vid, start, end, 0.0)
        show_point(vid, s[-1 if forward else 0].b, False, False, False)


class NavigateParagraphCommand(TextCommand):
    forward = re.compile(r"(\n[\t ]*){2,}")
    backward = re.compile(r"\S(?=[\t ]*\n\n)")

    def add_regs(self, regs, forward: bool, extend: bool = False):
        v = self.view
        s = v.sel()
        vid = v.id()

        s.clear()
        if extend:
            for a, b, *_ in regs:
                add_region(vid, a, b, 0.0)
        else:
            for a, b, *_ in regs:
                add_point(vid, b)

        show_point(vid, s[-1 if forward else 0].b, False, False, False)


sels = set()


class LineOrParagraphCommand(NavigateParagraphCommand):
    backpat = re.compile(r"\S\s*(\n|\Z)")

    def run(self, _, forward: bool = True):
        v = self.view
        s = v.sel()
        global sels
        global then
        now = time.time()

        bufind = buffer_slice(v, forward, True)
        bufind.send(None)
        current_sels = {r.b for r in s}
        check_lines = (
            any(r.a != r.b for r in s) or now - then >= 1 or bool(sels - current_sels)
        )

        if check_lines:
            if forward:
                regs = [(r.begin(), v.line(r.b).b, r.b) for r in s]
            else:
                regs = []
                for r in reversed(s):
                    line = v.line(r.b)
                    end = bufind.send((line.b, self.backpat))[0] - 1
                    start = end if end < line.a else max(r.end(), end)
                    regs.append((start, end, r.b))
            check_lines = any(b != c for _, b, c in regs)

        if not check_lines:
            pattern = self.forward if forward else self.backward
            sel = s if forward else reversed(s)
            regs = [bufind.send((b - 1, pattern)) for a, b in sel]
            then = now

        sels = {b for (a, b, *_) in regs}
        self.add_regs(regs, forward, check_lines)


class ExpandParagraphCommand(NavigateParagraphCommand):
    forline = re.compile(r"\S\n(?=\n[\t ]*)")
    shrink_forline = re.compile(r"\n\n(?=[\t ]*\S)")
    backline = re.compile(r".[\t ]*(?=(([\t ]*\n){2,}))")
    shrink_backline = re.compile(r"\n(?=\n\S)")

    def run(self, _, forward: bool = True):
        v = self.view
        s = v.sel()

        all_empty = all(r.a == r.b for r in s)
        buffinder_b = buffer_slice(v, forward, True)
        buffinder_b.send(None)
        pattern = self.forline if forward else self.backline
        bregs = []
        if forward:
            shrinkpattern = self.shrink_forline
            growpattern = self.forline
        else:
            shrinkpattern = self.shrink_backline
            growpattern = self.backline

        offset = -1 if forward else 1
        for a, b in s if forward else reversed(s):
            if a != b:
                pattern = shrinkpattern if (a > b) is forward else growpattern
                pt = buffinder_b.send((b, pattern))[1]
                if forward and pt > a or not forward and pt < a:
                    pt = buffinder_b.send((b, growpattern))[1]
            else:
                pt = buffinder_b.send((b + offset, growpattern))[1]

            bregs.append(pt)

        if all_empty:
            buffinder_a = buffer_slice(v, not forward, True)
            buffinder_a.send(None)
            offset = 1 if forward else -1

            _pattern = self.backline if forward else self.forline

            a_regs = [
                buffinder_a.send((b + offset, _pattern))
                for a, b in (s if forward else reversed(s))
            ]

            aregs = [b for a, b in a_regs]
        else:
            aregs = [
                (b if ((x >= a > b) if forward else (x <= a < b)) else a)
                for (a, b), x in zip(s, bregs)
            ]

        regs = list(zip(aregs, bregs))

        self.add_regs(regs, forward, True)


class SmartFindWordCommand(sublime_plugin.TextCommand):
    def find_pt(self, line: str, start: int, stop: int, forward: bool) -> int:
        for i in range(start, stop, 1 if forward else -1):
            if line[i].isalnum() or line[i] == "_":
                return i
        return stop

    def run(self, _) -> None:
        v = self.view
        sel = v.sel()
        for reg in sel:
            if not (line := v.substr(v.full_line(reg.b))):
                continue

            line_no, column = v.rowcol(reg.b)

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

            pos = v.text_point(line_no, pos)
            sel.subtract(reg)
            sel.add(Region(pos))
        v.run_command("find_under_expand")
