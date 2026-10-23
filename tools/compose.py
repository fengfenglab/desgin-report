"""把截图拼成带标签的对比图。compose(rows, out, col_labels, row_labels)；rows = [[png路径,...],...]"""
from PIL import Image, ImageDraw, ImageFont
F = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def compose(rows, out, cols=None, rlabels=None, title=None, w=520):
    h = int(w * 844 / 390); g = 24; lw = 120 if rlabels else 0; th = 110 if title else 0; ch = 70 if cols else 0
    W = lw + len(rows[0]) * (w + g) + g; H = th + ch + len(rows) * (h + g) + g
    sh = Image.new('RGB', (W, H), '#ffffff'); d = ImageDraw.Draw(sh)
    f1 = ImageFont.truetype(F, 44, index=2); f2 = ImageFont.truetype(F, 32, index=2)
    if title: d.text((g + lw, 34), title, font=f1, fill='#3a342e')
    for j, c in enumerate(cols or []): d.text((lw + g + j * (w + g) + w / 2, th + 30), c, font=f2, fill='#3a342e', anchor='mm')
    for i, r in enumerate(rows):
        y = th + ch + g + i * (h + g)
        if rlabels:
            for k, ch_ in enumerate(rlabels[i]): d.text((lw / 2 + 6, y + 60 + k * 44), ch_, font=f2, fill='#3a342e', anchor='mm')
        for j, p in enumerate(r):
            if not p: continue
            im = Image.open(p).convert('RGB').resize((w, h), Image.LANCZOS)
            x = lw + g + j * (w + g); sh.paste(im, (x, y)); d.rectangle([x - 1, y - 1, x + w, y + h], outline='#d8d0c4')
    sh.save(out, optimize=True); return sh.size
