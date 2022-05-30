from sublime import Edit, View, Region, Selection, active_window
import sublime
import sublime_plugin

from typing import List, Union
import re
import string

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

        buf.show(sel[-1].end(), True)


class SingleSelectionLastCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        buf = self.view
        reg = buf.sel()[-1]
        buf.sel().clear()
        buf.sel().add(reg)
        buf.show(reg.end(), True)


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
            buf.show(selection[0].end(), True)
            return

        selected_word = buf.substr(selection[-1])
        min_point = selection[0].begin()
        max_point = selection[-1].end()

        res = buf.find(selected_word, start_pt=max_point)
        if res.begin() != -1:
            selection.subtract(selection[-1])
            buf.show(selection[-1].end(), True)
            return

        reg = Region(min_point, max_point)
        all_regs = [min_point +  m.end() for m in re.finditer(selected_word, buf.substr(reg))]

        i = 0
        for region in selection:
            if region.end() < all_regs[i]:
                # Consider a continue statement here instead.
                # Depends on what strategy works best
                selection.subtract(region)
                buf.show(selection[i-1].end(), True)
                return
            elif region.end() > all_regs[i]:
                selection.subtract(selection[i-1])
                buf.show(selection[i-2].end(), True)
                return
            i += 1

        selection.subtract(selection[-1])
        buf.show(selection[-1].end(), True)

class SubtractFirstSelectionCommand(sublime_plugin.TextCommand):
    def run(self, _) -> None:
        selections = self.view.sel()
        if len(selections) > 1:
            selections.subtract(selections[0])
            self.view.show(selections[0].end(), True)
