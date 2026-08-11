# The Google Hotels `batchexecute` protocol

This document is the project's reverse-engineering record: everything
`ghotels` knows about the wire format, in one place. If Google shifts a slot,
fix `src/ghotels/protocol/` and update this file in the same PR.

Provenance: the protocol was originally mapped by the
[stays](https://github.com/him229/stays) project by intercepting the Google
Hotels UI's own XHR traffic (Playwright capture runs) and live probing.
`ghotels` re-derived its implementation against those documented findings and
re-verifies them with live tests (`pytest --live -m live`).

## Transport

| Item | Value |
|---|---|
| Endpoint | `POST https://www.google.com/_/TravelFrontendUi/data/batchexecute` |
| RPC id | `AtySUc` (serves both search and detail) |
| Content type | `application/x-www-form-urlencoded;charset=UTF-8` |
| TLS | Chrome impersonation via `curl_cffi` (plain `requests` gets blocked quickly) |
| Anti-bot signals | response containing `/sorry/` or "unusual traffic" |

## Request envelope

The form body is a single field:

```
f.req=<urlencoded JSON>
```

where the JSON is:

```
[[["AtySUc", "<inner payload as a JSON string>", null, "1"]]]
```

The inner payload is double-encoded: built as a nested list, dumped to a JSON
string, embedded in the envelope, and the whole envelope dumped again.

## Inner payload (request)

```
[query, SearchParams, RequestMeta]
```

- **`[0]` query** — free text, sent verbatim (`"tokyo hotels"`).
- **`[1]` SearchParams** — see below.
- **`[2]` RequestMeta** — `[1, null, null, null, null, entity_key | null, 13, null, 0]`.
  Must always be present: Google silently **ignores all filters** when it is
  missing. Slot `[2][5]` routes the RPC — `null` means list-view search, an
  entity key (opaque base64 token from a prior search result) switches the
  same RPC into single-hotel detail mode.

### SearchParams — `[1]`

```
[property_type, party_block, place_and_stay, null, filters_record]
```

| Slot | Content |
|---|---|
| `[1][0]` | Property type: `1` hotels, `2` vacation rentals. Always sent. |
| `[1][1]` | Party block; `null` for the default 2 adults / no children. |
| `[1][2]` | `[place_slot, stay_slot]`; `null` when neither is set. |
| `[1][3]` | Reserved, always `null`. |
| `[1][4]` | Filters record. |

**Party block `[1][1]`** — `[party, 1]` where `party` has one `[3]` marker
per adult followed by one `[low, high]` age-bucket pair per child. Observed
buckets: ages 2–12 → `[2, 12]` (confirmed from captures); `[0, 1]` and
`[13, 17]` follow the same boundary pattern.

**Place slot `[1][2][0]`** — `null` unless the location is pinned:
`[null, [[kgmid, null, null, null, null, fid, display_name]], []]`. The pin
only takes effect when the query text is neutral; a query naming a city wins
over the pin.

**Stay slot `[1][2][1]`** —
`[null, [[Y,M,D], [Y,M,D], nights], null, null, null, [null, child_count]]`.
Adults are *not* carried here — they travel in the party block.

### Filters record — `[1][4]`

```
[filter_details, null, [], price_slot, (min_rating), (special_offers)]
```

- Positions 4 and 5 are trailing toggles: a minimum-guest-rating id appends
  at 4; the special-offers flag appends `1` at 5 (with a `null` placeholder
  at 4 when no rating filter is set).

**Filter details `[1][4][0]`** (8 elements, 10 when eco-certified):

| Pos | Content |
|---|---|
| 0 | Amenity ids, or `null` — see table below |
| 1 | Star classes sorted ascending (`[4, 5]`), or `null` |
| 2 | Reserved, `null` in every capture |
| 3 | Free cancellation: `1` or `null` |
| 4 | Sort id: `3` lowest price, `8` highest rating, `13` most reviewed, `null` relevance (the default has no wire value) |
| 5 | Reserved, `null` in every capture |
| 6 | ISO 4217 currency string, always present |
| 7 | Brands, or `null` — see below |
| 8 | (eco only) `null` |
| 9 | (eco only) `1` |

**Price slot `[1][4][3]`** — `[[null, min] | null, [null, max] | null, 1]` in
the *preset-chip* encoding: dollar amounts are sent directly. (The UI's
slider-drag emits a different, percentile-indexed encoding — not used here.)
`[null, null, 1]` means no price band.

**Minimum guest rating `[1][4][4]`** — `round(rating * 2)`: 3.5+ → `7`,
4.0+ → `8`, 4.5+ → `9`.

### Amenity ids (confirmed live)

| Amenity | Id | Amenity | Id |
|---|---|---|---|
| Parking (free) | 1 | Bar | 15 |
| Indoor pool | 4 | Pet-friendly | 19 |
| Outdoor pool | 5 | Room service | 22 |
| Pool | 6 | Wi-Fi (free) | 35 |
| Gym | 7 | Air-conditioned | 40 |
| Restaurant | 8 | All-inclusive | 52 |
| Breakfast (free) | 9 | Wheelchair accessible | 53 |
| Spa | 10 | EV charger | 61 |
| Beach access | 11 | Kid-friendly | 12 |

### Brand ids

Brands are sent at `[1][4][0][7]` as `[family_id, [sub_brand_ids...]]`
pairs. **The sub-brand list must be enumerated** — an empty list makes Google
silently ignore the filter (confirmed live: `[[28, []]]` returned non-Hilton
results). Four Seasons (289) is the shape exception: it has no sub-brands and
is sent as a bare `[289]`.

| Family | Id | Sub-brands |
|---|---|---|
| IHG | 17 | 10 ids |
| Best Western | 18 | 6 ids |
| Choice | 20 | 8 ids |
| Hilton | 28 | 15 ids |
| Accor | 33 | 2 ids |
| Hyatt | 37 | 11 ids |
| Marriott | 46 | 23 ids |
| Wyndham | 53 | 13 ids |
| Four Seasons | 289 | none — bare `[289]` |

The exact sub-brand id lists live in `src/ghotels/protocol/ids.py`.
Note: Hyatt/Marriott ids look swapped relative to intuition; the assignment
above was confirmed live (id 37 returns Hyatt properties, id 46 Marriott).

## Response envelope

Responses start with the anti-JSON-hijacking prefix `)]}'` followed by
length-delimited JSON chunks. The payload frame looks like:

```
["wrb.fr", "AtySUc", "<payload JSON string>", null, null, null, "1"]
```

- Frames are tagged `wrb.fr`; the second element is the RPC id.
- The third element is the actual response payload, double-encoded as a JSON
  string (`null`/empty means the request was malformed).
- `ghotels` walks the chunks with a real JSON decoder
  (`ghotels.protocol.response`) instead of regex-scanning, so escapes and
  unicode survive intact.

## Response payload (inner)

The decoded payload's hotel entries live in a large nested list. The slot map
for list-view results and detail responses is documented alongside the
parsers in `src/ghotels/parsing/` (see that package's docstrings), with
captured fixtures under `tests/fixtures/`.

## Operational notes

- **Rate limiting**: stay at or below ~10 requests/second (the
  `GHOTELS_RPS` default). Google blocks aggressively above that.
- **Retries**: 429/5xx/network failures and anti-bot interstitials are
  retryable with exponential backoff; malformed-request errors are not.
- **Filters vanish silently**: if results look unfiltered, check that
  RequestMeta `[2]` is present and that brand pairs carry sub-brand ids.
