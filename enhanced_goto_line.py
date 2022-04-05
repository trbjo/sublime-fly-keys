from sublime import View, Region, Selection
import sublime_plugin
from typing import Union

should_extend: bool = False
should_change_to_bol: bool = False
first_view: Union[View,None] = None
old_pos: int = -1

class GotoInputListener(sublime_plugin.ViewEventListener):
    def on_query_context(self, key: str, _, __: bool, ___):
        view: View = self.view
        global should_extend
        global should_change_to_bol
        global first_view

        # this line listens for the keys "sent" in the keymap file
        if key =="can_expand":
            first_view = view
            if view.sel()[0].empty():
                should_extend = False
                should_change_to_bol = True
            else:
                global old_pos
                old_pos = view.sel()[0].end()
                should_extend = True
                should_change_to_bol = False
            return True
        else:
            return None


    def on_activated(self):
        view: View = self.view
        if view is None:
            return
        if view.element() is not None:
            return
        global first_view
        if first_view is None:
            return
        if view.id() != first_view.id():
            return
        sels: Selection = view.sel()
        if sels[0].end() == old_pos:
            return
        global should_extend
        global should_change_to_bol
        if should_extend:
            should_extend = False
            new_pos = view.sel()[0].a
            sels.clear()
            if new_pos > old_pos:
                view.sel().add(Region(view.line(old_pos).begin(),view.full_line(new_pos).end()))
            else:
                view.sel().add(Region(view.line(new_pos).begin(),view.full_line(old_pos).end()))
        elif should_change_to_bol:
            should_change_to_bol = False
            next_res, _ = view.find(r'\S|^$|^\s+$', view.sel()[0].a)
            view.sel().clear()
            view.sel().add(next_res)

        return
