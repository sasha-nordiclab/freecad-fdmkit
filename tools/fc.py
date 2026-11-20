#!/usr/bin/env python3
"""Send one fdmkit call to the running FreeCAD over XML-RPC.

  fc.py "pad('outline', 'height')"   one transaction, one line back
  fc.py --reload                     re-import fdmkit after editing it
  fc.py --selftest                   build and check a throwaway part
"""
import os
import socket
import sys
import xmlrpc.client

MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repo, whatever FreeCAD version links it
URL = os.environ.get('FREECAD_RPC', 'http://127.0.0.1:9875')
# Run budget of one call in seconds (the addon caps it at 1800). FreeCAD cannot cancel a started
# call: past the budget only the answer is lost. Keep the client's tool timeout above it.
TIMEOUT = float(os.environ.get('FDMKIT_RPC_TIMEOUT', '120'))
PREFLIGHT = 15      # a GUI that does not start an empty task within this is blocked or busy


class _Transport(xmlrpc.client.Transport):
    def __init__(self, timeout):
        super().__init__()
        self._timeout = timeout

    def make_connection(self, host):
        c = super().make_connection(host)
        c.timeout = self._timeout
        return c


def _proxy(timeout):
    return xmlrpc.client.ServerProxy(URL, allow_none=True, transport=_Transport(timeout))


def call(arg):
    arg = {'selftest()': '--selftest', 'reload()': '--reload'}.get(arg.strip(), arg)
    head = (f'import sys, importlib\nsys.path.count({MOD!r}) or sys.path.insert(0, {MOD!r})\n'
            'import fdmkit\n')
    if arg == '--reload':
        body = ("import fdmkit.machining, fdmkit.drawing, fdmkit.tests\n"   # submodules bind the core helpers:
                "for m in ('fdmkit', 'fdmkit.machining', 'fdmkit.drawing', 'fdmkit.tests', 'fdmkit'):\n"  # core, subs, core
                "    importlib.reload(sys.modules[m])\n"
                "fdmkit = sys.modules['fdmkit']; fdmkit._boot(); print('reloaded', fdmkit.__version__)")
    elif arg == '--selftest':
        body = 'print(fdmkit.selftest())'
    else:
        body = f'print(fdmkit.run({arg!r}))'
    try:
        r0 = _proxy(PREFLIGHT + 15).execute_code('pass', PREFLIGHT)
        e0 = '' if r0.get('success') else str(r0.get('error') or r0.get('message') or '')
        if 'to start' in e0 or 'unavailable' in e0 or r0.get('code') == 'GUI_DISPATCH_STUCK':
            return 'RPC ERR ' + e0      # blocked or busy GUI: answered in 15 s, nothing was started
        r = _proxy(TIMEOUT + 60).execute_code(head + body, TIMEOUT)
    except socket.timeout:
        return ('RPC ERR no answer from FreeCAD (GUI thread busy or frozen); the call may still be '
                'running, wait before the next call')
    except OSError as e:
        return f'ERR FreeCAD RPC unreachable at {URL}: {e}'
    msg = r.get('message') or r.get('error') or str(r)
    return msg.split('Output: ', 1)[-1].strip() if r.get('success') else 'RPC ERR ' + msg


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(call(sys.argv[1]))
