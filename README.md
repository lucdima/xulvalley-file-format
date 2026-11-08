# The Xul Valley file format

[Xul Valley](https://xulvalley.com) is an infinite-canvas board app for macOS. It saves a board as a `.xulvalley` document, which is a plain directory of readable JSON that macOS presents as a single file.

This repository documents that format, so that "your boards are yours" is something you can check for yourself. Anyone writing a tool that reads or writes a board can do it without the app, and without guessing.

```
Board.xulvalley/
  board.json              the board itself
  media/<sha256>.<ext>    binary files, named by content hash
  collab/<replica>.json   per-writer merge state (optional, machine-only)
  quicklook/thumbnail.png a picture of the board (optional)
```

`board.json` alone is a complete board. Deleting `collab/` is safe and lossless for a single copy of a document. It costs only the ability to merge that copy against another copy of the same board edited elsewhere.

## What's here

| | |
| --- | --- |
| [`file-format.md`](file-format.md) | The spec. Every key, its type, its default, and the sharp edges. |
| [`board.schema.json`](board.schema.json) | JSON Schema (draft 2020-12) for `board.json`, format version 2. |
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

Past the schema, the validator checks four things a schema has no way to express:

- every media reference resolves to a file whose bytes hash to its own name
- every connector and group points at an item that exists
- the items array is sorted by its order keys
- a `quicklook/thumbnail.png`, if there is one, is a real PNG (a size or shape the app wouldn't write only gets a note)

Without `jsonschema` installed it still checks those, and every key the app cannot open a document without; it just doesn't check value types.

## The samples

**`minimal.xulvalley`** is the smallest board that opens. One key, one item. Everything else falls back to a default.

**`diagram.xulvalley`** has five elements and four connectors. One connector carries a label. One has an end that floats free in space.

**`kitchen-sink.xulvalley`** uses all ten element kinds. Its `media/` folder holds real bytes, so the board opens with nothing missing. It also carries the parts that are easy to get wrong by hand: captions, a group, a locked item, per-character color and emphasis spans, a saved camera position, and the full set of per-document style defaults.

`diagram` and `kitchen-sink` are real app output, so they show the shape of a saved file, down to the keys sitting at their default. They stay at format 1 on purpose, so a newer build may write optional keys they don't have. `minimal` is hand-written, to show how little a board needs.

## What tools can rely on

- **IDs are stable.** An item's or connector's `id` is minted once, at creation. Nothing an editor does to an element rewrites it. Duplicate and paste mint new ids, because a copy is a new object.
- **Key order is deterministic.** The encoder writes pretty-printed with sorted keys, so every object is alphabetical and one field to a line. The same model produces the same bytes on any machine.
- **Edits diff locally.** Nudging a sticky note is a two-line diff, the x and y of that item's `frame`. Depth is a fractional order key, so a reorder renumbers only the elements that actually moved.
- **Defaults are omitted, so a reverted edit is byte-identical.** Cropping an image and then un-cropping it leaves the JSON exactly as if the crop had never happened.
- **`board.json` is regenerated in full on every save.** Every save writes the whole file out of the model held in memory. Rewriting it by hand is legitimate. For now, we recommend closing the board in the app first, and a package with a `collab/` folder needs the same change there too. See [Editing a saved board](file-format.md#editing-a-saved-board).

## Format version

`board.json` carries a top-level `"version"` integer. **The current format is 2**, and an absent key means 1. The one move so far: version 2 (2026-10-18) added the `"crossfade"` and `"fade"` values of `transition`; everything else added since the stamp was a new key, so files kept opening everywhere. The samples here are stamped 1 and use none of the version-2 values, so every build opens them.

A new key does not bump it. Decoding is tolerant across most of the model, so an older build ignores a key it has no slot for and the board opens. A new value in a string-backed enum does bump it, because an unknown string is a decode error that takes the whole file down with it. A build that meets a file stamped higher than its own refuses to open it and says why.

One consequence worth knowing before you write a tool: a key an older build doesn't know is ignored on read, and gone after its next save. A round-trip through an older build can lose a newly added field.

**The schema can still change.** A new key can appear in any release, and a change an older build can't read moves `version`, which is what makes changing it safe.

## Feedback

Found a mistake, or something the app does differently from the spec? Let us know at [xulvalley.com/support](https://xulvalley.com/support/). Pull requests are welcome too. When the spec and the app disagree, the app is right and the spec needs fixing.

## License

MIT, see [LICENSE](LICENSE). The spec, the schema, the samples and the validator are yours to use, including in commercial software that reads or writes `.xulvalley` documents.
