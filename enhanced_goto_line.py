from sublime import View, Region, Selection
import sublime_plugin
from typing import Union
from enum import IntEnum

class Action(IntEnum):
    DO_NOTHING = 0
    CHANGE_TO_BOL = 1
    EXTEND = 2

action: Action = Action.DO_NOTHING
first_view: Union[View,None] = None
old_pos: int = -1

class GotoInputListener(sublime_plugin.ViewEventListener):
    def on_query_context(self, key: str, _, __: bool, ___):
        if key =="can_expand":
            view: View = self.view
            global first_view
            global action
            first_view = view
            if view.sel()[0].empty():
                action = Action.CHANGE_TO_BOL
            else:
                global old_pos
                old_pos = view.sel()[0].end()
                action = Action.EXTEND
            return True
        else:
            return None


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
        if view.id() != first_view.id():
            action = Action.DO_NOTHING
            return
        sels: Selection = view.sel()
        if sels[0].end() == old_pos:
            action = Action.DO_NOTHING
            return
        if action == Action.EXTEND:
            new_pos = view.sel()[0].a
            sels.clear()
            if new_pos > old_pos:
                view.sel().add(Region(view.line(old_pos).begin(),view.full_line(new_pos).end()))
            else:
                view.sel().add(Region(view.line(new_pos).begin(),view.full_line(old_pos).end()))
        elif action == Action.CHANGE_TO_BOL:
            next_res, _ = view.find(r'\S|^$|^\s+$', view.sel()[0].a)
            view.sel().clear()
            view.sel().add(next_res)

        action = Action.DO_NOTHING
        return
