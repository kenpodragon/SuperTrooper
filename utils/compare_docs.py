"""Diff two .docx files and show text changes paragraph by paragraph.

Shows added, removed, and changed paragraphs with context using Python's
difflib for comparison.

Usage:
    python compare_docs.py <file1.docx> <file2.docx> [--format text|html]

Dependencies:
    pip install python-docx
"""

import argparse
import difflib
import sys
from pathlib import Path
from typing import Optional

from docx import Document


def extract_paragraphs(path: str) -> list[str]:
    """Extract all paragraph texts from a .docx file.

    Args:
        path: Path to the .docx file.

    Returns:
        List of paragraph text strings (empty paragraphs included).
    """
    doc = Document(path)
    return [p.text for p in doc.paragraphs]


def compare_text(paragraphs_a: list[str], paragraphs_b: list[str]) -> str:
    """Generate a unified diff between two lists of paragraphs.

    Args:
        paragraphs_a: Paragraphs from the first document.
        paragraphs_b: Paragraphs from the second document.

    Returns:
        Unified diff as a string.
    """
    diff = difflib.unified_diff(
        paragraphs_a,
        paragraphs_b,
        fromfile="document_a",
        tofile="document_b",
        lineterm="",
    )
    return "\n".join(diff)


def compare_html(paragraphs_a: list[str], paragraphs_b: list[str],
                 file_a: str = "document_a", file_b: str = "document_b") -> str:
    """Generate an HTML side-by-side diff between two lists of paragraphs.

    Args:
        paragraphs_a: Paragraphs from the first document.
        paragraphs_b: Paragraphs from the second document.
        file_a: Label for the first document.
        file_b: Label for the second document.

    Returns:
        HTML diff as a string.
    """
    differ = difflib.HtmlDiff(wrapcolumn=80)
    return differ.make_file(
        paragraphs_a,
        paragraphs_b,
        fromdesc=file_a,
        todesc=file_b,
    )


def summarize_changes(paragraphs_a: list[str], paragraphs_b: list[str]) -> dict[str, int]:
    """Produce a summary of changes between two documents.

    Args:
        paragraphs_a: Paragraphs from the first document.
        paragraphs_b: Paragraphs from the second document.

    Returns:
        Dictionary with counts of added, removed, and changed lines.
    """
    matcher = difflib.SequenceMatcher(None, paragraphs_a, paragraphs_b)
    added = 0
    removed = 0
    changed = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added += j2 - j1
        elif tag == "delete":
            removed += i2 - i1
        elif tag == "replace":
            changed += max(i2 - i1, j2 - j1)

    return {"added": added, "removed": removed, "changed": changed}


def compare_docs(file_a: str, file_b: str, output_format: str = "text") -> str:
    """Compare two .docx files and return the diff.

    Args:
        file_a: Path to the first .docx file.
        file_b: Path to the second .docx file.
        output_format: "text" for unified diff, "html" for HTML diff.

    Returns:
        The diff output as a string.
    """
    paras_a = extract_paragraphs(file_a)
    paras_b = extract_paragraphs(file_b)

    if output_format == "html":
        return compare_html(paras_a, paras_b, file_a, file_b)
    else:
        summary = summarize_changes(paras_a, paras_b)
        diff_text = compare_text(paras_a, paras_b)

        header = (
            f"Comparing: {file_a} vs {file_b}\n"
            f"  Added paragraphs:   {summary['added']}\n"
            f"  Removed paragraphs: {summary['removed']}\n"
            f"  Changed paragraphs: {summary['changed']}\n"
        )

        if not diff_text:
            return header + "\nNo differences found."
        return header + "\n" + diff_text


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Diff two .docx files and show text changes."
    )
    parser.add_argument("file1", help="Path to the first .docx file")
    parser.add_argument("file2", help="Path to the second .docx file")
    parser.add_argument(
        "--format",
        choices=["text", "html"],
        default="text",
        dest="output_format",
        help="Output format: text (unified diff) or html (side-by-side). Default: text",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Save diff to a file instead of printing to stdout",
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

    for filepath in [args.file1, args.file2]:
        if not Path(filepath).exists():
            print(f"Error: file not found: {filepath}", file=sys.stderr)
            return 1

    try:
        result = compare_docs(args.file1, args.file2, args.output_format)

        if args.output:
            Path(args.output).write_text(result, encoding="utf-8")
            print(f"Diff saved to: {args.output}")
        else:
            print(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
