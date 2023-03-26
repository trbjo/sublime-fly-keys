import sublime_api
import sublime_plugin
from sublime import Edit
from sublime_api import view_selection_add_region as add_region


class ExpandSelectionToNextCommand(sublime_plugin.TextCommand):
    string = "(meta.string, string) - punctuation.definition.string"

    def run(self, edit: Edit, around=False, left=True):
        v = self.view
        vi = v.id()
        size: int = v.size()
        self.buf_str: str = sublime_api.view_cached_substr(vi, 0, size)

        regs = []
        for r in v.sel():
            if any(s[0] < r.b < s[1] or s[0] > r.b > s[1] for s in regs):
                continue

            rpt = r.begin() if abs(r.b - r.a) == 1 else r.b

            while True:
                if (in_string := v.expand_to_scope(rpt, self.string)) is not None and (
                    r.end() + 1 != in_string.b or r.begin() - 1 != in_string.a
                ):
                    lpt = in_string.a
                    reg_b = in_string.b
                else:
                    lpt = -1
                    reg_b = size

                rpt = self.find_char(rpt, reg_b, True, bool(in_string))
                if left:
                    if charpair := {"}": "}{", "]": "][", ")": ")("}.get(v.substr(rpt)):
                        lpt = (
                            self.find_char(
                                rpt - 1, lpt, False, bool(in_string), charpair
                            )
                            + 1
                        )
                else:
                    lpt = r.begin()

                if around or r.begin() != lpt or r.end() != rpt:
                    break

                rpt += 1

            if rpt == size or lpt == 0:
                continue

            offset = 1 if around else 0
            if r.b < r.a:
                regs.append((rpt + offset, lpt - offset))
            else:
                regs.append((lpt - offset, rpt + offset))

        if regs:
            v.sel().clear()
            [add_region(vi, *r, 0.0) for r in regs]
            self.view.show(self.view.sel()[-1].b, True)

    def find_char(
        self,
        start: int,
        stop: int,
        forward: bool,
        in_string: bool,
        charpair="([{)]}",
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
