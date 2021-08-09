import sublime
import sublime_plugin

prev_buf_id = 0
pos_begin = 0
allow_extend = False
ought_to_extend = False
should_change_to_bol = False

class SampleListener(sublime_plugin.EventListener):
    def on_query_context(self, view, key, operator, operand, match_all):
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

    def on_activated(self, view):
        global prev_buf_id
        global pos_begin
        global allow_extend
        global should_change_to_bol
        if allow_extend == True:
            allow_extend = False
            v = sublime.active_window().active_view()
            if prev_buf_id == v.id():
                end = v.full_line(v.sel()[0].end()).end()
                v.sel().add(sublime.Region(pos_begin,end))
        elif should_change_to_bol:
            v = sublime.active_window().active_view()
            end = v.full_line(v.sel()[0].end()).end()
            should_change_to_bol = False
            next_res, next_res_end = v.find(r'\S|^$|^\s+$', v.sel()[0].end())
            v.sel().clear()
            v.sel().add(sublime.Region(next_res,next_res))

    def on_deactivated_async(self, view):
        global prev_buf_id
        global pos_begin
        global ought_to_extend
        v = sublime.active_window().active_view()
        has_selection = v.sel()[0].empty()
        if not has_selection:
            prev_buf_id = v.id()
            pos, _ = v.sel()[0]
            pos_begin = pos
            ought_to_extend = True
        else:
            ought_to_extend = False
