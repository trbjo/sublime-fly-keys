from sublime import Edit, Region
import sublime_plugin
import sublime_api

from typing import List, Tuple

matchers: str = """([{)]}"'"""

PositionAndType=Tuple[int,int]

class ExpandSelectionToNextCommand(sublime_plugin.TextCommand):

    def get_left_point(self, l_pointer: int, single_quotes: bool, double_quotes: bool) -> PositionAndType:
        chars: List[int] = []
        local_double_quotes = False
        local_single_quotes = False

        while l_pointer > 0:
            l_pointer-=1
            char: str = self.buf_str[l_pointer]
            index: int = matchers.find(char)

            if local_double_quotes and index != 6:
                continue
            if local_single_quotes and index != 7:
                continue

            if index == -1:
                continue
            elif index == 6:
                if double_quotes and not local_double_quotes:
                    if 'string.begin' in self.view.scope_name(l_pointer):
                        return l_pointer, index
                if not single_quotes and not local_single_quotes:
                    local_double_quotes = not local_double_quotes

            elif index == 7:
                if single_quotes and not local_single_quotes:
                    if 'string.begin' in self.view.scope_name(l_pointer):
                        return l_pointer, index
                if not double_quotes and not local_double_quotes:
                    local_single_quotes = not local_single_quotes

            elif index >= 3:
                chars.append(index)
            elif index <= 2:
                if chars and chars[-1] == index + 3:
                    chars.pop()
                else:
                    return l_pointer, index

        return -2, -2


    def get_right_point(self, r_pointer: int, single_quotes: bool, double_quotes: bool) -> PositionAndType:
        chars: List[int] = []
        local_double_quotes = False
        local_single_quotes = False

        while r_pointer < self.size-1:
            r_pointer+=1
            char: str = self.buf_str[r_pointer]
            index: int = matchers.find(char)

            if local_double_quotes and index != 6:
                continue

            elif local_single_quotes and index != 7:
                continue

            if index == -1:
                continue

            elif index == 6:
                if double_quotes and not local_double_quotes:
                    if 'string.end' in self.view.scope_name(r_pointer):
                        return r_pointer, index
                if not single_quotes and not local_single_quotes:
                    local_double_quotes = not local_double_quotes

            elif index == 7:
                if single_quotes and not local_single_quotes:
                    if 'string.end' in self.view.scope_name(r_pointer):
                        return r_pointer, index
                if not double_quotes and not local_double_quotes:
                    local_single_quotes = not local_single_quotes

            elif index <= 2:
                chars.append(index)

            elif index >= 3:
                if chars and chars[-1] == index - 3:
                    chars.pop()
                else:
                    return r_pointer, index - 3 # we emulate the offset -3

        return -3, -3


    def looper(self, region: Region) -> None:

        did_right: bool = self.size / 2 < region.b

        left_types: List[int] = []
        right_types: List[int] = []
        left_indices: List[int] = []
        right_indices: List[int] = []

        l_index: int = region.b
        r_index: int = region.b -1

        single_quotes = False
        double_quotes = False

        right_type = 100
        left_type = 101

        reg = self.view.expand_to_scope(region.b, "(meta.string, string) - punctuation.definition.string")
        if reg is not None:
            r_scope = self.view.scope_name(reg.b)
            if 'string.' in r_scope:
                if 'string.quoted.double' in r_scope:
                    double_quotes = True
                elif 'string.quoted.single' in r_scope:
                    single_quotes = True

        while True:

            if right_type != -3 and (did_right or left_type == -2):
                r_index, right_type = self.get_right_point(r_index, single_quotes, double_quotes)
                did_right = False

                if right_type == -3:
                    if not right_types:
                        return
                    else:
                        continue

                for i in range(len(left_types)):
                    if left_types[i] == right_type:
                        if region.a == region.b:
                            l_index = left_indices[i]
                            break
                        else:
                            if self.around:
                                l_index = left_indices[i]
                                break
                            else:
                                if left_indices[i] + 1 != region.a:
                                    l_index = left_indices[i]
                                    break
                else:
                    right_indices.append(r_index)
                    right_types.append(right_type)
                    continue

            elif left_type != -2 and (not did_right or right_type == -3):
                l_index, left_type = self.get_left_point(l_index, single_quotes, double_quotes)
                did_right = True
                if left_type == -2:
                    if not left_types:
                        return
                    else:
                        continue

                for i in range(len(right_types)):
                    if right_types[i] == left_type:
                        if region.a == region.b:
                            r_index = right_indices[i]
                            break
                        else:
                            if self.around:
                                r_index = right_indices[i]
                                break
                            else:
                                if right_indices[i] != region.b:
                                    r_index = right_indices[i]
                                    break

                else:
                    left_indices.append(l_index)
                    left_types.append(left_type)
                    continue

            else:
                return

            if r_index - 1 == l_index: # no extent, e.g. ()
                left_types = []
                right_types = []
                left_indices = []
                right_indices = []
                continue

            if (self.buf_str[l_index+1] == self.buf_str[l_index] and # deal with multiple, subsequent parentheses
               self.buf_str[r_index-1] == self.buf_str[r_index]):
                continue

            break

        self.view.sel().subtract(region)

        if self.around:
            r_index+=1
            l_index-=1
            while (self.buf_str[l_index+1] == self.buf_str[l_index] and
               self.buf_str[r_index-1] == self.buf_str[r_index]):
                l_index-=1
                r_index+=1

        if self.from_here:
            l_index = region.a - 1
        elif self.to_here:
            r_index = region.a

        if region.b < region.a or self.to_here:
            sublime_api.view_selection_add_region(self.buf_id, r_index, l_index + 1, 0.0)
        else:
            sublime_api.view_selection_add_region(self.buf_id, l_index + 1, r_index, 0.0)


    def run(self, edit: Edit, around=False, from_here=False, to_here=False):
        self.size: int = self.view.size()
        self.buf_id = self.view.id()
        self.around = around
        self.from_here = from_here
        self.to_here = to_here
        self.buf_str: str = sublime_api.view_cached_substr(self.buf_id, 0, self.size)

        for region in self.view.sel():
            if region.end() != self.size:
                self.looper(region)

        self.view.show(self.view.sel()[-1].b, True)
