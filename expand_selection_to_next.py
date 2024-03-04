
import sublime_api
import sublime_plugin
from sublime import Edit, Region
from sublime_api import view_selection_add_region as add_region
from sublime_api import view_selection_subtract_region as subtract_region


charpair="([{)]}"

class ExpandSelectionToNextCommand(sublime_plugin.TextCommand):
    string = "meta.string, string"

    def run(
        self,
        _: Edit,
        left:bool=True,
        right:bool=True,
        around: bool=False,
    ):

        v = self.view
        vi = v.id()
        size: int = v.size()
        to_add = []
        self.buf_str: str = sublime_api.view_cached_substr(vi, 0, size)

        for r in v.sel():
            left_pt = self.find_pt(r, False) if left else r.begin()
            right_pt = self.find_pt(r, True) if right else r.end()
            to_add.append((left_pt, right_pt))

        self.view.sel().clear()
        for r in to_add:
            add_region(vi, *r, 0.0)
        self.view.show(self.view.sel()[-1].b, True)

            # if any(s[0] < r.b < s[1] or s[0] > r.b > s[1] for s in regs):
                # continue

    def find_pt(self, r: Region, forward: bool) -> int:
        v = self.view
        size = v.size()
        # expand right point if we have a selection
        rpt = r.b if r.b == r.a else r.b + 1

        while True:
            if (
                (in_string := v.expand_to_scope(rpt, self.string))
                and (
                    in_string.a < r.end() < in_string.b
                    or in_string.a < r.begin() < in_string.b
                )
                and not (
                    local_scope := v.scope_name(rpt).split(" ")[-2]
                ).startswith("punctuation.definition.string.begin")
            ):
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

                reg_b = in_string.b - 1
            else:
                in_string = False
                reg_b = size

            pt = self.find_char(charpair, rpt, reg_b, forward, bool(in_string))
            return pt

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
