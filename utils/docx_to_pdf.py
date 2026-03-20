"""Convert .docx files to .pdf using MS Word COM automation (Windows).

Uses the docx2pdf library which drives Microsoft Word for pixel-perfect
PDF conversion that preserves all formatting, fonts, and layout.

Usage:
    python docx_to_pdf.py <input.docx> [--output <output.pdf>]

Dependencies:
    pip install docx2pdf
    Requires Microsoft Word to be installed.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from docx2pdf import convert


def docx_to_pdf(input_path: str, output_path: Optional[str] = None) -> str:
    """Convert a .docx file to PDF using Microsoft Word.

    Args:
        input_path: Path to the input .docx file.
        output_path: Path for the output PDF. If None, uses the same name
                     with a .pdf extension.

    Returns:
        The path to the generated PDF file.

    Raises:
        FileNotFoundError: If the input file does not exist.
        RuntimeError: If conversion fails.
    """
    input_p = Path(input_path).resolve()
    if not input_p.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path is None:
        output_p = input_p.with_suffix(".pdf")
    else:
        output_p = Path(output_path).resolve()

    # Ensure output directory exists
    output_p.parent.mkdir(parents=True, exist_ok=True)

    convert(str(input_p), str(output_p))
    return str(output_p)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Convert .docx to .pdf using Microsoft Word (perfect fidelity)."
    )
    parser.add_argument("input", help="Path to the input .docx file")
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Output PDF path (default: same name with .pdf extension)",
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

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        result = docx_to_pdf(str(input_path), args.output)
        print(f"Converted: {input_path} -> {result}")
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
