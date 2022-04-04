from sublime import Edit, View, Region, Selection, set_clipboard, active_window
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
        window: Union[sublime.Window,None] = view.window()
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
        buf: Union[View,None] = active_window().active_view()
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

