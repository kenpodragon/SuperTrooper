"""Extract text from PDF files, with optional page range and search.

Useful for reading job descriptions saved as PDFs.

Usage:
    python read_pdf.py <file.pdf> [--pages 1-3] [--search "query"]

Dependencies:
    pip install pdfplumber
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

import pdfplumber


def parse_page_range(page_spec: str, total_pages: int) -> list[int]:
    """Parse a page range string into a list of zero-based page indices.

    Supports formats like "1", "1-3", "1,3,5", "1-3,7,9-11".

    Args:
        page_spec: Page range string (1-based).
        total_pages: Total number of pages in the PDF.

    Returns:
        Sorted list of zero-based page indices.

    Raises:
        ValueError: If the page specification is invalid.
    """
    pages: set[int] = set()

    for part in page_spec.split(","):
        part = part.strip()
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            if start < 1 or end > total_pages or start > end:
                raise ValueError(
                    f"Invalid page range '{part}' (document has {total_pages} pages)"
                )
            for p in range(start, end + 1):
                pages.add(p - 1)  # Convert to zero-based
        else:
            p = int(part)
            if p < 1 or p > total_pages:
                raise ValueError(
                    f"Invalid page number {p} (document has {total_pages} pages)"
                )
            pages.add(p - 1)

    return sorted(pages)


def read_pdf_text(path: str, pages: Optional[str] = None) -> str:
    """Extract text from a PDF file.

    Args:
        path: Path to the PDF file.
        pages: Optional page range string (e.g., "1-3"). If None, reads all pages.

    Returns:
        Extracted text with page separators.
    """
    output_parts: list[str] = []

    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)

        if pages:
            page_indices = parse_page_range(pages, total)
        else:
            page_indices = list(range(total))

        for idx in page_indices:
            page = pdf.pages[idx]
            text = page.extract_text() or ""
            if len(page_indices) > 1:
                output_parts.append(f"--- Page {idx + 1} ---")
            output_parts.append(text)

    return "\n\n".join(output_parts)


def search_pdf(path: str, query: str, pages: Optional[str] = None) -> list[dict[str, any]]:
    """Search for text in a PDF file.

    Args:
        path: Path to the PDF file.
        query: Text to search for (case-insensitive).
        pages: Optional page range to limit search.

    Returns:
        List of dicts with 'page' (1-based) and 'line' keys for each match.
    """
    results: list[dict] = []
    query_lower = query.lower()

    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)

        if pages:
            page_indices = parse_page_range(pages, total)
        else:
            page_indices = list(range(total))

        for idx in page_indices:
            page = pdf.pages[idx]
            text = page.extract_text() or ""
            for line in text.split("\n"):
                if query_lower in line.lower():
                    results.append({"page": idx + 1, "line": line.strip()})

    return results


def get_pdf_info(path: str) -> dict[str, any]:
    """Get basic information about a PDF file.

    Args:
        path: Path to the PDF file.

    Returns:
        Dictionary with page count and metadata.
    """
    with pdfplumber.open(path) as pdf:
        return {
            "pages": len(pdf.pages),
            "metadata": pdf.metadata or {},
        }


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract text from PDF files."
    )
    parser.add_argument("file", help="Path to the PDF file")
    parser.add_argument(
        "--pages",
        metavar="RANGE",
        help="Page range to extract (e.g., '1-3', '1,3,5'). Default: all pages",
    )
    parser.add_argument(
        "--search",
        metavar="QUERY",
        help="Search for text in the PDF",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show PDF info (page count, metadata) instead of text",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    try:
        if args.info:
            info = get_pdf_info(str(path))
            print(f"Pages: {info['pages']}")
            if info["metadata"]:
                print("Metadata:")
                for key, value in info["metadata"].items():
                    if value:
                        print(f"  {key}: {value}")
        elif args.search:
            results = search_pdf(str(path), args.search, args.pages)
            if not results:
                print(f"No matches found for: {args.search}")
            else:
                print(f"Found {len(results)} match(es) for '{args.search}':\n")
                for r in results:
                    print(f"  [Page {r['page']}] {r['line']}")
        else:
            text = read_pdf_text(str(path), args.pages)
            if text.strip():
                print(text)
            else:
                print("(No text extracted — PDF may be image-based.)")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
