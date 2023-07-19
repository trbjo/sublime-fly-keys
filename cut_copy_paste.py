import itertools
from typing import List, Tuple

import sublime_plugin
from sublime import (
    DRAW_NO_OUTLINE,
    Edit,
    Region,
    Selection,
    View,
    get_clipboard,
    set_clipboard,
)
from sublime_api import set_timeout_async as set_timeout_async  # pyright: ignore
from sublime_api import view_add_regions  # pyright: ignore
from sublime_api import view_cached_substr as ssubstr  # pyright: ignore
from sublime_api import view_erase as erase  # pyright: ignore
from sublime_api import view_selection_add_point as add_pt  # pyright: ignore
from sublime_api import view_selection_add_region as add_region  # pyright: ignore
from sublime_api import view_selection_subtract_region as subtract  # pyright: ignore


class CopyBufferCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit):
        buf = self.view
        set_clipboard(buf.substr(Region(0, buf.size())))


class SmartCopyCommand(sublime_plugin.TextCommand):
    def run(self, _, whole_line: bool = False) -> None:
        v: View = self.view
        vi = v.id()
        sel = v.sel()

        if whole_line:
            regs = [r.b if l.contains(r.b) else l.a for r in sel for l in v.lines(r)]
            sel.clear()
            sel.add_all(regs)

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

        v.show(v.sel()[-1].b, False)
        if clip.isspace():
            return

        name = "copy_regions"
        regs = [self.view.full_line(r.b) if r.empty() else r for r in sel]
        color = "light"
        view_add_regions(vi, name, regs, color, "", DRAW_NO_OUTLINE, [], "", None, None)
        set_timeout_async(lambda: self.view.erase_regions("copy_regions"), 250)

        if only_empty_selections and contiguous_regions:
            regs = [sel[-1].b]
            sel.clear()
            for p in regs:
                add_pt(vi, p)

        set_clipboard(clip)


class SmartCutCommand(sublime_plugin.TextCommand):
    """docstring for SmartCopyCommand"""

    def run(self, edit: Edit, whole_line: bool = False) -> None:
        v: View = self.view
        sel = v.sel()

        if whole_line:
            regs = [r.b if l.contains(r.b) else l.a for r in sel for l in v.lines(r)]
            sel.clear()
            sel.add_all(regs)

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

        v.show(v.sel()[-1].b, False)
        if not clip.isspace():
            set_clipboard(clip)


class SmartPasteCutNewlinesAndWhitespaceCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
        v: View = self.view

        wschar = " " if v.settings().get("translate_tabs_to_spaces") else "\t"
        sels: Selection = v.sel()

        clips = [c.strip() for c in get_clipboard().splitlines() if c.strip()]
        clip_pos: List[Tuple[int, int]] = [(len(clips[-1]), len(clips[-1]) + 1)]

        for clip in reversed(clips[:-1]):
            clip_pos.append((len(clip) + 1 + clip_pos[-1][0], len(clip) + 1))

        rev_sel: reversed[Region] = reversed(sels)
        for reg in rev_sel:
            if not reg.empty():
                v.erase(edit, reg)
            v.insert(edit, reg.a, wschar.join(clips))

        rev_sel_new: reversed[Region] = reversed(sels)
        for reg in rev_sel_new:
            sels.add_all(
                Region(reg.begin() - pos[0], reg.begin() - pos[0] + pos[1] - 1)
                for pos in clip_pos
            )

        v.show(v.sel()[-1].b, False)


class SmartPasteCutWhitespaceCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit):
        v: View = self.view
        stripped_clipboard = get_clipboard().strip()
        s: Selection = v.sel()
        for r in reversed(s):
            v.erase(edit, r)
            v.insert(edit, r.begin(), stripped_clipboard)

        v.show(v.sel()[-1].b, False)


def find_indent(
    v: View,
    line: Region,
    region: Region,
    wschar: str,
    before: bool = False,
) -> int:
    vi = v.id()
    if line.a == line.b:
        if before:
            l_beg = line.b
            while l_beg > 1:
                l_beg, l_end = v.line(l_beg - 1)
                if (prev_line := ssubstr(vi, l_beg, l_end)).startswith(wschar):
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
            return region.b - line.a

        if not before and (next_line_content := v.substr(v.line(line.b + 1))) != "":
            line_content = next_line_content

        return len(line_content) - len(line_content.lstrip())


class SmartPasteCommand(sublime_plugin.TextCommand):
    def selections_match_clipboard(self, s: Selection, clips: List[str]) -> bool:
        if len(clips) == len(s):
            return True
        vi = self.view.id()
        return all(not r.empty() for r in s) and len(set(clips)) == len(
            set(ssubstr(vi, r.a, r.b) for r in s)
        )

    def run(
        self, edit: Edit, before: bool = False, replace=True, indent_same=False
    ) -> None:
        v: View = self.view

        wschar = " " if v.settings().get("translate_tabs_to_spaces") else "\t"
        s: Selection = v.sel()
        clipboard = get_clipboard()
        clips = clipboard.splitlines()
        vi = v.id()

        selections_match = self.selections_match_clipboard(s, clips)
        if replace:
            [erase(vi, edit.edit_token, r) for r in s if r.a != r.b]
            # return
        else:
            if before:
                [(subtract(vi, r.begin(), r.end()), add_pt(vi, r.begin())) for r in s]
            else:
                [(subtract(vi, r.begin(), r.end()), add_pt(vi, r.end())) for r in s]

        if not clipboard.endswith("\n"):
            clipboard_iterator = clips if selections_match else [clipboard]
            for r, cliplet in zip(s, itertools.cycle(clipboard_iterator)):
                insert_pos = r.begin() if before else r.end()
                v.insert(edit, insert_pos, cliplet)
                add_region(vi, insert_pos, insert_pos + len(cliplet), 0.0)
            return

        stripped_lines = [line.lstrip() for line in clips]
        if selections_match:
            for r, cliplet in zip(s, itertools.cycle(stripped_lines)):
                line_reg = v.line(r.begin())
                insert_pos = line_reg.a if before else v.full_line(r.begin()).b
                indent = find_indent(v, line_reg, r, wschar, before)
                insert_string = wschar * indent + cliplet + "\n"

                s.subtract(r)
                v.insert(edit, insert_pos, insert_string)
                add_pt(vi, insert_pos + indent)
        else:
            content_line = -1
            padding = 0
            line_lengths = []
            for i, line in enumerate(clips):
                line_lengths.append(len(line))
                if line.isspace():
                    padding += len(line)
                elif not (len(line) == 0) and content_line == -1:
                    content_line = i
            if content_line == -1:
                content_line = 0

            init_indent = len(clips[content_line]) - len(stripped_lines[content_line])
            for r in s:
                line_reg = v.line(r.begin())
                insert_pos = line_reg.a if before else v.full_line(r.begin()).b
                buf_indent = indent = find_indent(v, line_reg, r, wschar, before)
                strings = []
                for lline, sline in zip(line_lengths, stripped_lines):
                    if not indent_same:
                        indent = buf_indent + lline - len(sline) - init_indent
                    strings.extend([wschar * indent, sline, "\n"])

                insert_string = "".join(strings)

                s.subtract(r)
                v.insert(edit, insert_pos, insert_string)
                add_pt(vi, insert_pos + buf_indent + content_line + padding)

        v.show(v.sel()[-1].b, False)
