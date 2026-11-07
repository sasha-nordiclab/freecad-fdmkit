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

WORKFLOW_POLICY = 'GLOBAL WORKFLOW: ONE working FCStd per project; history in Git. No versioned model copies, backup folders or per-revision scripts/reports unless requested. One small change -> check -> save SAME file -> Git commit. Batch only that step.'

DESCRIPTION = WORKFLOW_POLICY + "\n\n" + """Run fdmkit calls in the open FreeCAD. 'a(); b(); c()' = one transaction, one result
per call; any ERR rolls the whole batch back. Batch related steps to save round trips.
Lengths/angles: number or expression; bare params names allowed ('wall*2').
P(name=val,...) set (lengths 'x mm') | P() list | new(name) = NEW DOCUMENT; a Body in the open
one: b=App.ActiveDocument.addObject('PartDesign::Body',n); Gui.ActiveDocument.ActiveView.setActiveObject('pdbody',b)
(else helpers use the last Body; sk() names it when there are several) | plane(name, base='XY'|datum, offset)
sk(name, on='XY'|datum) | rect(sk,w,h,x=0,y=0,at='c'|'bl') | circ(sk,d,x,y)
Parallel loft sections: attach sketches to an origin plane and set a parametric
AttachmentOffset; create separate datum planes only when they add a real reference.
Radial sketch on 'XZ' (normal -Y) turned to azimuth a about Z: AttachmentOffset
placement(vector(d*sin(a); 0 mm; d*cos(a)); rotation(vector(0; 1; 0); a)), a = 0 on -Y.
slot(sk,length,width,x,y,angle) | poly(sk,[(x,y),...]) | fil(sk,(x,y),r)
half(sk) cuts a sketch symmetric about its H axis to y>=0, in place
pad(sk,len,side='one'|'two'|'sym',reverse,length2) | pocket(sk,depth='through',reverse,depth2)
side='two' needs length2/depth2 (a number, expression or 'through') | revolve(sk,angle=360,axis='V_Axis'|'Z')
26.3 starts: pad/pocket/revolve/groove(...,start='profile'|'offset'|'reference',
offset=expr (revolve/groove: deg),reference='XY'|datum|(sk,(x,y))); pocket/groove/hole(...,operation='subtract'|'common')
Offset runs along the feature: pad +normal, pocket into the cut (pocket offset=-6 starts 6 above).
Sketch regions (26.3 internals): pad/pocket(...,at=(x,y)|[(x,y),...]) use only the closed
regions under those sketch-coord points, so one master sketch drives several features;
regions(sk) lists InternalFaceN, area, an inner point, holes. Pick by point, never by N.
After a sketch edit lint() reports 'lost ?InternalFaceN' (the feature keeps a stale
shape); remap(feature,(x,y),...) re-picks the regions, remap(feature) = whole sketch.
hole(sk,diameter,depth='through',thread_type=None,thread_size=None,model_thread=False,
cosmetic_thread=True,drill_point='flat'|'angled') blind floor flat at depth ('angled' adds a cone
below it); threaded: diameter = nominal (4 -> M4x0.7, tap drill set) | groove(sk,angle=360,axis=)
revolve/groove(...,project_axis=True (axis outside the sketch plane), type='angle'|'up_to_face'|
'up_to_first'|'up_to_last'(revolve)|'through'(groove), up_to=plane|'Feature.FaceN')
midplane(name,a,b) datum midway between two planes/faces (bisector if not parallel)
Refs: origin key 'XY'/'Z', object name, or 'Feature.Face3'/'sketch.Edge1' as sel() prints.
linear(features,'X'|'Feature.EdgeN',count,step=|extent=,direction2=,count2=1,suppressed=[i|(i,j)])
one feature for a row or a grid (2x2 mount holes); step2/extent2 default to step/extent
polar(features,occurrences,axis='Z',angle=360,suppressed=()) indices are zero-based
circular(features,rings,radial,tangential,axis='Z',symmetry=1) concentric circles |
path_pattern(features,path,count=None,spacing=None,align=False) first instance = original |
point_pattern(features,points) at a sketch's points/circle centres or 'Feature.VertexN'; first = original.
Every pattern becomes the Body Tip; a pattern that changes nothing is an ERR.
defeature(['Tip.Face7',...]) removes faces of the Body Tip and heals | thickness(faces,value,
mode='skin'|'recto_verso',join='arc'|'intersection',inward=True) shell; fails on complex solids
mirror([features],plane='XY'|datum) PartDesign::Mirrored | move(feature, after)
dim(sk,'r1_w',val) (angles in deg) | chk(body=None) | why(name) | tree() | selftest() | reload() alone in a call
undo() reverts the last committed call and names it; right after an ERR it refuses once.
mass(*objs,density=g/cm³) = V, m, CoG, principal I (materials' density unless 'Default')
LINKS/ASSEMBLY: link_array(source,'linear'|'polar'|'path'|'point',count,step,axis,angle,path,
points,into=assembly) = App::Link instances, joints attach to any | rigid_group(*links) joint |
snapshot(name) store/re-capture placements+visibility | snapshot_restore(name,solve=True)
SPEED: '?expr' = read-only (its changes are discarded, no recompute); '?' only at the start, never
mid-batch: write steps and the read go in separate calls. focus('Body',...) = recompute only
those Bodies + params until full(); full() = one recompute + Assembly solve.
freeze('Name',...) / thaw(...) = Std_ToggleFreeze heavy objects (Assembly, gears, STEP).
freeze_all() / thaw_all() = every non-link object (animations); then full().
i10g_video() = render the i10g Animation async (hidden links dropped); wait for ffmpeg.
CHECK: check() = whole document: one valid solid per Body, no errors, DoF 0, no Body
intersections, every Fasteners object on a hole axis | lint() = traps: lost sketch regions/refs, hole sketch tangent
to a cylinder, countersink apex on the hole floor, sketches placed by plain numbers,
cross-Body expression refs, unused params | case('alias'|'sheet.alias', value) = set (a bare number keeps the cell's unit),
check(), restore (stress test) | errors() = new errors/tracebacks in FreeCAD's Report view
(addons, recomputes, GUI); when FreeCAD reported errors since the last call, the result ends
with ' | FreeCAD report: N new errors since the last call' - read errors() and fix the cause | sel() = GUI selection + distance, angle of axes/normals,
distance of parallel hole axes, diameters; names items 'pad.Face6'/'sk.Edge1', usable as refs |
reopen() = save, close, open, recompute (clears undo). full() reports lost Assembly joint refs.
TechDraw: SVG export only (exportPageAsPdf crashes 26.3; untested on 27.1).
CNC (metal, lathe + 4-axis mill, A = part Z; cutter Ø = 2 x params.CncCornerRadius or cutter=):
cnc(*bodies, skip=('Name',...), cutter=None, holes=False) = sharp inside corners without a floor the
cutter reaches (stick-out <= 6 Ø), fillets < cutter R, unreachable milled faces, slots < Ø or
deeper than 4 x width, lathe grooves < 0.5, holes L/D > 8, walls < 0.3; holes=True lists tap
drill / ISO 273 sizes | cnc_show() / cnc_restore() = faces of the last cnc() red / colours back.
CAM (native workbench): cam_job(name, body, stock=feature_before, azimuth=deg, cutter=Ø) =
one setup; azimuth = A-axis index (model + stock clones turned so that radial is +Z, the
simulator is 3-axis); name gets a 'Job' prefix | cam_slot(job, p1, p2, depth) = Slot op,
points in PART coordinates on the top surface | cam_sim(job) = CAM_SimulatorGL tab, Play
| cam_del(job) = CAM's own teardown.
Namespace: fdmkit calls + App + Gui; import other modules inside the call.
Sketch shapes are fully constrained (DoF 0); names: r1_w, c1_d, s1_l...
LOCAL COORDINATES: model each Body about its own functional origin and symmetry planes;
Assembly Links/joints place it in the assembly. Use geometric relations and construction
geometry, then minimal named dimensions; no per-vertex dimension grids or mass Block/Fixed.
For local source Bodies, check(*assembly_link_names) / case(name, value, *assembly_link_names)
check the assembled parts; plain check() would compare Bodies overlapping at their origins.
Migration procedure: skill/rules.md "Local part coordinates and assembly placement"."""

INSTRUCTIONS = WORKFLOW_POLICY + "\n\n" + """fdmkit rules (full text: skill/rules.md, fem.md; read the named section first).
1. Understand the part in use: mounting, load paths, real loads, mating parts. Proven
   functional details (ledges, fits) stay unless told.
2. Standard first: native features, installed workbenches (rules.md "Standard workbenches
   for each job"), standard parts, manufacturer CAD; verify sizes, resize via parameters.
   AddonManager only after the user agrees. Assembly joints, not Placement expressions.
3. Symmetry: copy vs mirror by hole/mount coordinates, never bbox; build one side, derive
   the other natively (Mirrored / App::Link); symmetric layouts; re-check every revision.
4. Native PartDesign, sketches DoF 0, sizes in params. Reference features to real datums
   through params, never an absolute Z. Bosses before holes; after adding material holes
   stay through, nothing passes bed/mount faces. Small tree: loft sections on one origin
   plane with expression AttachmentOffset; datum planes only for real references.
   Local Body origins + Assembly placement: rules.md "Local part coordinates".
5. Print: overhang <= 40 deg from vertical; ligaments >= 3; rims >= 6; countersink/
   counterbore/nut outline >= 3 from every edge, wall, slot (M4 Ø9.8: centre >= 7.9);
   walls k x 0.6, never < 1.8; lighten with tapered recesses, not windows. Radial hole
   sketches 1 mm outside the cylinder (tangent sketches make OCC drop holes).
6. Strength/lightening only from FEM (fem.md): real supports, impact by energy,
   anisotropic layers; show a table, change the model only after the user agrees.
7. Time/grams: tools/orca_slice.py with the user's presets (A1 NordicLab, 0.20mm NordicLab
   0.6 Ballance, AzureFilm PETG HF); strength parts 100 % zig-zag.
8. Reply OK / errors / numbers. No exports unless asked; temp files in scratchpad.
   Use as few subagents as possible: call run() from the main session; at most one
   subagent per edit batch, never a separate read-only inspection agent.
9. Keep the project AGENTS.md minimal (about 60-70 lines) so a new session starts cheap:
   FreeCAD version, rules, one line per model file, latest verified state, decisions, open
   questions. Details live in the params sheets and in Git history; no session logs or
   per-part essays. Update once after a substantive change, replacing outdated lines.
   When the user asks about trimmed details, read them from Git history (git log, git show <commit>:path).
10. After every model change: reopen(), check(), lint(); before handover case() on the
   main drivers. reopen() clears the undo history.
11. Before deleting an object whose expressions use the params sheet, clear them
   (setExpression(p, None) for each ExpressionEngine entry) and recompute: else the next
   sheet change segfaults FreeCAD 26.3 (untested on 27.1).
12. Speed (rules.md "Speed with big documents"): focus() the edited Bodies, freeze() the
   Assembly and heavy parts, '?expr' reads, one batch per edit, Suppressed not delete,
   one full() at the end. Never call while FreeCAD is still busy.
13. GUI: move the camera freely; at the end leave edit mode, restore final visibility,
   axonometric + Fit All; keep the user's selection. Every final Body gets a distinct
   saturated pastel ShapeColor as soon as it exists.
14. Pictures only via View3D.saveImage of the user's real document, white background;
   renders pastel, no text, colour = deflection. No staged scenes or copies.
15. Animations: rules.md "Animations and exploded views" (freeze_all first, i10g
   ShapeAppearance patch, thaw_all + full() after).
16. Caliper reverse engineering: ignore 0.1-0.2 deviations, prefer stack checks between
   two sel() faces, change where several checks agree.
17. Metal CNC (rules.md "Metal CNC parts"): turning first, one Revolution of a closed R-Z
   profile; inside corners along the cutter axis = params.CncCornerRadius, floor-wall
   corners sharp; ISO tap drills, ISO 273 clearances; cnc() after each change; show doubts
   with cam_job + cam_slot + cam_sim on the real model.
18. Local-coordinate migration: Git checkpoint, no file copies; compare assembled geometry
   both ways, test drivers/joints, reopen/check/lint (cnc for metal)."""

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
                  'serverInfo': {'name': 'fdmkit', 'version': '0.4.0'},
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
