from typing import Tuple

import sublime_api
import sublime_plugin
from sublime import Edit
from sublime_api import view_selection_add_region as add_region
from sublime_api import view_selection_subtract_region as subtract_region


class ExpandSelectionToNextCommand(sublime_plugin.TextCommand):
    string = "meta.string, string"

    def get_action(self) -> Tuple[str, bool, bool]:
        v = self.view
        if (set_number := self.view.settings().get("set_number")) is not None:
            v.settings().erase("set_number")

        if (multiplier := self.view.settings().get("multiplier")) is not None:
            v.settings().erase("multiplier")
            if multiplier == 1:
                return "()", False, False
            elif multiplier == 2:
                return "()", True, False
            elif multiplier == 3:
                return "[]", False, False
            elif multiplier == 4:
                return "[]", True, False
            elif multiplier == 5:
                return r"{}", False, False
            elif multiplier == 6:
                return r"{}", True, False
        return "([{)]}", False, True

    def run(
        self,
        _: Edit,
        left=True,
        right=True,
    ):
        charpair, around, include_string = self.get_action()

        v = self.view
        vi = v.id()
        size: int = v.size()
        to_subtract = []
        self.buf_str: str = sublime_api.view_cached_substr(vi, 0, size)

        regs = []
        for r in v.sel():
            if any(s[0] < r.b < s[1] or s[0] > r.b > s[1] for s in regs):
                continue

            rpt = r.begin() if abs(r.b - r.a) == 1 else r.b
            lpt = r.begin()

            while True:
                around_offset = 0 if around else 1
                if (
                    (in_string := v.expand_to_scope(rpt, self.string))
                    and (
                        in_string.a < r.end() < in_string.b - around_offset
                        or in_string.a + around_offset < r.begin() < in_string.b
                    )
                    and not (
                        local_scope := v.scope_name(rpt).split(" ")[-2]
                    ).startswith("punctuation.definition.string.begin")
                ) and include_string:
                    # we deal with nested string scopes, e.g. a string inside a format string

                    nested = False
                    if local_scope.startswith("string"):
                        nested = v.extract_scope(rpt)
                    elif local_scope.startswith("punctuation.definition.string.end"):
                        nested = v.extract_scope(rpt - 1)

                    if nested and (nested.b < in_string.b or nested.a < in_string.a):
                        substr = v.substr(nested.b - 1)
                        if (substr == "'" and "single" in local_scope) or (
                            substr == '"' and "double" in local_scope
                        ):
                            in_string = nested

                    lpt = in_string.a + 1
                    reg_b = in_string.b - 1
                else:
                    in_string = False
                    lpt = -1
                    reg_b = size

                rpt = self.find_char(charpair, rpt, reg_b, True, bool(in_string))
                if left:
                    if char := {"}": "}{", "]": "][", ")": ")("}.get(v.substr(rpt)):
                        if (
                            llpt := self.find_char(
                                char, rpt - 1, lpt, False, bool(in_string)
                            )
                        ) == lpt - 1:
                            rpt = reg_b
                        else:
                            lpt = llpt + 1
                else:
                    lpt = r.begin()

                if around or r.begin() != lpt or r.end() != rpt:
                    break

                rpt += 1

            if rpt == size or lpt <= 0:
                continue

            if not right:
                rpt = lpt
                lpt = r.b

            offset = 1 if around else 0
            to_subtract.append(r)
            if r.b < r.a:
                regs.append((rpt + offset, lpt - offset))
            else:
                regs.append((lpt - offset, rpt + offset))

        [subtract_region(vi, *r) for r in to_subtract]
        [add_region(vi, *r, 0.0) for r in regs]
        self.view.show(self.view.sel()[-1].b, True)

    def find_char(
        self,
        charpair: str,
        start: int,
        stop: int,
        forward: bool,
        in_string: bool,
    ) -> int:
        stack = []
        offset = int(len(charpair) / 2)

        for i in range(start, stop, 1 if forward else -1):
            char = self.buf_str[i]
            if (score := charpair.find(char)) == -1:
                continue

            if not in_string and "string" in self.view.scope_name(i):
                continue

            if score >= offset:
                if len(stack) == 0:
                    return i

                if stack[-1] + offset == score:
                    stack.pop()

            else:
                stack.append(score)

        return stop
