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
Sketch shapes are fully constrained (DoF 0); names: r1_w, c1_d, s1_l...
RULE symmetry: parts are often mirrored pairs (Module_A/Module_B) or symmetric about a
plane (bays about a divider). Model one side, derive the other by mirroring; make
layouts (windows, holes, ribs) symmetric; every design revision checks symmetry first."""

INSTRUCTIONS = """fdmkit design rules (details: skill rules.md, fem.md):
1. Understand the part in use first: how it mounts, what bears where, real loads,
   mating-part shapes. Proven functional details (ledges, fits) stay unless told.
2. Symmetry first. Copy vs mirror is decided by hole/mount coordinates, never bbox.
   Build one side; derive the other natively (Part::Mirroring / App::Link).
   Layouts symmetric; every revision re-checks symmetry.
3. Native PartDesign only; sketches DoF 0; sizes in params. Bosses before holes.
   After adding material: holes still through, nothing past bed/mount faces.
4. Overhangs <= 40 deg from print vertical; ligaments >= 3 mm; rims >= 6 mm.
   Walls: multiples of 0.6, never < 1.8 (3 x 0.6 lines; 0.4 nozzle, 0.2 layer).
   Lighten with tapered recesses / thin zones, not through windows (windows cost time).
5. Strength/lightening only from FEM (fem.md): real supports (bolt seat + one-sided
   wall contact), impact by energy, anisotropic layer criterion; show a table and
   change the model only after the user agrees.
6. Print time/grams: slice with tools/orca_slice.py (the user's own Orca presets, A1 NordicLab,
   0.20mm NordicLab 0.6 Ballance, AzureFilm PETG HF); strength parts solid: 100 % zig-zag.
7. Reply OK / errors / numbers. No exports unless asked (temp FEM files in scratchpad,
   deleted after). Renders: white, pastel, no text; colour = deflection.
8. At the start of work in each CAD project, immediately create or update that project's
   AGENTS.md as a handoff for the next AI: purpose, current model and parameters,
   verified state, decisions, open questions, and how to resume through this MCP.
   Keep it current after each substantive model change; do not wait until the end."""

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
                  'serverInfo': {'name': 'fdmkit', 'version': '0.1.0'},
                  'instructions': INSTRUCTIONS}
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
