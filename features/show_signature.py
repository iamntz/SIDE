import sublime
import sublime_plugin
import os
import re
import linecache

from html import escape
from SIDE.features.lib.helpers import definition, get_word, get_function_name, get_line, open_view


MAX_LEN = None  # used to limit up / down when keyboard is used to show signiture
PREVIOUS_INDEX = None # previous index in popup


class SideShowSignature(sublime_plugin.TextCommand):
    def run(self, edit, locations=None, point=None, index=None):
        """ index - when specefied show the current location. """
        global MAX_LEN
        global PREVIOUS_INDEX
        # restart the counter of signiture help to 0
        PREVIOUS_INDEX = 0

        if point is None:
            point = self.view.sel()[0].begin()

        word = None
        if locations is None:
            word = get_function_name(self.view, point)
            locations = definition(word, self.view)

        if len(locations) == 0:
            return

        MAX_LEN = len(locations)

        # display the reference count
        if len(locations) > 1 and index is None:
            self.view.run_command('side_show_signature', {
                'locations': locations, 
                'point': point,
                'index': 0
            })
            return

        location = None
        if index:
            location = locations[index]
        else:
            location = locations[0]

        file_path, relative_file_path, row_col = location
        row, _col = row_col  # signiture row

        get_docs_params = {
            'file_path': file_path, 
            'row_above_signiture': row - 1,
            'row_below_signiture': None
        }

        function_line = get_line(self.view, file_path, row).strip()

        signiture, row = self.get_signiture(function_line, 
                                            file_path, 
                                            row)
        # prettify signiture
        signiture = signiture.strip('{').strip(':')

        get_docs_params['row_below_signiture'] = row + 1 
        docs = self._get_docs(get_docs_params)  

        if docs:
            docs = """
            <div style="padding: 7px; 
                        border-top: 1px solid color(var(--foreground) alpha(0.1))">
                {}
            </div>""".format(docs)

        # prettyfy file origin
        if len(relative_file_path) > 70:
            relative_file_path = '...' + relative_file_path[-50:]
        
        if len(locations) == 1:
            range_count = ''
        else: 
            current_index = 1 if index is None else index + 1
            range_count = "[{}-{}]".format(current_index, len(locations))
        origin = """
        <div style="padding: 7px; 
                    border-top: 1px solid color(var(--foreground) alpha(0.1));
                    color: color(var(--foreground) alpha(0.7))">
            {} {}
        </div>""".format(range_count, relative_file_path)

        content = """
        <body id="side-hover" style="margin:0">
            <div style="color: var(--orangish); 
                        padding: 7px;">
                {}
            </div>
            {} 
            {}
        </body>""".format(escape(signiture, False), origin, docs)
        if index is not None:
            self.view.update_popup(content)

        self._show_popup(content, point)
        # end of command execution
        # perfect place to clear the linecache
        linecache.clearcache()

    def _show_popup(self, content, point):
        self.view.show_popup(content, sublime.HIDE_ON_MOUSE_MOVE_AWAY, location=point, max_width=700)

    def get_signiture(self, signiture, file_path, row):
        while '{' not in signiture and ')' not in signiture :
            row += 1
            signiture += ' ' + get_line(self.view, file_path, row).strip()
        return signiture, row

    def _get_docs(self, find_comment_params):
        file_path = find_comment_params['file_path']

        # extract docs above function
        row = find_comment_params['row_above_signiture']
        docs = get_line(self.view, file_path, row).strip()
        # go in reverse
        if '*/' in docs:
            while '/*' not in docs:
                row -= 1
                docs = get_line(self.view, file_path, row).strip() + '<br>' + docs
            return docs

        # extract docs below function
        row = find_comment_params['row_below_signiture']
        docs = get_line(self.view, file_path, row).strip()
        if re.match('(\'\'\'|""")', docs):
            while not re.match('(\'\'\'|""").*?(\'\'\'|""")', docs,  re.MULTILINE):
                row += 1
                docs += '<br>' + get_line(self.view, file_path, row).strip()
            return docs
        return ''


class SideSignatureListener(sublime_plugin.ViewEventListener):
    def on_query_context(self, key, _operator, operand, _match_all):
        global MAX_LEN
        global PREVIOUS_INDEX

        if key != "side.signature_help":
            PREVIOUS_INDEX = 0
            return False  # Let someone else handle this keybinding.

        if self.view.is_popup_visible():
            # We use the "operand" for the number -1 or +1. See the keybindings.
            if PREVIOUS_INDEX is None:
                PREVIOUS_INDEX = 0

            # if enter is pressed
            if operand == 0:
                point = self.view.sel()[0].begin()
                word = get_function_name(self.view, point)
                locations = definition(word, self.view)
                location = locations[PREVIOUS_INDEX]

                # sublime crasches if window.focus_view is called
                # seting a timeout, fixes is
                # I don't know why this is the case
                def fix_window_focus_view_crach():
                    open_view(location, self.view)
                    self.view.hide_popup()
                sublime.set_timeout(fix_window_focus_view_crach, 0)
                return True

            # else up or down is pressed
            new_index = PREVIOUS_INDEX + operand

            # # clamp signature index
            new_index = max(0, min(new_index, MAX_LEN - 1))

            # # only update when changed
            if new_index != PREVIOUS_INDEX or (PREVIOUS_INDEX == 0 and operand == 1 and MAX_LEN != 1) :
                self.view.run_command('side_show_signature', {
                    'index': new_index
                })
                PREVIOUS_INDEX = new_index

            return True  # We handled this keybinding.
        else: 
            return False