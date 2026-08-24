"""Build the offline PERLA labelling sheet from results/validation/labelling.parquet.

Emits a single self-contained HTML file: every sampled image is embedded
as a downscaled JPEG data URI, so the sheet can be e-mailed to a labeller
who does not have the (gitignored) PNG corpus. The labeller records a
PERLA tone per image and copies the resulting CSV back out.

The sheet is deliberately blind: it shows the image and nothing else. The
occupation, language, model and the algorithmic ``perla_consensus`` are
all withheld, because seeing "CEO" or the classifier's own answer would
anchor the rating that the validation exists to check. Presentation order
is shuffled with a fixed seed for the same reason.

It does NOT draw a PERLA reference palette. The LAPOP ``colorr`` variable
this validation is compared against was recorded by interviewers holding
the physical PERLA palette card, so the labellers must use that same card
for their ratings to be on the same scale. Inventing on-screen swatches
would silently create a second, differently-calibrated instrument.

Usage:
    uv run python scripts/make_labelling_sheet.py [--labeller CL] [--px 384]
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from apd.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("labelling_sheet")

VALIDATION_DIR = settings.results_tables.parent / "validation"
LABELLING_IN = VALIDATION_DIR / "labelling.parquet"


def thumbnail_data_uri(path: Path, px: int, quality: int) -> str | None:
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((px, px), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=quality, optimize=True)
    except OSError as exc:
        log.warning("could not read %s: %s", path, exc)
        return None
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


PAGE_CSS = """
:root { --bg:#fff; --fg:#1a1a1a; --muted:#666; --line:#ddd; --accent:#1a4f8a; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161616; --fg:#ececec; --muted:#9a9a9a; --line:#333; --accent:#7ab3f0; }
}
* { box-sizing: border-box; }
body { margin:0; padding:24px; background:var(--bg); color:var(--fg);
       font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
header { max-width:900px; margin:0 auto 28px; }
h1 { font-size:22px; margin:0 0 8px; }
.note { background:rgba(127,127,127,.09); border-left:3px solid var(--accent);
        padding:12px 14px; margin:14px 0; border-radius:0 4px 4px 0; }
.grid { max-width:900px; margin:0 auto; display:grid; gap:22px; }
.card { border:1px solid var(--line); border-radius:8px; padding:14px;
        display:grid; grid-template-columns:auto 1fr; gap:16px; align-items:start; }
.card img { width:220px; height:auto; border-radius:5px; display:block; }
.meta { font:12px ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--muted);
        word-break:break-all; margin-bottom:10px; }
.tones { display:flex; flex-wrap:wrap; gap:6px; }
.tones label { border:1px solid var(--line); border-radius:5px; padding:7px 11px;
               cursor:pointer; user-select:none; min-width:42px; text-align:center; }
.tones input { position:absolute; opacity:0; width:0; height:0; }
.tones input:checked + span { font-weight:700; }
.tones label:has(input:checked) { background:var(--accent); color:#fff;
                                  border-color:var(--accent); }
footer { max-width:900px; margin:32px auto 0; }
textarea { width:100%; height:220px; font:12px ui-monospace,Menlo,monospace;
           background:var(--bg); color:var(--fg); border:1px solid var(--line);
           border-radius:6px; padding:10px; }
button { font:inherit; padding:9px 16px; border-radius:6px; cursor:pointer;
         border:1px solid var(--accent); background:var(--accent); color:#fff; }
#progress { position:sticky; top:0; background:var(--bg); padding:10px 0;
            border-bottom:1px solid var(--line); z-index:5; max-width:900px;
            margin:0 auto 18px; font-variant-numeric:tabular-nums; }
@media (max-width:640px){ .card{grid-template-columns:1fr;} .card img{width:100%;} }
"""

PAGE_JS = """
const total = document.querySelectorAll('.card').length;
function refresh() {
  const done = document.querySelectorAll('.card input:checked').length;
  document.getElementById('progress').textContent =
    `${done} / ${total} rated` + (done === total ? '  — complete, copy the CSV below' : '');
}
document.addEventListener('change', e => { if (e.target.matches('.tones input')) refresh(); });
function buildCsv() {
  const who = document.getElementById('who').value.trim() || 'UNKNOWN';
  const lines = ['image_id,labeller,perla'];
  document.querySelectorAll('.card').forEach(card => {
    const sel = card.querySelector('input:checked');
    lines.push(`${card.dataset.imageId},${who},${sel ? sel.value : ''}`);
  });
  return lines.join('\\n');
}
function showCsv() { document.getElementById('csv').value = buildCsv(); }
async function copyCsv() {
  showCsv();
  try { await navigator.clipboard.writeText(buildCsv()); alert('CSV copied to clipboard.'); }
  catch { alert('Copy failed — select the text in the box and copy manually.'); }
}
refresh();
"""


def build_html(rows: list[dict], labeller: str) -> str:
    cards = []
    for i, r in enumerate(rows, start=1):
        # The visible caption is a bare sequence number. image_id encodes
        # the model and the occupation ("pollinations_flux__CEO__<seed>"),
        # so printing it would show the labeller exactly the two things
        # the blind protocol withholds. It stays in the data attribute,
        # which is not rendered, because the CSV has to join back on it.
        tones = "".join(
            f'<label><input type="radio" name="t_{i}" '
            f'value="{t}"><span>{t}</span></label>'
            for t in range(1, 12)
        )
        cards.append(
            f'<div class="card" data-image-id="{html.escape(r["image_id"])}">'
            f'<img src="{r["uri"]}" alt="image to rate" loading="lazy">'
            f'<div><div class="meta">Image {i:03d}</div>'
            f'<div class="tones">{tones}</div></div></div>',
        )
    return f"""<title>PERLA labelling sheet</title>
<style>{PAGE_CSS}</style>
<header>
<h1>PERLA labelling sheet</h1>
<p>Rate the skin tone of the main person in each image on the PERLA
ordinal scale, <strong>1 (lightest) to 11 (darkest)</strong>.</p>
<div class="note"><strong>Use the physical PERLA palette card.</strong>
LAPOP's <code>colorr</code> variable — the empirical baseline these
ratings are compared against — was recorded by interviewers holding that
card. Rating from memory, or against an on-screen approximation, puts
your labels on a different scale and defeats the purpose of the exercise.</div>
<div class="note">The sheet shows the image only. Occupation, language,
model and the classifier's own answer are withheld on purpose — knowing
them would anchor your rating. If no person is visible, or the face is
too small or too poorly lit to judge, leave the row blank.</div>
<p>Labeller initials:
<input id="who" value="{html.escape(labeller)}" size="8"></p>
</header>
<div id="progress"></div>
<div class="grid">{"".join(cards)}</div>
<footer>
<h2>When you are done</h2>
<p>Click <em>Copy CSV</em> and paste it into a file named
<code>labels_{html.escape(labeller.lower())}.csv</code>, then send that
file back.</p>
<p><button onclick="copyCsv()">Copy CSV</button>
<button onclick="showCsv()" style="background:transparent;color:var(--accent)">Show CSV</button></p>
<textarea id="csv" placeholder="The CSV appears here."></textarea>
</footer>
<script>{PAGE_JS}</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labeller", default="CL", help="initials pre-filled in the sheet")
    ap.add_argument("--px", type=int, default=384, help="thumbnail long edge")
    ap.add_argument("--quality", type=int, default=88, help="JPEG quality")
    ap.add_argument("--seed", type=int, default=settings.seed)
    args = ap.parse_args()

    if not LABELLING_IN.exists():
        log.error("Missing %s — run scripts/08_visual_validation.py first.", LABELLING_IN)
        return 1

    labels = pd.read_parquet(LABELLING_IN)
    log.info("Loaded %d sampled images.", len(labels))

    # Shuffle so rating drift cannot line up with occupation order, and
    # derive the seed from the labeller so the two raters get different
    # orders. With a shared order, drift over a 300-image session would be
    # correlated between them and inflate Cohen's κ; independent orders
    # keep the agreement estimate honest. The CSV joins on image_id, so
    # the orders need not match.
    labeller_seed = args.seed + int.from_bytes(args.labeller.upper().encode(), "big")
    order = np.random.default_rng(labeller_seed).permutation(len(labels))
    labels = labels.iloc[order].reset_index(drop=True)
    log.info("Presentation order seeded for labeller %s.", args.labeller.upper())

    rows: list[dict] = []
    for image_id, rel in zip(labels["image_id"], labels["path"], strict=True):
        p = Path(rel)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        uri = thumbnail_data_uri(p, args.px, args.quality)
        if uri is None:
            continue
        rows.append({"image_id": image_id, "uri": uri})
    log.info("Embedded %d thumbnails.", len(rows))

    out = VALIDATION_DIR / f"labelling_sheet_{args.labeller.lower()}.html"
    out.write_text(build_html(rows, args.labeller), encoding="utf-8")
    log.info("Wrote %s (%.1f MB)", out, out.stat().st_size / 1024 / 1024)
    return 0


if __name__ == "__main__":
    sys.exit(main())
