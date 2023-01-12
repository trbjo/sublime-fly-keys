from sublime_api import view_selection_add_region as add_region
from sublime_api import view_selection_subtract_region as subtract_region
from sublime_plugin import TextCommand, TextInputHandler

LAST_PATTERN_INCLUDE: str = ""
LAST_PATTERN_EXCLUDE: str = ""


def findall(p, length, s):
    """Yields all the positions of
    the pattern p in the string s."""
    i = s.find(p)
    while i != -1:
        yield i
        i = s.find(p, i + length)


class SelectOnlyDelimiterInSelection(TextCommand):
    def input(self, args):
        return IncludePattern()

    def input_description(self) -> str:
        return "Pattern"

    def is_enabled(self) -> bool:
        return True
        # if self.view is None:
        # return False
        # return any(r.a != r.b for r in self.view.sel())

    def run(self, _, include_pattern):
        v = self.view
        vid = v.id()
        sels = v.sel()
        global LAST_PATTERN_INCLUDE
        LAST_PATTERN_INCLUDE = include_pattern

        if not include_pattern:
            return

        length = len(include_pattern)
        for reg in sels:
            if reg.empty():
                continue
            idx = list(findall(include_pattern, length, v.substr(reg)))
            if not idx:
                continue
            subtract_region(vid, reg.a, reg.b)
            [add_region(vid, reg.a + i, reg.a + i + length, 0.0) for i in idx]


class RemoveDelimiterFromSelection(TextCommand):
    def input(self, args):
        return ExcludePattern()

    def input_description(self) -> str:
        return "Pattern"

    def is_enabled(self) -> bool:
        return True
        # if self.view is None:
        # return False
        # return any(r.a != r.b for r in self.view.sel())

    def run(self, _, exclude_pattern):
        v = self.view
        vid = v.id()
        sels = v.sel()
        global LAST_PATTERN_EXCLUDE
        LAST_PATTERN_EXCLUDE = exclude_pattern

        if not exclude_pattern:
            return

        length = len(exclude_pattern)
        for reg in sels:
            if reg.empty():
                continue
            idx = findall(exclude_pattern, length, v.substr(reg))
            [subtract_region(vid, reg.a + i, reg.a + i + length) for i in idx]


class IncludePattern(TextInputHandler):
    def initial_text(self):
        return LAST_PATTERN_INCLUDE

    def validate(self, name):
        return len(name) > 0


class ExcludePattern(TextInputHandler):
    def initial_text(self):
        return LAST_PATTERN_EXCLUDE

    def validate(self, value):
        return len(value) > 0
