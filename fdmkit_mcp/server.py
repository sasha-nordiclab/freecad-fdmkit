#!/usr/bin/env python3
"""fdmkit MCP server: one tool, run(expr), over stdio. No dependencies.

Shared by Claude Code and Codex; forwards to the running FreeCAD via tools/fc.py.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import fc  # noqa: E402

WORKFLOW_POLICY = 'WORKFLOW: ONE FCStd per project, history in Git; no versioned copies/backups/per-revision scripts/reports unless requested. Small change -> check -> save SAME file -> Git commit; batch only that step.'

DESCRIPTION = """Run fdmkit calls in the open FreeCAD. 'a(); b(); c()' = one transaction, one result; any ERR rolls the whole batch back. Batch related steps.
Lengths/angles: number or expression; bare params names allowed ('wall*2').
P(name=val,...) set (lengths 'x mm'; a bare number is unitless) | P() list
new(name) = NEW DOCUMENT; body(name) = new Body in the open one, made active (else helpers use the last Body; sk() names it when there are several)
plane(name, base='XY'|datum, offset) | sk(name, on='XY'|datum) | rect(sk,w,h,x=0,y=0,at='c'|'bl') | circ(sk,d,x,y)
slot(sk,length,width,x,y,angle) | poly(sk,[(x,y),...]) | fil(sk,(x,y),r) | half(sk) cuts a sketch symmetric about its H axis to y>=0, in place
Sketch shapes are fully constrained (DoF 0); names: r1_w, c1_d, s1_l...
pad(sk,len,side='one'|'two'|'sym',reverse,length2) | pocket(sk,depth='through',reverse,depth2); side='two' needs length2/depth2 (number, expression or 'through')
revolve(sk,angle=360,axis='V_Axis'|'Z') | groove(sk,angle=360,axis=) | hole(sk,diameter,depth='through') plain; threads/drill point: help('hole')
mirror([features],plane='XY'|datum) PartDesign::Mirrored | move(feature, after)
dim(sk,'r1_w',val) (angles in deg) | chk(body=None) | why(name) | tree() | selftest() | reload() alone in a call
undo() reverts the last committed call and names it; right after an ERR it refuses once.
Refs: origin key 'XY'/'Z', object name, or 'Feature.Face3'/'sketch.Edge1' as sel() prints.
Radial sketch on 'XZ' (normal -Y) turned to azimuth a about Z: AttachmentOffset
placement(vector(d*sin(a); 0 mm; d*cos(a)); rotation(vector(0; 1; 0); a)), a = 0 on -Y.
help('topic') = full reference of the rarer calls (call it before first use):
 starts: start=/offset=/reference=, operation='common', up_to, project_axis, midplane
 regions: pad/pocket(at=), regions, remap (one master sketch, several features)
 patterns: linear polar circular path_pattern point_pattern (rows, grids, rings)
 dressup: defeature thickness (remove Tip faces, shell)
 hole: threads, cosmetic/modelled, drill_point
 assembly: link_array rigid_group snapshot snapshot_restore mass; check() of local-origin parts
 anim: freeze_all thaw_all i10g_video (animations)
 drawing: TechDraw dim_add dim_layout dim_check (SVG export only, never exportPageAsPdf)
 cnc: cnc cnc_show cnc_restore (metal lathe/mill checks)
 cam: cam_job cam_slot cam_sim cam_del (native CAM simulation)
SPEED: '?expr' = read-only (its changes are discarded, no recompute); '?' only at the start of a call, never
mid-batch: write steps and the read go in separate calls. focus('Body',...) = recompute only
those Bodies + params until full(); full() = one recompute + Assembly solve (reports lost joint refs).
freeze('Name',...) / thaw(...) = Std_ToggleFreeze heavy objects (Assembly, gears, STEP).
CHECK: check() = whole document: one valid solid per Body, no errors, DoF 0, no Body
intersections, every Fasteners object on a hole axis; local-origin parts: check(*assembly_link_names) |
lint() = traps: lost sketch regions/refs, hole sketch tangent to a cylinder, countersink apex on the
hole floor, sketches placed by plain numbers, cross-Body expression refs, unused params |
case('alias'|'sheet.alias', value) = set (a bare number keeps the cell's unit), check(), restore
(stress test) | errors() = new errors/tracebacks in FreeCAD's Report view (addons, recomputes, GUI);
when FreeCAD reported errors since the last call, the result ends with
' | FreeCAD report: N new errors since the last call' - read errors() and fix the cause |
sel() = GUI selection + distance, angle of axes/normals, distance of parallel hole axes, diameters;
names items 'pad.Face6'/'sk.Edge1', usable as refs | reopen() = save, close, open, recompute (clears undo).
Namespace: fdmkit calls + App + Gui; import other modules inside the call."""

INSTRUCTIONS = WORKFLOW_POLICY + """

Rules (full text skill/rules.md,fem.md;read named section first).
1. Know the part's use (mounting,load paths,loads,mating parts);keep proven functional details unless told.
2. Standard first: native features,workbenches (rules.md "Standard workbenches for each job"),standard/manufacturer parts;verify sizes;AddonManager only after user agrees;Assembly joints,not Placement expressions.
3. Symmetry: copy vs mirror by hole/mount coordinates,never bbox;build one side,derive the other natively (Mirrored/App::Link);re-check each revision.
4. Native PartDesign,sketches DoF 0,sizes in params,features on real datums via params (never absolute Z). Bosses before holes;after adding material holes stay through,nothing passes bed/mount faces. Loft sections/datum planes: rules.md "Sketch supports and minimal datum planes". Local Body origins + Assembly: rules.md "Local part coordinates".
5. Print: overhang ≤40° from vertical;ligaments ≥3;rims ≥6;countersink/counterbore/nut outline ≥3 from any edge,wall,slot (M4 Ø9.8: centre ≥7.9);walls k x 0.6,never <1.8;lighten with tapered recesses,not windows. Radial hole sketches 1 mm outside the cylinder (tangent: OCC drops holes).
6. Strength/lightening only from FEM (fem.md);table first,change the model only after user agrees.
7. Time/grams: tools/orca_slice.py,presets (A1 NordicLab,0.20mm NordicLab 0.6 Ballance,AzureFilm PETG HF);strength parts 100 % zig-zag.
8. Reply OK/errors/numbers;no exports unless asked;temp files in scratchpad. Tokens (rules.md "Token economy";state in chat when asked): main session plans/briefs/reviews,one mid-tier subagent per edit batch (Claude: sonnet,effort medium;high for Assembly joints,cross-document params,check scripts),never the smallest tier or read-only inspection agents.
9. Project AGENTS.md 60-70 lines: FreeCAD version,rules,one line per model file,verified state,decisions,open questions;details in params sheets/Git history;no session logs/per-part essays;update once per substantive change;trimmed details: read Git history (git log,git show <commit>:path).
10. After every model change: reopen(),check(),lint();before handover case() on main drivers.
11. Before deleting an object with params-sheet expressions,clear them (setExpression(p,None) per ExpressionEngine entry) and recompute: else the next sheet change segfaults FreeCAD (27.1 too).
12. Speed (rules.md "Speed with big documents"): focus() edited Bodies,freeze() Assembly/heavy parts,one batch per edit,Suppressed not delete,one full() at the end;never call while FreeCAD is busy.
13. GUI: camera free;at the end leave edit mode,restore final visibility,axonometric + Fit All,keep user's selection;final Bodies: distinct saturated pastel ShapeColor at once.
14. Pictures only via View3D.saveImage of the user's document: white background,pastel,no text,colour = deflection;no staged scenes.
15. Animations: rules.md "Animations and exploded views" (freeze_all first,i10g ShapeAppearance patch,thaw_all + full() after).
16. Caliper reverse engineering: ignore 0.1-0.2 deviations,prefer stack checks between two sel() faces,change where several checks agree.
17. Metal CNC (rules.md "Metal CNC parts"): turning first,one Revolution of a closed R-Z profile;inside corners along the cutter axis = params.CncCornerRadius,floor-wall corners sharp;ISO tap drills,ISO 273 clearances;cnc() after each change;doubts: cam_job+cam_slot+cam_sim on the real model.
18. Local-coordinate migration: Git checkpoint;compare assembled geometry both ways,test drivers/joints,reopen/check/lint (cnc for metal).
19. Critical FreeCAD failure (crash,RPC unreachable,segfault,corrupt/lost save,hang): append a dated line to fdmkit KNOWN_ISSUES.md (build,call,documents,symptom,loss,workaround),commit only if asked. doc.save() before reopen();after a crash restart FreeCAD,verify saved state,redo lost edits."""

LOG = os.path.expanduser('~/Library/Logs/fdmkit/mcp.log')


def log_call(expr, out, seconds):
    """One JSON line per call (time, seconds, expr, result) in ~/Library/Logs/fdmkit/mcp.log;
    rotated at 5 MB. Logging never breaks a call."""
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        if os.path.exists(LOG) and os.path.getsize(LOG) > 5e6:
            os.replace(LOG, LOG + '.1')
        rec = {'t': time.strftime('%Y-%m-%d %H:%M:%S'), 's': round(seconds, 2),
               'expr': expr[:500], 'out': out[:1000],
               'err': out.startswith(('ERR', 'RPC ERR')) or ' | FreeCAD report:' in out}
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except OSError:
        pass


TOOL = {'name': 'run', 'description': DESCRIPTION,
        'inputSchema': {'type': 'object', 'properties': {'expr': {'type': 'string'}},
                        'required': ['expr']}}


def handle(msg):
    method, mid = msg.get('method'), msg.get('id')
    if mid is None:
        return None  # notification
    if method == 'initialize':
        result = {'protocolVersion': (msg.get('params') or {}).get('protocolVersion', '2025-06-18'),
                  'capabilities': {'tools': {}},
                  'serverInfo': {'name': 'fdmkit', 'version': '0.5.0'},
                  'instructions': INSTRUCTIONS}
    elif method == 'tools/list':
        result = {'tools': [TOOL]}
    elif method == 'tools/call':
        p = msg.get('params') or {}
        if p.get('name') != 'run':
            return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': 'unknown tool'}}
        expr = (p.get('arguments') or {}).get('expr', '')
        t0 = time.time()
        try:
            out = fc.call(expr)
        except Exception as e:      # HTTP errors, XML faults, bad bytes: still answer this id
            out = f'RPC ERR {type(e).__name__}: {e}'
        log_call(expr, out, time.time() - t0)
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
        mid = None
        try:
            msg = json.loads(line)
            mid = msg.get('id') if isinstance(msg, dict) else None
            reply = handle(msg)
        except Exception as e:
            reply = {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32603, 'message': str(e)}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + '\n')
            sys.stdout.flush()


if __name__ == '__main__':
    main()
