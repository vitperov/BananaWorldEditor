#!/usr/bin/env python3
"""bwe_cli - headless CLI for BananaWorldEditor.

Drives the same model / helper / generator layer used by the GUI editor, so
maps can be inspected and edited from scripts (or by an LLM harness)
without opening the Qt interface.

Invocation (from the Unity project root, via the symlink):
    python3 Assets/TtMapsEditor/bwe_cli.py <command> [options]

Commands are split into read-only queries (list-objects, list-generators,
describe, dump) and one-op-per-call mutating edits (added in a later step).
"""

import argparse
import contextlib
import json
import os
import sys

# Original working directory: map-file arguments are resolved against this
# BEFORE we chdir into the editor root below.
ORIG_CWD = os.getcwd()

# Real editor root (resolve symlinks so relative paths - mapObjects, generators,
# generatorsSettings.json, settings/application.json - point at the true repo).
EDITOR_ROOT = os.path.dirname(os.path.realpath(__file__))


@contextlib.contextmanager
def _stdout_to_stderr():
    """Redirect library chatter (print statements in the model/loader) to stderr
    so command output on stdout stays clean and machine-parseable."""
    old = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old


def _abs_from_orig(path):
    """Resolve a user-supplied path against the ORIGINAL cwd (pre-chdir)."""
    if path is None:
        return None
    return os.path.abspath(os.path.join(ORIG_CWD, path))


def build_model(map_path=None, base_prefab=None, need_generators=False):
    """Build the headless model with the unified object collection.

    Mirrors what the GUI does (showHouseEditor / Terrain.Model) minus the
    GUI-only bits: textures and loot collections are None (they only feed
    picker dialogs). basePrefab is auto-restored from the file on load.
    Returns (objectsCollection, mapModel[, generatorsLoader]).
    """
    from modules.commonModels.MapModelGeneral import MapModelGeneral
    from modules.commonModels.MapObjectModelGeneral import MapObjectModelGeneral
    from modules.commonModels.ObjectsCollection import ObjectsCollection
    from modules.ApplicationSettings.ApplicationSettingsModel import ApplicationSettingsModel

    with _stdout_to_stderr():
        settings = ApplicationSettingsModel()
        native = os.path.join(EDITOR_ROOT, 'mapObjects')
        ext = settings.getAdditionalMapObjectsDir()
        searchpaths = [native] + ([ext] if ext else [])
        oc = ObjectsCollection(searchpaths)

        model = MapModelGeneral(MapObjectModelGeneral, oc, None, None, basePrefab=base_prefab)
        model.setUpdatedCallback(lambda: None)
        if map_path is not None and os.path.exists(map_path):
            model.openMap(map_path)

    if not need_generators:
        return oc, model

    from modules.GeneratorPluginsModel.GeneratorPluginsLoader import GeneratorPluginsLoader
    with _stdout_to_stderr():
        loader = GeneratorPluginsLoader(model)
        loader.loadPluginsFrom('generators')
    return oc, model, loader


def _require_map(path):
    if not os.path.exists(path):
        sys.exit("Error: map file not found: " + path)


def _emit(obj, as_json):
    """Print a structured result: pretty JSON when as_json, else the caller has
    already printed text and passes as_json=False with obj=None."""
    if as_json:
        print(json.dumps(obj, indent=2))


BASE_PROPS = ('rotation', 'model')  # properties on MapObjectModelGeneral.classnames


def _selection(rect, z):
    from modules.commonModels.SelectionRange import SelectionRange
    x, y, w, h = rect
    return SelectionRange.fromRect(x, y, w, h, z)


def _parse_kv(items):
    result = {}
    for item in items or []:
        if "=" not in item:
            sys.exit("Error: expected key=value, got: " + item)
        key, value = item.split("=", 1)
        result[key] = value
    return result


_BOOL_TRUE = ('true', '1', 'yes', 'on')
_BOOL_FALSE = ('false', '0', 'no', 'off')


def _prop_type(oc, model_name, key):
    """Declared additionalProperty type for model_name.key from the catalog,
    or None if the model/property is unknown (custom key on any object)."""
    for p in oc.getAdditionalProperties(model_name):
        if p.name == key:
            return p.type
    return None


def _coerce_prop_value(oc, model_name, key, raw):
    """Coerce a CLI string --prop value to the native JSON type the object
    catalog declares for model_name.key, mirroring the GUI properties dialog
    (AdditionalPropertiesDlg). Bool/int/stringArray become real JSON
    true/5/["x"] instead of strings "true"/"5"/"x"; JsonUtility maps these to
    the bool/int/string[] fields on AdditionalProperties.cs. Unknown types and
    string-like types (string, texture, enum, lootContainer) pass through
    unchanged."""
    ptype = _prop_type(oc, model_name, key)
    if ptype == 'bool':
        low = raw.strip().lower()
        if low in _BOOL_TRUE:
            return True
        if low in _BOOL_FALSE:
            return False
        sys.exit("Error: property '%s' is bool; expected true/false, got: %r" % (key, raw))
    if ptype == 'int':
        try:
            return int(raw)
        except (TypeError, ValueError):
            sys.exit("Error: property '%s' is int; expected an integer, got: %r" % (key, raw))
    if ptype == 'stringArray':
        return [v.strip() for v in raw.split(',') if v.strip()]
    return raw


def _find_generator(loader, name):
    for gen_name, _order, plugin in loader.generators:
        if name in (gen_name, plugin.childPluginClassName):
            return plugin
    available = ", ".join(n for n, _o, _p in loader.generators)
    sys.exit("Error: generator not found: %s\nAvailable: %s" % (name, available))


def save_model(model, path):
    with _stdout_to_stderr():
        model.saveMap(path)


# --------------------------------------------------------------------------- #
# Read-only commands
# --------------------------------------------------------------------------- #

def cmd_list_objects(args):
    oc, _ = build_model()
    rows = []
    for name in sorted(oc.objects.keys()):
        o = oc.objects[name]
        cats = [c.strip() for c in o.categories.split(',') if c.strip()]
        if args.category and args.category not in cats:
            continue
        props = [{'name': p.name, 'type': p.type, 'options': p.options} for p in o.additional_properties]
        rows.append({'name': name, 'w': o.w, 'h': o.h, 'categories': cats, 'additionalProperties': props})

    if args.json:
        _emit(rows, True)
        return

    if not rows:
        print("(no objects match)")
        return
    namew = max(len(r['name']) for r in rows)
    print("%-*s  %-5s  %-18s  %s" % (namew, 'NAME', 'WxH', 'CATEGORIES', 'ADDITIONAL PROPS'))
    for r in rows:
        size = "%dx%d" % (r['w'], r['h'])
        cats = ",".join(r['categories']) or "-"
        props = ", ".join("%s(%s)" % (p['name'], p['type']) for p in r['additionalProperties']) or "-"
        print("%-*s  %-5s  %-18s  %s" % (namew, r['name'], size, cats, props))


def cmd_list_generators(args):
    _, _, loader = build_model(need_generators=True)
    gens = []
    for name, order, plugin in loader.generators:
        static = plugin.pluginStaticSettings
        cls = plugin.childPluginClassName
        options = []
        for opt, spec in plugin.schema.items():
            options.append({
                'name': opt,
                'type': spec.get('type', ''),
                'default': spec.get('value', ''),
                'description': spec.get('description', ''),
            })
        gens.append({
            'name': name,
            'class': cls,
            'order': order,
            'description': static.get('description', ''),
            'options': options,
        })

    if args.json:
        _emit(gens, True)
        return

    for g in gens:
        header = g['name']
        if g['class'] != g['name']:
            header += " (class: %s)" % g['class']
        header += " [order %s]" % g['order']
        print(header)
        if g['description']:
            print("  " + g['description'])
        if g['options']:
            print("  options:")
            optw = max(len(o['name']) for o in g['options'])
            for o in g['options']:
                line = "    %-*s  %-6s  default=%s" % (optw, o['name'], o['type'], o['default'])
                if o['description']:
                    line += "   " + o['description']
                print(line)
        print("")


def cmd_describe(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    zlevels = sorted({sq.z for sq in model.getSquares()})
    counts = {}
    for sq in model.getSquares():
        counts.setdefault(sq.z, {})
        m = sq.properties.get('model')
        counts[sq.z][m] = counts[sq.z].get(m, 0) + 1

    if args.json:
        result = {
            'map': args.map,
            'width': model.width,
            'height': model.height,
            'basePrefab': model.basePrefab,
            'zLevels': zlevels,
            'counts': {str(z): counts[z] for z in zlevels},
        }
        if model.basePrefab is not None:
            result['floorHeight'] = model.floorHeight
        _emit(result, True)
        return

    print("map:        %s" % args.map)
    print("size:       %d x %d  (width x height)" % (model.width, model.height))
    print("basePrefab: %s" % model.basePrefab)
    if model.basePrefab is not None:
        print("floorHeight: %s" % model.floorHeight)
    print("z-levels:   %s" % (zlevels or "[]"))
    for z in zlevels:
        print("counts (z=%d):" % z)
        modelw = max((len(str(k)) for k in counts[z]), default=0)
        for m in sorted(counts[z], key=lambda k: (-counts[z][k], str(k))):
            print("  %-*s  %d" % (modelw, m, counts[z][m]))


def cmd_dump(args):
    _require_map(args.map)
    _, model = build_model(args.map)

    rect = args.rect
    squares = []
    for sq in model.getSquares():
        if args.z is not None and sq.z != args.z:
            continue
        if args.model is not None and sq.getModel() != args.model:
            continue
        if rect is not None:
            x0, y0, w, h = rect
            if not (x0 <= sq.x < x0 + w and y0 <= sq.y < y0 + h):
                continue
        squares.append(sq)

    if args.json:
        _emit([sq.toSerializableObj() for sq in squares], True)
        return

    if not squares:
        print("(no squares match)")
        return
    for sq in squares:
        rot = sq.properties.get('rotation')
        rot = getattr(rot, 'value', rot)
        extra = ""
        if sq.additional_properties:
            extra = "  props={%s}" % ", ".join("%s=%s" % (p.name, p.value) for p in sq.additional_properties)
        # wxh is the rotation-aware on-grid footprint (getSize), not the raw
        # stored w/h, so it matches the cells the object actually covers.
        size = sq.getSize()
        print("x=%-3d y=%-3d z=%d  model=%-16s rot=%-3s wxh=%dx%d%s" % (
            sq.x, sq.y, sq.z, sq.properties.get('model'), rot, size.w, size.h, extra))
    print("-- %d square(s)" % len(squares))


def cmd_render(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    from modules.commonModels.MapRenderer import MapRenderer

    result = MapRenderer(model).render(z=args.z, rect=args.rect)
    rows, legend = result['rows'], result['legend']
    rx, ry, rw, rh = result['rect']

    if args.json:
        _emit({
            'map': args.map,
            'z': args.z,
            'rect': [rx, ry, rw, rh],
            'legend': legend,
            'rows': rows,
        }, True)
        return

    # x ruler: a tens digit above each column that is a multiple of 10.
    ruler = "".join(str((rx + i) // 10 % 10) if (rx + i) % 10 == 0 else ' '
                    for i in range(rw))
    labelw = max(3, len(str(ry + rh - 1)))
    print("%s %s" % (" " * labelw, ruler))
    for i, row in enumerate(rows):
        print("%*d %s" % (labelw, ry + i, row))
    print("")
    zdesc = "z=%d" % args.z if args.z is not None else "all z (topmost shown)"
    print("legend (%s; lowercase = multi-cell footprint):" % zdesc)
    for item in legend:
        print("  %s  %s" % (item['glyph'], item['model']))


# --------------------------------------------------------------------------- #
# Mutating commands (load -> one op -> save in place, or --out)
# --------------------------------------------------------------------------- #

def cmd_new(args):
    _, model = build_model(None, base_prefab=args.base_prefab)
    width, height = args.size
    model.newMap(width, height)
    out = args.out or args.map
    save_model(model, out)
    print("created %dx%d map (basePrefab=%s) -> %s" % (width, height, model.basePrefab, out))


def cmd_fill(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    sel = _selection(args.rect, args.z)
    with _stdout_to_stderr():
        model.fillSelection(sel, args.model, args.rotation)
    out = args.out or args.map
    save_model(model, out)
    n = len(model.getAllObjectOfType(args.model, sel))
    print("filled %d cells with %s in rect %s -> %s" % (n, args.model, args.rect, out))


def cmd_border(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    sel = _selection(args.rect, args.z)
    with _stdout_to_stderr():
        model.fillBorder(sel, args.model, args.width, args.rotation)
    out = args.out or args.map
    save_model(model, out)
    print("drew %s border (width %d) around rect %s -> %s" % (args.model, args.width, args.rect, out))


def cmd_place(args):
    _require_map(args.map)
    oc, model = build_model(args.map)
    x, y = args.at
    z = args.z if args.z is not None else 0
    obj = model.createObjectAt(x, y, z)
    obj.setModel(args.model)
    if args.rotation is not None:
        obj.setProperty('rotation', str(args.rotation))
    model.updateModelSize(obj)
    for key, value in _parse_kv(args.prop).items():
        obj.setAdditioanalProperty(key, _coerce_prop_value(oc, args.model, key, value))
    out = args.out or args.map
    save_model(model, out)
    print("placed %s at (%d,%d,%d) -> %s" % (args.model, x, y, z, out))


def cmd_delete(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    sel = _selection(args.rect, args.z)
    count = len(model.getAllObjectOfType(args.model, sel))
    model.deleteObjectsInSelection(sel, args.model)
    out = args.out or args.map
    save_model(model, out)
    what = args.model if args.model else "all models"
    print("deleted %d squares (%s) in rect %s -> %s" % (count, what, args.rect, out))


def cmd_setprop(args):
    _require_map(args.map)
    oc, model = build_model(args.map)
    sel = _selection(args.rect, args.z)
    kv = _parse_kv(args.prop)
    # Count matches BEFORE mutating: if a --prop changes 'model', the filter would
    # no longer match afterwards and the report would wrongly say 0.
    n = len(model.getAllObjectOfType(args.model, sel))
    additional = {}
    for key, value in kv.items():
        if key in BASE_PROPS:
            model.setGroupProperty(sel, args.model, key, value)
        else:
            additional[key] = _coerce_prop_value(oc, args.model, key, value)
    if additional:
        model.setGroupProperty(sel, args.model, 'additionalProperties', additional)
    out = args.out or args.map
    save_model(model, out)
    changes = ", ".join("%s=%s" % (k, v) for k, v in kv.items())
    print("updated %d %s squares (%s) in rect %s -> %s" % (n, args.model, changes, args.rect, out))


def cmd_delprop(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    sel = _selection(args.rect, args.z)
    if args.all:
        n = model.deleteGroupAdditionalProperty(sel, args.model, clearAll=True)
        what = "all additional properties"
    else:
        # Accept bare keys ("doorState") or forgiving "key=value" pairs (drop the value).
        keys = [k.split("=", 1)[0] for k in args.prop]
        for key in keys:
            if key in BASE_PROPS:
                sys.exit("Error: cannot delete base property '%s' - model/rotation are "
                         "intrinsic; use setprop to change them, delprop only removes "
                         "additionalProperties." % key)
        n = model.deleteGroupAdditionalProperty(sel, args.model, names=keys)
        what = ", ".join(keys)
    out = args.out or args.map
    save_model(model, out)
    print("deleted %s from %d %s square(s) in rect %s -> %s" % (what, n, args.model, args.rect, out))


def cmd_wall_frame(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    from modules.commonModels.EditorHelper import EditorHelper
    sel = _selection(args.rect, args.z)
    EditorHelper(model).generateWallFrame(sel)
    out = args.out or args.map
    save_model(model, out)
    print("generated wall frame in rect %s -> %s" % (args.rect, out))


def cmd_roof_frame(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    from modules.commonModels.EditorHelper import EditorHelper
    sel = _selection(args.rect, args.z)
    helper = EditorHelper(model)
    if args.half:
        helper.generateRoofFrameHalf(sel)
    else:
        helper.generateRoofFrame(sel)
    out = args.out or args.map
    save_model(model, out)
    kind = "half-roof" if args.half else "roof"
    print("generated %s frame in rect %s -> %s" % (kind, args.rect, out))


def cmd_generate(args):
    _require_map(args.map)
    _, model, loader = build_model(args.map, need_generators=True)
    plugin = _find_generator(loader, args.name)
    for key, value in _parse_kv(args.set).items():
        plugin.settings[key] = value
    with _stdout_to_stderr():
        plugin.generate()
    out = args.out or args.map
    save_model(model, out)
    print("ran generator %s -> %s" % (args.name, out))


def cmd_clear(args):
    _require_map(args.map)
    _, model, loader = build_model(args.map, need_generators=True)
    plugin = _find_generator(loader, args.name)
    with _stdout_to_stderr():
        plugin.clear_generated()
    out = args.out or args.map
    save_model(model, out)
    print("cleared generator %s output -> %s" % (args.name, out))


def cmd_insert(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    size = model.height if args.axis == 'row' else model.width
    if args.count < 1:
        sys.exit("Error: --count must be >= 1")
    if not (0 <= args.at <= size):
        sys.exit("Error: --at %d out of range for %s (0..%d, %d appends at the far edge)"
                 % (args.at, args.axis, size, size))
    if args.copy_from is not None and not (0 <= args.copy_from < size):
        sys.exit("Error: --copy-from %d out of range for %s (0..%d)"
                 % (args.copy_from, args.axis, size - 1))
    with _stdout_to_stderr():
        model.insertLine(args.axis, args.at, args.count, args.fill, args.copy_from)
    out = args.out or args.map
    save_model(model, out)
    if args.copy_from is not None:
        how = "copied from %s %d" % (args.axis, args.copy_from)
    elif args.fill:
        how = "filled with %s" % args.fill
    else:
        how = "empty"
    print("inserted %d %s(s) before %s %d (%s); new size %dx%d -> %s" % (
        args.count, args.axis, args.axis, args.at, how, model.width, model.height, out))


def cmd_remove(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    size = model.height if args.axis == 'row' else model.width
    if args.count < 1:
        sys.exit("Error: --count must be >= 1")
    if not (0 <= args.at and args.at + args.count <= size):
        sys.exit("Error: remove range %d..%d out of bounds for %s (size %d)"
                 % (args.at, args.at + args.count - 1, args.axis, size))
    with _stdout_to_stderr():
        model.removeLine(args.axis, args.at, args.count)
    out = args.out or args.map
    save_model(model, out)
    print("removed %d %s(s) at index %d; new size %dx%d -> %s" % (
        args.count, args.axis, args.at, model.width, model.height, out))


def cmd_move(args):
    _require_map(args.map)
    _, model = build_model(args.map)
    fx, fy = args.src
    tx, ty = args.dst
    z = args.z if args.z is not None else 0
    try:
        with _stdout_to_stderr():
            result = model.moveObject((fx, fy), (tx, ty), z,
                                      args.model, args.fill_old, args.clear_new)
    except ValueError as e:
        sys.exit("Error: " + str(e))
    out = args.out or args.map
    save_model(model, out)
    extra = []
    if args.clear_new:
        extra.append("cleared destination footprint")
    if args.fill_old:
        extra.append("backfilled origin with %s" % args.fill_old)
    suffix = (" [" + "; ".join(extra) + "]") if extra else ""
    names = ",".join(result['names'])
    print("moved %d square(s) [%s] from (%d,%d) to (%d,%d) at z=%d%s -> %s" % (
        result['count'], names, fx, fy, tx, ty, z, suffix, out))


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #

def _rect(value):
    parts = value.split()
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--rect expects 4 integers: 'x y w h'")
    try:
        return [int(p) for p in parts]
    except ValueError:
        raise argparse.ArgumentTypeError("--rect values must be integers")


def _coord(value):
    parts = value.split()
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("expects 2 integers: 'x y'")
    try:
        return [int(p) for p in parts]
    except ValueError:
        raise argparse.ArgumentTypeError("coordinate values must be integers")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="bwe_cli",
        description="Headless CLI for BananaWorldEditor.")
    sub = parser.add_subparsers(dest="command", required=True)

    jsonparent = argparse.ArgumentParser(add_help=False)
    jsonparent.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    p = sub.add_parser("list-objects", parents=[jsonparent],
                       help="list all placeable object types (name, size, categories, props)")
    p.add_argument("--category", help="only objects in this category")
    p.set_defaults(func=cmd_list_objects)

    p = sub.add_parser("list-generators", parents=[jsonparent],
                       help="list available generators, their descriptions and options")
    p.set_defaults(func=cmd_list_generators)

    p = sub.add_parser("describe", parents=[jsonparent],
                       help="summarize a map: size, basePrefab, z-levels, per-model counts")
    p.add_argument("map", help="path to the map JSON file")
    p.set_defaults(func=cmd_describe)

    p = sub.add_parser("dump", parents=[jsonparent],
                       help="list squares in a map, optionally filtered by model, z-level and rect")
    p.add_argument("map", help="path to the map JSON file")
    p.add_argument("--z", type=int, help="only squares at this z-level")
    p.add_argument("--model", help="only squares of this model (find all of one type)")
    p.add_argument("--rect", type=_rect, metavar='"x y w h"',
                   help="only squares inside this rectangle")
    p.set_defaults(func=cmd_dump)

    p = sub.add_parser("render", parents=[jsonparent],
                       help="draw the map as an ASCII grid (one glyph per model, "
                            "footprints marked) with a legend")
    p.add_argument("map", help="path to the map JSON file")
    p.add_argument("--z", type=int, default=None,
                   help="render only this z-level; omit to show the topmost layer per cell")
    p.add_argument("--rect", type=_rect, metavar='"x y w h"',
                   help="render only this rectangle")
    p.set_defaults(func=cmd_render)

    # --- mutating commands --- #
    outparent = argparse.ArgumentParser(add_help=False)
    outparent.add_argument("--out", help="write result here instead of editing in place")

    p = sub.add_parser("new", parents=[outparent],
                       help="create a new empty map of the given size")
    p.add_argument("map", help="path to the map JSON file to create")
    p.add_argument("--size", type=int, nargs=2, required=True, metavar=("W", "H"))
    p.add_argument("--base-prefab", default=None,
                   help="root prefab for the runtime loader (e.g. House); omit for terrain")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("fill", parents=[outparent],
                       help="replace everything in a rect with one model (z-correct)")
    p.add_argument("map")
    p.add_argument("--rect", type=_rect, required=True, metavar='"x y w h"')
    p.add_argument("--z", type=int, default=None)
    p.add_argument("--model", required=True)
    p.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=None)
    p.set_defaults(func=cmd_fill)

    p = sub.add_parser("border", parents=[outparent],
                       help="draw a ring of one model around a rect")
    p.add_argument("map")
    p.add_argument("--rect", type=_rect, required=True, metavar='"x y w h"')
    p.add_argument("--z", type=int, default=None)
    p.add_argument("--model", required=True)
    p.add_argument("--width", type=int, default=1, help="border thickness (default 1)")
    p.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=None)
    p.set_defaults(func=cmd_border)

    p = sub.add_parser("place", parents=[outparent],
                       help="add a single object (a layer) at one cell")
    p.add_argument("map")
    p.add_argument("--at", type=int, nargs=2, required=True, metavar=("X", "Y"))
    p.add_argument("--z", type=int, default=None)
    p.add_argument("--model", required=True)
    p.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=None)
    p.add_argument("--prop", action="append", metavar="KEY=VALUE",
                   help="additional property (repeatable)")
    p.set_defaults(func=cmd_place)

    p = sub.add_parser("delete", parents=[outparent],
                       help="delete squares in a rect (optionally only one model)")
    p.add_argument("map")
    p.add_argument("--rect", type=_rect, required=True, metavar='"x y w h"')
    p.add_argument("--z", type=int, default=None)
    p.add_argument("--model", default=None, help="only delete this model; omit to delete all")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("setprop", parents=[outparent],
                       help="set properties on all squares of one model in a rect")
    p.add_argument("map")
    p.add_argument("--rect", type=_rect, required=True, metavar='"x y w h"')
    p.add_argument("--z", type=int, default=None)
    p.add_argument("--model", required=True, help="only squares of this model are changed")
    p.add_argument("--prop", action="append", required=True, metavar="KEY=VALUE",
                   help="property to set (repeatable); rotation/model are base props, "
                        "anything else is an additionalProperty")
    p.set_defaults(func=cmd_setprop)

    p = sub.add_parser("delprop", parents=[outparent],
                       help="delete additionalProperties from all squares of one model "
                            "in a rect (setprop's inverse)")
    p.add_argument("map")
    p.add_argument("--rect", type=_rect, required=True, metavar='"x y w h"')
    p.add_argument("--z", type=int, default=None)
    p.add_argument("--model", required=True, help="only squares of this model are changed")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--prop", action="append", metavar="KEY",
                     help="additionalProperty key to delete (repeatable); base props "
                          "rotation/model cannot be deleted")
    grp.add_argument("--all", action="store_true",
                     help="delete ALL additionalProperties (reset the object to none)")
    p.set_defaults(func=cmd_delprop)

    p = sub.add_parser("wall-frame", parents=[outparent],
                       help="generate walls + corners around a rect (House)")
    p.add_argument("map")
    p.add_argument("--rect", type=_rect, required=True, metavar='"x y w h"')
    p.add_argument("--z", type=int, default=None)
    p.set_defaults(func=cmd_wall_frame)

    p = sub.add_parser("roof-frame", parents=[outparent],
                       help="generate a pitched roof frame around a rect (House)")
    p.add_argument("map")
    p.add_argument("--rect", type=_rect, required=True, metavar='"x y w h"')
    p.add_argument("--z", type=int, default=None)
    p.add_argument("--half", action="store_true", help="use the half-height roof variant")
    p.set_defaults(func=cmd_roof_frame)

    p = sub.add_parser("generate", parents=[outparent],
                       help="run a generator (see list-generators)")
    p.add_argument("map")
    p.add_argument("--name", required=True, help="generator name or class")
    p.add_argument("--set", action="append", metavar="KEY=VALUE",
                   help="override a generator option (repeatable)")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("clear", parents=[outparent],
                       help="clear a generator's output (see list-generators)")
    p.add_argument("map")
    p.add_argument("--name", required=True, help="generator name or class")
    p.set_defaults(func=cmd_clear)

    p = sub.add_parser("insert", parents=[outparent],
                       help="insert rows/columns to grow the map (prefer the middle "
                            "to preserve the outer forest border)")
    p.add_argument("map")
    p.add_argument("--axis", choices=("row", "col"), required=True,
                   help="'row' inserts horizontal rows; 'col' inserts vertical columns")
    p.add_argument("--at", type=int, required=True, metavar="POS",
                   help="insert BEFORE this row/col index; POS==size appends at the far edge. "
                        "Insert in the middle (not at 0/size) to keep the border ring intact")
    p.add_argument("--count", type=int, default=1,
                   help="how many rows/cols to insert (default 1)")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--fill", metavar="MODEL",
                     help="fill new cells with this single model at z=0 (e.g. Grass)")
    grp.add_argument("--copy-from", type=int, metavar="POS", dest="copy_from",
                     help="duplicate the full content (all layers/z) of this existing "
                          "row/col into each new one - the cleanest way to reproduce a "
                          "border ring (copy an interior line that already has Forest at its ends)")
    p.set_defaults(func=cmd_insert)

    p = sub.add_parser("remove", parents=[outparent],
                       help="remove rows/columns to shrink the map")
    p.add_argument("map")
    p.add_argument("--axis", choices=("row", "col"), required=True)
    p.add_argument("--at", type=int, required=True, metavar="POS",
                   help="first row/col index to remove")
    p.add_argument("--count", type=int, default=1,
                   help="how many rows/cols to remove (default 1)")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("move", parents=[outparent],
                       help="relocate the object(s) at one cell to another cell")
    p.add_argument("map")
    p.add_argument("--from", type=_coord, required=True, dest="src", metavar='"X Y"')
    p.add_argument("--to", type=_coord, required=True, dest="dst", metavar='"X Y"')
    p.add_argument("--z", type=int, default=None)
    p.add_argument("--model", default=None,
                   help="only move squares of this model at the cell (default: every layer)")
    p.add_argument("--fill-old", metavar="MODEL", dest="fill_old",
                   help="backfill the vacated footprint with this model (e.g. Grass)")
    p.add_argument("--clear-new", action="store_true", dest="clear_new",
                   help="delete other squares under the destination footprint "
                        "(e.g. clear Grass so nothing shows under a moved house)")
    p.set_defaults(func=cmd_move)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # Resolve paths against the original cwd before chdir.
    if getattr(args, "map", None) is not None:
        args.map = _abs_from_orig(args.map)
    if getattr(args, "out", None) is not None:
        args.out = _abs_from_orig(args.out)

    os.chdir(EDITOR_ROOT)
    if EDITOR_ROOT not in sys.path:
        sys.path.insert(0, EDITOR_ROOT)

    args.func(args)


if __name__ == "__main__":
    main()
