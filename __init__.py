import os
import re
import subprocess
from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import HtmlFormatter
from pygments.styles.native import NativeStyle

from binaryninja import log
from binaryninja.plugin import PluginCommand
from binaryninja.interaction import show_message_box, show_html_report
from binaryninja.enums import MessageBoxButtonSet, MessageBoxIcon

BG_COLOR = '#272811'


class ExceptionWithMessageBox(Exception):
    def __init__(self, msg, info, icon=MessageBoxIcon.InformationIcon):
        super(ExceptionWithMessageBox, self).__init__(msg)
        show_message_box(msg, info, MessageBoxButtonSet.OKButtonSet, icon)

class RetDec(object):
    def __init__(self, view, function):
        self._view = view
        if view.arch.name == 'armv7':
            self.arch = "arm"
        else:
            msg = 'unsupported architecture: {}'.format(arch)
            info = 'Add arch to plugin'
            raise ExceptionWithMessageBox(msg, info)
        self.endianness = 'big' if view.endianness else 'little'
        self.function = function
        path = str(view)
        path = path[path.find("'") + 1:]
        path = path[:path.find("'")]
        print path
        i = 0
        for c in path:
            i+=1
            if c == '/':
                i-=1
        path = path[:i]
        self.path = '{}temp_binary.out'.format(path)
        self._cmdline = ['retdec-decompiler.py']
        self._cmdline.append('--cleanup')

    def decompile(self, inputfile):
        self._cmdline.append(inputfile)

        log.log_info(" ".join(self._cmdline))

        subprocess.call(self._cmdline) 

        with open('{}.c'.format(inputfile), 'r') as f:
            code = f.read()

        os.unlink('{}'.format(inputfile))

        return code

    def decompile_bin(self):
        self._cmdline.extend(['--mode', 'bin'])
        self._cmdline.extend(['--arch', self.arch])
        self._cmdline.extend(['--endian', self.endianness])
        self._cmdline.extend(['--select-ranges', '{:#x}-{:#x}'.format(self.function.start,
                                                                      self.function.start+1)])

        with open(self.path, 'w+b') as file:
            file.write(self._view.file.raw.read(0, len(self._view.file.raw)))
            file.close()
            code = self.decompile(file.name)

        code = self.merge_symbols(code)
        self.render_output(code)


    def merge_symbols(self, code):
        pcode = []
        pattern = re.compile(r'(unknown_|0x)([a-f0-9]+)')

        for line in code.splitlines():
            if line.strip().startswith('//') or line.strip().startswith('#'):
                pcode.append(line)
                continue

            if 'entry_point' in line:
                line = self.replace_symbols(line, self.function.start, 'entry_point')

            for match in pattern.findall(line):
                address = int(match[1], 16)
                line = self.replace_symbols(line, address, ''.join(match))

            pcode.append(line)

        return '\n'.join(pcode)

    def replace_symbols(self, line, address, string):
        symbol = self._view.get_symbol_at(address)
        if symbol is not None:
            return line.replace(string, symbol.name)

        function = self._view.get_function_at(address)
        if function is not None:
            return line.replace(string, function.name)

        return line

    def render_output(self, code):
        lexer = CLexer()
        style = NativeStyle()
        style.background_color = BG_COLOR
        formatter = HtmlFormatter(full=True, style='native', noclasses=True)
        colored_code = highlight(code, lexer, formatter)
        show_html_report('{}.c'.format(self.function.name), colored_code)

def decompile_bin(view, function):
    try:
        retdec = RetDec(view, function)
        retdec.decompile_bin()
    except Exception as e:
        log.log_error('failed to decompile function: {}'.format(e))

PluginCommand.register_for_function('Decompile Function with RetDec',
                                    'Decompile-Slow', decompile_bin)
