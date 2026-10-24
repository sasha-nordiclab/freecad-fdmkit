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
Parallel loft sections: attach sketches to an origin plane and set a parametric
AttachmentOffset; create separate datum planes only when they add a real reference.
slot(sk,length,width,x,y,angle) | poly(sk,[(x,y),...]) | fil(sk,(x,y),r)
half(sk) cuts a sketch symmetric about its H axis to y>=0, in place
pad(sk,len,side='one'|'two'|'sym',reverse) | pocket(sk,depth='through') | revolve(sk,angle=360,axis='V_Axis'|'Z')
26.3 starts: pad/pocket/revolve/groove(...,start='profile'|'offset'|'reference',
offset=expr,reference='XY'|datum); pocket/groove/hole(...,operation='subtract'|'common')
hole(sk,diameter,depth='through',thread_type=None,thread_size=None,
model_thread=False,cosmetic_thread=True) | groove(sk,angle=360,axis='V_Axis'|'Z')
polar(features,occurrences,axis='Z',angle=360,suppressed=()) indices are zero-based
mirror([features],plane='XY'|datum) PartDesign::Mirrored | move(feature, after)
dim(sk,'r1_w',val) | chk() | why(name) | tree() | undo() | selftest() | reload()
SPEED: '?expr' = read-only (no transaction/recompute). focus('Body',...) = recompute only
those Bodies + params until full(); full() = one recompute + Assembly solve.
freeze('Name',...) / thaw(...) = Std_ToggleFreeze heavy objects (Assembly, gears, STEP).
freeze_all() / thaw_all() = every non-link object (animations); then full().
i10g_video() = render the i10g Animation async (hidden links dropped); wait for ffmpeg.
Namespace: fdmkit calls + App + Gui; import other modules inside the call.
Sketch shapes are fully constrained (DoF 0); names: r1_w, c1_d, s1_l...
RULE symmetry: parts are often mirrored pairs (Module_A/Module_B) or symmetric about a
plane (bays about a divider). Model one side, derive the other by mirroring; make
layouts (windows, holes, ribs) symmetric; every design revision checks symmetry first."""

INSTRUCTIONS = """fdmkit design rules (details: skill rules.md, fem.md):
1. Understand the part in use first: how it mounts, what bears where, real loads,
   mating-part shapes. Proven functional details (ledges, fits) stay unless told.
2. Before creating a component, check FreeCAD native features, installed workbenches,
   standard parts and manufacturer CAD. Prefer a suitable standard solution; verify
   its dimensions and interfaces, and resize it through supported parameters.
   Model custom geometry when no suitable option meets the requirements.
3. Symmetry first. Copy vs mirror is decided by hole/mount coordinates, never bbox.
   Build one side; derive the other natively (Part::Mirroring / App::Link).
   Layouts symmetric; every revision re-checks symmetry.
4. Native PartDesign only; sketches DoF 0; sizes in params. Bosses before holes.
   After adding material: holes still through, nothing past bed/mount faces.
   Keep the feature tree small and editable: for parallel loft sections, attach
   sketches to one origin plane with expression-driven AttachmentOffset values.
   Add separate datum planes only for distinct geometric references, not merely
   to give each parallel sketch a different height.
5. Overhangs <= 40 deg from print vertical; ligaments >= 3 mm; rims >= 6 mm.
   Fastener edge distance: the countersink/counterbore/nut-pocket outline keeps >= 3 mm
   to every edge, wall, slot and recess (M4 countersunk/counterdrill Ø9.8: centre >= 7.9 from each edge);
   size ears and bases from the fastener; check numbers after each change.
   Walls: multiples of 0.6, never < 1.8 (3 x 0.6 lines; 0.4 nozzle, 0.2 layer).
   Lighten with tapered recesses / thin zones, not through windows (windows cost time).
6. Strength/lightening only from FEM (fem.md): real supports (bolt seat + one-sided
   wall contact), impact by energy, anisotropic layer criterion; show a table and
   change the model only after the user agrees.
7. Print time/grams: slice with tools/orca_slice.py (the user's own Orca presets, A1 NordicLab,
   0.20mm NordicLab 0.6 Ballance, AzureFilm PETG HF); strength parts solid: 100 % zig-zag.
8. Reply OK / errors / numbers. No exports unless asked (temp FEM files in scratchpad,
   deleted after). Renders: white, pastel, no text; colour = deflection.
9. At the start of work in each CAD project, immediately create or update that project's
   AGENTS.md as a handoff for the next AI: purpose, current model and parameters,
   verified state, decisions, open questions, and how to resume through this MCP.
   Keep it current after each substantive model change; do not wait until the end.
10. Move the FreeCAD camera freely as needed while working. After all model operations,
   return the GUI to an overall view of the final model: leave any temporary edit
   mode, restore the intended final Body visibility, switch to axonometric view and
   Fit All via fdmkit.run(expr). Preserve the user's selection unless the agent made
   a temporary selection; then clear only that selection.
11. Give each final FreeCAD Body a distinct saturated pastel ShapeColor as soon as it
    exists, so the model looks finished in the live GUI throughout construction and
    in the final overall view. Use light colours with clear hue contrast; do not defer
    the colours to renders or exports.
12. Pictures of a model or assembly come only from FreeCAD's standard image export of
    the user's real document (View3D.saveImage of its own 3D view, white background).
    Never generate a scene yourself: no shape copies, temporary documents, re-placed
    or re-coloured parts, or compositing. What the image shows is what the model is.
13. Before deleting any object whose expressions use the params sheet (features, sketches,
    datum planes, links, whole Bodies), first clear its expressions (setExpression(p, None)
    for every entry in ExpressionEngine) and recompute; only then delete it. Otherwise the
    next change of the sheet segfaults FreeCAD 26.3 (RC1 and RC2) in Document::recompute /
    enforceRecompute, even after an intermediate recompute (minimal repro confirmed without
    addons). Rebuild a part in a new Body, relink, clear the old Body's expressions, delete it.
14. Use FreeCAD's standard tools and workbenches for their jobs instead of custom scripts
    (full table: rules.md "Standard workbenches for each job"): Sketcher + PartDesign for
    printable parts, Part for reference/purchased shapes and checks, Spreadsheet for params,
    Assembly for assemblies, joints, motion limits, Simulation, BOM and exploded views,
    Fasteners, freecad.gears, UNI-Rolling-Bearing, SheetMetal for hardware and sheet parts,
    Measure, Material, Fem/Plot, Mesh/MeshPart, Import, TechDraw, Draft, Surface, Inspection,
    Points/ReverseEngineering for their own tasks. CAM/BIM/Robot are not used. Install a
    workbench via AddonManager only after the user agrees. No Placement expressions to
    place or animate parts when an Assembly joint can do it.
15. Speed (rules.md "Speed with big documents"): focus() the Bodies being edited, freeze()
    the Assembly and heavy parts, read with '?expr' (never raise Exception to read),
    batch a whole edit per call, Suppressed instead of delete, one full() at the end.
    Never send a call while FreeCAD is still busy with the previous one.
16. Animations/exploded videos (rules.md "Animations and exploded views"): i10g steps of
    link placements, stages along the real assembly order, loop 0..n..0 for social media.
    freeze_all() first (else the Assembly solver and i10g's forced recompute undo the
    explode and take minutes), fixed perspective camera fitted on the exploded state,
    NaviCube off, i10g_video() async, wait for ffmpeg, check frames, then thaw_all(),
    full() and restore the view. i10g on FreeCAD 26 needs the ShapeAppearance patch
    (tools/patches/i10g-shapeappearance.patch); re-apply after addon updates."""

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
                  'serverInfo': {'name': 'fdmkit', 'version': '0.2.0'},
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
