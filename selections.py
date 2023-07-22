import re
from collections import defaultdict
from typing import Iterable, List, Tuple, Union

import sublime_api
import sublime_plugin
from sublime import Edit, Region, Selection, View, active_window
from sublime_api import view_cached_substr as substr  # pyright: ignore
from sublime_api import view_selection_add_point as add_point  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_api import (
    view_selection_subtract_region as subtract_region,  # pyright: ignore
)
from sublime_api import view_show_point as show_point  # pyright: ignore
from sublime_plugin import TextCommand, TextInputHandler

# expand to next
matchers: str = """([{)]}"'"""
PositionAndType = Tuple[int, int]


pattern_cache = {}


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

                for region in to_add:
                    next_line_reg = v.line(v.line(region.b).b + 1)

                    col = v.rowcol(region.b)[1]
                    if (next_line_reg.b - next_line_reg.a) > col:
                        s.add(next_line_reg.a + col)
                    else:
                        s.add(next_line_reg.b)
            else:
                cols = [v.rowcol(r.b)[1] for r in s]
                for r, col in zip(list(s), cols):
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


class RecordSelectionsCommand(sublime_plugin.TextCommand):
    recorded_selections = {}

    def run(self, edit, retrieve: bool = False):
        vi = self.view.id()
        if retrieve:
            for r in self.recorded_selections.get(vi, []):
                add_region(vi, r[0], r[1], 0.0)
        else:
            sels = self.view.sel()
            self.recorded_selections[vi] = [(r.a, r.b) for r in sels]


class SmarterFindUnderExpand(sublime_plugin.TextCommand):
    def run(
        self,
        edit,
        forward: bool = True,
        skip: bool = False,
        find_all: bool = False,
    ) -> None:
        vi = self.view.id()
        sels = self.view.sel()
        size = self.view.size()

        if find_all:
            first = 0
            last = size
        else:
            first = sels[0].begin()
            last = sels[-1].end()

        if forward:
            padding = "\a" if first == 0 else ""
            buf: str = f"{padding}{substr(vi, first - 1, size)}\a"
        else:
            padding = "\a" if last == size else ""
            buf: str = f"\a{substr(vi, 0, last + 1)}{padding}"[::-1]

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

            if find_all:
                idx = 0

            at_boundary = all(re.match(regex, buf[o : wlen + 2 + o]) for o in offsets)

            while (idx := buf.find(word, idx + 1)) != -1:
                if not at_boundary or re.match(regex, buf[idx - 1 : idx + wlen + 1]):
                    if skip:
                        del_reg = regs[-1 if forward else 0]
                        subtract_region(vi, del_reg.a, del_reg.b)

                    if forward:
                        start = first + idx - 1
                        end = start + wlen
                    else:
                        end = last - idx + 1
                        start = end - wlen

                    reg = (start, end) if any(r.b > r.a for r in regs) else (end, start)
                    add_region(vi, *reg, 0.0)

                    if not find_all:
                        break
            else:
                continue

        show_point(vi, sels[-1 if forward else 0].b, True, False, True)


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


class SearchInSelectionCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        w = active_window()

        if (view := w.active_view()) is None:
            return

        vi = view.id()
        key = "search_in_selection"
        w.settings().set(key=key, value=True)
        sel = view.sel()
        cursors = [(r.a, r.b) for r in sel]
        w.settings().set(f"{vi}_cursors", cursors)
        toggle = not any("\n" in substr(vi, r.a, r.b) for r in sel)

        w.run_command(cmd="show_panel", args={"panel": "find", "reverse": False})
        w.run_command(cmd="left_delete")
        if toggle:
            w.run_command(cmd="toggle_in_selection")


class HideSearchInSelectionCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        w = active_window()
        if (view := w.active_view()) is None:
            return

        vi = view.id()
        w.run_command(cmd="hide_panel", args={"cancel": True})
        key = f"search_in_selection"

        if not w.settings().get(key):
            return

        vi = view.id()
        if not (cursors := w.settings().get(f"{vi}_cursors")):
            return

        view.sel().clear()
        for cursor in cursors:
            add_region(vi, *cursor, 0.0)
        w.settings().erase(key)


class SplitSelectionIntoLinesCommand(sublime_plugin.TextCommand):
    newline = r"\r?\n+"
    whitespace = r"\s+"
    word_n_punctuation = r"[^-\._\w]+"
    word_n_punctuation_ext = r"[^-_\w]+"
    word = r"[^A-Za-z]+"

    regex_order = [
        newline,
        whitespace,
        word_n_punctuation,
        word_n_punctuation_ext,
        word,
    ]

    def bounds(self, regex: str):
        buf: View = self.view
        selections = buf.sel()
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
            word_boundaries.extend(local_bounds)
        return word_boundaries

    def run(self, edit: Edit) -> None:
        view = self.view
        vid = view.id()
        sels = self.view.sel()
        for regex in self.regex_order:
            if word_boundaries := self.bounds(regex):
                if len(sels) == len(word_boundaries) and all(
                    w[0] == r.begin() and w[1] == r.end()
                    for w, r in zip(word_boundaries, sels)
                ):
                    return
                for r in word_boundaries:
                    subtract_region(vid, *r)
                return
