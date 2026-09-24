"""
image_extractor.py
------------------
Crops embedded raster images from a question's region in the PDF and saves them
as high-DPI PNGs into an `images/` sub-folder of the output directory.

Returned paths are *relative* (e.g. "images/Q45_fig1.png") so they can be
embedded directly into Markdown as  ![Figure for Q45](images/Q45_fig1.png).

This module is used exclusively by the Graphic-Heavy CBT pipeline branch.
It has zero impact on the standard CBT or Offline Booklet paths.
"""

from __future__ import annotations

import fitz
from pathlib import Path
from typing import List

# Minimum pixel dimensions for an image to be considered a diagram
# (filters out tiny checkmark / bullet icons)
MIN_IMAGE_WIDTH_PT  = 30   # points in the PDF coordinate system
MIN_IMAGE_HEIGHT_PT = 30


def extract_question_images(
    block,          # RawQuestionBlock
    out_dir: Path,
    dpi: int = 300,
) -> List[str]:
    """
    Detect and crop all meaningful embedded images from the region of the PDF
    belonging to *block*, save each as a PNG, and return a list of relative
    paths (relative to *out_dir*) suitable for Markdown image links.

    Parameters
    ----------
    block   : RawQuestionBlock  — the parsed question block (contains pdf_path,
              page extents and vertical boundaries).
    out_dir : Path              — root output directory for this PDF run.
    dpi     : int               — render resolution for the cropped PNGs.

    Returns
    -------
    List of relative path strings, e.g. ["images/Q45_fig1.png"].
    Returns an empty list when no images are found (backward compatible).
    """
    if not block.pdf_path or not Path(block.pdf_path).exists():
        return []

    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(block.pdf_path)
    try:
        saved: List[str] = []
        fig_index = 1
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        # Determine the vertical span of this block's *content* (below header/marks line)
        content_pno = (
            (block.content_page_number - 1)
            if block.content_page_number and block.content_page_number > 0
            else (block.page_number - 1)
        )
        end_pno = (
            (block.end_page_number - 1)
            if block.end_page_number and block.end_page_number >= block.page_number
            else content_pno
        )
        content_start_y = block.content_start_y if block.content_start_y > 0 else block.bbox[1]
        end_y = block.end_y

        for pno in range(content_pno, end_pno + 1):
            if pno >= doc.page_count:
                break

            page = doc[pno]
            page_h = page.rect.height

            # Vertical window within this page that belongs to the question
            if pno == content_pno:
                top_limit = content_start_y
            else:
                top_limit = 0.0

            if pno == end_pno:
                bottom_limit = end_y
            else:
                bottom_limit = page_h

            # --- Raster images embedded in the PDF (type-1 blocks) ---
            blocks_dict = page.get_text("dict").get("blocks", [])
            for b in blocks_dict:
                if b.get("type") != 1:
                    continue  # only image blocks

                bx0, by0, bx1, by1 = b.get("bbox", (0, 0, 0, 0))
                bw = bx1 - bx0
                bh = by1 - by0

                # Skip tiny icons
                if bw < MIN_IMAGE_WIDTH_PT or bh < MIN_IMAGE_HEIGHT_PT:
                    continue

                # Check vertical overlap with question region
                if by1 < top_limit - 2 or by0 > bottom_limit + 2:
                    continue

                # Clip and render
                clip = fitz.Rect(bx0, by0, bx1, by1)
                pix = page.get_pixmap(matrix=mat, clip=clip)
                fname = f"Q{block.qnum}_fig{fig_index}.png"
                out_path = images_dir / fname
                pix.save(str(out_path))
                saved.append(f"images/{fname}")
                fig_index += 1

            # --- Vector / drawn graphics: render the whole question region ---
            # If the page has no raster image blocks in the question zone but the
            # question was flagged has_images=True, fall back to rendering the
            # full question content area (captures vector drawings, tables, etc.)
            if not saved and block.has_images and pno == content_pno:
                clip = fitz.Rect(
                    0,
                    top_limit + 1,
                    page.rect.width,
                    min(page_h - 15, bottom_limit),
                )
                if clip.height > MIN_IMAGE_HEIGHT_PT:
                    pix = page.get_pixmap(matrix=mat, clip=clip)
                    fname = f"Q{block.qnum}_fig{fig_index}.png"
                    out_path = images_dir / fname
                    pix.save(str(out_path))
                    saved.append(f"images/{fname}")
                    fig_index += 1

        return saved
    except Exception as e:
        # Never crash the main pipeline because of image extraction failure
        print(f"  [ImageExtractor] Warning: could not extract images for Q{block.qnum}: {e}")
        return []
    finally:
        doc.close()
