#!/usr/bin/env python3
"""Send one fdmkit call to the running FreeCAD over XML-RPC.

  fc.py "pad('outline', 'height')"   one transaction, one line back
  fc.py --reload                     re-import fdmkit after editing it
  fc.py --selftest                   build and check a throwaway part
"""
import os
import sys
import xmlrpc.client

MOD = os.path.expanduser('~/Library/Application Support/FreeCAD/v26-3/Mod/fdmkit')
URL = os.environ.get('FREECAD_RPC', 'http://127.0.0.1:9875')


def call(arg):
    arg = {'selftest()': '--selftest', 'reload()': '--reload'}.get(arg.strip(), arg)
    head = (f'import sys, importlib\nsys.path.count({MOD!r}) or sys.path.insert(0, {MOD!r})\n'
            'import fdmkit\n')
    if arg == '--reload':
        body = "fdmkit = importlib.reload(fdmkit); fdmkit._boot(); print('reloaded', fdmkit.__version__)"
    elif arg == '--selftest':
        body = 'print(fdmkit.selftest())'
    else:
        body = f'print(fdmkit.run({arg!r}))'
    try:
        r = xmlrpc.client.ServerProxy(URL, allow_none=True).execute_code(head + body, 120)
    except OSError as e:
        return f'ERR FreeCAD RPC unreachable at {URL}: {e}'
    msg = r.get('message') or r.get('error') or str(r)
    return msg.split('Output: ', 1)[-1].strip() if r.get('success') else 'RPC ERR ' + msg


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(call(sys.argv[1]))
