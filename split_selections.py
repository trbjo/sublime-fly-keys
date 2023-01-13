from sublime_api import view_selection_add_region as add_region
from sublime_api import view_selection_subtract_region as subtract_region
from sublime_plugin import TextCommand, TextInputHandler

pattern_cache = {}


def findall(p, length, s):
    """Yields all the positions of
    the pattern p in the string s."""
    i = s.find(p)
    while i != -1:
        yield i
        i = s.find(p, i + length)


class SelectOnlyDelimiterInSelection(TextCommand):
    def input(self, args):
        if "characters" not in args:
            include = args.get("include", False)
            return PatternInputHandler(pattern_cache.get(include, ""))

    def input_description(self) -> str:
        return "Pattern"

    def is_enabled(self) -> bool:
        if self.view is None:
            return False
        return any(r.a != r.b for r in self.view.sel())

    def run(self, _, pattern, include=False):
        if not pattern:
            return

        v = self.view
        vid = v.id()
        pattern_cache[include] = pattern
        length = len(pattern)
        for reg in v.sel():
            if reg.empty():
                continue
            if include:
                idx = list(findall(pattern, length, v.substr(reg)))
                if not idx:
                    continue
                subtract_region(vid, reg.a, reg.b)
                [add_region(vid, reg.a + i, reg.a + i + length, 0.0) for i in idx]
            else:
                idx = findall(pattern, length, v.substr(reg))
                [subtract_region(vid, reg.a + i, reg.a + i + length) for i in idx]


class PatternInputHandler(TextInputHandler):
    def __init__(self, initial_text):
        self._initial_text = initial_text

    def initial_text(self):
        return self._initial_text

    def validate(self, name):
        return len(name) > 0
