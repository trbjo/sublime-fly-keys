import re
from collections import defaultdict
from typing import List

import sublime_api
import sublime_plugin
from sublime import Edit, Region
from sublime_api import view_cached_substr as substr
from sublime_api import view_cached_substr as view_substr
from sublime_api import view_selection_add_region as add_region
from sublime_api import view_selection_subtract_region as subtract_region
from sublime_api import view_show_point as show_point
from sublime_plugin import TextCommand, TextInputHandler

from .base import PositionAndType, matchers

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

        if s[-1].end() == v.size():
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
                    hej = v.line(r)
                    if hej.a <= r.b <= hej.b:
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

    def is_enabled(self) -> bool:
        if self.view is None:
            return False
        return any(r.a != r.b for r in self.view.sel())

    def run(self, _, pattern, include=False):
        if not pattern:
            return

        v = self.view
        vid = v.id()
        pattern_cache[include] = pattern
        length = len(pattern)
        for reg in list(v.sel()):
            if reg.empty():
                continue
            idx = list(findall(pattern, length, v.substr(reg)))
            if not idx:
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


class SmarterFindUnderExpand(sublime_plugin.TextCommand):
    def run(self, edit, forward: bool = False, skip: bool = False) -> None:
        vi = self.view.id()
        sels = self.view.sel()
        first = sels[0].begin()
        last = sels[-1].end()

        if forward:
            buf: str = view_substr(vi, first - 1, self.view.size())
        else:
            buf: str = view_substr(vi, 0, last + 1)[::-1]

        words = defaultdict(list)
        for reg in sels:
            if reg.empty():
                continue
            wlength = reg.end() - reg.begin()
            offset = reg.begin() - first if forward else last - reg.end()
            word = buf[1 + offset : wlength + 1 + offset]
            words[word].append(reg)

        for word, regs in words.items():
            wlength = len(word)

            regex = r"\W" + re.escape(word) + r"\W"
            # imitate find under expand's boundary detection
            boundary_selection = True
            for r in regs:
                offset = r.begin() - first if forward else last - r.end()
                bword = buf[offset : wlength + 2 + offset]
                if not re.match(regex, bword):
                    boundary_selection = False
                    break

            buffer_length = len(buf)
            idx = regs[-1].end() - first if forward else last - regs[0].begin()
            word_not_found = False
            while True:
                idx = buf.find(word, idx + 1)

                if idx == -1:
                    word_not_found = True
                    break

                if not boundary_selection:
                    break

                if wlength + idx == buffer_length:  # beginning/end of the buffer
                    boundary_word = buf[idx - 1 : idx + wlength]
                    regex = r"\W" + re.escape(word)
                else:
                    boundary_word = buf[idx - 1 : idx + wlength + 1]

                if re.match(regex, boundary_word):
                    break

            if word_not_found:
                continue

            if skip:
                del_reg = regs[-1 if forward else 0]
                subtract_region(vi, del_reg.a, del_reg.b)

            if forward:
                start = first + idx - 1
                end = start + wlength
            else:
                end = last - idx + 1
                start = end - wlength

            add_region(
                vi,
                *((start, end) if any(r.b > r.a for r in regs) else (end, start)),
                0.0,
            )
            show_point(vi, end, True, False, True)


class ExpandSelectionToNextCommand(sublime_plugin.TextCommand):
    def get_left_point(
        self, l_pointer: int, single_quotes: bool, double_quotes: bool
    ) -> PositionAndType:
        chars: List[int] = []
        local_double_quotes = False
        local_single_quotes = False

        while l_pointer > 0:
            l_pointer -= 1
            char: str = self.buf_str[l_pointer]
            index: int = matchers.find(char)

            if index == -1:
                continue

            elif local_double_quotes and index != 6:
                continue
            elif local_single_quotes and index != 7:
                continue

            elif index == 6:
                lscp = self.view.scope_name(l_pointer)
                if local_double_quotes and "string.begin" in lscp:
                    local_double_quotes = False
                elif "string.begin" in lscp:
                    return l_pointer, index
                else:
                    local_double_quotes = True

            elif index == 7:
                if single_quotes and not local_single_quotes:
                    if "string.begin" in self.view.scope_name(l_pointer):
                        return l_pointer, index
                if not double_quotes and not local_double_quotes:
                    local_single_quotes = not local_single_quotes

            elif index >= 3:
                chars.append(index)
            elif index <= 2:
                if chars:
                    for i in range(len(chars)):
                        backward_idx = len(chars) - 1 - i
                        if chars[backward_idx] == index + 3:
                            chars = chars[0:backward_idx]
                            break
                    else:
                        return l_pointer, index
                else:
                    return l_pointer, index

        return -2, -2

    def get_right_point(
        self, r_pointer: int, single_quotes: bool, double_quotes: bool
    ) -> PositionAndType:
        chars: List[int] = []
        local_double_quotes = False
        local_single_quotes = False

        while r_pointer < self.size - 1:
            r_pointer += 1
            char: str = self.buf_str[r_pointer]
            index: int = matchers.find(char)

            if index == -1:
                continue

            elif local_double_quotes and index != 6:
                continue
            elif local_single_quotes and index != 7:
                continue

            elif index == 6:
                if double_quotes and not local_double_quotes:
                    if "string.end" in self.view.scope_name(r_pointer):
                        return r_pointer, index
                if not single_quotes and not local_single_quotes:
                    local_double_quotes = not local_double_quotes

            elif index == 7:
                if single_quotes and not local_single_quotes:
                    if "string.end" in self.view.scope_name(r_pointer):
                        return r_pointer, index
                if not double_quotes and not local_double_quotes:
                    local_single_quotes = not local_single_quotes

            elif index <= 2:
                chars.append(index)

            elif index >= 3:
                if chars:
                    for i in range(len(chars)):
                        backward_idx = len(chars) - 1 - i
                        if chars[backward_idx] == index - 3:
                            chars = chars[0:backward_idx]
                            break
                    else:
                        return r_pointer, index - 3
                else:
                    return r_pointer, index - 3

        return -3, -3

    def looper(self, region: Region) -> None:
        did_right: bool = self.size / 2 < region.b

        left_types: List[int] = []
        right_types: List[int] = []
        left_indices: List[int] = []
        right_indices: List[int] = []

        l_index: int = region.b
        r_index: int = region.b - 1

        single_quotes = False
        double_quotes = False

        right_type = 100
        left_type = 101

        reg = self.view.expand_to_scope(
            region.b, "(meta.string, string) - punctuation.definition.string"
        )
        if reg is not None:
            r_scope = self.view.scope_name(reg.b)
            if "string." in r_scope:
                if "string.quoted.double" in r_scope:
                    double_quotes = True
                elif "string.quoted.single" in r_scope:
                    single_quotes = True

        while True:
            if right_type != -3 and (did_right or left_type == -2):
                r_index, right_type = self.get_right_point(
                    r_index, single_quotes, double_quotes
                )
                did_right = False

                if right_type == -3:
                    if not right_types:
                        return
                    else:
                        continue

                for i in range(len(left_types)):
                    if left_types[i] == right_type:
                        if region.a == region.b:
                            l_index = left_indices[i]
                            break
                        else:
                            if self.around:
                                l_index = left_indices[i]
                                break
                            else:
                                if not (
                                    region.begin() <= left_indices[i] + 1
                                    or region.end() == r_index
                                ):
                                    l_index = left_indices[i]
                                    break
                else:
                    right_indices.append(r_index)
                    right_types.append(right_type)
                    continue

            elif left_type != -2 and (not did_right or right_type == -3):
                l_index, left_type = self.get_left_point(
                    l_index, single_quotes, double_quotes
                )
                did_right = True
                if left_type == -2:
                    if not left_types:
                        return
                    else:
                        continue

                for i in range(len(right_types)):
                    if right_types[i] == left_type:
                        if region.a == region.b:
                            r_index = right_indices[i]
                            break
                        else:
                            if self.around:
                                r_index = right_indices[i]
                                break
                            else:
                                if not (
                                    region.end() == right_indices[i]
                                    or region.begin() <= l_index + 1
                                ):
                                    r_index = right_indices[i]
                                    break

                else:
                    left_indices.append(l_index)
                    left_types.append(left_type)
                    continue

            else:
                return

            if r_index - 1 == l_index:  # no extent, e.g. ()
                left_types = []
                right_types = []
                left_indices = []
                right_indices = []
                continue

            if (
                self.buf_str[l_index + 1] == self.buf_str[l_index]
                and self.buf_str[  # deal with multiple, subsequent parentheses
                    r_index - 1
                ]
                == self.buf_str[r_index]
            ):
                continue

            break

        self.view.sel().subtract(region)

        if self.around:
            r_index += 1
            l_index -= 1
            while (
                self.buf_str[l_index + 1] == self.buf_str[l_index]
                and self.buf_str[r_index - 1] == self.buf_str[r_index]
            ):
                l_index -= 1
                r_index += 1

        if self.from_here:
            l_index = region.a - 1
        elif self.to_here:
            r_index = region.a

        if region.b < region.a or self.to_here:
            sublime_api.view_selection_add_region(
                self.buf_id, r_index, l_index + 1, 0.0
            )
        else:
            sublime_api.view_selection_add_region(
                self.buf_id, l_index + 1, r_index, 0.0
            )

    def run(self, edit: Edit, around=False, from_here=False, to_here=False):
        self.size: int = self.view.size()
        self.buf_id = self.view.id()
        self.around = around
        self.from_here = from_here
        self.to_here = to_here
        self.buf_str: str = sublime_api.view_cached_substr(self.buf_id, 0, self.size)

        s = self.view.sel()
        sels = list(s)

        for region in self.view.sel():
            if region.end() != self.size:
                self.looper(region)

        self.view.show(self.view.sel()[-1].b, True)


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


class RevertSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        sel = buf.sel()
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


class SplitSelectionIntoLinesWholeWordsCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        selections = buf.sel()
        rev_sels: reversed[Region] = reversed(selections)
        for region in rev_sels:
            if region.empty():
                continue

            contents = buf.substr(region)
            begin = region.begin()
            word_boundaries = [
                Region(m.start() + begin, m.end() + begin)
                for m in re.finditer(WORDCHARS, contents)
            ]
            if word_boundaries != []:
                selections.subtract(region)
                selections.add_all(word_boundaries)


class SplitSelectionIntoLinesSpacesCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        selections = buf.sel()
        rev_sels: reversed[Region] = reversed(selections)
        for region in rev_sels:
            if region.empty():
                continue

            contents = buf.substr(region)
            begin = region.begin()
            word_boundaries = [
                Region(m.start() + begin, m.end() + begin)
                for m in re.finditer(r"[\S]+", contents)
            ]
            if word_boundaries != []:
                selections.subtract(region)
                selections.add_all(word_boundaries)
