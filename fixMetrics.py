"""Fix font metrics for proper rendering in terminal emulators (kitty, etc.).

Fixes:
1. Empty COLR base glyphs given bounding-box outlines so FreeType/kitty can
   determine glyph extents for positioning before COLR layer rendering
2. Vertical metrics rebalanced and made consistent across OS/2, hhea, and head
3. Panose classification set to Latin Symbol
"""

import sys
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen

if len(sys.argv) < 2:
    print("Usage: python3 fixMetrics.py <font.ttf>", file=sys.stderr)
    sys.exit(1)

fontfile = sys.argv[1]
font = TTFont(fontfile)

glyf = font["glyf"]
colr = font["COLR"]

# --- Add bounding-box outlines to empty COLR base glyphs ---
# Iterates all COLR base glyphs (including ligatures like flags and ZWJ sequences).
# For each empty base glyph, calculates the combined bounds of its COLR layers
# and adds a minimal rectangle outline.

fixed_count = 0

for gname in colr.ColorLayers:
    g = glyf.get(gname)
    if g is None:
        continue
    if g.numberOfContours > 0 or g.isComposite():
        continue

    layers = colr[gname]
    if not layers:
        continue

    x_min, y_min, x_max, y_max = None, None, None, None
    for layer in layers:
        lg = glyf.get(layer.name)
        if lg is None:
            continue
        if hasattr(lg, "xMin") and lg.numberOfContours > 0:
            if x_min is None:
                x_min, y_min = lg.xMin, lg.yMin
                x_max, y_max = lg.xMax, lg.yMax
            else:
                x_min = min(x_min, lg.xMin)
                y_min = min(y_min, lg.yMin)
                x_max = max(x_max, lg.xMax)
                y_max = max(y_max, lg.yMax)

    if x_min is None:
        continue

    pen = TTGlyphPen(None)
    pen.moveTo((x_min, y_min))
    pen.lineTo((x_max, y_min))
    pen.lineTo((x_max, y_max))
    pen.lineTo((x_min, y_max))
    pen.closePath()

    glyf[gname] = pen.glyph()
    fixed_count += 1

print(f"  Added bounding-box outlines to {fixed_count} empty COLR base glyphs", file=sys.stderr)

# --- Rebalance vertical metrics ---
em = font["head"].unitsPerEm

y_min_all = 0
y_max_all = 0
for gname in glyf.keys():
    g = glyf[gname]
    if hasattr(g, "yMin") and (g.numberOfContours > 0 or g.isComposite()):
        y_min_all = min(y_min_all, g.yMin)
        y_max_all = max(y_max_all, g.yMax)

new_ascent = max(y_max_all, int(em * 0.80))
new_descent = max(abs(y_min_all), int(em * 0.20))
if new_ascent + new_descent < em:
    new_descent = em - new_ascent

print(f"  Metrics: ascent={new_ascent} descent={new_descent} (EM={em})", file=sys.stderr)

os2 = font["OS/2"]
os2.sTypoAscender = new_ascent
os2.sTypoDescender = -new_descent
os2.sTypoLineGap = 0
os2.usWinAscent = new_ascent
os2.usWinDescent = new_descent
os2.fsSelection |= 0x80  # USE_TYPO_METRICS
os2.panose.bFamilyType = 5  # Latin Symbol

hhea = font["hhea"]
hhea.ascent = new_ascent
hhea.descent = -new_descent
hhea.lineGap = 0

font["head"].yMin = -new_descent
font["head"].yMax = new_ascent

font.save(fontfile)
print(f"  Saved: {fontfile}", file=sys.stderr)
