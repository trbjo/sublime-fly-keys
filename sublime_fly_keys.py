from sublime import LAYOUT_INLINE, LITERAL, Edit, View, Region, Selection, get_clipboard, set_clipboard, active_window
import sublime
import sublime_plugin

from typing import List, Tuple, Dict, Union
from os import path
import bisect
import datetime
import re
import string

interesting_regions: Dict[View, Dict[str, Tuple[int]]] = {}
timeout = datetime.datetime.now()
WORDCHARS = r'[-\._\w]+'

class AddCursorsToBeginningOfParagraphCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit):
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
                prev_line = cur_line_num
                while prev_line.a - 1 > 0:
                    prev_line = buf.line(prev_line.a - 1)
                    while len(prev_line) == 0 and prev_line.b - 1 < 0:
                        has_empty_lines = True
                        prev_line = buf.line(prev_line.a - 1)
                    mod_whitespace = prev_line.b - prev_line.a - len(buf.substr(prev_line).lstrip())
                    if mod_whitespace < orig_whitespace or (has_empty_lines and mod_whitespace == 0):
                        break
                    positions.append(prev_line.a + mod_whitespace)

            elif put_at_end == True:
                prev_line = buf.line(cur_line_num.a - 1)
                mod_whitespace = prev_line.b - prev_line.a - len(buf.substr(prev_line).lstrip())
                while mod_whitespace >= orig_whitespace and prev_line.a != prev_line.b and prev_line.a - 1 > 0:
                    positions.append(prev_line.b)
                    prev_line = buf.line(prev_line.a - 1)
                    mod_whitespace = prev_line.b - prev_line.a - len(buf.substr(prev_line).lstrip())
            else:
                prev_line = buf.line(cur_line_num.a - 1)
                mod_whitespace = prev_line.b - prev_line.a - len(buf.substr(prev_line).lstrip())
                while len(prev_line) > 0 and prev_line.a - 1 > 0:
                    if prev_line.a + current_pos_on_line > prev_line.b:
                        positions.append(prev_line.b)
                    else:
                        positions.append(prev_line.a + current_pos_on_line)

                    prev_line = buf.line(prev_line.a - 1)
                    mod_whitespace = prev_line.b - prev_line.a - len(buf.substr(prev_line).lstrip())

        selections.add_all(positions)



class AddCursorsToEndOfParagraphCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit):
        buf = self.view
        selections = buf.sel()
        positions: List[int] = []
        maybe_positions: List[int] = []

        for region in selections:
            cur_line_num = buf.line(region.begin())
            orig_whitespace = cur_line_num.b - cur_line_num.a - len(buf.substr(cur_line_num).lstrip())
            current_pos_on_line = region.begin() - cur_line_num.a
            put_at_soft_bol = orig_whitespace == current_pos_on_line
            put_at_end = region.begin() == cur_line_num.b
            if put_at_soft_bol:
                next_line = cur_line_num

                while next_line.b - 1 < buf.size():
                    next_line = buf.line(next_line.b + 1)
                    while len(next_line) == 0 and next_line.b - 1 < buf.size():
                        next_line = buf.line(next_line.b + 1)
                        maybe_positions.append(next_line.a - 1)

                    current_white_space = next_line.b - next_line.a - len(buf.substr(next_line).lstrip())

                    if current_white_space == orig_whitespace == 0:
                        break

                    if current_white_space < orig_whitespace:
                        break
                    else:
                        positions.extend(maybe_positions)

                    positions.append(next_line.a + current_white_space)

            elif put_at_end:
                next_line = buf.line(cur_line_num.b + 1)
                current_white_space = next_line.b - next_line.a - len(buf.substr(next_line).lstrip())
                while current_white_space >= orig_whitespace and next_line.a != next_line.b and next_line.b - 1 < buf.size():
                    positions.append(next_line.b)
                    next_line = buf.line(next_line.b + 1)
                    current_white_space = next_line.b - next_line.a - len(buf.substr(next_line).lstrip())

            else:
                next_line = buf.line(cur_line_num.b + 1)
                current_white_space = next_line.b - next_line.a - len(buf.substr(next_line).lstrip())
                while current_white_space >= orig_whitespace and len(next_line) > 0 and next_line.b - 1 < buf.size():
                    if next_line.a + current_pos_on_line > next_line.b:
                        positions.append(next_line.b)
                    else:
                        positions.append(next_line.a + current_pos_on_line)

                    next_line = buf.line(next_line.b + 1)
                    current_white_space = next_line.b - next_line.a - len(buf.substr(next_line).lstrip())

        selections.add_all(positions)


class ClearSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _, forward: bool) -> None:
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

true_false_dict = {
    "false": "true",
    "False": "True",
    "true": "false",
    "True": "False"
}

class ToggleTrueFalseCommand(sublime_plugin.TextCommand):
    """First we try around the cursor (-6, +6), else we try the whole line"""
    def run(self, edit: Edit) -> None:
        buf = self.view
        for region in reversed(buf.sel()):
            if region.empty():
                linestr = self.view.substr(Region(region.a - 6, region.a + 6))
                g = [(m.start(), m.end(), m.groups()[0]) for m in re.finditer(r'((F|f)alse|(T|t)rue)', linestr)]
                # if more than one match was found, we take the one that is nearest
                # the caret
                if len(g) > 2:
                    return
                elif len(g) == 2:
                    if abs(6-g[1][0]) > abs(6-g[0][1]):
                        myval = 0
                    else:
                        myval = 1
                    begin = g[myval][0] + region.begin() - 6
                    end = g[myval][1] + region.begin() - 6
                    mybool = g[myval][2]
                elif len(g) == 1:
                    begin = g[0][0] + region.begin() - 6
                    end = g[0][1] + region.begin() - 6
                    mybool = g[0][2]
                elif len(g) == 0:
                    lr = self.view.line(region.begin())
                    linestr = self.view.substr(Region(lr.a, lr.b))
                    g = re.search(r'((F|f)alse|(T|t)rue)', linestr)
                    if g is None:
                        return
                    begin = g.span()[0] + lr.a
                    end = g.span()[1] + lr.a
                    mybool = g.group(0)
                else:
                    return
                myregion=Region(begin, end)
                buf.sel().subtract(region)
                myopposite=true_false_dict[mybool]
                buf.replace(edit, myregion, myopposite)
                buf.sel().add(begin)
            else:
                pass



class CopyInFindInFilesCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
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


class CreateRegionFromSelectionsCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        sel = buf.sel()
        line_beg = buf.full_line(sel[0]).begin()
        line_end = buf.full_line(sel[-1]).end()
        sel.clear()
        sel.add(Region(line_beg, line_end))

class DeleteSmartCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
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
                reg = Region(reg_beg, reg_end + 1)
            buf.erase(edit, reg)



class ExpandSelectionToSentenceCommand(sublime_plugin.TextCommand):
    # TODO: Add foward command to go forward and backward selction of sentences
    def run(self, _) -> None:
        view = self.view
        # whitespace = '\t\n\x0b\x0c\r ' # Equivalent to string.whitespace
        oldSelRegions = list(view.sel())
        view.sel().clear()
        for region in oldSelRegions:
            reg_begin = region.begin() - 1
            while ((view.substr(reg_begin) not in ".") and (reg_begin >= 0)):
                reg_begin -= 1
            reg_begin += 1
            while((view.substr(reg_begin) in string.whitespace) and (reg_begin < view.size())):
                reg_begin += 1
            reg_begin -= 1

            reg_end = region.end()
            while((view.substr(reg_end) not in ".") and (reg_end < view.size())):
                reg_end += 1

            if(reg_begin != reg_end):
                view.sel().add(Region(reg_begin, reg_end+1))
            else:
                view.sel().add(Region(reg_begin, reg_begin))


class ExpandSelectionToStringCommand(sublime_plugin.TextCommand):
    def op(self)->str:
        return ''
    def run(self, _) -> None:
        view = self.view
        for region in view.sel():
            reg_begin = region.begin() - 1
            while ((view.substr(reg_begin) not in self.op()) and (reg_begin >= 0)):
                reg_begin -= 1
            reg_begin += 1
            while((view.substr(reg_begin) in string.whitespace) and (reg_begin < view.size())):
                reg_begin += 1

            reg_end: int = region.end()
            while((view.substr(reg_end) not in self.op()) and (reg_end < view.size())):
                reg_end += 1
            reg_end -= 1

            if(reg_begin != reg_end):
                view.sel().add(Region(reg_begin, reg_end+1))
            else:
                view.sel().add(Region(reg_begin, reg_begin))

class ExpandSelectionToStringDoubleCommand(ExpandSelectionToStringCommand):
    def op(self) -> str:
          return '"'

class ExpandSelectionToStringSingleCommand(ExpandSelectionToStringCommand):
    def op(self) -> str:
          return "'"

class SetReadOnly(sublime_plugin.EventListener):
    def on_new_async(self, view: View):
        if view.name() == 'Find Results':
            view.set_read_only(True)

class FindInFilesGotoCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        view = self.view
        if view is None:
            return
        window: sublime.Window|None = view.window()
        if window is None:
            return
        if view.name() == "Find Results":
            line_no = self.get_line_no()
            file_name = self.get_file()
            if line_no is not None and file_name is not None:
                caretpos = view.sel()[0].begin()
                (_,col) = view.rowcol(caretpos)
                file_loc = "%s:%s:%s" % (file_name, line_no, col -6)
                window.open_file(file_loc, sublime.ENCODED_POSITION)
            elif file_name is not None:
                window.open_file(file_name)

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
    def on_query_context(self, view: View, key: str, _, operand: int, __):
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
            v: View | None = active_window().active_view()
            if v is None:
                return
            if prev_buf_id == v.id():
                end = v.full_line(v.sel()[0].end()).end()
                v.sel().add(Region(pos_begin,end))
        elif should_change_to_bol:
            v: View | None = active_window().active_view()
            if v is None:
                return
            end = v.full_line(v.sel()[0].end()).end()
            should_change_to_bol = False
            next_res, _ = v.find(r'\S|^$|^\s+$', v.sel()[0].end())
            v.sel().clear()
            v.sel().add(Region(next_res,next_res))

    def on_deactivated_async(self, _):
        global prev_buf_id
        global pos_begin
        global ought_to_extend
        v = active_window().active_view()
        if v is None:
            return
        if len(v.sel()) == 0:
            v.sel().add(0)
            v.show(0, False)
            return
        has_selection = v.sel()[0].empty()
        if not has_selection:
            prev_buf_id = v.id()
            pos, _ = v.sel()[0]
            pos_begin = pos
            ought_to_extend = True
        else:
            ought_to_extend = False


class NumberCommand(sublime_plugin.TextCommand):
    def op(self, value: int) -> int:
          return value

    def run(self, edit: Edit) -> None:
        buf = self.view
        selection = buf.sel()
        for region in selection:
            if region.empty() == False:
                mystr = buf.substr(region)
                if mystr.isdigit() or mystr.startswith('-') and mystr[1:].isdigit():
                    continue
                reg_list = [Region(m.start() + region.begin(), m.end() + region.begin()) for m in re.finditer(r'-?\d+', buf.substr(region))]
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
                    selection.add(Region(buf.text_point(line, start_pos), buf.text_point(line, end_pos + 1)))

        for region in selection:
            try:
                value = int(buf.substr(region))
                buf.replace(edit, region, str(self.op(value)))
            except ValueError:
                    pass


class IncrementCommand(NumberCommand):
    def op(self, value: int) -> int:
          return value + 1

class DecrementCommand(NumberCommand):
    def op(self, value: int) -> int:
          return value - 1


class InsertModeCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
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
    def run(self, edit: Edit) -> None:
        buf = self.view
        if buf.is_read_only() == True:
            sublime.status_message('Buffer is read only')
            return

        sels: Selection = buf.sel()
        for reg in reversed(sels):
            if reg.empty():
                line = buf.line(reg.begin())
                buf.erase(edit, Region(reg.begin(), line.end()))
            else:
                buf.erase(edit, reg)
        buf.settings().set(key="block_caret", value=False)
        buf.settings().set(key="command_mode", value=False)


class CommandModeCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        buf: View | None = active_window().active_view()
        active_window().run_command('hide_popup')
        # active_window().run_command('hide_panel')
        if buf is None:
            return
        buf.settings().set(key="block_caret", value=True)
        buf.settings().set(key="waiting_for_char", value=False)
        buf.settings().set(key="command_mode", value=True)


class InsertBeforeOrAfterCommand(sublime_plugin.TextCommand):
    def run(self, _, after=False, plusone=False) -> None:
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


class ReverseSelectionListener(sublime_plugin.EventListener):
    def on_query_context(self, view, key, operator, operand, match_all):
        if key != "reversed_selection":
            return None

        lhs = operand
        if match_all:
            rhs = all([r.a > r.b for r in view.sel()])
        else:
            rhs = view.sel()[0].a > view.sel()[0].b

        return True if operator == sublime.OP_EQUAL and rhs == lhs else False


def build_or_rebuild_ws_for_view(view: View, immediate: bool):
    if view is None:
        return
    global interesting_regions
    global timeout
    if (datetime.datetime.now() - timeout).total_seconds() > 2 or immediate == True:
        interesting_regions[view] = dict()
        try:
            whitespaces: List[Region] = view.find_all(r'\n[\t ]*\n[\t ]*\S')
            size = view.size() + 1
            first, last = zip(*[(-2, -1)] + [(first, last -1) for first, last in whitespaces] + [(size, size)])
            interesting_regions[view]['first'] = first
            interesting_regions[view]['last'] = last
        except ValueError:
            pass
    timeout = datetime.datetime.now()


class ModifiedViewListener(sublime_plugin.EventListener):
    def on_modified_async(self, view: View):
        if view.element() is None:
            try:
                global interesting_regions
                del interesting_regions[view]
            except KeyError:
                pass
            sublime.set_timeout(lambda: build_or_rebuild_ws_for_view(view, immediate=False), 2000)

    def on_load_async(self, view: View):
        if view not in interesting_regions and view.element() is None:
            build_or_rebuild_ws_for_view(view, immediate=True)

class NavigateByParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        region = buf.sel()[-1].begin()
        try:
            myregs: Tuple[int] = interesting_regions[buf]['last']
        except KeyError:
            build_or_rebuild_ws_for_view(buf, immediate=True)
            myregs: Tuple[int] = interesting_regions[buf]['last']
        bisect_res = bisect.bisect(myregs, region)
        sel_end = myregs[bisect_res]
        reg = Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, True)


class NavigateByParagraphBackwardCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        region = buf.sel()[0].begin()
        try:
            myregs: Tuple[int] = interesting_regions[buf]['last']
        except KeyError:
            build_or_rebuild_ws_for_view(buf, immediate=True)
            myregs: Tuple[int] = interesting_regions[buf]['last']
        bisect_res = bisect.bisect(myregs, region - 1)
        sel_end: int = myregs[bisect_res -1 ]
        reg = Region(sel_end)
        buf.sel().clear()
        buf.sel().add(reg)

        buf.show(reg, True)

class ExtendedExpandSelectionToParagraphForwardCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        regs_dict: Dict[int, int] = dict()
        for region in buf.sel():

            try:
                first: Tuple[int] = interesting_regions[buf]['first']
            except KeyError:
                build_or_rebuild_ws_for_view(buf, immediate=True)
                first: Tuple[int] = interesting_regions[buf]['first']

            if region.b > region.a:
                bisect_res = bisect.bisect(first, region.b)
                sel_begin = buf.full_line(region.a).a
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

            else:
                return

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all(Region(begin,end) for begin,end in regs_dict.items())
        buf.show(buf.sel()[-1], False)


class ExtendedExpandSelectionToParagraphBackwardCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        regs_dict: Dict[int, int] = dict()
        for region in buf.sel():

            try:
                first: Tuple[int] = interesting_regions[buf]['first']
            except KeyError:
                build_or_rebuild_ws_for_view(buf, immediate=True)
                first: Tuple[int] = interesting_regions[buf]['first']

            if region.b > region.a:
                bisect_end = bisect.bisect(first, region.b - 3)
                sel_end = first[bisect_end -1] + 2
                if region.a == sel_end:
                    sel_end = region.a
                    sel_begin = region.b
                else:
                    sel_begin = buf.full_line(region.a).a
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

            else:
                return

            regs_dict[sel_begin] = sel_end

        buf.sel().add_all(Region(begin, end) for begin,end in regs_dict.items())
        buf.show(buf.sel()[0], False)

# tuple of (char: str, forward: bool, extend: bool)
char_forward_tuple: Tuple[str, bool, bool] = ('', True, False)
matches : List[Region] = []
class FindNextCharacterBaseCommand(sublime_plugin.TextCommand):
    def find_next(self, forward: bool, char: str, pt: int) -> int:
        if forward:
            return self.view.find(char, pt + 1, LITERAL).a
        else:
            char = char[::-1]
            mybuf = self.view.substr(Region(0, pt -1))
            try:
                return pt - mybuf[::-1].index(char) -2
            except ValueError:
                return -1


    myhtml="""<body id="my-plugin-feature"><style>div.matcher{{padding: 0 2px 0 1px; margin: 0; border-radius:2px;background-color:{background};color:{color};}}</style><div class="matcher">{counter}</div></body>"""
    charlist = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']
    def execute(self, forward: bool, search_string: str, extend: bool) -> None:
        buf = self.view
        sels: Selection = buf.sel()
        regs_to_add: List[Union[Region,int]] = []
        regs_to_subtract: List[Region] = []
        offset = 1 if not forward and len(search_string) == 1 else 0
        for region in sels:
            pt = self.find_next(forward, search_string, region.b)
            if pt == -1:
                return
            if region.a == region.b:
                if extend:
                    tp = pt + len(search_string) if forward else pt -1
                    regs_to_add.append(sublime.Region(region.a, tp))
                else:
                    tp = pt if forward else pt -1
                    regs_to_subtract.append(region)
                    regs_to_add.append(tp + offset)
                # normal sel
            elif region.a < region.b:
                if forward:
                    regs_to_add.append(Region(region.b -1, pt + len(search_string)))
                else:
                    if pt < region.a:
                        regs_to_subtract.append(Region(region.b, region.a))
                        regs_to_add.append(Region(region.a))
                    else:
                        regs_to_subtract.append(Region(region.b, pt+1))
                # reverse sel
            elif region.a > region.b:
                if forward:
                    if pt > region.a:
                        regs_to_subtract.append(Region(region.a, region.b))
                        regs_to_add.append(Region(region.a))
                    else:
                        regs_to_subtract.append(Region(region.b, pt))
                else:
                    regs_to_add.append(Region(region.a, pt -1 + offset))

        for reg in regs_to_subtract:
            sels.subtract(reg)
        sels.add_all(regs_to_add)
        buf.show(buf.sel()[-1], True)

        # now we look for highlights
        offset = offset-1 if not forward else offset
        max_res: int = 1 if len(sels) > 1 else 10
        global matches
        matches = []
        for region in sels:
            pt = region.b
            for _ in range(max_res):
                new_pt = self.find_next(forward, search_string, pt)
                if new_pt == pt or new_pt == -1:
                    break
                pt = new_pt + offset
                matches.append(Region(pt, pt + len(search_string)))
                pt = new_pt
        if not matches:
            return
        # we use phantoms if we have one match, regions, if more
        if len(sels) > 1:
            for match in enumerate(matches):
                self.view.add_regions("Sneak", matches, "accent", flags=sublime.DRAW_NO_OUTLINE)
            return

        bg_color = buf.style()["accent"]
        fg_color = buf.style()["background"]

        for i,match in enumerate(matches):
            self.view.add_phantom("Sneak", region=match, content=self.myhtml.format(counter=self.charlist[i], background=bg_color, color=fg_color), layout=LAYOUT_INLINE)
        return

class StoreCharacterCommand(FindNextCharacterBaseCommand):
    def run(self, _, character: str, forward: bool, extend: bool = False) -> None:
        self.view.settings().set(key="waiting_for_char", value=True)
        global char_forward_tuple
        char_forward_tuple = (character, forward, extend)

class RepeatFindNextCharacterCommand(FindNextCharacterBaseCommand):
    def run(self, _, **kwargs: bool) -> None:
        search_string, forward, extend = char_forward_tuple
        if not search_string:
            return
        if bool(kwargs):
            forward = kwargs['forward']
        self.view.settings().set(key="has_stored_search", value=True)
        self.execute(forward, search_string, extend)

class GoToNthMatchCommand(FindNextCharacterBaseCommand):
    def run(self, _, **kwargs: int) -> None:
        if bool(kwargs):
            number: int = kwargs['number']
        else:
            return
        buf = self.view
        sels: Selection = buf.sel()
        region = sels[0]
        if len(sels) != 1:
            return
        _, _, extend = char_forward_tuple
        if region.a != region.b:
            extend = True

        global matches
        if len(matches) < number:
            return
        mymatch: Region = matches[number - 1]
        if extend:
            pt = mymatch.b if region.a < region.b else mymatch.a
            start = sels[0].a
            sels.clear()
            sels.add(Region(start, pt))
        else:
            sels.clear()
            sels.add(mymatch.a)
        buf.show(sels[0], True)
        return


class FindNextCharacterCommand(FindNextCharacterBaseCommand):
    def run(self, _, **kwargs: str) -> None:
        self.view.settings().set(key="has_stored_search", value=True)
        self.view.settings().set(key="sneak_override_find_keybinding", value=True)
        self.view.settings().set(key="waiting_for_char", value=False)
        if bool(kwargs):
            mychar = kwargs['character']
        else:
            mychar = ''
        global char_forward_tuple
        character, forward, extend = char_forward_tuple
        search_string: str = character + mychar
        char_forward_tuple = (search_string, forward, extend)
        self.execute(forward, search_string, extend)


class FindNextCharacterListener(sublime_plugin.EventListener):
    def on_window_command(self, window: sublime.Window, _, __):
        view: Union[View,None] = window.active_view()
        if view is None:
            return
        view.erase_phantoms("Sneak")
        view.erase_regions("Sneak")
        view.settings().set(key="waiting_for_char", value=False)
        view.settings().set(key="has_stored_search", value=False)

    def on_text_command(self, view: View, command_name: str, _):
        view.erase_regions("Sneak")
        view.erase_phantoms("Sneak")
        if (command_name != "find_next_character" and command_name != "repeat_find_next_character"
        and command_name != "store_character" and command_name != "revert_selection"):
            view.settings().set(key="has_stored_search", value=False)
            view.settings().set(key="waiting_for_char", value=False)


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
            reg_list += [Region(m.start() + reg_begin) for m in re.finditer(r'\S.*\n', buffer)]
        buf.sel().clear()
        buf.sel().add_all(reg_list)



class PoorMansDebuggingCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
        buf = self.view
        if buf.is_read_only():
            return
        selections = buf.sel()

        for region in reversed(selections):
            if region.empty():
                continue

            cur_line_num = buf.line(region.end())
            indent = cur_line_num.b - cur_line_num.a - len(buf.substr(cur_line_num).lstrip())
            content = "\n" + indent*" " + "print(f'{"+ buf.substr(region)+ "=}')"
            _, insert_pos = buf.line(region.end())
            sel_beg_pos = cur_line_num.b + indent + 10
            sel_beg_end = sel_beg_pos + region.end() - region.begin()
            buf.insert(edit, insert_pos, content)
            selections.subtract(region)
            new_reg = Region(sel_beg_pos, sel_beg_end)

            selections.add(new_reg)


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

        buf.show(sel[-1], True)


class SingleSelectionLastCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        reg = buf.sel()[-1]
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg, True)


class SmartFindWordCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
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

            rev_reg = Region(cur_line_in_points_beg, reg.begin())
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
                forw_reg = Region(cur_line_in_points_end, reg.begin())
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
        buf = self.view
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

class SmartPasteCutNewlinesCommand(sublime_plugin.TextCommand):
    def run(self, edit: Edit) -> None:
        buf = self.view
        sels: Selection = buf.sel()

        clipboard = get_clipboard()
        clips = clipboard.splitlines()

        if clipboard.endswith('\n'):
            pass
        else:

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
        buf = self.view
        stripped_clipboard = get_clipboard().strip()
        sels: Selection = buf.sel()
        for region in reversed(sels):
            buf.erase(edit, region)
            buf.insert(edit, region.begin(), stripped_clipboard)

class SmartPasteCommand(sublime_plugin.TextCommand):
    def find_indent(self, cur_line_num: Region, cur_line: str) -> int:
        buf = self.view
        # if we have a new, empty file:
        if buf.size() == 0:
            return 0
        clipboard = get_clipboard()
        if len(cur_line) == 0 and clipboard.startswith(' '):
            return 0
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
        buf = self.view
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
            word_boundaries = [Region(m.start() + begin, m.end() + begin) for m in re.finditer(WORDCHARS, contents)]
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

        reg = Region(min_point, max_point)
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
    def run(self, _) -> None:
        selections = self.view.sel()
        if len(selections) > 1:
            selections.subtract(selections[0])
            self.view.show(selections[0], True)

