<!-- Generated from docs/file-format.md in the Xul Valley app repository by
     Tools/syncformat.sh. Edit it there; changes made here are overwritten. -->
# The `.xulvalley` file format

A key-by-key reference for `board.json`, the readable half of a Xul Valley document.

This is the schema, written for someone outside the app: a script, an AI agent, a future importer, or a person hand-editing a board in a text editor. It covers what each key means and what the app does with it. It does not cover why the app is built the way it is.

Every type named below is a Swift type of the same name in the app's own model, which is the source of truth. Where the two disagree, the code is right and this file is stale.

## The package

A document is a file package, a directory macOS presents as a single file, with the `.xulvalley` extension and the UTI `com.lucasdima.xulvalley.document`.

```
Board.xulvalley/
  board.json              the model, everything in this document
  media/<sha256>.<ext>    binary files, named by content hash
  collab/<replica>.json   per-field merge state (optional)
```

Three things a tool outside the app should know:

- **`board.json` alone is a complete board.** A package with no `collab/` opens as precisely what `board.json` says. Deleting `collab/` is safe and lossless for a single copy of a document. It costs only the ability to merge that copy against another copy of the same board edited elsewhere. **If you keep boards in git, ignore `collab/`.** It carries nothing you can read. Its diffs are localized (a stamp changes only for a field that was actually written, so a save with no edits produces no diff at all), but it is machine state, and each replica file holds a whole model, so an N-writer package is roughly N× `board.json`.
- **`board.json` is regenerated in full on every save.** Every save writes the whole file out of the model held in memory. Rewriting it by hand is legitimate; the app reads what you wrote.
- **Media is never inlined.** `media/` holds the bytes under a content-addressed name, `<sha256hex>.<ext>` (extension lowercased). Model fields that name media hold that bare filename. A blob no item references is dropped on the next save.

## Format version

`board.json` carries a top-level `"version"` integer. The current format is **1**.

- The key is stamped by the writer at save time, so it always names the build that actually wrote the file. The build that first created the board leaves no trace.
- **Absent means 1**: files written before the stamp existed, and models that are not saved documents at all (the bundled templates leave the key out entirely).
- A build that meets a file whose `version` is **higher than its own refuses to open it**, and says the board was created with a newer version. The alternative would be opening it and dropping whole elements it has no way to draw.

When the number moves:

| Change | Bump? | Why |
| --- | --- | --- |
| A new **key** on an existing object | No | An older build ignores it and opens the board. |
| A new **value** in a string-backed enum (an item kind, a connector dash, a background pattern) | **Yes** | An older build cannot decode it, and the whole file fails to open. |

The version has not moved yet, so both rows are best read as what *would* happen.

**A new key.** `locked` and `z` were both added to `BoardItem` after boards had already been saved without them. An item written today looks like this:

```json
{ "id": "…", "frame": [[0, 0], [200, 120]], "rotation": 0,
  "content": { "text": { "_0": { "string": "…" } } },
  "locked": true,
  "z": "1V" }
```

A build from before those two fields existed opens that file, ignores the keys it has no slot for, and draws the text at the right place with the right words. It shows that item unlocked, and it takes depth from array order. Everything the user made is on the board, so the version stays where it is.

**A new value.** Say a later build adds a `"sticker"` item kind, or a fourth connector dash:

```json
"content": { "sticker": { "_0": { "string": "…" } } }
"dash": "dashDot"
```

A build that has never heard of `sticker` has no way to skip that one item and carry on. The unknown string is a decode error, the error comes out of the whole `items` array, and the document fails to open. This is the case the stamp exists for.

The enums stay strict on purpose. Loosening them would let the file open, drop the value the old build didn't understand, and make that permanent on the next save. A refused file stays intact until a build that understands it comes along. Content dropped on save is gone for good. The stamp is what turns that failure into a sentence a user can act on.

## Shared encodings

These appear throughout.

| Type | JSON | Example |
| --- | --- | --- |
| `RGBAColor` | `"#RRGGBBAA"`, uppercase hex, alpha always present | `"#FBF8F2FF"` |
| `CGPoint` | `[x, y]` | `[120, -40]` |
| `CGSize` | `[width, height]` | `[640, 480]` |
| `CGRect` | `[[x, y], [width, height]]` | `[[-720, -430], [700, 52]]` |
| `UUID` | uppercase hyphenated string | `"00000002-0000-4000-8000-000000000001"` |
| `OrderKey` | a base-62 string, `0-9A-Za-z` | `"1V"` |
| Enum with a payload | one key naming the case; unlabeled payloads are `_0` | `{"text": {"_0": {…}}}` |

All coordinates are **world coordinates** on the infinite canvas plane. They are never screen points, and never relative to another item. The plane has no origin corner: negative coordinates are ordinary. Angles (`rotation`) are **degrees, clockwise**, about the frame's center.

## Board

The top-level object.

| Key | Type | Required | Default |
| --- | --- | --- | --- |
| `version` | int | no | absent = 1 |
| `items` | `[BoardItem]` | **yes** | none |
| `connectors` | `[Connector]` | no | `[]` |
| `background` | `RGBAColor` | no | canvas background |
| `pattern` | `"none"` \| `"dots"` \| `"grid"` \| `"lines"` | no | `"dots"` |
| `patternColor` | `RGBAColor` | no | pattern gray |
| `viewport` | `{ "center": CGPoint, "scale": number }` | no | absent. Both keys required when present. |
| `transition` | `"ease"` \| `"fly"` \| `"direct"` | no | absent = `"ease"` |
| `slidePause` | int (seconds) | no | absent = 3, clamped to a 1-second minimum |
| `autoplayLoop` | bool | no | absent |
| `hudPosition` | `"topLeading"` \| `"top"` \| `"topTrailing"` \| `"leading"` \| `"center"` \| `"trailing"` \| `"bottomLeading"` \| `"bottom"` \| `"bottomTrailing"` | no | absent = `"bottomTrailing"` |
| `styleDefaults` | `BoardStyleDefaults` | no | absent |
| `groups` | `[BoardGroup]` | no | omitted when empty |

`hudPosition` is where the presenter HUD sits while presenting — per-document, because the corner that stays out of the way depends on where the board puts its content. It is the one key here decoded through its **raw value** rather than as its enum: a position string this build has no case for falls back to the default instead of failing the open, since a newer build's chrome choice is no reason to refuse a file. New boards are seeded from an app preference; every board after that answers for itself.

`items` is the only key a board cannot be written without. `viewport` records pan and zoom so reopening restores the camera. It is the one key that changes when the user only *looked* around, so expect it in diffs after a scroll.

`groups` is membership metadata only: an item's own `groupID` is what puts it in a group. A `BoardGroup` is `{ "id": UUID, "rotation": number }`; `id` is required, `rotation` defaults to `0`.

`styleDefaults` (`BoardStyleDefaults`) is the per-document "what a new shape/text/note/connector/table/caption looks like", 53 flat keys tracking the last style used. See [Style defaults](#style-defaults).

## Style defaults

`styleDefaults` is one flat object of 53 optional keys: the look a newly created element inherits **on this board**. Every whole-element style edit writes them back, so they track the last style used. Absent means the factory value, and an absent object means all of them.

| Group | Keys |
| --- | --- |
| Shape | `shapeHasFill`, `shapeFill`, `shapeHasBorder`, `shapeStroke`, `shapeStrokeWidth`, `shapeRandomStyle` |
| Shape label | `shapeLabelColor`, `shapeLabelFont`, `shapeLabelFace`, `shapeLabelOutlineEnabled`, `shapeLabelOutlineColor`, `shapeLabelOutlineWidth` |
| Note | `noteColor`, `noteTextColor`, `noteFont`, `noteFace`, `noteSize` |
| Text | `textFont`, `textFace`, `textSize`, `textColor`, `textOutlineEnabled`, `textOutlineColor`, `textOutlineWidth` |
| Connector | `connectorColor`, `connectorWidth`, `connectorRouting`, `connectorDash`, `connectorStartArrow`, `connectorEndArrow` |
| Caption | `captionColor`, `captionFont`, `captionFace`, `captionSize`, `captionBackground`, `captionBackgroundOpacity` |
| Slide | `slideAspect` |
| Table | `tableFill`, `tableTextColor`, `tableFont`, `tableFace`, `tableTextSize`, `tableGridColor`, `tableGridWidth`, `tableRandomStyle` |
| Table header & banding | `tableHeaderEnabled`, `tableHeaderHasFill`, `tableHeaderFill`, `tableHeaderTextColor`, `tableHeaderBold`, `tableHeaderSizeScale`, `tableBandEnabled`, `tableBandFill` |

The names say the types: anything ending `Color`, `Fill`, `Stroke` or `Background` is an `RGBAColor`; `Font` and `Face` are strings; `Width`, `Size`, `Scale` and `Opacity` are numbers; the rest are bools. The three exceptions are `connectorRouting`, `connectorDash` and `slideAspect`, which take the same values as the element fields of those names.

Four things to know before writing them:

- **`shapeLabelFont`, `textFace` and the other font keys are empty strings when unset**, meaning the system font. `TextContent` uses an absent key for the same thing.
- **A color or width survives its own switch.** `textOutlineColor` is retained while `textOutlineEnabled` is false, the same retain pattern the element fields use.
- **`shapeRandomStyle` and `tableRandomStyle` override the concrete fields beside them.** Each new shape (or table) is born from a fresh random roll. Choosing any concrete style again clears the flag.
- **A shape's label has no size of its own** and shares `textSize`. A caption does have one: `captionSize` exists because caption type wants to read smaller than body text.

## Item

An entry in `items`.

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID | **yes** | Stable for the life of the item. See [Guarantees](#guarantees-for-tools). |
| `frame` | `CGRect` | **yes** | Bounding box in world space, always axis-aligned. |
| `rotation` | number | no | Absent = `0`. Degrees clockwise about the frame's center. The app always writes it. |
| `content` | `ItemContent` | **yes** | The payload; one key, named for the kind. |
| `groupID` | UUID | no | Group membership; absent = ungrouped. |
| `locked` | bool | no | Omitted when `false`. Blocks editing. The item stays selectable. |
| `caption` | `ItemCaption` | no | Only meaningful on media kinds. |
| `z` | `OrderKey` | no | Paint order. Absent = unassigned; the app fills it in on open. |

**Z-order is the `z` key.** The array is kept sorted by `z`, so reading it in order gives back-to-front paint order, and the key is what carries the intent. Two items tying on `z` are broken by UUID, and the app remints one of them so the tie can't recur.

Assigning `z` by hand is allowed: any base-62 string sorts by the obvious lexicographic rule, and the app fits new keys into the gaps between existing ones. Leaving `z` out entirely is also fine. Array order is then taken as the intent, and keys are minted from it.

## Item content

`content` is a single-key object naming one of ten kinds, whose payload sits under `_0`:

```json
"content": { "note": { "_0": { "string": "…", "noteColor": "#FFE28AFF" } } }
```

The kinds are `text`, `shape`, `note`, `image`, `video`, `audio`, `pdf`, `slide`, `link` and `table`. **Adding a kind bumps the format version** (see above).

### `text` (`TextContent`)

The same type serves as a shape's label, a connector's label, a caption's text and a table cell's styling, so this table applies in five places.

| Key | Type | Default |
| --- | --- | --- |
| `string` | string | `""` |
| `fontSize` | number | `24` |
| `fontFamily` | string? | absent = system font |
| `fontFace` | string? | absent |
| `bold`, `italic`, `underline`, `strikethrough` | bool | `false` |
| `alignment` | `"leading"` \| `"center"` \| `"trailing"` | `"leading"` |
| `color` | `RGBAColor` | text color |
| `colorSpans` | `[TextColorSpan]` | `[]` |
| `highlight` | `RGBAColor`? | absent |
| `highlightSpans` | `[TextColorSpan]` | `[]` |
| `emphasisSpans` | `[TextEmphasisSpan]` | `[]` |
| `outline` | `TextOutline`? | absent |
| `width` | number? | absent = content-sized |
| `height` | number? | absent = hugs the text; a value is a **minimum** box height (the box still grows to fit; a text box never clips) |

A `TextColorSpan` is `{ "start": int, "length": int, "color": RGBAColor }`, with offsets in characters. A `TextEmphasisSpan` is `{ "start", "length" }` plus any of `bold`, `italic`, `underline`, `strikethrough` as optional bools, where an absent trait means "inherit". A `TextOutline` is `{ "enabled": bool, "color": RGBAColor, "width": number }`, each optional (defaults `true`, white, `2`).

### `shape` (`ShapeContent`)

| Key | Type | Default |
| --- | --- | --- |
| `kind` | `"rectangle"` \| `"ellipse"` \| `"triangle"` \| `"roundedRectangle"` \| `"diamond"` \| `"vector"` | `"rectangle"` |
| `vector` | `VectorGlyph`? | absent; required in practice when `kind` is `"vector"` |
| `hasFill` | bool | `true` |
| `fillColor` | `RGBAColor` | shape fill |
| `hasBorder` | bool | `true` |
| `stroke` | `RGBAColor` | shape stroke |
| `strokeWidth` | number | `2` |
| `cornerRadius` | number | `16` (only meaningful for `roundedRectangle`) |
| `showsLabel` | bool | `true` |
| `label` | `TextContent`? | absent = no label |
| `labelVerticalAlignment` | `"top"` \| `"center"` \| `"bottom"` | `"center"` |
| `flipH`, `flipV` | bool | `false` |

`hasFill`, `hasBorder` and `showsLabel` are switches. The color, width and label text are retained while they are off, so turning one back on restores what was there.

A `VectorGlyph` is inlined into the document. Path data is small, and keeping it in the file means the document still draws if a catalog entry is ever retired.

```json
{ "id": "lucide.tree", "name": "Tree", "tags": ["plant"], "category": "Nature",
  "size": [1000, 1000],
  "paths": [ { "d": "M500 100…", "rule": "nonZero" } ] }
```

`id`, `name`, `size` and `paths` are required; `tags` and `category` default to empty. A path's `rule` is `"nonZero"` (the default) or `"evenOdd"`, where the even-odd rule makes an inner contour cut a hole. Coordinates in `d` live in the glyph's own `size` box (normalized to a 1000-unit side). Catalog ids are **never reused or renamed**: an id is part of the file format the way a font name is.

### `note` (`NoteContent`)

| Key | Type | Default |
| --- | --- | --- |
| `string` | string | `""` |
| `noteColor` | `RGBAColor` | note yellow |
| `textColor` | `RGBAColor` | text color |
| `fontSize` | number | `20` (clamped to 6…800 on read) |
| `fontFamily` | string | absent = system font |
| `fontFace` | string | absent = the family's default face |
| `bold`, `italic` | bool | `false` |
| `alignment` | `"leading"` \| `"center"` \| `"trailing"` | `"leading"` |

Every key is optional on read (since 2026-09-18, when `fontSize`/`fontFamily`/`fontFace` were added and the type gained a lenient decoder).

### `image` (`ImageContent`)

| Key | Type | Default |
| --- | --- | --- |
| `media` | string | **required**. A filename in `media/`. |
| `naturalSize` | `CGSize` | **required** |
| `border` | `ImageBorder`? | absent |
| `cornerRadius` | number | `0` |
| `flipH`, `flipV` | bool | `false` |
| `crop` | `CropRect`? | absent = uncropped |
| `opacity` | number 0…1 | `1` |
| `grayscale` | bool | `false` |
| `originalMedia` | string? | absent. The pre-edit blob, when one is kept. |

A `CropRect` is `{ "x", "y", "width", "height" }` in **unit coordinates** (0…1) of the source image, minimum side 0.02. An `ImageBorder` is `{ "enabled": bool, "color": RGBAColor, "width": number }`, each optional (defaults `true`, shape stroke, `3`).

### `video` (`VideoContent`) and `audio` (`AudioContent`)

`video`: `media` (required), `naturalSize` (required), `border`, `cornerRadius`, `loop`. `audio`: `media` (required), `border`, `cornerRadius`, `loop`.

### `pdf` (`PDFContent`)

`media`, `naturalSize` and `pageCount` are required. `pageIndex` (default `0`), `border`, `cornerRadius` and `showsPageControls` (default `true`) are optional.

### `slide` (`SlideContent`)

`name` (string, default `""`) and `aspect`, one of `"square"`, `"landscape"`, `"portrait"`, `"fourThree"`, `"threeFour"`, `"free"`, default `"landscape"`. A slide is a frame on the canvas that the presentation walks. It holds no children, it just bounds a region.

### `link` (`LinkContent`)

| Key | Type | Default |
| --- | --- | --- |
| `url` | string | **required** |
| `title` | string? | absent |
| `summary` | string? | absent |
| `imageMedia` | string? | absent. The fetched preview image, in `media/`. |
| `imageNaturalSize` | `CGSize`? | absent |
| `showsPreview` | bool | `true` |
| `transparentBackground` | bool | `true` |

`title`, `summary` and `imageMedia` are Open Graph metadata fetched from the URL. This is the app's **only** network path, and it is outbound-only.

### `table` (`TableContent`)

| Key | Type | Notes |
| --- | --- | --- |
| `columns` | `[number]` | Column widths; length = column count. |
| `rows` | `[number]` | Row heights; length = row count. |
| `cells` | `[[TableCellContent]]` | Row-major, `cells[row][column]`. |
| `text` | `TextContent` | The table-wide text style. |
| `fillColor` | `RGBAColor` | |
| `gridColor` | `RGBAColor` | |
| `gridWidth` | number | |

A `TableCellContent` is `{ "string": string }` plus optional `text` (`TextContent`, for a cell that overrides the table style) and `fill` (`RGBAColor`). Cells at their default write only what they carry.

The table is the one kind whose **item `frame` is derived**: it is recomputed from `columns` and `rows` when the document is loaded or mutated. Writing a `frame` that disagrees with the tracks is legal, and the app overwrites it.

Rows and columns have **no identity** (they are bare number arrays), which is why concurrent row inserts cannot merge.

## Caption

An item's optional `caption` is a label drawn **inside** the frame, over one end of a media item, on a translucent scrim. Drawing inside keeps the frame meaning exactly the item: nothing outside it moves, and connectors, borders and export bounds stay untouched.

| Key | Type | Default |
| --- | --- | --- |
| `text` | `TextContent` | required |
| `position` | `"top"` \| `"bottom"` | `"bottom"` |
| `shown` | bool | `true` |
| `background` | `RGBAColor` | caption scrim |
| `backgroundOpacity` | number 0…1 | `0.5`. **0 lays the text straight on the media.** |

Captions are offered by the kinds that carry no text of their own: image, video, audio, pdf and link. The text is a full `TextContent` without the outline halo. The halo exists to make text legible over a busy background, and the scrim already does that job.

## Connector

An entry in `connectors`. Connectors are not items. They have no frame, they reference items, and they sit outside the `items` array.

| Key | Type | Default |
| --- | --- | --- |
| `id` | UUID | required |
| `from`, `to` | `ConnectorEndpoint` | required |
| `points` | `[CGPoint]` | `[]`. User-dragged waypoints. |
| `color` | `RGBAColor` | connector stroke |
| `width` | number | `2` |
| `routing` | `"straight"` \| `"step"` \| `"curved"` | `"curved"` |
| `dash` | `"solid"` \| `"dashed"` \| `"dotted"` | `"solid"` |
| `startArrow` | bool | `false` |
| `endArrow` | bool | `true` |
| `label` | `TextContent`? | absent |
| `labelPosition` | `"horizontal"` \| `"over"` \| `"center"` \| `"under"` | `"horizontal"` |
| `labelBackground` | bool | `true` |
| `above` | UUID? | absent = behind everything |

An endpoint is either attached to an item's edge or free in space:

```json
"from": { "attached": { "item": "0000000C-…-000000000002", "side": "left" } }
"to":   { "free": { "_0": [420, 180] } }
```

`side` is `"top"`, `"right"`, `"bottom"` or `"left"`.

A connector has no slot in the `items` array, so it takes its depth from `above`: the id of the item it draws immediately in front of, or absent for behind everything. Painting the two collections in two passes is wrong. Interleave by `z` and `above`.

## Guarantees for tools

These are the properties a script, a diffing tool or a model can rely on.

- **IDs are stable.** An item's or connector's `id` is minted once, at creation, and never rewritten by moving, resizing, restyling, reordering, saving, reopening or merging. Duplicate and paste mint new ids: a copy is a new object, and sharing an id would make two items fight over one identity. Vector glyph ids are stable across releases too.
- **Key order is deterministic.** The encoder writes with sorted keys and pretty printing, so every object is alphabetical and one field to a line, byte-for-byte reproducible across machines and runs.
- **Edits diff locally.** Nudging a sticky note is a two-line diff, the x and y under that item's `frame`. Reordering renumbers only the items that actually moved, never every index in between, because depth is a fractional key. Restyling one item touches one object.
- **Defaults are omitted, so a reverted edit is byte-identical.** Most content types write only what differs from the default. Cropping an image and then un-cropping it leaves the JSON exactly as if the crop had never happened, with no `"crop"` left behind at its identity value. Round-trips don't accumulate noise.
- **Values a build can't understand are refused.** A key an older build doesn't know is ignored on read and gone after its next save, so a round-trip through an older build can lose newly added fields. See [Format version](#format-version).
- **The readable file is the whole document.** No part of a board lives only in `collab/`.

What is *not* guaranteed: the schema itself is pre-1.0 and will change before release. The `version` key is what makes changing it safe. It is no promise that the schema will stay put.

## Sharp edges

Things to check when writing a board by hand.

- **A key with a default is optional; the rest are required, and that list is short.** Every default in the tables above is applied on read, so a hand-written board may leave those keys out. The keys a board cannot be written without are exactly: `items` on the board; `id`, `frame` and `content` on an item; `id`, `from` and `to` on a connector; `id` on a group; `center` and `scale` on a viewport; `start`, `length` (and `color`, on a color span) on a span; `media` and `naturalSize` on image and video, `media` on audio, plus `pageCount` on pdf; `url` on a link; `text` on a caption; `id`, `name`, `size` and `paths` on a vector glyph, and `d` on a path. A missing required key fails the open. The app itself always writes complete objects, so this only matters for JSON written by hand or by another tool.
- **`frame` on a table is advisory.** It is recomputed from the tracks.
- **`z` and array order can disagree.** The keys win, except when the array order changed relative to the previous state, in which case the array is taken as the intent. If you are generating a board from scratch, pick one: either write `z` on every item or on none.
- **Span offsets are character offsets** into `string`, and never UTF-8 byte offsets. A span that runs past the end of the string is clamped, and the file still opens.
- **Media filenames are content hashes.** Writing a `media` value that names a file not in `media/` leaves an item with no bytes to draw.
