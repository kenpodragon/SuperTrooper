# Template Thumbnail Generation — Design Spec

**Date:** 2026-03-29
**Status:** Approved

## Summary

Generate PNG thumbnails of resume templates during onboard upload. Store in the existing `preview_blob` BYTEA column. Display in TemplatePicker grid instead of placeholder boxes.

## Trigger

During `_process_file()` in `onboard.py`, after the templatize step produces the template .docx, before the template DB insert.

## Pipeline

```
existing: templatize → template .docx bytes + template_map JSON
    new: template .docx bytes → LibreOffice headless → full-page PNG → Pillow resize → 200x260 PNG bytes
existing: INSERT INTO resume_templates (template_blob, template_map, preview_blob, ...)
```

## Backend

### New utility: `code/utils/thumbnail.py`

`generate_thumbnail(docx_bytes: bytes) -> bytes | None`

1. Write docx_bytes to temp file
2. Run `libreoffice --headless --convert-to png --outdir <tmpdir> <tmpfile>`
3. LibreOffice outputs one PNG per page... take the first page only
4. Resize to 200x260 via Pillow (maintain aspect ratio, white background fill if needed)
5. Return PNG bytes
6. On any error, log warning and return None (non-fatal)

### Modify: `code/backend/routes/onboard.py`

In `_process_file()`, after templatize step:
- Call `generate_thumbnail(template_docx_bytes)`
- Pass result to template insert as `preview_blob`

### Modify: template insert query

Ensure `preview_blob` is included in the INSERT statement for `resume_templates`.

## Frontend

### Modify: `TemplatePicker.tsx`

- If template has `preview_url` (base64 data URI or endpoint URL), show `<img>` tag
- If no preview, show existing gray placeholder as fallback

### Template list API

Option A: Return `preview_blob` as base64 in the list response (thumbnails are ~10-20KB, fine for a small list).
Option B: Separate `GET /api/templates/:id/preview` endpoint returning image/png.

**Decision:** Option A for simplicity... template lists are small (< 20 templates). Encode as base64 data URI in the JSON response.

## Docker

- Verify LibreOffice is installed in the backend container (expected yes... `docx_to_pdf.py` uses it)
- Add `Pillow` to `requirements.txt` if not present

## Error Handling

Thumbnail generation is non-fatal. If LibreOffice fails, corrupt file, or any error:
- Log warning with filename and error
- Store NULL in `preview_blob`
- Frontend shows placeholder fallback
- Upload continues normally

## Thumbnail Specs

- **Dimensions:** 200x260px
- **Format:** PNG
- **Size:** ~10-20KB per thumbnail
- **Storage:** BYTEA in `preview_blob` column (migration 030 already added this)

## Sanity Check (post-implementation)

Via Chrome DevTools container (port 9102):

1. Upload v32.docx through the frontend Import modal
2. View the template thumbnail in TemplatePicker... verify it looks like the resume
3. View the template details... verify the template content matches
4. Generate a resume from the template... verify the output .docx matches the original formatting
5. Consistent appearance across all three views

## Out of Scope

- Full resume preview in browser (separate future work... "4 box monstrosity" fix)
- Re-generating thumbnails for existing templates (DB will be cleared, re-import handles it)
- Multi-page thumbnails (first page only)
