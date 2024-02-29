import re
from collections import defaultdict
from typing import Dict, List, Tuple

import sublime_plugin
from sublime import Edit, Region, View, active_window
from sublime_api import view_cached_substr as substr  # pyright: ignore
from sublime_api import view_selection_add_point as add_point  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_api import (
    view_selection_subtract_region as subtract_region,  # pyright: ignore
)
from sublime_api import view_show_point as show_point  # pyright: ignore
from sublime_plugin import TextCommand, TextInputHandler

from .base import buffer_slice

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

        vid = v.id()

        hardeol = True
        softbol = True

        columns = []

        selections = list(s)
        for r in selections:
            row, column = v.rowcol(r.b)
            columns.append(column)

            line = v.line(r.b)
            if len(line) == 0:
                continue  # can't decide if there is only a newline

            if line.b == r.b:
                softbol = False
            else:
                hardeol = False

            if softbol is True:
                line_str = substr(vid, line.a, r.b + 1)
                # cursor border check:
                before_cursor = line_str[0:-1]
                after_cursor = line_str[-1]

                if (
                    len(before_cursor) > 0 and not before_cursor.isspace()
                ) or after_cursor.isspace():
                    softbol = False

        mode = "normal" if softbol == hardeol else "softbol" if softbol else "hardeol"

        current_lines: set[int] = {v.line(r.b).a for r in selections}
        if forward:
            next_lines = [v.line(v.line(pt).b + 1) for _, pt in selections]
        else:
            next_lines = [v.line(v.line(pt).a - 1) for pt in current_lines if pt > 1]
        folds = v.folded_regions()
        for i, next_line in enumerate(next_lines):
            if next_line.a in current_lines:
                continue

            if f := next((f for f in folds if next_line.intersects(f)), None):
                [s.add(reg.a) for reg in v.lines(f)]

            elif next_line.empty():
                s.add(next_line.a)

            elif mode == "hardeol":
                s.add(next_line.b)

            elif mode == "softbol":
                mysubstr: str = substr(vid, next_line.a, next_line.b)
                idx = len(mysubstr) - len(mysubstr.lstrip())
                s.add(next_line.a + idx)
            else:
                col = columns[i]
                s.add(min((next_line.a + col), next_line.b))

        cursor = s[-1 if forward else 0]
        for fold in folds:
            if fold.intersects(cursor):
                return
        v.show(cursor.b)


def findall(p, s):
    """Yields all the positions of
    the pattern p in the string s."""
    i = s.find(p)
    length = len(p)
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


class FindNextLolCommand(sublime_plugin.TextCommand):
    def run(self, edit, forward: bool = True):
        v: View = self.view
        v.run_command("clear_selection", args={"forward": True, "after": False})
        v.run_command("find_under_expand")
        if forward:
            v.run_command("find_next")
        else:
            v.run_command("find_prev")


class SmarterFindUnderExpand(sublime_plugin.TextCommand):
    def run(
        self, _, forward: bool = True, skip: bool = False, find_all: bool = False
    ) -> None:
        v = self.view
        vid = self.view.id()
        s = self.view.sel()

        first = max(s[0].begin() - 1, 0)
        last = min(s[-1].end() + 1, v.size())

        buf = f"\a{substr(vid, first, last)}\a"
        middle = set()
        words: Dict[str, List[Region]] = defaultdict(list)
        compiled_regexes = {}
        for reg in s if forward else reversed(s):
            if reg.a == reg.b:
                continue

            surroundings = buf[reg.begin() - first : reg.end() + 2 - first]
            if not forward:
                surroundings = surroundings[::-1]

            word = surroundings[1:-1]
            words[word].append(reg)

            if word not in compiled_regexes:
                compiled_regexes[word] = re.compile(r"\b" + re.escape(word) + r"\b")
            regex = compiled_regexes[word]

            if not word.isalnum() or not regex.search(surroundings):
                middle.add(word)

        buffer_iter = buffer_slice(v, forward)
        buffer_iter.send(None)

        for word, regs in words.items():
            a, b = regs[-1]
            idx = (0, 0) if find_all else (b, a) if (a > b) is forward else (a, b)
            rgx = re.escape(word) if word in middle else compiled_regexes[word]
            revert = all(reg.a > reg.b for reg in regs) is forward

            while idx := buffer_iter.send((*idx, rgx)):
                add_region(vid, *(idx[::-1] if revert else idx), 0.0)
                if skip:
                    subtract_region(vid, a, b)
                if not find_all:
                    break

        show_point(vid, s[-1 if forward else 0].b, True, False, True)


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
        buffer = substr(v.id(), first, v.sel()[-1].end())
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
            _, viewport_y = buf.viewport_extent()
            _, view_y_begin = buf.viewport_position()
            view_y_end = view_y_begin + viewport_y

            _, first_cur_y = buf.text_to_layout(sel[0].b)
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
    def run(self, panel="find") -> None:
        w = active_window()

        if (view := w.active_view()) is None:
            return

        vi = view.id()
        sel = view.sel()
        toggle = any("\n" in substr(vi, r.a, r.b) for r in sel)

        # if toggle:
        key = "search_in_selection"
        w.settings().set(key=key, value=True)
        cursors = [(r.a, r.b) for r in sel]
        w.settings().set(f"{vi}_cursors", cursors)

        w.run_command(cmd="show_panel", args={"panel": panel, "reverse": False})
        w.run_command(cmd="left_delete")
        if not toggle:
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

    regex_order = [
        newline,
        whitespace,
        word_n_punctuation_ext,
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
