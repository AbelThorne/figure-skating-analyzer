# Skater Merge Feature

## Problem

When a skater's family name changes between competitions (marriage, typo, hyphenation), the import creates separate `Skater` records, splitting their competition history. There is no way to reunify these records.

## Solution

An admin "merge skaters" feature with two parts:

1. **Merge endpoint** — reassign all scores, category results, and user links from source skaters to a target skater, then delete the sources
2. **Alias table** — remember old names so future re-imports automatically resolve to the merged skater

## Data Model

### New table: `skater_aliases`

| Column     | Type         | Constraints                          |
|------------|--------------|--------------------------------------|
| id         | Integer (PK) |                                      |
| first_name | String(255)  | NOT NULL                             |
| last_name  | String(255)  | NOT NULL                             |
| skater_id  | Integer (FK) | → skaters.id, ON DELETE CASCADE      |

- Unique constraint on `(first_name, last_name)` — a name can only alias one skater

## Backend

### `POST /api/skaters/merge` (admin only)

**Request body:**
```json
{
  "target_id": 5,
  "source_ids": [12, 34]
}
```

**Logic (per source skater):**

1. Reassign `Score` records: `UPDATE scores SET skater_id = target_id WHERE skater_id = source_id`. Handle unique constraint conflicts (same competition + skater + category + segment) by deleting the source's duplicate score.
2. Reassign `CategoryResult` records: same approach — reassign, delete on conflict (same competition + skater + category).
3. Reassign `UserSkater` links: reassign to target, skip/delete duplicates (same user + skater).
4. **Flush the session** (`await session.flush()`) — the `Score` and `CategoryResult` FKs do not have `ON DELETE CASCADE`, so all reassignments must be committed before deleting the source skater.
5. Fill blank metadata on target from source: for each of `club`, `nationality`, `birth_year`, if target's value is NULL and source's is not, copy source's value to target.
6. Create a `SkaterAlias` with the source's `(first_name, last_name)` pointing to `target_id`. If an alias with that `(first_name, last_name)` already exists for a different skater, the merge should fail with an error.
7. Delete the source skater.

**Response:**
```json
{
  "merged": 2,
  "aliases_created": 2
}
```

**Validations:**
- `target_id` must exist
- `source_ids` must not be empty and must not contain `target_id`
- All source skaters must exist

### Import pipeline change

In `_get_or_create_skater` (import_service.py), after the existing lookup by `(first_name, last_name)` returns `None` (and after the existing pairs migration block) but before creating a new skater, check `SkaterAlias`:

```python
if not skater:
    alias_stmt = select(SkaterAlias).where(
        SkaterAlias.first_name == first_name,
        SkaterAlias.last_name == last_name,
    )
    alias = (await session.execute(alias_stmt)).scalar_one_or_none()
    if alias:
        skater = await session.get(Skater, alias.skater_id)
```

### Orphan cleanup change

The orphan cleanup at the end of `run_import` must also exclude skaters that are alias targets. Add to the orphan query:

```python
~exists(select(SkaterAlias.id).where(SkaterAlias.skater_id == Skater.id))
```

### Enrich pipeline note

`run_enrich` matches PDF skater names against `Score` joined with `Skater` by `first_name`/`last_name`. After a merge, the source skater is deleted and its name is stored as an alias. Since enrich always runs after import, and import resolves aliases, the scores will already be linked to the target skater. No change needed in `run_enrich` — the PDF name lookup will match the target skater's name (or the score will have been created under the target via alias resolution during import).

## Frontend (Settings page)

### New section: "Fusionner des patineurs" (admin only)

Placed in the Settings page, visible only to admins.

**Flow:**
1. Search input — admin types a skater name, results appear below
2. Clicking a result adds it to a "selected skaters" list (displayed as removable chips)
3. Once 2+ skaters are selected, a "Fusionner" button appears
4. Each selected skater has a radio button to designate the primary (default: first selected)
5. Clicking "Fusionner" shows inline confirmation text: "Fusionner N patineurs en [Prénom NOM] ? Les scores seront regroupés."
6. On confirm, calls `POST /api/skaters/merge`, shows success toast, clears selection, invalidates skater queries

### API client addition

```typescript
skaters: {
  // ... existing methods
  merge: (targetId: number, sourceIds: number[]) =>
    request<{ merged: number; aliases_created: number }>("/skaters/merge", {
      method: "POST",
      body: JSON.stringify({ target_id: targetId, source_ids: sourceIds }),
    }),
}
```

## Testing

- **Backend unit test**: merge endpoint — verify scores/category results/user links reassigned, source deleted, alias created, metadata filled
- **Backend unit test**: merge with conflicts — verify duplicate scores/category results handled gracefully
- **Backend unit test**: `_get_or_create_skater` — verify alias lookup returns existing skater instead of creating a new one
