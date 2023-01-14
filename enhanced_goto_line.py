from enum import IntEnum
from typing import Union

import sublime_plugin
from sublime import Selection, View
from sublime_api import view_selection_add_region as add_region


class Action(IntEnum):
    DO_NOTHING = 0
    CHANGE_TO_BOL = 1
    EXTEND = 2


action: Action = Action.DO_NOTHING
first_view: Union[View, None] = None
old_pos: int = -1


class GotoInputListener(sublime_plugin.ViewEventListener):
    def on_query_context(self, key: str, _, __: bool, ___):
        if key != "can_expand":
            return None
        view: View = self.view
        global first_view
        global action
        first_view = view
        global old_pos
        if view.sel()[0].empty():
            old_pos = view.sel()[0].b
            action = Action.CHANGE_TO_BOL
        else:
            old_pos = view.sel()[0].a
            action = Action.EXTEND
        return True

    def on_activated(self):
        global action
        if action == Action.DO_NOTHING:
            return
        view: View = self.view
        if view.element() is not None:
            return
        global first_view
        if first_view is None:
            return
        sels: Selection = view.sel()
        if sels[0].end() == old_pos:
            action = Action.DO_NOTHING
            return
        if action == Action.EXTEND and view.id() == first_view.id():
            new_pos = view.sel()[0].b
            sels.clear()
            if new_pos > old_pos:
                start = view.line(old_pos).begin()
                end = view.full_line(new_pos).end()
            else:
                start = view.full_line(old_pos).end()
                end = view.line(new_pos).begin()
            add_region(view.id(), start, end, 0.0)
        else:
            next_res, _ = view.find(r"\S|^$|^\s+$", view.sel()[0].a)
            view.sel().clear()
            view.sel().add(next_res)

        action = Action.DO_NOTHING
