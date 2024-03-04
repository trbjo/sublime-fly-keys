import re
from collections import defaultdict
from typing import Dict, List, Tuple

import sublime_plugin
from sublime import Edit, Region, View, active_window
from sublime_api import view_cached_substr as substr  # pyright: ignore
from sublime_api import view_selection_add_point as add_point  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_api import view_selection_size as selection_length  # pyright: ignore
from sublime_api import view_selection_get as ith_selection  # pyright: ignore
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




class AlignCursors(sublime_plugin.TextCommand):

    def run(self, edit: Edit):
        max_point = 0
        for cursor in self.view.sel():
            _, point = self.view.rowcol(cursor.b)
            if max_point < point:
                max_point = point

        for cursor in reversed(self.view.sel()):
            _, point = self.view.rowcol(cursor.b)
            if point < max_point:
                self.view.insert(edit, cursor.b, ' ' * (max_point - point))

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
        v.run_command("clear_selection", args={"forward": True})
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
    def run(self, _, after: bool = False) -> None:
        v = self.view
        vi = v.id()
        selections = [ith_selection(vi, i) for i in range(0, selection_length(vi))]
        if all(r.a == r.b for r in selections):
            return
        pts = []
        for r in selections:
            line = v.line(r.begin())
            while line.a < r.end() and line.b <= v.size():
                pts.append(line.b if after else line.a)
                line = v.line(line.b + 1)

        v.sel().clear()
        for pt in pts:
            add_point(vi, pt)


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


class SmarterSearchCommand(sublime_plugin.WindowCommand):
    """remember to disable auto_find_in_selection"""
    def run(self, panel: str="find", reverse: bool = False) -> None:
        w = active_window()

        if (view := w.active_view()) is None:
            return

        vi = view.id()
        sel = view.sel()
        toggle = any(" " in substr(vi, r.a, r.b) for r in sel)

        key = f"{vi}_cursors"
        cursors = [(r.a, r.b) for r in sel]
        w.settings().set(key, cursors)

        w.run_command(cmd="show_panel", args={"panel": panel, "reverse": reverse})
        # w.run_command(cmd="left_delete")
        if toggle:
            w.run_command(cmd="toggle_in_selection")


class HideSearchInSelectionCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        w = active_window()
        if (view := w.active_view()) is None:
            return

        vi = view.id()
        w.run_command(cmd="hide_panel", args={"cancel": True})

        vi = view.id()
        key=f"{vi}_cursors"
        if not (cursors := w.settings().get(key)):
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
