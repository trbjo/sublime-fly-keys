import sublime, sublime_plugin, string
class ExpandSelectionToSentenceCommand(sublime_plugin.TextCommand):
    # TODO: Add foward command to go forward and backward selction of sentences
    def run(self, edit, forward = False):
        view = self.view
        # whitespace = '\t\n\x0b\x0c\r ' # Equivalent to string.whitespace
        oldSelRegions = list(view.sel())
        view.sel().clear()
        for thisregion in oldSelRegions:
            thisRegionBegin = thisregion.begin() - 1
            while ((view.substr(thisRegionBegin) not in ".") and (thisRegionBegin >= 0)):
                thisRegionBegin -= 1
            thisRegionBegin += 1
        while((view.substr(thisRegionBegin) in string.whitespace) and (thisRegionBegin < view.size())):
            thisRegionBegin += 1

        thisRegionEnd = thisregion.end()
        while((view.substr(thisRegionEnd) not in ".") and (thisRegionEnd < view.size())):
            thisRegionEnd += 1

        if(thisRegionBegin != thisRegionEnd):
            view.sel().add(sublime.Region(thisRegionBegin, thisRegionEnd+1))
        else:
            view.sel().add(sublime.Region(thisRegionBegin, thisRegionBegin))
