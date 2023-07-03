import re
from collections import defaultdict
from typing import Iterable, List, Tuple

import sublime_api
import sublime_plugin
from sublime import Edit, Region, Selection, View, active_window
from sublime_api import view_cached_substr as substr
from sublime_api import view_cached_substr as view_substr
from sublime_api import view_selection_add_point as add_point
from sublime_api import view_selection_add_region as add_region
from sublime_api import view_selection_subtract_region as subtract_region
from sublime_api import view_show_point as show_point
from sublime_plugin import TextCommand, TextInputHandler

# expand to next
matchers: str = """([{)]}"'"""
PositionAndType = Tuple[int, int]


pattern_cache = {}
WORDCHARS = r"[-\._\w]+"


class SmarterSelectLines(TextCommand):
    def run(self, edit, forward: bool):
        v = self.view
        s = v.sel()

        if len(s) == 0:
            return

        if [
            (s.subtract(x), s.add(x.b if forward else x.a))
            for x in filter(lambda r: r.a != r.b, s)
        ]:
            return

        if (s[-1].end() == v.size() and forward) or (s[0].begin() == 0 and not forward):
            return

        vid = v.id()

        # hardbol
        if all(v.line(r.b).a == r.b for r in s):
            if forward:
                for r in list(s):
                    s.add(v.line(v.line(r.b).b + 1).a)
            else:
                for r in list(s):
                    s.add(v.line(r.b - 1).a)

        # softbol
        elif all(
            (mystr := substr(vid, v.line(r.b).a, r.b + 1))[0:-1:].isspace()
            and not mystr[-1].isspace()
            or len(mystr) == 1
            # or mystr.isspace()
            for r in s
        ):
            if forward:
                for r in list(s):
                    next_line_reg = v.line(v.line(r.b).b + 1)
                    if next_line_reg.empty():
                        s.add(v.line(r.b).b + 1)
                    else:
                        mysubstr: str = substr(vid, next_line_reg.a, next_line_reg.b)
                        idx = len(mysubstr) - len(mysubstr.lstrip())
                        s.add(v.line(r.b).b + 1 + idx)
            else:
                for r in list(s):
                    prev_line_reg = v.line(v.line(r.b).a - 1)
                    if prev_line_reg.empty():
                        s.add(prev_line_reg.a)
                    else:
                        mysubstr: str = substr(vid, prev_line_reg.a, prev_line_reg.b)
                        idx = len(mysubstr) - len(mysubstr.lstrip())
                        s.add(v.line(prev_line_reg.a).a + idx)

        # hardeol
        elif all(v.line(r.b).b == r.b for r in s):
            if forward:
                for r in list(s):
                    s.add(v.line(r.b + 1).b)
            else:
                for r in list(s):
                    s.add(v.line(v.line(r.b).a - 1).b)

        # normal
        else:
            if forward:
                to_add: List[Region] = []
                for r in s:
                    line = v.line(r)
                    if line.a <= r.b <= line.b:
                        to_add.append(r)

                # cols = [v.rowcol(r.b)[1] for r in s]
                # col = max(cols)
                for lol in to_add:
                    next_line_reg = v.line(v.line(lol.b).b + 1)

                    col = v.rowcol(lol.b)[1]
                    if (next_line_reg.b - next_line_reg.a) > col:
                        s.add(next_line_reg.a + col)
                    else:
                        s.add(next_line_reg.b)
            else:
                cols = [v.rowcol(r.b)[1] for r in s]
                col = max(cols)
                for r in list(s):
                    prev_line_reg = v.line(v.line(r.b).a - 1)
                    if (prev_line_reg.b - prev_line_reg.a) > col:
                        s.add(prev_line_reg.a + col)
                    else:
                        s.add(prev_line_reg.b)

        if forward:
            v.show(s[-1].b)
        else:
            v.show(s[0].b)


def findall(p, length, s):
    """Yields all the positions of
    the pattern p in the string s."""
    i = s.find(p)
    while i != -1:
        yield i
        i = s.find(p, i + length)


class SelectOnlyDelimiterInSelection(TextCommand):
    def input(self, args):
        if "characters" not in args:
            include = args.get("include", False)
            return PatternInputHandler(pattern_cache.get(include, " "))

    def input_description(self) -> str:
        return "Pattern"

    def run(self, _, pattern, include=False):
        if not pattern:
            return

        pattern_cache[include] = pattern
        raw_pattern = pattern
        pattern = ""
        counter = 0
        while counter < len(raw_pattern):
            char = raw_pattern[counter]
            if ord(char) == 92:
                counter += 1
                if raw_pattern[counter] == "n":
                    pattern += "\n"
                elif raw_pattern[counter] == "r":
                    pattern += "\r"
                elif raw_pattern[counter] == "t":
                    pattern += "\t"
                elif raw_pattern[counter] == "\\":
                    pattern += "\\"
            else:
                pattern += char
            counter += 1

        v = self.view
        vid = v.id()
        length = len(pattern)

        if all(r.a == r.b for r in self.view.sel()):
            reg = Region(0, v.size())
            idx = list(findall(pattern, length, v.substr(reg)))
            if not idx:
                return
            if include:
                subtract_region(vid, reg.a, reg.b)
                [
                    add_region(vid, reg.begin() + i, reg.begin() + i + length, 0.0)
                    for i in idx
                ]
            else:
                add_region(vid, 0, v.size(), 0.0)
                [
                    subtract_region(vid, reg.begin() + i, reg.begin() + i + length)
                    for i in idx
                ]
            return

        for reg in list(v.sel()):
            if reg.empty():
                v.sel().subtract(reg)
                continue
            idx = list(findall(pattern, length, v.substr(reg)))
            if not idx:
                v.sel().subtract(reg)
                continue
            if include:
                subtract_region(vid, reg.a, reg.b)
                [
                    add_region(vid, reg.begin() + i, reg.begin() + i + length, 0.0)
                    for i in idx
                ]
            else:
                [
                    subtract_region(vid, reg.begin() + i, reg.begin() + i + length)
                    for i in idx
                ]


class PatternInputHandler(TextInputHandler):
    def __init__(self, initial_text):
        self._initial_text = initial_text

    def initial_text(self):
        return self._initial_text

    def validate(self, name):
        return len(name) > 0


class SubtractSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _, last=False) -> None:
        selections = self.view.sel()
        if len(selections) > 1:
            sel = -1 if last else 0
            selections.subtract(selections[sel])
            self.view.show(selections[sel].b, True)


recorded_selections = {}


class RecordSelectionsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        vi = self.view.id()
        sels = self.view.sel()
        recorded_selections[vi] = [(r.a, r.b) for r in sels]


class AddRecordedSelectionsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        vi = self.view.id()
        try:
            new_sels = recorded_selections[vi]
            [add_region(vi, r[0], r[1], 0.0) for r in new_sels]
        except KeyError:
            return


class SmarterFindUnderExpand(sublime_plugin.TextCommand):
    def run(self, edit, forward: bool = False, skip: bool = False) -> None:
        vi = self.view.id()
        sels = self.view.sel()
        first = sels[0].begin()
        last = sels[-1].end()
        size = self.view.size()

        if forward:
            padding = "\a" if first == 0 else ""
            buf: str = f"{padding}{view_substr(vi, first - 1, size)}\a"
        else:
            padding = "\a" if last == size else ""
            buf: str = f"\a{view_substr(vi, 0, last + 1)}{padding}"[::-1]

        words = defaultdict(list)
        for reg in sels:
            if reg.empty():
                continue
            wlen = reg.end() - reg.begin()
            offset = reg.begin() - first if forward else last - reg.end()
            word = buf[1 + offset : wlen + 1 + offset]
            words[word].append(reg)

        for word, regs in words.items():
            wlen = len(word)
            regex = r"\W" + re.escape(word) + r"\W"

            # imitate find under expand's boundary detection
            if forward:
                offsets = [r.begin() - first for r in regs]
                idx = regs[-1].end() - first
            else:
                offsets = [last - r.end() for r in regs]
                idx = last - regs[0].begin()

            at_boundary = all(re.match(regex, buf[o : wlen + 2 + o]) for o in offsets)

            while (idx := buf.find(word, idx + 1)) != -1:
                if not at_boundary or re.match(regex, buf[idx - 1 : idx + wlen + 1]):
                    break
            else:
                continue

            if skip:
                del_reg = regs[-1 if forward else 0]
                subtract_region(vi, del_reg.a, del_reg.b)

            if forward:
                start = first + idx - 1
                end = start + wlen
            else:
                end = last - idx + 1
                start = end - wlen

            add_region(
                vi,
                *((start, end) if any(r.b > r.a for r in regs) else (end, start)),
                0.0,
            )
            show_point(vi, end, True, False, True)


class MultipleCursorsFromSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        reg_list: List[Region] = []
        for region in buf.sel():
            reg_begin = region.begin() - 1
            buffer = buf.substr(Region(reg_begin, region.end()))
            if reg_begin <= 1:
                reg_begin += 1
                reg_list.append(Region(-2))
            reg_list += [
                Region(m.start() + reg_begin) for m in re.finditer(r"\S.*\n", buffer)
            ]
        buf.sel().clear()
        buf.sel().add_all(reg_list)


class MultipleCursorsFromSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _, after: bool = False) -> None:
        v = self.view
        vi = v.id()
        first = v.sel()[0].begin()
        buffer = sublime_api.view_cached_substr(v.id(), first, v.sel()[-1].end())
        for r in v.sel():
            v.sel().subtract(r)
            line = v.line(r.begin())
            line = Region(max(r.begin(), line.a), line.b)
            while line.a < r.end() and line.b <= v.size():
                if after:
                    add_point(vi, line.b)
                elif x := re.search(r"\S", buffer[line.a - first : line.b - first]):
                    add_point(vi, line.a + x.start())
                line = v.line(line.b + 1)


class FancySplitCommand(sublime_plugin.TextCommand):
    def run(self, _, after: bool = False) -> None:
        v = self.view
        vi = v.id()
        first = v.sel()[0].begin()
        buffer = sublime_api.view_cached_substr(v.id(), first, v.sel()[-1].end())
        regs = []
        for r in v.sel():
            line = v.line(r.begin())
            line = Region(max(r.begin(), line.a), line.b)
            while line.a < r.end() and line.b <= v.size():
                if x := re.search(r"\S", buffer[line.a - first : line.b - first]):
                    if after:
                        regs.append((line.a + x.start(), line.b))
                    else:
                        regs.append((line.b, line.a + x.start()))
                line = v.line(line.b + 1)
        v.sel().clear()
        [add_region(vi, *r, 0.0) for r in regs]


class RevertSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        sel = buf.sel()
        if all(r.a == r.b for r in sel):
            viewport_x, viewport_y = buf.viewport_extent()
            view_x_begin, view_y_begin = buf.viewport_position()
            view_y_end = view_y_begin + viewport_y

            first_cur_x, first_cur_y = buf.text_to_layout(sel[0].b)
            if view_y_begin < first_cur_y < view_y_end:
                buf.show(sel[-1].b, True)
            else:
                buf.show(sel[0].b, True)

        else:
            for reg in sel:
                if reg.empty():
                    continue
                region = Region(reg.b, reg.a)
                sel.subtract(reg)
                sel.add(region)

            buf.show(sel[-1].b, True)


class SingleSelectionLastCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        reg = buf.sel()[-1]
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg.b, True)


class SplitSelectionIntoLinesCommand(sublime_plugin.TextCommand):
    def bounds(self, regex: str):
        buf: View = self.view
        selections = buf.sel()
        to_subtract = []
        word_boundaries = []
        for region in selections:
            if region.empty():
                continue
            contents = buf.substr(region)
            begin = region.begin()
            local_bounds = [
                (m.start() + begin, m.end() + begin)
                for m in re.finditer(regex, contents)
            ]
            if len(local_bounds) > 1 and (
                local_bounds[0][0] != region.a or local_bounds[0][1] != region.b
            ):
                word_boundaries.extend(local_bounds)
                to_subtract.append(region)
        return word_boundaries, to_subtract

    def run(self, edit: Edit) -> None:
        view = self.view
        vid = view.id()
        word_boundaries, to_subtract = self.bounds(r"[\S]+")
        if not word_boundaries:
            word_boundaries, to_subtract = self.bounds(WORDCHARS)
        [view.sel().subtract(r) for r in to_subtract]
        [add_region(vid, *r, 0.0) for r in word_boundaries]
