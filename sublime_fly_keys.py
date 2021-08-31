import sublime
import sublime_plugin

from typing import List, Tuple
from os import path
import bisect
import datetime
import re
import string

interesting_regions = {}
timeout = datetime.datetime.now()
WORDCHARS = r'[-\._\w]+'


class AddCursorsToEndOfParagraphCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        selections = buf.sel()
        positions: List[int] = []

        for region in selections:
            cur_line_num = buf.line(region.begin())
            orig_whitespace = cur_line_num.b - cur_line_num.a - len(buf.substr(cur_line_num).lstrip())
            current_pos_on_line = region.begin() - cur_line_num.a
            put_at_soft_bol = orig_whitespace == current_pos_on_line
            put_at_end = region.begin() == cur_line_num.b
            if put_at_soft_bol:
                has_empty_lines = False
                next_line = cur_line_num
                while next_line.b - 1 < buf.size():
                    next_line = buf.line(next_line.b + 1)
                    while len(next_line) == 0 and next_line.b - 1 < buf.size():
                        has_empty_lines = True
                        next_line = buf.line(next_line.b + 1)
                    mod_whitespace = next_line.b - next_line.a - len(buf.substr(next_line).lstrip())
                    if mod_whitespace < orig_whitespace or (has_empty_lines and mod_whitespace == 0):
                        break
                    positions.append(next_line.a + mod_whitespace)

            elif put_at_end == True:
                next_line = buf.line(cur_line_num.b + 1)
                mod_whitespace = next_line.b - next_line.a - len(buf.substr(next_line).lstrip())
                while mod_whitespace >= orig_whitespace and next_line.a != next_line.b and next_line.b - 1 < buf.size():
                    positions.append(next_line.b)
                    next_line = buf.line(next_line.b + 1)
                    mod_whitespace = next_line.b - next_line.a - len(buf.substr(next_line).lstrip())
            else:
                next_line = buf.line(cur_line_num.b + 1)
                mod_whitespace = next_line.b - next_line.a - len(buf.substr(next_line).lstrip())
                while mod_whitespace >= orig_whitespace and len(next_line) > 0 and next_line.b - 1 < buf.size():
                    if next_line.a + current_pos_on_line > next_line.b:
                        positions.append(next_line.b)
                    else:
                        positions.append(next_line.a + current_pos_on_line)

                    next_line = buf.line(next_line.b + 1)
                    mod_whitespace = next_line.b - next_line.a - len(buf.substr(next_line).lstrip())

        selections.add_all(positions)



class AddLineCommand(sublime_plugin.TextCommand):
    def eol_token_helper(self, cur_line: str, buf: sublime.View) -> bool:
        syntax = buf.syntax().name
        if syntax == 'Python':
            if cur_line[-1] == ':':
                return True
            else:
                return False
        elif syntax == 'Bash':
            if cur_line.endswith('else') or cur_line.endswith('then') or cur_line.endswith('{'):
                return True
            else:
                return False

        return False


    def run(self, edit, forward):
        buf = self.view
        if buf.is_read_only() == True:
            return
        selections = buf.sel()
        for region in reversed(selections):

            cur_line_num = buf.line(region.begin())
            cur_line = buf.substr(cur_line_num)
            cur_indent = len(cur_line) - len(cur_line.lstrip())

            if forward == True and cur_line and self.eol_token_helper(cur_line, buf):
                indent = cur_indent + 4
                target_line_offset = cur_line_num.b + 1

            else:
                if forward == True:
                    target_line_offset = cur_line_num.b + 1

                    target_line = buf.line(target_line_offset)
                    while target_line.b - target_line.a < 1 and target_line.b < buf.size():
                        target_line = buf.line(target_line.b + 1)

                else:
                    target_line_offset = cur_line_num.a
                    target_line = buf.line(target_line_offset)
                    while target_line.b - target_line.a < 1 and target_line.a > 1:
                        target_line = buf.line(target_line.a - 1)

                target_line = buf.substr(target_line)
                target_indent = len(target_line) - len(target_line.lstrip())

                if target_indent > cur_indent:
                    indent = target_indent
                else:
                    indent = cur_indent

            selections.subtract(region)
            buf.insert(edit, target_line_offset,' ' * indent + '\n')
            selections.add(target_line_offset + indent)

        buf.settings().set(key="block_caret", value=False)
        buf.settings().set(key="command_mode", value=False)



class ClearSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _, forward):
        buf = self.view
        for region in buf.sel():
            buf.sel().subtract(region)
            if forward == True:
                _, col = buf.rowcol(region.end())
                if col == 0:
                    reg = region.end() - 1
                else:
                    reg = region.end()
            else:
                reg = region.begin()
            buf.sel().add(reg)
            buf.show(reg, False)

class CopyInFindInFilesCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        sel = buf.sel()
        line = buf.line(sel[0])
        line_content = buf.substr(line)

        if line_content.startswith('/'):
            sublime.set_clipboard(line_content[:-1])
            return

        line_match = re.match(r"^\s+\d+", line_content)
        if line_match:
            offset = line_match.end() + 2
            sublime.set_clipboard(line_content[offset:])
            return


class CreateRegionFromSelectionsCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        sel = buf.sel()
        line_beg = buf.full_line(sel[0]).begin()
        line_end = buf.full_line(sel[-1]).end()
        sel.clear()
        sel.add(sublime.Region(line_beg, line_end))

class DeleteSmartCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        for region in reversed(buf.sel()):
            if region.empty():
                if region.a == buf.size():
                    reg = buf.full_line(region.begin() -1)
                else:
                    reg = buf.full_line(region.begin())
            else:
                begin_line, _ = buf.rowcol(region.begin())
                end_line, col = buf.rowcol(region.end())
                if col != 0:
                    end_line += 1
                reg_beg = buf.text_point(begin_line, 0)
                reg_end = buf.text_point(end_line, 0) - 1
                reg = sublime.Region(reg_beg, reg_end + 1)
            buf.erase(edit, reg)



class ExpandSelectionToSentenceCommand(sublime_plugin.TextCommand):
    # TODO: Add foward command to go forward and backward selction of sentences
    def run(self, _):
        view = self.view
        # whitespace = '\t\n\x0b\x0c\r ' # Equivalent to string.whitespace
        oldSelRegions = list(view.sel())
        view.sel().clear()
        for thisregion in oldSelRegions:
            thisRegionBegin = thisregion.begin() - 1
            while ((view.substr(thisRegionBegin) not in ".") and (thisRegionBegin >= 0)):
                thisRegionBegin -= 1
            thisRegionBegin += 1
        while((view.substr(thisRegionBegin) in string.whitespace) and (thisRegionBegin < view.size())):
            thisRegionBegin += 1

        thisRegionEnd = thisregion.end()
        while((view.substr(thisRegionEnd) not in ".") and (thisRegionEnd < view.size())):
            thisRegionEnd += 1

        if(thisRegionBegin != thisRegionEnd):
            view.sel().add(sublime.Region(thisRegionBegin, thisRegionEnd+1))
        else:
            view.sel().add(sublime.Region(thisRegionBegin, thisRegionBegin))


class SetReadOnly(sublime_plugin.EventListener):
    def on_new_async(self, view):
        if view.name() == 'Find Results':
            view.set_read_only(True)

class FindInFilesGotoCommand(sublime_plugin.TextCommand):

    def run(self, _):
        view = self.view
        if view.name() == "Find Results":
            line_no = self.get_line_no()
            file_name = self.get_file()
            if line_no is not None and file_name is not None:
                caretpos = view.sel()[0].begin()
                (_,col) = view.rowcol(caretpos)
                file_loc = "%s:%s:%s" % (file_name, line_no, col -6)
                view.window().open_file(file_loc, sublime.ENCODED_POSITION)
            elif file_name is not None:
                view.window().open_file(file_name)

    def get_line_no(self):
        view = self.view
        if len(view.sel()) == 1:
            line_text = view.substr(view.line(view.sel()[0]))
            match = re.match(r"\s*(\d+).+", line_text)
            if match:
                return match.group(1)
        return None

    def get_file(self):
        view = self.view
        if len(view.sel()) == 1:
            line = view.line(view.sel()[0])
            while line.begin() > 0:
                line_text = view.substr(line)
                match = re.match(r"(.+):$", line_text)
                if match:
                    if path.exists(match.group(1)):
                        return match.group(1)
                line = view.line(line.begin() - 1)
        return None

prev_buf_id = 0
pos_begin = 0
allow_extend = False
ought_to_extend = False
should_change_to_bol = False



class SampleListener(sublime_plugin.EventListener):
    def on_query_context(self, view, key, _, operand, __):
        global allow_extend
        global ought_to_extend
        global should_change_to_bol
        if key in ("goto_anything:input"):
            lhs = view.element() == "goto_anything:input"
            if view.element() == "goto_anything:input":
                if ought_to_extend == True:
                    allow_extend = True
                should_change_to_bol = True
            else:
                allow_extend = False
            rhs = bool(operand)

            return lhs == rhs if operand != sublime.OP_EQUAL else lhs != rhs
        return None

    def on_activated(self, _):
        global prev_buf_id
        global pos_begin
        global allow_extend
        global should_change_to_bol
        if allow_extend == True:
            allow_extend = False
            v = sublime.active_window().active_view()
            if prev_buf_id == v.id():
                end = v.full_line(v.sel()[0].end()).end()
                v.sel().add(sublime.Region(pos_begin,end))
        elif should_change_to_bol:
            v = sublime.active_window().active_view()
            end = v.full_line(v.sel()[0].end()).end()
            should_change_to_bol = False
            next_res, next_res_end = v.find(r'\S|^$|^\s+$', v.sel()[0].end())
            v.sel().clear()
            v.sel().add(sublime.Region(next_res,next_res))

    def on_deactivated_async(self, _):
        global prev_buf_id
        global pos_begin
        global ought_to_extend
        v = sublime.active_window().active_view()
        has_selection = v.sel()[0].empty()
        if not has_selection:
            prev_buf_id = v.id()
            pos, _ = v.sel()[0]
            pos_begin = pos
            ought_to_extend = True
        else:
            ought_to_extend = False


class NumberCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        buf = self.view
        selection = buf.sel()
        for region in selection:
            if region.empty() == False:
                mystr = buf.substr(region)
                if mystr.isdigit() or mystr.startswith('-') and mystr[1:].isdigit():
                    continue
                reg_list = [sublime.Region(m.start() + region.begin(), m.end() + region.begin()) for m in re.finditer(r'-?\d+', buf.substr(region))]
                if reg_list != []:
                    selection.subtract(region)
                    for maybe_digit in reg_list:
                        selection.add(maybe_digit)
            else:
                line, column = buf.rowcol(region.begin())
                cur_line = buf.substr(buf.full_line(buf.text_point(line,-1)))
                line_length = len(cur_line)
                start_pos = None
                end_pos = None
                to_the_right = line_length - column
                to_the_left = line_length - (line_length - column) + 0

                if cur_line[column].isdigit() or (cur_line[column] == '-' and cur_line[column + 1].isdigit()):
                    first_char_is_digit = True
                else:
                    first_char_is_digit = False

                for i in range(to_the_right):
                    i_pointer = column + i
                    if cur_line[i_pointer].isdigit() or (not end_pos and cur_line[i_pointer] == '-' and cur_line[i_pointer + 1].isdigit()):

                        if not start_pos and first_char_is_digit == False:
                            start_pos = i_pointer

                        end_pos = i_pointer

                    elif end_pos:
                        break

                if not start_pos:
                    for j in range(to_the_left):
                        j_pointer = column - j
                        if cur_line[j_pointer].isdigit() or (cur_line[j_pointer] == '-' and cur_line[j_pointer + 1].isdigit()):

                            if not end_pos:
                                end_pos = j_pointer

                            start_pos = j_pointer

                        elif start_pos:
                            break

                if start_pos is not None and end_pos is not None:
                    selection.subtract(region)
                    selection.add(sublime.Region(buf.text_point(line, start_pos), buf.text_point(line, end_pos + 1)))

        for region in selection:
            try:
                value = int(buf.substr(region))
                buf.replace(edit, region, str(self.op(value)))
            except ValueError:
                    pass


class IncrementCommand(NumberCommand):
    def op(self, value):
          return value + 1

class DecrementCommand(NumberCommand):
    def op(self, value):
          return value - 1


class InsertModeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        if buf.is_read_only() == True:
            sublime.status_message('Buffer is read only')
            return

        for region in reversed(buf.sel()):
            if region.empty():
                continue
            buf.erase(edit, region)
        buf.settings().set(key="block_caret", value=False)
        buf.settings().set(key="command_mode", value=False)


class DeleteRestOfLineAndInsertModeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        buf = self.view
        if buf.is_read_only() == True:
            sublime.status_message('Buffer is read only')
            return

        rev_sel: reversed[List[sublime.Region]] = reversed(buf.sel())
        for reg in rev_sel:
            if reg.empty():
                line = buf.line(reg.begin())
                buf.erase(edit, sublime.Region(reg.begin(), line.end()))
            else:
                buf.erase(edit, region)
        buf.settings().set(key="block_caret", value=False)
        buf.settings().set(key="command_mode", value=False)


class CommandModeCommand(sublime_plugin.WindowCommand):
    def run(self):
        buf = sublime.active_window().active_view()
        buf.settings().set(key="block_caret", value=True)
        buf.settings().set(key="command_mode", value=True)
        buf.window().run_command('hide_panel')
        buf.window().run_command('hide_popup')


class InsertBeforeOrAfterCommand(sublime_plugin.TextCommand):
    def run(self, _, after=False, plusone=False):
        if plusone == True:
            offset = 1
        else:
            offset = 0
        buf = self.view
        selections = buf.sel()
        for region in selections:

            if region.empty():
                if len(selections) == 1:
                    return
                selections.subtract(region)

            if after == True:
                reg = region.end() + offset
            else:
                reg = region.begin() - offset

            selections.subtract(region)
            selections.add(reg)

        buf.settings().set(key="block_caret", value=False)
        buf.settings().set(key="command_mode", value=False)



def build_or_rebuild_ws_for_view(view, immediate: bool):
    global interesting_regions
    global timeout
    if (datetime.datetime.now() - timeout).total_seconds() > 2 or immediate == True:
        interesting_regions[view] = {}
        try:
            whitespaces = view.find_all(r'\n\n *\S')
            first, last = zip(*[(-2, -1)] + [(first, last -1) for first, last in whitespaces] + [(view.size() + 1, view.size() + 1)])
            interesting_regions[view]['first'] = first
            interesting_regions[view]['last'] = last
        except ValueError:
            pass
    timeout = datetime.datetime.now()


class HejSampleListener(sublime_plugin.EventListener):
    def on_modified_async(self, view):
        if view.element() is None:
            try:
                global interesting_regions
                del interesting_regions[view]
            except KeyError:
                pass
            sublime.set_timeout(lambda: build_or_rebuild_ws_for_view(view, immediate=False), 2000)

    def on_load_async(self, view):
        if view not in interesting_regions and view.element() is None:
            build_or_rebuild_ws_for_view(view, immediate=True)

class NavigateByParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        region = buf.sel()[-1].begin()
        try:
            myregs = interesting_regions[buf]['last']
        except KeyError:
            build_or_rebuild_ws_for_view(buf, immediate=True)
            myregs = interesting_regions[buf]['last']
        bisect_res = bisect.bisect(myregs, region)
        sel_end = myregs[bisect_res]
        reg = sublime.Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, False)


class NavigateByParagraphBackwardCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        region = buf.sel()[0].begin()
        try:
            myregs = interesting_regions[buf]['last']
        except KeyError:
            build_or_rebuild_ws_for_view(buf, immediate=True)
            myregs = interesting_regions[buf]['last']
        bisect_res = bisect.bisect(myregs, region - 1)
        sel_end = myregs[bisect_res -1 ]
        reg = sublime.Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, False)


class ExtendedExpandSelectionToParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        regs_dict = {}
        for region in buf.sel():

            try:
                first = interesting_regions[buf]['first']
            except KeyError:
                build_or_rebuild_ws_for_view(buf, immediate=True)
                first = interesting_regions[buf]['first']

            if region.b > region.a:
                bisect_res = bisect.bisect(first, region.b)
                sel_begin = region.a
                sel_end = first[bisect_res] + 2

            elif region.a > region.b:
                bisect_res = bisect.bisect(first, region.b)
                sel_end = first[bisect_res] + 2
                if region.a == sel_end or sel_end - 3 == region.a:
                    sel_end = region.a
                    sel_begin = region.b
                else:
                    sel_begin = region.a
                    buf.sel().subtract(region)

            elif region.a == region.b:
                bisect_res = bisect.bisect(first, region.b -2)
                sel_begin = first[bisect_res -1] + 2
                sel_end = first[bisect_res] + 2

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all(sublime.Region(begin,end) for begin,end in regs_dict.items())
        buf.show(buf.sel()[-1], False)


class ExtendedExpandSelectionToParagraphBackwardCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        regs_dict = {}
        for region in buf.sel():

            try:
                first = interesting_regions[buf]['first']
            except KeyError:
                build_or_rebuild_ws_for_view(buf, immediate=True)
                first = interesting_regions[buf]['first']

            if region.b > region.a:
                bisect_end = bisect.bisect(first, region.b - 3)
                sel_end = first[bisect_end -1] + 2
                if region.a == sel_end:
                    sel_end = region.a
                    sel_begin = region.b
                else:
                    sel_begin = region.a
                    buf.sel().subtract(region)

            elif region.a > region.b:
                sel_begin = region.a
                bisect_end = bisect.bisect(first, region.b - 3)
                if bisect_end == 0:
                    sel_end = -1
                else:
                    sel_end = first[bisect_end -1] + 2

            elif region.b == region.a:
                bisect_end = bisect.bisect(first, region.b - 2)
                sel_end = first[bisect_end -1] + 2
                sel_begin = first[bisect_end] + 2

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all(sublime.Region(begin, end) for begin,end in regs_dict.items())
        buf.show(buf.sel()[0], False)


class MultipleCursorsFromSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        reg_list = []
        for region in buf.sel():
            reg_begin = region.begin() - 1
            buffer = buf.substr(sublime.Region(reg_begin, region.end()))
            if reg_begin <= 1:
                reg_begin += 1
                reg_list.append(-2)
            reg_list += [sublime.Region(m.start() + reg_begin) for m in re.finditer(r'\S.*\n', buffer)]
        buf.sel().clear()
        buf.sel().add_all(reg_list)



class RevertSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        sel = buf.sel()
        for reg in sel:
            if reg.empty():
                continue
            region = sublime.Region(reg.b, reg.a)
            sel.subtract(reg)
            sel.add(region)



class SingleSelectionLastCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        reg = buf.sel()[-1]
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, True)


class SmartFindWordCommand(sublime_plugin.TextCommand):
    def run(self, _):
        buf = self.view
        sel = buf.sel()
        positions: List[int] = []
        for reg in sel:
            if not reg.empty():
                end_pos = reg.end()
                sel.subtract(reg)
                sel.add(end_pos)

            str_after_cur = buf.substr(reg.begin())
            if str_after_cur.isalnum() or str_after_cur == '_':
                if len(sel) > 1:
                    positions.append(reg.a)
                    continue
                else:
                    return

            str_before_cur = buf.substr(reg.begin() -1)
            if str_before_cur.isalnum() or str_before_cur == '_':
                if len(sel) > 1:
                    positions.append(reg.a)
                    continue
                else:
                    return

            cur_line_in_points_beg, cur_line_in_points_end = buf.line(reg)

            rev_reg = sublime.Region(cur_line_in_points_beg, reg.begin())
            rev_reg_str = buf.substr(rev_reg)
            i = 0
            rev_beg = -1
            for char in reversed(rev_reg_str):
                if rev_beg == -1:
                    if (char.isalnum() or char == '_'):
                        rev_beg = i
                        break
                i += 1

            forw_reg_str = ''
            if rev_beg > 1 or rev_beg == -1:
                forw_reg = sublime.Region(cur_line_in_points_end, reg.begin())
                forw_reg_str = buf.substr(forw_reg)
            if len(forw_reg_str) > 0:
                j = 0
                forw_beg = -1
                for char in forw_reg_str:
                    if forw_beg == -1:
                        if (char.isalnum() or char == '_'):
                            forw_beg = j
                            break
                    j += 1

                if forw_beg != -1 and rev_beg == -1:
                    positions.append(reg.a + forw_beg)
                elif forw_beg < rev_beg:
                    positions.append(reg.a + forw_beg)
                elif rev_beg != -1:
                    positions.append(reg.a - rev_beg)
                else:
                    positions.append(reg.a)
                    continue
            else:
                positions.append(reg.a - rev_beg)

        sel.clear()
        buf.sel().add_all(positions)


class SmartCopyCommand(sublime_plugin.TextCommand):
    def run(self, _, whole_line: bool = False) -> None:
        buf = self.view
        sel = buf.sel()

        if whole_line:
            sublime.set_clipboard(''.join(buf.substr(buf.full_line(reg)) for reg in sel))
            reg = sel[-1].b
            sel.clear()
            sel.add(reg)
            return

        regions_to_copy: List[sublime.Region] = []
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
                clip = buf.substr(sublime.Region(regions_to_copy[0].a, regions_to_copy[-1].b))
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

        sublime.set_clipboard(clip)
        return



class SmartCutCommand(sublime_plugin.TextCommand):
    """docstring for SmartCopyCommand"""
    def run(self, edit: sublime.Edit) -> None:
        buf = self.view
        sel = buf.sel()

        regions_to_copy: List[sublime.Region] = []
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
                interesting_region = sublime.Region(regions_to_copy[0].begin(), regions_to_copy[-1].end())
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

        sublime.set_clipboard(clip)
        return

class SmartPasteCutNewlinesCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit) -> None:
        buf = self.view
        sels: sublime.Selection = buf.sel()

        clipboard = sublime.get_clipboard()
        clips = clipboard.splitlines()

        if clipboard.endswith('\n'):
            pass
        else:

            clip_pos: List[Tuple[int, int]] = [(len(clips[-1]), len(clips[-1]) + 1)]
            for clip in reversed(clips[:-1]):
                clip_pos.append((len(clip) + 1 + clip_pos[-1][0], len(clip) + 1))

            rev_sel: reversed[sublime.Region] = reversed(sels)
            for reg in rev_sel:
                if not reg.empty():
                    buf.erase(edit, reg)
                buf.insert(edit, reg.a, ' '.join(clips))

            rev_sel_new: reversed[sublime.Region] = reversed(sels)
            for reg in rev_sel_new:
                sels.add_all(sublime.Region(reg.begin() - pos[0], reg.begin() - pos[0] + pos[1] -1) for pos in clip_pos)


class SmartPasteCommand(sublime_plugin.TextCommand):
    def find_indent(self, cur_line_num: sublime.Region, cur_line: str) -> int:
        buf = self.view
        # if we have a new, empty file:
        if buf.size() == 0:
            return 0

        clipboard = sublime.get_clipboard()
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


    def run(self, edit: sublime.Edit):
        buf = self.view
        sels: sublime.Selection = buf.sel()
        clipboard = sublime.get_clipboard()
        clips = clipboard.splitlines()

        if clipboard.endswith('\n'):
            has_final_newline = True
        else:
            has_final_newline = False

        # means we need to match the selections with the clips
        if len(clips) == len(sels):

            rev_sel: reversed[sublime.Region] = reversed(sels)
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


        # Ok, just regular paste
        elif len(clips) > len(sels):
            rev_sel: reversed[sublime.Region] = reversed(sels)
            for region in rev_sel:

                cur_line_num = buf.line(region.begin())
                cur_line = buf.substr(cur_line_num)

                insert_pos, _ = buf.line(region.begin())
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

                # print(regions_to_remove)

                # Now we have the regions, and we now if we should delete anything
                # on the lines. We can now do the loop again where we modify the buffer
                # regions to be deleted will be those with more than two elements in the
                # inner list
                for regs in reversed(regions_to_remove):
                    if len(regs) > 1:
                        buf.erase(edit, sublime.Region(regs[0], regs[-1]))

                # now we can start inserting:
                rev_sel: reversed[sublime.Region] = reversed(sels)
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
                rev_sel: reversed[sublime.Region] = reversed(sels)
                for region in rev_sel:
                    if not region.empty():
                        buf.erase(edit, region)
                    insert_pos = region.begin()
                    buf.insert(edit, insert_pos, clipboard)


class SplitSelectionIntoLinesWholeWordsCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        selections = buf.sel()
        rev_sels: reversed[sublime.Region] = reversed(selections)
        for region in rev_sels:
            if region.empty():
                continue

            contents = buf.substr(region)
            begin = region.begin()
            word_boundaries = [sublime.Region(m.start() + begin, m.end() + begin) for m in re.finditer(WORDCHARS, contents)]
            if word_boundaries != []:
                selections.subtract(region)
                selections.add_all(word_boundaries)


class UndoFindUnderExpandCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        selection = buf.sel()

        if len(selection) == 1:
            buf.show(selection[0], True)
            return

        selected_word = buf.substr(selection[-1])
        min_point = selection[0].begin()
        max_point = selection[-1].end()

        res = buf.find(selected_word, start_pt=max_point)
        if res.begin() != -1:
            selection.subtract(selection[-1])
            buf.show(selection[-1], True)
            return

        reg = sublime.Region(min_point, max_point)
        all_regs = [min_point +  m.end() for m in re.finditer(selected_word, buf.substr(reg))]

        i = 0
        for region in selection:
            if region.end() < all_regs[i]:
                # Consider a continue statement here instead.
                # Depends on what strategy works best
                selection.subtract(region)
                buf.show(selection[i-1], True)
                return
            elif region.end() > all_regs[i]:
                selection.subtract(selection[i-1])
                buf.show(selection[i-2], True)
                return
            i += 1

        selection.subtract(selection[-1])
        buf.show(selection[-1], True)

class SubtractFirstSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _):
        selections = self.view.sel()
        if len(selections) > 1:
            selections.subtract(selections[0])
            self.view.show(selections[0], True)

