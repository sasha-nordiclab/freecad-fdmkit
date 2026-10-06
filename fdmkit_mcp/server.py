#!/usr/bin/env python3
"""fdmkit MCP server: one tool, run(expr), over stdio. No dependencies.

Shared by Claude Code and Codex; forwards to the running FreeCAD via tools/fc.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import fc  # noqa: E402

DESCRIPTION = """Run fdmkit calls in the open FreeCAD. 'a(); b(); c()' = one transaction, one result
per call; any ERR rolls the whole batch back. Batch related steps to save round trips.
Lengths/angles: number or expression; bare params names allowed ('wall*2').
P(name=val,...) set | P() list | new(name) | plane(name, base='XY'|datum, offset)
sk(name, on='XY'|datum) | rect(sk,w,h,x=0,y=0,at='c'|'bl') | circ(sk,d,x,y)
slot(sk,length,width,x,y,angle) | poly(sk,[(x,y),...]) | fil(sk,(x,y),r)
pad(sk,len,side='one'|'two'|'sym',reverse) | pocket(sk,depth='through') | revolve(sk,angle=360,axis='V_Axis'|'Z')
dim(sk,'r1_w',val) | chk() | why(name) | tree() | undo() | selftest() | reload()
Sketch shapes are fully constrained (DoF 0); names: r1_w, c1_d, s1_l..."""

TOOL = {'name': 'run', 'description': DESCRIPTION,
        'inputSchema': {'type': 'object', 'properties': {'expr': {'type': 'string'}},
                        'required': ['expr']}}


def handle(msg):
    method, mid = msg.get('method'), msg.get('id')
    if mid is None:
        return None  # notification
    if method == 'initialize':
        result = {'protocolVersion': msg.get('params', {}).get('protocolVersion', '2025-06-18'),
                  'capabilities': {'tools': {}},
                  'serverInfo': {'name': 'fdmkit', 'version': '0.1.0'}}
    elif method == 'tools/list':
        result = {'tools': [TOOL]}
    elif method == 'tools/call':
        p = msg.get('params', {})
        if p.get('name') != 'run':
            return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': 'unknown tool'}}
        out = fc.call(p.get('arguments', {}).get('expr', ''))
        result = {'content': [{'type': 'text', 'text': out}],
                  'isError': out.startswith(('ERR', 'RPC ERR'))}
    elif method == 'ping':
        result = {}
    else:
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'no method {method}'}}
    return {'jsonrpc': '2.0', 'id': mid, 'result': result}


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            reply = handle(json.loads(line))
        except Exception as e:
            reply = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32603, 'message': str(e)}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + '\n')
            sys.stdout.flush()


if __name__ == '__main__':
    main()
