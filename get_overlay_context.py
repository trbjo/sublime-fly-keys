class SampleListener(sublime_plugin.EventListener):
    def on_query_context(self, view, key, operator, operand, match_all):
        if key in ("goto_anything:input", "command_palette:input"):
            lhs = view.element() == key
            rhs = bool(operand)

            return lhs == rhs if operand != sublime.OP_EQUAL else lhs != rhs

        return None
