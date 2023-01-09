import re

import sublime_plugin
from sublime import Edit, Region

true_false_dict = {"false": "true", "False": "True", "true": "false", "True": "False"}


class ToggleTrueFalseCommand(sublime_plugin.TextCommand):
    """First we try around the cursor (-6, +6), else we try the whole line"""

    def run(self, edit: Edit) -> None:
        buf = self.view
        for region in reversed(buf.sel()):
            if region.empty():
                linestr = self.view.substr(Region(region.a - 6, region.a + 6))
                g = [
                    (m.start(), m.end(), m.groups()[0])
                    for m in re.finditer(r"((F|f)alse|(T|t)rue)", linestr)
                ]
                # if more than one match was found, we take the one that is nearest
                # the caret
                if len(g) > 2:
                    return
                elif len(g) == 2:
                    if abs(6 - g[1][0]) > abs(6 - g[0][1]):
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
                    g = re.search(r"((F|f)alse|(T|t)rue)", linestr)
                    if g is None:
                        return
                    begin = g.span()[0] + lr.a
                    end = g.span()[1] + lr.a
                    mybool = g.group(0)
                else:
                    return
                myregion = Region(begin, end)
                buf.sel().subtract(region)
                myopposite = true_false_dict[mybool]
                buf.replace(edit, myregion, myopposite)
                buf.sel().add(begin)
            else:
                pass
