from sublime import Edit, View, Region, Selection, get_clipboard, set_clipboard
import sublime_plugin
import re

from typing import List, Tuple
class SmartCopyCommand(sublime_plugin.TextCommand):
    def run(self, _, whole_line: bool = False) -> None:
        buf: View = self.view
        sel = buf.sel()

        if whole_line:
            set_clipboard(''.join(buf.substr(buf.full_line(reg)) for reg in sel))
            reg = sel[-1].b
            sel.clear()
            sel.add(reg)
            return

        regions_to_copy: List[Region] = []
        end = buf.full_line(sel[0].a).a

        only_empty_selections = True
        contiguous_regions = True

        for region in sel:
            if region.empty():

                line = buf.full_line(region.a)
                if regions_to_copy:
                    if regions_to_copy[-1].a != line.a and regions_to_copy[-1].b != line.b:
                        regions_to_copy.append(line)
                else:
                    regions_to_copy.append(line)

                if contiguous_regions == True:
                    if end == line.a:
                        end = line.b
                    else:
                        contiguous_regions = False

            else:
                only_empty_selections = False
                regions_to_copy.append(region)

        if only_empty_selections:
            if contiguous_regions:
                clip = buf.substr(Region(regions_to_copy[0].a, regions_to_copy[-1].b))
            else:
                clip = ''.join(buf.substr(reg) for reg in regions_to_copy)
        else:
            clip = '\n'.join(buf.substr(reg) for reg in regions_to_copy)

        if clip.isspace():
            return

        if only_empty_selections and contiguous_regions:
            reg = sel[-1].a
            sel.clear()
            sel.add(reg)
        else:
            pos = [reg.end() for reg in sel]
            sel.clear()
            sel.add_all(pos)

        set_clipboard(clip)
        return



class SmartCutCommand(sublime_plugin.TextCommand):
    """docstring for SmartCopyCommand"""
    def run(self, edit: Edit) -> None:
        buf: View = self.view
        sel = buf.sel()

        regions_to_copy: List[Region] = []
        end = buf.full_line(sel[0].begin()).begin()

        only_empty_selections = True
        contiguous_regions = True

        for region in sel:
            if region.empty():
                line = buf.full_line(region.begin())

                if regions_to_copy != []:
                    if regions_to_copy[-1].a != line.a and regions_to_copy[-1].b != line.b:
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
                interesting_region = Region(regions_to_copy[0].begin(), regions_to_copy[-1].end())
                clip = buf.substr(interesting_region)
                buf.erase(edit, interesting_region)
            else:
                clip = ''.join(buf.substr(reg) for reg in regions_to_copy)
                for reg in reversed(regions_to_copy):
                    buf.erase(edit, reg)

        else:
            clip = '\n'.join(buf.substr(reg) for reg in regions_to_copy)
            for reg in reversed(regions_to_copy):
                buf.erase(edit, reg)

        if clip.isspace():
            return

        set_clipboard(clip)
        return

class SmartPasteCutNewlinesOrWhitespaceCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
        buf: View = self.view
        sels: Selection = buf.sel()
        clipboard = get_clipboard()
        if clipboard.endswith('\n'):
            stripped_clipboard = clipboard.strip()
            for region in reversed(sels):
                if not region.empty():
                    buf.erase(edit, region)
                buf.insert(edit, region.begin(), stripped_clipboard)
            return
        else:
            clips = clipboard.splitlines()
            clip_pos: List[Tuple[int, int]] = [(len(clips[-1]), len(clips[-1]) + 1)]
            for clip in reversed(clips[:-1]):
                clip_pos.append((len(clip) + 1 + clip_pos[-1][0], len(clip) + 1))

            rev_sel: reversed[Region] = reversed(sels)
            for reg in rev_sel:
                if not reg.empty():
                    buf.erase(edit, reg)
                buf.insert(edit, reg.a, ' '.join(clips))

            rev_sel_new: reversed[Region] = reversed(sels)
            for reg in rev_sel_new:
                sels.add_all(Region(reg.begin() - pos[0], reg.begin() - pos[0] + pos[1] -1) for pos in clip_pos)

class SmartPasteCutWhitespaceCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit):
        buf: View = self.view
        stripped_clipboard = get_clipboard().strip()
        sels: Selection = buf.sel()
        for region in reversed(sels):
            buf.erase(edit, region)
            buf.insert(edit, region.begin(), stripped_clipboard)

class SmartPasteCommand(sublime_plugin.TextCommand):
    def find_indent(self, cur_line_num: Region, cur_line: str) -> int:
        buf: View = self.view
        # if we have a new, empty file:
        if buf.size() == 0:
            return 0
        clipboard = get_clipboard()
        if len(cur_line) == 0 and clipboard.startswith(' '):
            lines_above, _ = buf.line(cur_line_num.begin())
            for line in range(lines_above):
                line += 1
                prev_line = buf.substr(buf.line(cur_line_num.begin() - line))
                if prev_line.startswith(' '):
                    break
            indent = len(prev_line) - len(prev_line.lstrip())
        else:
            indent = len(cur_line) - len(cur_line.lstrip())
        return indent


    def run(self, edit: Edit) -> None:
        buf: View = self.view
        sels: Selection = buf.sel()
        clipboard = get_clipboard()
        clips = clipboard.splitlines()

        if clipboard.endswith('\n'):
            has_final_newline = True
        else:
            has_final_newline = False

        # means we need to match the selections with the clips
        if len(clips) == len(sels):

            rev_sel: reversed[Region] = reversed(sels)
            for region, cliplet in zip(rev_sel, reversed(clips)):

                cur_line_num = buf.line(region.begin())
                cur_line = buf.substr(cur_line_num)

                if has_final_newline:
                    insert_pos, _ = buf.line(region.begin())
                    indent = self.find_indent(cur_line_num, cur_line)
                    insert_string = " " * indent + cliplet.lstrip() + '\n'
                else:
                    insert_string = cliplet
                    insert_pos = region.begin()

                if region.empty() == False:
                    buf.erase(edit, region)
                elif has_final_newline and len(sels) > 1:
                    if region.a == buf.size():
                        reg = buf.full_line(region.begin() -1)
                    else:
                        reg = buf.full_line(region.begin())
                    buf.erase(edit, reg)

                buf.insert(edit, insert_pos, insert_string)

            if has_final_newline and len(sels) > 1:
                m = buf.sel()[-1]
                buf.sel().clear()
                buf.sel().add(m)


        # Ok, just regular paste
        elif len(clips) > len(sels):
            rev_sel: reversed[Region] = reversed(sels)
            for region in rev_sel:

                cur_line_num = buf.line(region.begin())
                cur_line = buf.substr(cur_line_num)

                insert_pos, _ = buf.line(region.begin())
                above_indent = self.find_indent(cur_line_num, cur_line)
                insert_string = ''
                initial_indent = None
                for line in clips:
                    deindented_line = line.lstrip()
                    cur_indent = len(line) - len(deindented_line)
                    if initial_indent == None:
                        initial_indent = cur_indent
                    this_indent = above_indent + cur_indent - initial_indent
                    insert_string += " " * this_indent  + deindented_line + '\n'

                if region.empty() == False:
                    buf.erase(edit, region)

                buf.insert(edit, insert_pos, insert_string)

        # we can use the selections as markers of where to cut
        # but only if it is clear that we want to do that.
        # We have two criteria:
        # 1. they must belong to consecutive lines, and
        # 2. the selections must not be on the border of words
        elif len(clips) < len(sels):

            if has_final_newline:

                regions_to_remove: List[List[int]] = []
                # It has to be
                end: int = -1

                # first we just loop over all the regions, collecting consecutive lines regions
                i = -1
                for region in sels:
                    line = buf.full_line(region.begin())
                    if end == line.a:
                        regions_to_remove[i].append(line.end())
                    else:
                        i += 1
                        regions_to_remove.append([line.begin()])

                    end = line.end()

                # Now we have the regions, and we now if we should delete anything
                # on the lines. We can now do the loop again where we modify the buffer
                # regions to be deleted will be those with more than two elements in the
                # inner list
                for regs in reversed(regions_to_remove):
                    if len(regs) > 1:
                        buf.erase(edit, Region(regs[0], regs[-1]))

                # now we can start inserting:
                rev_sel: reversed[Region] = reversed(sels)
                for region in rev_sel:
                    cur_line_num = buf.line(region.begin())
                    cur_line = buf.substr(cur_line_num)

                    insert_pos = buf.line(region.begin()).begin()
                    above_indent = self.find_indent(cur_line_num, cur_line)
                    insert_string = ''
                    initial_indent = None
                    for line in clips:
                        deindented_line = line.lstrip().rstrip()
                        cur_indent = len(line) - len(deindented_line)
                        if initial_indent == None:
                            initial_indent = cur_indent
                        this_indent = above_indent + cur_indent - initial_indent
                        insert_string += " " * this_indent  + deindented_line + '\n'

                    buf.insert(edit, insert_pos, insert_string)

            else:
                rev_sel: reversed[Region] = reversed(sels)
                for region in rev_sel:
                    if not region.empty():
                        buf.erase(edit, region)
                    insert_pos = region.begin()
                    buf.insert(edit, insert_pos, clipboard)


class CopyInFindInFilesCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf: View = self.view
        sel = buf.sel()
        line = buf.line(sel[0])
        line_content = buf.substr(line)

        if line_content.startswith('/'):
            set_clipboard(line_content[:-1])
            return

        line_match = re.match(r"^\s+\d+", line_content)
        if line_match:
            offset = line_match.end() + 2
            set_clipboard(line_content[offset:])
            return
