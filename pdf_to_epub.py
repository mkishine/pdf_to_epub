#!/usr/bin/env python3
"""
PDF to EPUB Converter CLI

A command-line tool for converting PDF files to EPUB format.
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Error: pdfplumber is required. Install with: pip install pdfplumber")
    sys.exit(1)

try:
    from ebooklib import epub
except ImportError:
    print("Error: ebooklib is required. Install with: pip install ebooklib")
    sys.exit(1)


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Extract text content from each page of a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of dictionaries containing page number and text content
    """
    pages = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append({
                "page_number": i,
                "text": text.strip()
            })

    return pages


def create_epub(
    pages: list[dict],
    output_path: str,
    title: str,
    author: str,
    language: str = "en",
    chapter_pages: int = 1
) -> None:
    """
    Create an EPUB file from extracted PDF pages.

    Args:
        pages: List of page dictionaries with text content
        output_path: Path for the output EPUB file
        title: Book title
        author: Book author
        language: Language code (default: "en")
        chapter_pages: Number of PDF pages per EPUB chapter (default: 1)
    """
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier(f"pdf-to-epub-{hash(title)}")
    book.set_title(title)
    book.set_language(language)
    book.add_author(author)

    chapters = []
    spine = ["nav"]

    # Group pages into chapters
    for i in range(0, len(pages), chapter_pages):
        chapter_num = (i // chapter_pages) + 1
        chapter_pages_content = pages[i:i + chapter_pages]

        # Combine text from pages in this chapter
        chapter_text = "\n\n".join(
            f"<!-- Page {p['page_number']} -->\n{p['text']}"
            for p in chapter_pages_content if p['text']
        )

        if not chapter_text.strip():
            continue

        # Convert plain text to HTML paragraphs
        html_content = text_to_html(chapter_text)

        # Create chapter
        chapter = epub.EpubHtml(
            title=f"Chapter {chapter_num}",
            file_name=f"chapter_{chapter_num:04d}.xhtml",
            lang=language
        )
        chapter.content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="{language}">
<head>
    <title>Chapter {chapter_num}</title>
    <style>
        body {{ font-family: serif; line-height: 1.6; margin: 1em; }}
        p {{ margin-bottom: 1em; text-indent: 1.5em; }}
        .page-break {{ page-break-before: always; }}
    </style>
</head>
<body>
    <h2>Chapter {chapter_num}</h2>
    {html_content}
</body>
</html>"""

        book.add_item(chapter)
        chapters.append(chapter)
        spine.append(chapter)

    # Create table of contents
    book.toc = tuple(chapters)

    # Add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Set spine
    book.spine = spine

    # Write EPUB file
    epub.write_epub(output_path, book, {})


def text_to_html(text: str) -> str:
    """
    Convert plain text to HTML paragraphs.

    Args:
        text: Plain text content

    Returns:
        HTML formatted string with paragraphs
    """
    import html

    # Split into paragraphs (double newline or more)
    paragraphs = text.split("\n\n")

    html_parts = []
    for para in paragraphs:
        # Clean up the paragraph
        para = para.strip()
        if not para:
            continue

        # Skip HTML comments (page markers)
        if para.startswith("<!--") and para.endswith("-->"):
            continue

        # Handle page markers mixed with content
        if para.startswith("<!-- Page"):
            lines = para.split("\n", 1)
            if len(lines) > 1:
                para = lines[1].strip()
            else:
                continue

        if para:
            # Escape HTML entities and wrap in paragraph tags
            escaped = html.escape(para)
            # Replace single newlines with line breaks
            escaped = escaped.replace("\n", "<br/>\n")
            html_parts.append(f"<p>{escaped}</p>")

    return "\n".join(html_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF files to EPUB format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.pdf
  %(prog)s input.pdf -o output.epub
  %(prog)s input.pdf --title "My Book" --author "John Doe"
  %(prog)s input.pdf --chapter-pages 5
        """
    )

    parser.add_argument(
        "input",
        help="Path to the input PDF file"
    )

    parser.add_argument(
        "-o", "--output",
        help="Path for the output EPUB file (default: same name as input with .epub extension)"
    )

    parser.add_argument(
        "-t", "--title",
        help="Book title (default: PDF filename)"
    )

    parser.add_argument(
        "-a", "--author",
        default="Unknown",
        help="Book author (default: Unknown)"
    )

    parser.add_argument(
        "-l", "--language",
        default="en",
        help="Language code (default: en)"
    )

    parser.add_argument(
        "--chapter-pages",
        type=int,
        default=1,
        help="Number of PDF pages per EPUB chapter (default: 1)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not input_path.suffix.lower() == ".pdf":
        print(f"Warning: Input file may not be a PDF: {args.input}", file=sys.stderr)

    # Set output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(".epub")

    # Set title
    title = args.title or input_path.stem

    if args.verbose:
        print(f"Input: {input_path}")
        print(f"Output: {output_path}")
        print(f"Title: {title}")
        print(f"Author: {args.author}")
        print(f"Language: {args.language}")
        print(f"Pages per chapter: {args.chapter_pages}")
        print()

    # Extract text from PDF
    if args.verbose:
        print("Extracting text from PDF...")

    try:
        pages = extract_text_from_pdf(str(input_path))
    except Exception as e:
        print(f"Error reading PDF: {e}", file=sys.stderr)
        sys.exit(1)

    if not pages:
        print("Error: No pages found in PDF", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Extracted {len(pages)} pages")

    # Create EPUB
    if args.verbose:
        print("Creating EPUB...")

    try:
        create_epub(
            pages=pages,
            output_path=str(output_path),
            title=title,
            author=args.author,
            language=args.language,
            chapter_pages=args.chapter_pages
        )
    except Exception as e:
        print(f"Error creating EPUB: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Successfully created: {output_path}")


if __name__ == "__main__":
    main()
