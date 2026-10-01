#!/usr/bin/env python3
"""Validate .xulvalley documents against board.schema.json.

    python3 tools/validate.py samples/*.xulvalley
    python3 tools/validate.py --strict path/to/My\\ Board.xulvalley

Beyond the schema, this checks the things a schema cannot express: that media
references resolve to files whose bytes hash to their own name, that ids
referenced by connectors and groups exist, and that the items array is sorted by
its order keys.

The full JSON Schema check needs `pip install jsonschema`. Without it the
structural checks still run, and so does a check of every key the app cannot open
a document without.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(os.path.dirname(HERE), "board.schema.json")

# Keys each object may carry. The app ignores keys it doesn't know, so an unknown
# key is not an error — but it is almost always a typo, which --strict reports.
KNOWN = {
    "board": {"version", "items", "connectors", "background", "pattern", "patternColor",
              "viewport", "transition", "slidePause", "autoplayLoop", "hudPosition",
              "styleDefaults", "groups"},
    "item": {"id", "frame", "rotation", "content", "groupID", "locked", "caption", "z"},
    "connector": {"id", "from", "to", "points", "color", "width", "routing", "dash",
                  "startArrow", "endArrow", "label", "labelPosition", "labelBackground", "above"},
}
# Keys the app cannot open a document without. Every other key has a default and may
# be left out. Kept here as well as in the schema so the check runs without jsonschema.
REQUIRED = {
    "board": ["items"],
    "item": ["id", "frame", "content"],
    "connector": ["id", "from", "to"],
    "group": ["id"],
    "viewport": ["center", "scale"],
    "image": ["media", "naturalSize"],
    "video": ["media", "naturalSize"],
    "audio": ["media"],
    "pdf": ["media", "naturalSize", "pageCount"],
    "link": ["url"],
}
KINDS = {"text", "shape", "note", "image", "video", "audio", "pdf", "slide", "link", "table"}
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def order_value(key):
    """Sort key for an OrderKey: shorter keys compare as if right-padded with 0."""
    return [ALPHABET.index(c) for c in key]


def bad_order_keys(keys):
    """The keys carrying characters outside base 62, which the app refuses to decode."""
    return [k for k in keys if any(c not in ALPHABET for c in k)]


def media_names(content):
    """Every media filename an item's content references."""
    for kind, payload in content.items():
        body = payload.get("_0", {})
        for field in ("media", "originalMedia", "imageMedia"):
            if isinstance(body, dict) and body.get(field):
                yield body[field]


def check_package(path, strict=False, schema=None):
    problems = []
    board_path = os.path.join(path, "board.json")
    if not os.path.isfile(board_path):
        return ["no board.json — is this a .xulvalley package?"]
    with open(board_path) as f:
        try:
            board = json.load(f)
        except json.JSONDecodeError as e:
            return ["board.json is not valid JSON: %s" % e]

    if schema is not None:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema)
        for e in sorted(validator.iter_errors(board), key=lambda e: list(e.path)):
            where = "/".join(str(p) for p in e.path) or "(root)"
            problems.append("schema: %s: %s" % (where, e.message))

    def need(obj, kind, where):
        if not isinstance(obj, dict):
            problems.append("%s is not an object" % where)
            return
        for key in REQUIRED[kind]:
            if key not in obj:
                problems.append("%s has no %r — required, the app will not open this"
                                % (where, key))

    need(board, "board", "board")
    if "viewport" in board:
        need(board["viewport"], "viewport", "viewport")
    for i, it in enumerate(board.get("items", [])):
        where = "item %s" % (it.get("id", "#%d" % i) if isinstance(it, dict) else "#%d" % i)
        need(it, "item", where)
        content = it.get("content") if isinstance(it, dict) else None
        if isinstance(content, dict):
            for kind, payload in content.items():
                if kind in REQUIRED and isinstance(payload, dict):
                    need(payload.get("_0"), kind, "%s (%s)" % (where, kind))
    for i, c in enumerate(board.get("connectors", [])):
        need(c, "connector", "connector %s" % (c.get("id", "#%d" % i) if isinstance(c, dict) else "#%d" % i))
    for i, g in enumerate(board.get("groups", [])):
        need(g, "group", "group #%d" % i)

    items = board.get("items", [])
    ids = {i.get("id") for i in items if isinstance(i, dict)}

    # Order keys: the array is kept sorted by them, and ties are not allowed.
    keyed = [i.get("z") for i in items if isinstance(i, dict) and i.get("z")]
    if keyed and len(keyed) != len(items):
        problems.append("some items carry a z key and some do not — write it on every "
                        "item or on none")
    bad = bad_order_keys(keyed)
    for k in bad:
        problems.append("z key %r has characters outside 0-9A-Za-z" % k)
    if keyed and not bad:
        if len(set(keyed)) != len(keyed):
            problems.append("duplicate z keys: %s" % ", ".join(
                sorted({k for k in keyed if keyed.count(k) > 1})))
        ordered = sorted(keyed, key=order_value)
        if ordered != keyed:
            problems.append("items are not in z order (paint order is the z key, and the "
                            "array is kept sorted by it)")

    # Media: every reference resolves, every blob is referenced, every name is its hash.
    referenced = set()
    for it in items:
        if isinstance(it, dict) and isinstance(it.get("content"), dict):
            referenced.update(media_names(it["content"]))
    folder = os.path.join(path, "media")
    present = set(os.listdir(folder)) if os.path.isdir(folder) else set()
    present.discard(".DS_Store")
    for name in sorted(referenced - present):
        problems.append("media/%s is referenced but missing" % name)
    for name in sorted(present - referenced):
        problems.append("media/%s is not referenced by any item (dropped on next save)" % name)
    for name in sorted(referenced & present):
        digest = hashlib.sha256(open(os.path.join(folder, name), "rb").read()).hexdigest()
        if name.split(".")[0] != digest:
            problems.append("media/%s does not hash to its own name (expected %s)"
                            % (name, digest))

    # Cross-references.
    groups = {g.get("id") for g in board.get("groups", []) if isinstance(g, dict)}
    for it in items:
        gid = it.get("groupID") if isinstance(it, dict) else None
        if gid and gid not in groups:
            problems.append("item %s is in group %s, which has no entry in groups"
                            % (it.get("id"), gid))
    for c in board.get("connectors", []):
        if not isinstance(c, dict):
            continue
        for end in ("from", "to"):
            att = (c.get(end) or {}).get("attached")
            if att and att.get("item") not in ids:
                problems.append("connector %s is attached to %s, which is not an item"
                                % (c.get("id"), att.get("item")))
        if c.get("above") and c["above"] not in ids:
            problems.append("connector %s sits above %s, which is not an item"
                            % (c.get("id"), c["above"]))

    if strict:
        for key in sorted(set(board) - KNOWN["board"]):
            problems.append("unknown board key %r (ignored by the app)" % key)
        for it in items:
            for key in sorted(set(it) - KNOWN["item"]):
                problems.append("unknown item key %r on %s" % (key, it.get("id")))
            kinds = set(it.get("content", {}))
            for k in sorted(kinds - KINDS):
                problems.append("unknown item kind %r on %s" % (k, it.get("id")))
        for c in board.get("connectors", []):
            for key in sorted(set(c) - KNOWN["connector"]):
                problems.append("unknown connector key %r on %s" % (key, c.get("id")))

    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packages", nargs="+", help="one or more .xulvalley documents")
    ap.add_argument("--strict", action="store_true",
                    help="also report keys the app would ignore (usually typos)")
    args = ap.parse_args()

    schema = None
    try:
        import jsonschema  # noqa: F401
        with open(SCHEMA) as f:
            schema = json.load(f)
    except ImportError:
        print("note: jsonschema is not installed — checking required keys and structure "
              "only, not value types (pip install jsonschema)\n", file=sys.stderr)

    failed = 0
    for path in args.packages:
        problems = check_package(path.rstrip("/"), strict=args.strict, schema=schema)
        name = os.path.basename(path.rstrip("/"))
        if problems:
            failed += 1
            print("✗ %s" % name)
            for p in problems:
                print("    %s" % p)
        else:
            print("✓ %s" % name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
