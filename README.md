# The Xul Valley file format

[Xul Valley](https://xulvalley.com) is an infinite-canvas board app for macOS and iPad. It saves a board as a `.xulvalley` document, which is a plain directory of readable JSON that macOS presents as a single file.

This repository documents that format, so that "your boards are yours" is something you can check for yourself. Anyone writing a tool that reads or writes a board can do it without the app, and without guessing.

```
Board.xulvalley/
  board.json              the board itself
  media/<sha256>.<ext>    binary files, named by content hash
  collab/<replica>.json   per-writer merge state (optional, machine-only)
```

`board.json` alone is a complete board. Deleting `collab/` is safe and lossless for a single copy of a document. It costs only the ability to merge that copy against another copy of the same board edited elsewhere.

## What's here

| | |
| --- | --- |
| [`file-format.md`](file-format.md) | The spec. Every key, its type, its default, and the sharp edges. |
| [`board.schema.json`](board.schema.json) | JSON Schema (draft 2020-12) for `board.json`, format version 1. |
| [`samples/`](samples) | Three real documents, from the smallest board that opens to one using every element kind. |
| [`tools/validate.py`](tools/validate.py) | Checks a document against the schema, and against what a schema cannot say. |

## Try it

```sh
# Read a board
cat samples/diagram.xulvalley/board.json

# Check one (any .xulvalley document, including your own)
pip install jsonschema
python3 tools/validate.py --strict samples/*.xulvalley
```

Past the schema, the validator checks three things a schema has no way to express:

- every media reference resolves to a file whose bytes hash to its own name
- every connector and group points at an item that exists
- the items array is sorted by its order keys

Without `jsonschema` installed it still checks those, and every key the app cannot open a document without; it just doesn't check value types.

## The samples

**`minimal.xulvalley`** is the smallest board that opens. One key, one item. Everything else falls back to a default.

**`diagram.xulvalley`** has five elements and four connectors. One connector carries a label. One has an end that floats free in space.

**`kitchen-sink.xulvalley`** uses all ten element kinds. Its `media/` folder holds real bytes, so the board opens with nothing missing. It also carries the parts that are easy to get wrong by hand: captions, a group, a locked item, per-character color and emphasis spans, a saved camera position, and the full set of per-document style defaults.

`diagram` and `kitchen-sink` are byte-identical to what the app's own encoder writes, so they show the exact shape of a saved file, down to the keys sitting at their default. `minimal` is hand-written, to show how little a board needs.

## What tools can rely on

- **IDs are stable.** An item's or connector's `id` is minted once, at creation. Nothing an editor does to an element rewrites it. Duplicate and paste mint new ids, because a copy is a new object.
- **Key order is deterministic.** The encoder writes pretty-printed with sorted keys, so every object is alphabetical and one field to a line. The same model produces the same bytes on any machine.
- **Edits diff locally.** Nudging a sticky note is a two-line diff, the x and y of that item's `frame`. Depth is a fractional order key, so a reorder renumbers only the elements that actually moved.
- **Defaults are omitted, so a reverted edit is byte-identical.** Cropping an image and then un-cropping it leaves the JSON exactly as if the crop had never happened.
- **`board.json` is regenerated in full on every save.** Every save writes the whole file out of the model held in memory. Rewriting it by hand is legitimate, and the app reads what you wrote.

## Format version

`board.json` carries a top-level `"version"` integer. **The current format is 1**, and an absent key means 1.

A new key does not bump it. Decoding is tolerant across most of the model, so an older build ignores a key it has no slot for and the board opens. A new value in a string-backed enum does bump it, because an unknown string is a decode error that takes the whole file down with it. A build that meets a file stamped higher than its own refuses to open it and says why.

One consequence worth knowing before you write a tool: a key an older build doesn't know is ignored on read, and gone after its next save. A round-trip through an older build can lose a newly added field.

**The schema is pre-1.0 and will change before the app is released.** The `version` key is what makes changing it safe. It is no promise that the schema will stay put.

## Feedback

Issues and pull requests are welcome, especially "the spec says X but the app does Y". The app's source is closed. This repository is open, and the spec is written against the app's own model. Where the two disagree, the code is right and the spec is stale.

## License

MIT, see [LICENSE](LICENSE). The spec, the schema, the samples and the validator are yours to use, including in commercial software that reads or writes `.xulvalley` documents.
