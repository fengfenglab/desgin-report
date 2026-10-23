#!/usr/bin/env python3
"""汇报网页生成器 · 第 1 步：从 PPTX / PDF 中提取每一页的文字、图片和整页渲染图。

用法:
  python3 tools/extract.py 方案.pptx  --project my-project [--pdf 已导出的.pdf]
  python3 tools/extract.py 方案.pdf   --project my-project

输出: work/<project>/raw.json, work/<project>/media/*.jpg, work/<project>/render/pNN.jpg
"""
import argparse, hashlib, io, json, os, re, subprocess, sys, shutil
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_MAX = 3200          # 中间素材最长边（构建时再压缩成网页尺寸）
RENDER_W = 1800           # 整页渲染图宽度
NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
CJK = r'\u3000-\u303f\u4e00-\u9fff\uff00-\uffef'


def clean_text(t):
    """去掉 PPT 里为了排版加的字间空格，如「概    念    解  读」「C O N C E P T」。"""
    t = t.replace('\u000b', '\n').replace('\xa0', ' ')
    lines = []
    for ln in t.split('\n'):
        ln = ln.strip()
        # 中文字之间的空格
        ln = re.sub(rf'(?<=[{CJK}])\s+(?=[{CJK}])', '', ln)
        # 单字母空格拼写的英文: "C O N C E P T  I N T E R" -> "CONCEPT INTER"
        if re.fullmatch(r'(?:[A-Za-z] ?)+(?:\s{2,}(?:[A-Za-z] ?)+)*', ln) and re.search(r'[A-Za-z] [A-Za-z] [A-Za-z]', ln):
            ln = ' '.join(w.replace(' ', '') for w in re.split(r'\s{2,}', ln))
        ln = re.sub(r'[ \t]{2,}', ' ', ln)
        lines.append(ln)
    out = '\n'.join(lines)
    out = re.sub(r'\n{3,}', '\n\n', out).strip()
    return out


def save_image(blob, crop, outdir, cache):
    """按 PPT 的裁切参数裁图，缩到 MEDIA_MAX，存为 jpg/png，返回 (文件名, 宽, 高)。"""
    key = hashlib.md5(blob + json.dumps(crop).encode()).hexdigest()[:12]
    if key in cache:
        return cache[key]
    try:
        im = Image.open(io.BytesIO(blob))
        im.load()
    except Exception:
        return None  # EMF/WMF 等无法解码的格式跳过，整页渲染图兜底
    im = ImageOps.exif_transpose(im)
    l, t, r, b = [max(0.0, min(0.95, c)) for c in crop]
    W, H = im.size
    if l or t or r or b:
        box = (int(W * l), int(H * t), int(W * (1 - r)), int(H * (1 - b)))
        if box[2] - box[0] > 10 and box[3] - box[1] > 10:
            im = im.crop(box)
    if max(im.size) > MEDIA_MAX:
        im.thumbnail((MEDIA_MAX, MEDIA_MAX), Image.LANCZOS)
    has_alpha = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
    if has_alpha:
        im = im.convert('RGBA')
        alpha = im.getchannel('A')
        transparent = alpha.getextrema()[0] < 250
    else:
        transparent = False
    name = f'{key}.png' if transparent else f'{key}.jpg'
    path = os.path.join(outdir, name)
    if transparent:
        im.save(path, optimize=True)
    else:
        im.convert('RGB').save(path, quality=92)
    res = (name, im.size[0], im.size[1], transparent)
    cache[key] = res
    return res


# ---------------------------------------------------------------- PPTX
def extract_pptx(path, outdir):
    from pptx import Presentation
    prs = Presentation(path)
    SW, SH = prs.slide_width, prs.slide_height
    cache, slides = {}, []

    def xfrm_of(el):
        x = el.find('.//a:xfrm', NS)
        if x is None:
            return None
        off, ext = x.find('a:off', NS), x.find('a:ext', NS)
        if off is None or ext is None:
            return None
        r = dict(x=int(off.get('x')), y=int(off.get('y')), w=int(ext.get('cx')), h=int(ext.get('cy')))
        co, ce = x.find('a:chOff', NS), x.find('a:chExt', NS)
        if co is not None and ce is not None:
            r.update(cx=int(co.get('x')), cy=int(co.get('y')), cw=int(ce.get('cx')) or 1, ch=int(ce.get('cy')) or 1)
        return r

    def walk(slide, shapes, tf, out, depth=0):
        for sh in shapes:
            el = sh._element
            x, y, w, h = sh.left or 0, sh.top or 0, sh.width or 0, sh.height or 0
            ax, ay = tf(x, y)
            ax2, ay2 = tf(x + w, y + h)
            box = [ax / SW, ay / SH, (ax2 - ax) / SW, (ay2 - ay) / SH]
            if sh.shape_type == 6:  # GROUP
                g = xfrm_of(el.find('p:grpSpPr', NS)) or {}
                if 'cw' in g:
                    sx, sy = g['w'] / g['cw'], g['h'] / g['ch']
                    inner = (lambda gx=g, sx=sx, sy=sy: (lambda X, Y: tf(gx['x'] + (X - gx['cx']) * sx, gx['y'] + (Y - gx['cy']) * sy)))()
                else:
                    inner = tf
                walk(slide, sh.shapes, inner, out, depth + 1)
                continue
            # 图片：普通图片 或 用图片填充的形状（如圆形图片）
            blip = el.find('.//a:blip', NS)
            if blip is not None and blip.get('{%s}embed' % NS['r']):
                rid = blip.get('{%s}embed' % NS['r'])
                try:
                    blob = slide.part.related_part(rid).blob
                except Exception:
                    blob = None
                src = el.find('.//a:srcRect', NS)
                crop = [int(src.get(k, 0)) / 100000 if src is not None else 0 for k in ('l', 't', 'r', 'b')]
                if blob:
                    r = save_image(blob, crop, outdir, cache)
                    if r:
                        geom = el.find('.//a:prstGeom', NS)
                        out.append(dict(type='image', file=r[0], px=[r[1], r[2]], transparent=r[3], box=box,
                                        shape=(geom.get('prst') if geom is not None else 'rect'), z=len(out)))
            if sh.has_text_frame and sh.text_frame.text.strip():
                sizes, bold = [], False
                for p in sh.text_frame.paragraphs:
                    for run in p.runs:
                        if run.font.size: sizes.append(run.font.size.pt)
                        if run.font.bold: bold = True
                out.append(dict(type='text', text=clean_text(sh.text_frame.text), raw=sh.text_frame.text,
                                size=max(sizes) if sizes else None, bold=bold, box=box, z=len(out)))
            elif sh.has_table if hasattr(sh, 'has_table') else False:
                rows = [[c.text for c in r.cells] for r in sh.table.rows]
                out.append(dict(type='table', rows=rows, box=box, z=len(out)))

    for i, s in enumerate(prs.slides, 1):
        els = []
        walk(s, s.shapes, lambda X, Y: (X, Y), els)
        notes = ''
        if s.has_notes_slide:
            notes = s.notes_slide.notes_text_frame.text.strip()
        slides.append(dict(index=i, elements=els, notes=notes))
        print(f'  slide {i}: {sum(e["type"]=="image" for e in els)} images, {sum(e["type"]=="text" for e in els)} texts')
    return slides, SW / SH


# ---------------------------------------------------------------- PDF
def extract_pdf_content(pdf, outdir):
    import pymupdf
    doc = pymupdf.open(pdf)
    cache, slides = {}, []
    ratio = doc[0].rect.width / doc[0].rect.height
    for i, page in enumerate(doc, 1):
        PW, PH = page.rect.width, page.rect.height
        els = []
        for info in page.get_image_info(xrefs=True):
            if not info.get('xref'): continue
            try:
                blob = doc.extract_image(info['xref'])['image']
            except Exception:
                continue
            x0, y0, x1, y1 = info['bbox']
            r = save_image(blob, [0, 0, 0, 0], outdir, cache)
            if r:
                els.append(dict(type='image', file=r[0], px=[r[1], r[2]], transparent=r[3], shape='rect',
                                box=[x0 / PW, y0 / PH, (x1 - x0) / PW, (y1 - y0) / PH], z=len(els)))
        for b in page.get_text('dict')['blocks']:
            if b.get('type') != 0: continue
            txt = '\n'.join(''.join(s['text'] for s in l['spans']) for l in b['lines'])
            if not txt.strip(): continue
            size = max(s['size'] for l in b['lines'] for s in l['spans'])
            x0, y0, x1, y1 = b['bbox']
            els.append(dict(type='text', text=clean_text(txt), raw=txt, size=size, bold=False,
                            box=[x0 / PW, y0 / PH, (x1 - x0) / PW, (y1 - y0) / PH], z=len(els)))
        slides.append(dict(index=i, elements=els, notes=''))
    return slides, ratio


def ensure_pdf(src, workdir, given):
    if given:
        return given
    if src.lower().endswith('.pdf'):
        return src
    print('  用 LibreOffice 把 PPTX 转成 PDF（大文件需要几分钟）…')
    subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', workdir, src], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
    return os.path.join(workdir, os.path.splitext(os.path.basename(src))[0] + '.pdf')


def render_pages(pdf, rdir):
    import pymupdf
    doc = pymupdf.open(pdf)
    for i, page in enumerate(doc, 1):
        out = os.path.join(rdir, f'p{i:02d}.jpg')
        if os.path.exists(out): continue
        zoom = RENDER_W / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        Image.frombytes('RGB', (pix.width, pix.height), pix.samples).save(out, quality=88)
    return len(doc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', help='PPTX 或 PDF')
    ap.add_argument('--project', required=True, help='项目代号（英文/拼音），如 my-project')
    ap.add_argument('--pdf', help='已有的 PDF 导出（PPTX 输入时用来生成整页渲染图，省去转换时间）')
    a = ap.parse_args()
    work = os.path.join(ROOT, 'work', a.project)
    media, rdir = os.path.join(work, 'media'), os.path.join(work, 'render')
    os.makedirs(media, exist_ok=True); os.makedirs(rdir, exist_ok=True)
    print('1/2 提取文字与图片…')
    if a.source.lower().endswith('.pptx'):
        slides, ratio = extract_pptx(a.source, media)
    else:
        slides, ratio = extract_pdf_content(a.source, media)
    print('2/2 生成整页渲染图…')
    pdf = ensure_pdf(a.source, work, a.pdf)
    n = render_pages(pdf, rdir)
    for s in slides:
        s['render'] = f'p{s["index"]:02d}.jpg' if s['index'] <= n else None
    json.dump(dict(source=os.path.abspath(a.source), project=a.project, ratio=ratio, slides=slides),
              open(os.path.join(work, 'raw.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'完成：{len(slides)} 页 → {work}/raw.json')


if __name__ == '__main__':
    main()
