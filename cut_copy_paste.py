import itertools
from typing import List, Tuple

import sublime_plugin
from sublime import Edit, Region, Selection, View, get_clipboard, set_clipboard
from sublime_api import view_cached_substr as ssubstr  # pyright:ignore
from sublime_api import view_erase as erase  # pyright:ignore
from sublime_api import view_selection_add_point as add_pt  # pyright:ignore
from sublime_api import view_selection_add_region as add_region  # pyright:ignore
from sublime_api import view_selection_subtract_region as subtract  # pyright:ignore


class CopyBufferCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit):
        buf = self.view
        set_clipboard(buf.substr(Region(0, buf.size())))


class SmartCopyWholeLineCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        v: View = self.view
        sel = v.sel()
        set_clipboard("".join(v.substr(v.full_line(reg)) for reg in sel))
        reg = sel[-1].b
        sel.clear()
        sel.add(reg)
        v.show(sel[-1].b)
        return


class SmartCopyCommand(sublime_plugin.TextCommand):
    def run(self, _, whole_line: bool = False) -> None:
        v: View = self.view
        vi = v.id()
        sel = v.sel()

        future_cb: List[Region] = []
        end = v.full_line(sel[0].a).a

        contiguous_regions = True

        for r in sel:
            if r.a != r.b:
                future_cb.append(r)
            else:
                line = v.full_line(r.a)
                if future_cb:
                    if future_cb[-1].a != line.a and future_cb[-1].b != line.b:
                        future_cb.append(line)
                else:
                    future_cb.append(line)

                if contiguous_regions:
                    if end == line.a:
                        end = line.b
                    else:
                        contiguous_regions = False

        if only_empty_selections := all(r.b == r.a for r in sel):
            if contiguous_regions:
                clip = v.substr(Region(future_cb[0].a, future_cb[-1].b))
            else:
                clip = "".join(v.substr(reg) for reg in future_cb)
        else:
            clip = "\n".join(v.substr(reg) for reg in future_cb)

        if clip.isspace():
            return

        if only_empty_selections and contiguous_regions:
            regs = [sel[-1].b]
        else:
            regs = [reg.b for reg in sel]

        sel.clear()
        [add_pt(vi, p) for p in regs]
        set_clipboard(clip)


class SmartCutCommand(sublime_plugin.TextCommand):
    """docstring for SmartCopyCommand"""

    def run(self, edit: Edit) -> None:
        v: View = self.view
        sel = v.sel()

        regions_to_copy: List[Region] = []
        end = v.full_line(sel[0].begin()).begin()

        only_empty_selections = True
        contiguous_regions = True

        for region in sel:
            if region.empty():
                line = v.full_line(region.begin())

                if regions_to_copy != []:
                    if (
                        regions_to_copy[-1].a != line.a
                        and regions_to_copy[-1].b != line.b
                    ):
                        regions_to_copy.append(line)
                else:
                    regions_to_copy.append(line)

                if end == line.begin():
                    end = line.end()
                else:
                    contiguous_regions = False

            else:
                only_empty_selections = False
                regions_to_copy.append(region)

        if only_empty_selections:
            reg = sel[-1].a
            if contiguous_regions:
                interesting_region = Region(
                    regions_to_copy[0].begin(), regions_to_copy[-1].end()
                )
                clip = v.substr(interesting_region)
                v.erase(edit, interesting_region)
            else:
                clip = "".join(v.substr(reg) for reg in regions_to_copy)
                for reg in reversed(regions_to_copy):
                    v.erase(edit, reg)

        else:
            clip = "\n".join(v.substr(reg) for reg in regions_to_copy)
            for reg in reversed(regions_to_copy):
                v.erase(edit, reg)

        if clip.isspace():
            return

        set_clipboard(clip)
        return


class SmartPasteCutNewlinesOrWhitespaceCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
        v: View = self.view
        sels: Selection = v.sel()
        clipboard = get_clipboard()
        if clipboard.endswith("\n"):
            ws = "\n"
        else:
            ws = " "
        clips = clipboard.splitlines()
        clip_pos: List[Tuple[int, int]] = [(len(clips[-1]), len(clips[-1]) + 1)]
        for clip in reversed(clips[:-1]):
            clip_pos.append((len(clip) + 1 + clip_pos[-1][0], len(clip) + 1))

        rev_sel: reversed[Region] = reversed(sels)
        for reg in rev_sel:
            if not reg.empty():
                v.erase(edit, reg)
            v.insert(edit, reg.a, ws.join(clips))

        rev_sel_new: reversed[Region] = reversed(sels)
        for reg in rev_sel_new:
            sels.add_all(
                Region(reg.begin() - pos[0], reg.begin() - pos[0] + pos[1] - 1)
                for pos in clip_pos
            )


class SmartPasteCutWhitespaceCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit):
        v: View = self.view
        stripped_clipboard = get_clipboard().strip()
        s: Selection = v.sel()
        for r in reversed(s):
            v.erase(edit, r)
            v.insert(edit, r.begin(), stripped_clipboard)


def find_indent(v: View, line: Region, above: bool = False) -> int:
    vi = v.id()
    if line.a == line.b:
        if above:
            l_beg = line.b
            while l_beg > 1:
                l_beg, l_end = v.line(l_beg - 1)
                if (prev_line := ssubstr(vi, l_beg, l_end)).startswith(" "):
                    return len(prev_line) - len(prev_line.lstrip())
        else:
            l_end = line.b
            while l_end < v.size():
                l_beg, l_end = v.line(l_end + 1)
                if (next_line := ssubstr(vi, l_beg, l_end)) != "":
                    return len(next_line) - len(next_line.lstrip())
        return 0
    else:
        if (line_content := v.substr(line)).isspace():
            return len(line_content)

        if not above and (next_line_content := v.substr(v.line(line.b + 1))) != "":
            line_content = next_line_content

        return len(line_content) - len(line_content.lstrip())


class SmartPasteCommand(sublime_plugin.TextCommand):
    def selections_match_clipboard(self, s: Selection, clips: List[str]) -> bool:
        vi = self.view.id()
        return all(not r.empty() for r in s) and len(set(clips)) == len(
            set(ssubstr(vi, r.a, r.b) for r in s)
        )

    def run(self, edit: Edit, above: bool = False, replace=True) -> None:
        v: View = self.view
        s: Selection = v.sel()
        clipboard = get_clipboard()
        clips = clipboard.splitlines()
        vi = v.id()
        is_whole_line = clipboard.endswith("\n")

        if replace:
            [erase(vi, edit.edit_token, r) for r in s if r.a != r.b]
        else:
            [(subtract(vi, r.begin(), r.end()), add_pt(vi, r.b)) for r in s]

        if len(clips) == len(s) or self.selections_match_clipboard(s, clips):
            if is_whole_line:
                for r, cliplet in zip(s, itertools.cycle(clips)):
                    line_reg = v.line(r.begin())
                    insert_pos = line_reg.begin() if above else line_reg.end() + 1
                    indent = find_indent(v, line_reg, above)
                    insert_string = " " * indent + cliplet.lstrip() + "\n"

                    s.subtract(r)
                    v.insert(edit, insert_pos, insert_string)
                    add_pt(vi, insert_pos + indent)

            else:
                for r, cliplet in zip(s, itertools.cycle(clips)):
                    insert_string = cliplet
                    insert_pos = r.begin() if above else r.end()
                    v.insert(edit, insert_pos, insert_string)
                    add_region(vi, insert_pos, insert_pos + len(insert_string), 0.0)

        else:
            if is_whole_line:
                for r in s:
                    line_reg = v.line(r.begin())
                    insert_pos = line_reg.begin() if above else line_reg.end() + 1
                    indent = find_indent(v, line_reg, above)

                    insert_string = ""
                    initial_indent = None
                    for line in clips:
                        deindented_line = line.lstrip()
                        cur_indent = len(line) - len(deindented_line)
                        if initial_indent == None:
                            initial_indent = cur_indent
                        this_indent = indent + cur_indent - initial_indent
                        insert_string += " " * this_indent + deindented_line + "\n"

                    s.subtract(r)
                    v.insert(edit, insert_pos, insert_string)
                    s.add(insert_pos + indent)
            else:
                for r in s:
                    insert_pos = r.begin() if above else r.end()
                    v.insert(edit, insert_pos, clipboard)
                    add_region(vi, insert_pos, insert_pos + len(clipboard), 0.0)
