"""Generate PNG thumbnails from .docx files.

Pipeline: .docx → LibreOffice headless → PDF → PyMuPDF → PNG → Pillow resize → 200x260 bytes

Non-fatal: returns None on any error so the upload pipeline continues.
"""

import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

THUMB_WIDTH = 200
THUMB_HEIGHT = 260


def generate_thumbnail(docx_bytes: bytes) -> bytes | None:
    """Convert a .docx to a 200x260 PNG thumbnail (first page only).

    Args:
        docx_bytes: Raw .docx file content.

    Returns:
        PNG bytes for the thumbnail, or None if generation fails.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="thumb_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            docx_path = tmpdir_path / "input.docx"
            docx_path.write_bytes(docx_bytes)

            # Step 1: .docx → .pdf via LibreOffice headless
            pdf_path = _docx_to_pdf(docx_path, tmpdir_path)
            if pdf_path is None:
                return None

            # Step 2: PDF page 1 → PNG via PyMuPDF
            png_bytes = _pdf_to_png(pdf_path)
            if png_bytes is None:
                return None

            # Step 3: Resize to thumbnail dimensions via Pillow
            return _resize_png(png_bytes, THUMB_WIDTH, THUMB_HEIGHT)

    except Exception:
        logger.warning("Thumbnail generation failed", exc_info=True)
        return None


def _docx_to_pdf(docx_path: Path, outdir: Path) -> Path | None:
    """Convert .docx to .pdf using LibreOffice headless."""
    try:
        result = subprocess.run(
            [
                "libreoffice", "--headless", "--norestore", "--convert-to", "pdf",
                "--outdir", str(outdir), str(docx_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("LibreOffice conversion failed: %s", result.stderr[:500])
            return None

        pdf_path = outdir / docx_path.with_suffix(".pdf").name
        if not pdf_path.exists():
            logger.warning("LibreOffice produced no output PDF")
            return None

        return pdf_path

    except FileNotFoundError:
        logger.warning("LibreOffice not found — install libreoffice-writer-nogui")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("LibreOffice conversion timed out (30s)")
        return None


def _pdf_to_png(pdf_path: Path) -> bytes | None:
    """Render first page of PDF to PNG using PyMuPDF."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        if len(doc) == 0:
            logger.warning("PDF has no pages")
            return None

        page = doc[0]
        # Render at 2x for decent quality before resize
        pix = page.get_pixmap(dpi=144)
        png_bytes = pix.tobytes("png")
        doc.close()
        return png_bytes

    except Exception:
        logger.warning("PDF to PNG rendering failed", exc_info=True)
        return None


def _resize_png(png_bytes: bytes, width: int, height: int) -> bytes | None:
    """Resize PNG to target dimensions, maintaining aspect ratio with white fill."""
    try:
        from io import BytesIO
        from PIL import Image

        img = Image.open(BytesIO(png_bytes))

        # Resize maintaining aspect ratio
        img.thumbnail((width, height), Image.Resampling.LANCZOS)

        # Center on white background at exact target size
        bg = Image.new("RGB", (width, height), (255, 255, 255))
        x = (width - img.width) // 2
        y = (height - img.height) // 2
        bg.paste(img, (x, y))

        out = BytesIO()
        bg.save(out, format="PNG", optimize=True)
        return out.getvalue()

    except Exception:
        logger.warning("PNG resize failed", exc_info=True)
        return None
