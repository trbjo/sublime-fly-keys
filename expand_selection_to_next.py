import sublime_api
import sublime_plugin
from sublime import Edit
from sublime_api import view_selection_add_region as add_region


class ExpandSelectionToNextCommand(sublime_plugin.TextCommand):
    pair = {"}": "}{", "]": "][", ")": ")("}
    string = "(meta.string, string) - punctuation.definition.string"
    # string = "string, meta.string"

    def run(self, edit: Edit, around=False, left=True, right=True):
        v = self.view
        vi = v.id()
        size: int = v.size()
        self.buf_str: str = sublime_api.view_cached_substr(vi, 0, size)

        regs = []
        for r in v.sel():
            if any(s[0] < r.b < s[1] or s[0] > r.b > s[1] for s in regs):
                continue

            rpt = r.begin() if abs(r.b - r.a) == 1 else r.end()
            lpt = r.a

            while True:
                if (in_string := v.expand_to_scope(rpt, self.string)) is not None and (
                    r.b + 1 != in_string.b or r.a - 1 != in_string.a
                ):
                    reg_a = in_string.a - 1
                    reg_b = in_string.b - 1
                else:
                    in_string = False
                    reg_a = 1
                    reg_b = size - 1

                charpair = ")]}([{"
                if right:
                    rpt = self.find_char(rpt, reg_b + 1, True, bool(in_string))
                    if not in_string and not (charpair := self.pair.get(v.substr(rpt))):
                        break
                if left:
                    if in_string and not (charpair := self.pair.get(v.substr(rpt))):
                        lpt = reg_a + 1
                        rpt = reg_b + 1
                    else:
                        lpt = (
                            self.find_char(
                                rpt - 1, reg_a, False, bool(in_string), charpair
                            )
                            + 1
                        )

                if r.begin() != lpt or r.end() != rpt:
                    break

                if around:
                    break

                rpt += 1
                lpt -= 1

            if rpt == size:
                continue

            offset = 1 if around else 0
            if right and not left:
                lpt = r.begin()

            if r.b < r.a or (left and not right):
                regs.append((rpt - offset, lpt + offset))
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
