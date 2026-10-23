#!/usr/bin/env python3
"""汇报网页生成器 · 第 3 步：把 config.json 构建成静态网站（可直接托管）。

用法:
  python3 tools/build.py --project my-project

输出: out/<project>/index.html + assets/ + img/   （整个文件夹上传到任意静态托管即可）
"""
import argparse, hashlib, html, json, os, re, shutil, io
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, 'templates')
G = '/usr/share/fonts/truetype/sand-box/google/'
# 全部为 OFL 开源可商用字体；(路径, ttc 序号, 是否可变字重)
FONT_FILES = {
    'noto-serif-sc': ('/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc', 2),   # 思源宋体 / Noto Serif SC
    'cormorant': (G + 'Cormorant Garamond/CormorantGaramond-VariableFont_wght.ttf', None),
    'cormorant-i': (G + 'Cormorant Garamond/CormorantGaramond-Italic-VariableFont_wght.ttf', None),
    'marcellus': (G + 'Marcellus/Marcellus-Regular.ttf', None),
    'jost': (G + 'Jost/Jost-VariableFont_wght.ttf', None),
}
THEMES = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', 'themes', 'themes.json'), encoding='utf-8'))
THEMES.pop('_说明', None)
TH = {'id': 'wabi'}
SLIDE_IDX = {}
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import translate, load_glossary
GLOSS = load_glossary()
LOC_LOG = []
ROOM_PAGE = {}       # 房间名 → 页序号（效果图汇报模式下点房间跳转用）


FLOORS = []          # config.floors：[{"id":"B1F","name":"花园层","name_en":"Garden Level"}, …]，从下到上


def floor_order(f):
    ids = [x.get('id') for x in FLOORS]
    if f in ids: return ids.index(f)
    m = re.match(r'^B(\d+)F?$', f or '', re.I)
    if m: return -int(m.group(1))
    m = re.match(r'^(\d+)F?$', f or '', re.I)
    return int(m.group(1)) if m else 99


def floor_name(f):
    return next((x.get('name', '') for x in FLOORS if x.get('id') == f), '')


def split_room(name, floor=None):
    """「1F·阳台」「1F:阳台」→ ('1F', '阳台')；不带楼层的返回 (floor, name)。"""
    m = re.match(r'^\s*((?:B\d+|\d+)F)\s*[·:：/\s]\s*(.+)$', name or '', re.I)
    return (m.group(1).upper(), m.group(2).strip()) if m else (floor, name)


def resolve_locators(pages, work):
    """locator：页面里写 {"plan": 平面图页的PPT页码, "room": "客厅"} 或 {"plan":5,"x":40,"y":30}；
    false 表示不要；不写则按标题里的房间名自动匹配（匹配不唯一时取第一个并记录在日志里）。"""
    plans = [p for p in pages if p['template'] == 'plan' and p.get('rooms')]
    allrooms = [(pl, r) for pl in plans for r in pl['rooms']]
    def mk(pl, r, x=None, y=None):
        img = pl['images'][0]
        fl = (pl.get('_floors') and dict((k, v) for k, v in pl['_floors']).get(SLIDE_IDX.get(pl['slide']))) or pl.get('title', '')
        return dict(src=img['src'], w=img['w'], h=img['h'], x=r['x'] if r else x, y=r['y'] if r else y,
                    room=r['name'] if r else '', floor=fl, label=(pl.get('title', '') + ' · ' + (r['name'] if r else '')).strip(' ·'))
    for p in pages:
        L = p.get('locator')
        if L is False or p['template'] in ('plan', 'cover', 'section', 'about'): continue
        if isinstance(L, dict):
            pl = next((x for x in pages if x.get('slide') == L.get('plan') and x['template'] == 'plan'), None)
            if not pl: LOC_LOG.append(f'第{p.get("slide")}页 locator 指向的平面图页 {L.get("plan")} 不存在'); continue
            r = next((r for r in pl.get('rooms') or [] if r['name'] == L.get('room')), None)
            p['_loc'] = mk(pl, r, L.get('x', 50), L.get('y', 50)); continue
        if p.get('room'):           # 设计师填的房间名（可以是一个，也可以是列表）→ 在平面图编号里找
            names = p['room'] if isinstance(p['room'], list) else [p['room']]
            byplan, found = {}, []
            for nm in names:
                fl, nm2 = split_room(nm)
                cand = [(pl, r) for pl, r in allrooms if r['name'] == nm2 and (not fl or pl.get('floor') == fl)]
                # 同名房间出现在几层：优先本页 floor 那一层
                if len(cand) > 1 and not fl and p.get('floor'):
                    c2 = [x for x in cand if x[0].get('floor') == p['floor']]
                    cand = c2 or cand
                if len(cand) > 1: LOC_LOG.append(f'第{p.get("slide")}页 room「{nm}」在多张平面图上都有，用了 {cand[0][0].get("floor") or cand[0][0].get("title")}；可写成「1F·{nm2}」指定楼层')
                if not cand: LOC_LOG.append(f'第{p.get("slide")}页 room「{nm}」在平面图编号里找不到，角标上不标'); continue
                pl, r = cand[0]; byplan.setdefault(id(pl), (pl, []))[1].append(r); found.append(nm2)
            if not byplan: continue
            locs = []
            for pl, rs in sorted(byplan.values(), key=lambda v: -floor_order(v[0].get('floor'))):   # 上层在上
                L = mk(pl, rs[0]); L['pts'] = [(r['x'], r['y']) for r in rs]
                if pl.get('floor'): L['floor'] = pl['floor']
                L['room'] = '·'.join(r['name'] for r in rs); L['rooms'] = [r['name'] for r in rs]
                L['label'] = (pl.get('title', '') + ' · ' + L['room']).strip(' ·')
                locs.append(L)
            p['_loc'] = dict(locs[0], rooms=found, room='·'.join(found)); p['_locs'] = locs
            continue
        # 没填 room：只提示，不自动加角标
        title = p.get('title') or ''
        if p['template'] not in ('grid', 'full', 'split', 'selection', 'render', 'material') or not title or not allrooms: continue
        sug = sorted({r['name'] for pl, r in allrooms if r['name'] in title}, key=len, reverse=True)
        if sug: SUGGEST.append(f'第{p.get("slide")}页「{title}」没填 room，可能是：' + '、'.join(sug))


SUGGEST = []
SIZES = {'m': 900, 'l': 1800}
PLAN_SIZES = {'m': 1600, 'l': 3600}
LITE = {'m': 1200}                 # --lite：每张图只出一个尺寸，适合有容量/文件数限制的免费托管
LITE_PLAN = {'m': 1400, 'l': 2400}
Q = 78

e = lambda s: html.escape(s or '', quote=True)


def nl(s):
    """多行文本 → <br>，并去掉装饰用的破折号。"""
    s = re.sub(r'^[—\-–\s]+|[—\-–\s]+$', '', (s or '').strip())
    return '<br>'.join(e(x) for x in s.split('\n') if x.strip())


class Images:
    def __init__(self, work, out, lite=False):
        self.work, self.dir, self.lite = work, os.path.join(out, 'img'), lite
        os.makedirs(self.dir, exist_ok=True)
        self.used = set()

    def get(self, src, plan=False):
        path = os.path.join(self.work, src)
        sizes = (LITE_PLAN if plan else LITE) if self.lite else (PLAN_SIZES if plan else SIZES)
        key = hashlib.md5((src + str(sizes)).encode()).hexdigest()[:10]
        res = {}
        im = None
        for k, px in sizes.items():
            name = f'{key}-{k}.webp'
            fp = os.path.join(self.dir, name)
            self.used.add(name)
            if not os.path.exists(fp):
                if im is None:
                    im = ImageOps.exif_transpose(Image.open(path))
                    im = im.convert('RGBA') if im.mode in ('RGBA', 'LA', 'P') else im.convert('RGB')
                t = im.copy()
                t.thumbnail((px, px), Image.LANCZOS)
                t.save(fp, 'WEBP', quality=(68 if self.lite else Q) if not plan else (76 if self.lite else 82), method=6)
            with Image.open(fp) as t:
                res[k] = ('img/' + name, t.size[0], t.size[1])
        if 'l' not in res:
            res['l'] = res['m']
        # 原图小于大尺寸时，两个版本一样大，只保留一个
        elif res['l'][1] == res['m'][1]:
            os.remove(os.path.join(self.dir, res['l'][0][4:])) if os.path.exists(os.path.join(self.dir, res['l'][0][4:])) and res['l'][0] != res['m'][0] else None
            self.used.discard(res['l'][0][4:])
            res['l'] = res['m']
        return res

    def tag(self, src, sizes='100vw', lazy=True, cls='', plan=False, alt=''):
        r = self.get(src, plan)
        m, l = r['m'], r['l']
        srcset = f'{m[0]} {m[1]}w' + (f', {l[0]} {l[1]}w' if l != m else '')
        return (f'<img src="{m[0]}" srcset="{srcset}" sizes="{sizes}" width="{m[1]}" height="{m[2]}" alt="{e(alt)}"'
                f'{" loading=lazy" if lazy else ""} decoding="async"{(" class=" + cls) if cls else ""}>'), l[0]

    def thumb(self, src, px=280):
        """角标小平面图用的缩略图。"""
        key = hashlib.md5((src + 'thumb%d' % px).encode()).hexdigest()[:10]
        name = f'{key}-t.webp'; fp = os.path.join(self.dir, name); self.used.add(name)
        if not os.path.exists(fp):
            im = Image.open(os.path.join(self.work, src)).convert('RGB'); im.thumbnail((px, px), Image.LANCZOS)
            im.save(fp, 'WEBP', quality=80, method=6)
        return 'img/' + name

    def palette(self, srcs, n=5):
        thumbs = []
        for s in srcs:
            try:
                im = Image.open(os.path.join(self.work, s)).convert('RGB'); im.thumbnail((120, 120)); thumbs.append(im)
            except Exception:
                pass
        if not thumbs: return []
        W = sum(t.size[0] for t in thumbs); H = max(t.size[1] for t in thumbs)
        sheet = Image.new('RGB', (W, H), (244, 241, 236)); x = 0
        for t in thumbs: sheet.paste(t, (x, 0)); x += t.size[0]
        q = sheet.quantize(colors=n + 3, method=Image.Quantize.MEDIANCUT)
        pal = q.getpalette()[:(n + 3) * 3]
        counts = sorted(q.getcolors(), reverse=True)
        cols = []
        for cnt, idx in counts:
            c = tuple(pal[idx * 3: idx * 3 + 3])
            if sum(c) > 735 or sum(c) < 30: continue        # 去掉纯白纯黑
            if any(sum(abs(a - b) for a, b in zip(c, o)) < 40 for o in cols): continue
            cols.append(c)
            if len(cols) == n: break
        cols.sort(key=lambda c: -(0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]))
        return ['#%02x%02x%02x' % c for c in cols]


# ---------------------------------------------------------------- 模板
def head_block(p, idx=None, tag='h2'):
    h = '<div class="head%s">' % (' long' if len(p.get('title') or '') > 6 else '')
    if idx: h += f'<span class="idx">{e(idx)}</span>'
    if p.get('eyebrow'): h += f'<div class="cap">{e(p["eyebrow"])}</div>'
    if p.get('title'): h += f'<{tag} class="serif">{e(p["title"])}</{tag}>'
    if p.get('title_en'):
        if TH.get('mixed_title'): h += mixed(p['title_en'])
        elif TH.get('en_break'): h += '<div class="en">' + '<br>'.join(e(x) for x in p['title_en'].split(' · ')) + '</div>'
        else: h += f'<div class="en">{e(p["title_en"])}</div>'
    if p.get('subtitle'): h += f'<div class="sub">{nl(p["subtitle"])}</div>'
    return h + '</div>'


def mixed(en, cls='en mix'):
    """法式杂志标题：正体大写 —— 斜体 —— 正体，用细线连接。"""
    main, _, suf = en.partition(' · ')
    w = main.split()
    first, mid = (w[0], ' '.join(w[1:])) if len(w) > 1 else ('', main)
    out = f'<div class="{cls}">'
    if first: out += f'<b>{e(first.upper())}</b><i></i>'
    out += f'<em>{e(mid)}</em>'
    if suf: out += f'<i></i><b>{e(suf.upper())}</b>'
    return out + '</div>'


def vlabel(p):
    return f'<div class="vlabel" aria-hidden="true">{e(p.get("title_en", ""))}</div>' if p.get('title_en') else ''


def bars(cols, n=3):
    return '<div class="bars">' + ''.join(f'<span style="background:{c}"><em>{c.upper()}</em></span>' for c in cols[:n]) + '</div>' if cols else ''


def pal_html(cols):
    if not cols: return ''
    return ('<div class="pal">' + ''.join(f'<span style="background:{c}" title="{c}"></span>' for c in cols) + '<em>PALETTE</em></div>'
            + bars(cols))


def about_part(cfg, part=None):
    """brand.json 的 about：可分 studio / designer 两部分；{years} 按 当年 − career_start_year 计算；图片路径相对品牌目录。"""
    import datetime
    b = (cfg.get('_brand') or {}); ab = dict(b.get('about') or {})
    d = dict(ab.get(part) or {}) if part else {k: v for k, v in ab.items() if not isinstance(v, dict)}
    y0 = ab.get('career_start_year')
    yrs = str(datetime.date.today().year - int(y0)) if y0 else ''
    def sub(x): return x.replace('{years}', yrs) if isinstance(x, str) else x
    for k in ('body', 'items'):
        d[k] = [sub(x) for x in d.get(k) or [] if not ('{years}' in x and not yrs)]
    if d.get('image') and isinstance(d['image'], str):
        src = d['image'] if os.path.isabs(d['image']) else os.path.join(b.get('_dir', ''), d['image'])
        if os.path.exists(src):
            from PIL import Image as _I
            with _I.open(src) as t: d['image'] = dict(src=src, w=t.size[0], h=t.size[1])
        else: d.pop('image')
    return d


def ph(I, img, sizes, lazy=True, style='', cls='ph', plan=False):
    t, big = I.tag(img['src'], sizes, lazy, plan=plan, alt=img.get('caption', ''))
    cap = f' data-cap="{e(img.get("caption", ""))}"' if img.get('caption') else ''
    return f'<figure class="{cls} zoom" data-lb="{big}"{cap}{" data-plan" if plan else ""}{(" style=" + chr(34) + style + chr(34)) if style else ""}>{t}</figure>'


# 不对称拼图：6 列网格，(列起点, 列跨度, 行起点, 行跨度)
GRID = {
    1: (6, [(1, 6, 1, 6)]),
    2: (6, [(1, 6, 1, 4), (2, 5, 5, 2)]),
    3: (6, [(1, 6, 1, 3), (1, 4, 4, 3), (5, 2, 4, 3)]),
    4: (6, [(1, 4, 1, 3), (5, 2, 1, 3), (1, 2, 4, 3), (3, 4, 4, 3)]),
    5: (6, [(1, 4, 1, 3), (5, 2, 1, 3), (1, 2, 4, 3), (3, 2, 4, 3), (5, 2, 4, 3)]),
    6: (6, [(1, 4, 1, 2), (5, 2, 1, 2), (1, 3, 3, 2), (4, 3, 3, 2), (1, 2, 5, 2), (3, 4, 5, 2)]),
    7: (8, [(1, 4, 1, 3), (5, 2, 1, 3), (1, 2, 4, 2), (3, 2, 4, 2), (5, 2, 4, 2), (1, 3, 6, 3), (4, 3, 6, 3)]),
    8: (8, [(1, 4, 1, 3), (5, 2, 1, 3), (1, 2, 4, 2), (3, 2, 4, 2), (5, 2, 4, 2), (1, 2, 6, 3), (3, 2, 6, 3), (5, 2, 6, 3)]),
}


CN_NUM = '壹贰叁肆伍陆柒捌玖拾'
CHAPTERS = []          # [(页序号, 中文数字, 中文章节名, 英文)]
QR = {}


def seal_html(cfg):
    if cfg.get('_seal_src'): return f'<div class="seal simg"><img src="{cfg["_seal_src"]}" alt=""></div>'
    return f'<div class="seal">{e(cfg["seal"])}</div>' if cfg.get('seal') else ''


def copy_brand_assets(cfg, out):
    """把品牌的 logo / 印章图片拷进 assets。"""
    for k in ('logo', 'seal_image'):
        src = cfg.get(k)
        if src and os.path.exists(src):
            fn = k + os.path.splitext(src)[1]; shutil.copy(src, os.path.join(out, 'assets', fn))
            cfg['_' + k.split('_')[0] + '_src'] = 'assets/' + fn


def badge_html(p):
    return f'<div class="badge">{e(p["badge"])}</div>' if p.get('badge') else ''


def qr_html(cfg):
    if not QR: return ''
    return (f'<div class="qr"><img src="{QR["src"]}" alt="微信二维码" width="160" height="160">'
            f'<span>{nl(QR["label"])}</span></div>')


def make_qr(cfg, work, out):
    """结尾页微信二维码：config.contact.qr 指向真实二维码图片（work 目录下的相对路径）；没有就放一张「占位」图。"""
    QR.clear()
    if cfg.get('qr') is False: return
    src = (cfg.get('contact') or {}).get('qr')
    if not src: return                       # 没填就不显示（不留空框）
    os.makedirs(os.path.join(out, 'assets'), exist_ok=True)
    if src and os.path.exists(os.path.join(work, src)):
        shutil.copy(os.path.join(work, src), os.path.join(out, 'assets', 'qr' + os.path.splitext(src)[1]))
        QR.update(src='assets/qr' + os.path.splitext(src)[1], label='长按识别二维码\n添加微信'); return
    if src != 'placeholder':
        print(f'  [二维码] 找不到 {src}，结尾页不显示二维码'); return
    import random
    from PIL import ImageDraw, ImageFont
    random.seed(3); N, M = 25, 12
    im = Image.new('RGB', (N * M + 2 * M * 2, N * M + 2 * M * 2), 'white'); d = ImageDraw.Draw(im); o = M * 2
    for y in range(N):
        for x in range(N):
            if random.random() < .45: d.rectangle([o + x * M, o + y * M, o + x * M + M - 1, o + y * M + M - 1], fill='#3a342e')
    for fx, fy in ((0, 0), (N - 7, 0), (0, N - 7)):
        X, Y = o + fx * M, o + fy * M
        d.rectangle([X - M, Y - M, X + 8 * M - 1, Y + 8 * M - 1], fill='white')
        d.rectangle([X, Y, X + 7 * M - 1, Y + 7 * M - 1], fill='#3a342e'); d.rectangle([X + M, Y + M, X + 6 * M - 1, Y + 6 * M - 1], fill='white')
        d.rectangle([X + 2 * M, Y + 2 * M, X + 5 * M - 1, Y + 5 * M - 1], fill='#3a342e')
    W = im.size[0]; f = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 46, index=2)
    d.rectangle([W / 2 - 70, W / 2 - 40, W / 2 + 70, W / 2 + 40], fill='white', outline='#b4472e', width=3)
    d.text((W / 2, W / 2), '占位', font=f, fill='#b4472e', anchor='mm')
    im.save(os.path.join(out, 'assets', 'qr-placeholder.png'), optimize=True)
    QR.update(src='assets/qr-placeholder.png', label='微信二维码（占位，待替换）')


def locator_html(p, I):
    """角标小平面图：当前房间用点缀色圆点标出，点开看完整平面图。房间跨楼层时，每层一张小图上下叠放。"""
    locs = p.get('_locs') or ([p['_loc']] if p.get('_loc') else [])
    if not locs: return ''
    h = ''
    for L in locs[:3]:
        th = I.thumb(L['src'])
        big = I.get(L['src'], plan=True)['l'][0]
        h += (f'<button class="loc1" data-lb="{big}" data-plan data-solo data-cap="{e(L["label"])}" aria-label="查看平面图 {e(L["label"])}">'
              f'<b><img src="{th}" alt="" width="{L["w"]}" height="{L["h"]}" style="aspect-ratio:{L["w"]}/{L["h"]}">'
              + ''.join(f'<i style="left:{x}%;top:{y}%"></i>' for x, y in (L.get('pts') or [(L['x'], L['y'])])) + f'</b><span>{e(L["floor"])}</span></button>')
    return f'<div class="loc{" multi" if len(locs) > 1 else ""}">{h}</div>'


def render_cover(p, I, cfg, attrs):
    th = TH['id']
    name = p.get('title') or cfg['title']
    en = p.get('title_en') or cfg.get('title_en', '')
    sub = p.get('subtitle') or ''
    rep = cfg.get('report_name', '设计方案汇报'); rep_en = cfg.get('report_name_en', 'Design Proposal')
    st, st_en = cfg['studio'], cfg['studio_en'].upper()
    img, _ = I.tag(p['bg'], '100vw', lazy=False) if p.get('bg') else ('', '')
    if th == 'zen':
        return (f'<section class="pg cover cz"{attrs}><figure class="zstrip">{img}</figure>'
                f'<div class="ztitle"><h1>{e(name)}</h1><i class="vr"></i><div class="zsub">{e(rep)}</div>'
                f'<div class="zen-en">{e(en)} · {e(sub)}</div></div>'
                f'{seal_html(cfg)}'
                f'<div class="zfoot"><span>{e(st)}</span><span>{e(st_en)}</span></div><div class="hint">上滑 ︿</div></section>')
    if th == 'wabi':
        cols = I.palette([p['bg']], 4) if p.get('bg') else []
        return (f'<section class="pg cover cw" data-dark data-darkbot{attrs}><figure class="wimg">{img}</figure>'
                f'<div class="wblock"><div class="cap">{e(sub)}</div><h1>{e(en.upper())}</h1>'
                f'<div class="zh">{e(name)}<span>{e(rep)}</span></div>{bars(cols)}'
                f'<div class="studio">{e(st)} · {e(st_en)}</div></div></section>')
    if th == 'mono':
        w = en.split()
        big = (' '.join(w[:-1]) + '<br>' + w[-1]) if len(w) > 1 else e(en)
        return (f'<section class="pg cover cm"{attrs}><div class="mtop"><i class="sq"></i><span>{e(sub)}</span><b></b></div>'
                f'<figure class="mimg">{img}</figure>'
                f'<div class="mtitle"><div class="zh">{e(name)}<span>{e(rep)}</span></div><h1>{big}</h1>'
                f'<div class="mline"><i></i>{e(rep_en)}</div></div>'
                f'<div class="mv">{e(st_en)} — {e(st)}</div></section>')
    if th == 'french':
        return (f'<section class="pg cover cf"{attrs}><div class="frtop">{e(st_en)}<span>{e(st)}</span></div>'
                f'<figure class="frame">{img}</figure>'
                f'<div class="frtitle"><b>DESIGN</b><div class="row"><i></i><em>{e(en)}</em><i></i></div><b>PROPOSAL</b></div>'
                f'<div class="zh">{e(name)} · {e(rep)}</div><div class="frfoot">{e(sub)}</div></section>')
    raise ValueError(th)


def render_page(p, i, n, I, cfg, first):
    html_ = _render_page(p, i, n, I, cfg, first)
    loc = locator_html(p, I)
    if loc:
        html_ = re.sub(r'^<section class="pg ', '<section class="pg has-loc ', html_, count=1)
        html_ = html_.replace('>', '>' + loc, 1)
    return html_


def _render_page(p, i, n, I, cfg, first):
    t = p['template']
    lazy = i > 1
    num = '%02d' % (i + 1)
    attrs = f' data-chap="{e(p.get("_flabel", ""))}" data-ci="{p.get("_ci", 0)}"'
    if TH['id'] == 'wabi' and t in ('grid', 'material'):
        attrs += ' data-darkbot'
    imgs = p.get('images', [])
    if t == 'cover' and TH['id'] != 'wabi-classic':
        return render_cover(p, I, cfg, attrs)
    if t == 'cover':
        bg, _ = I.tag(p['bg'], '100vw', lazy=False) if p.get('bg') else ('', '')
        name = p.get('title') or cfg['title']
        en = p.get('title_en') or cfg.get('title_en', '')
        return (f'<section class="pg cover" data-dark data-darkbot{attrs}><div class="bgimg">{bg}</div>'
                f'<div class="vt">{e(name)}<small>{e(en)}</small></div>'
                f'<div class="meta"><div class="cap">{e(p.get("subtitle") or "")}</div>'
                f'<h1>{e(name)} · {e(cfg.get("report_name", ""))}</h1><div class="en">{e(cfg.get("report_name_en", ""))}</div>'
                f'<div class="rule"></div><div class="studio">{e(cfg["studio"])} · {e(cfg["studio_en"]).upper()}'
                f'{(" · " + e(cfg["date"])) if cfg.get("date") else ""}</div></div>'
                f'<div class="hint">上滑浏览 ︿</div></section>')
    if t == 'section':
        im = ph(I, imgs[0], '(min-width:900px) 50vw, 100vw', lazy, cls='ph simg') if imgs else ''
        no = p.get('_num') or re.sub(r'\D', '', p.get('eyebrow', '')) or ''
        return (f'<section class="pg section"{attrs}>{im}<div class="stext">'
                f'{("<div class=no>" + e(no) + "</div>") if no else ""}'
                f'<div class="cap">{e(p.get("eyebrow", ""))}</div>'
                f'<h2>{e(p.get("title", ""))}</h2><div class="en">{e(p.get("title_en", ""))}</div><div class="rule"></div>'
                f'{("<blockquote>" + e(p["quote"]) + "</blockquote>") if p.get("quote") else ""}'
                f'{("<div class=sub style=margin-top:14px;font-size:11px;letter-spacing:.2em;color:var(--muted)>" + e(p["subtitle"]) + "</div>") if p.get("subtitle") else ""}'
                f'</div></section>')
    if t == 'concept':
        nodes = ''
        for k, it in enumerate(p.get('items', [])[:3]):
            nodes += (f'<div class="node n{k}">{ph(I, it["image"], "(min-width:900px) 240px, 45vw", lazy)}'
                      f'<h3>{e(it.get("title", ""))}</h3><span class="en">{e(it.get("title_en", ""))}</span></div>')
        hp = dict(p); hp['title'] = p.get('eyebrow', '') or p.get('title'); hp['title_en'] = p.get('eyebrow_en', '') or p.get('title_en'); hp['eyebrow'] = ''
        center = f'<div class="center"><b>{e(p.get("title", ""))}</b><span class="en" style="font-size:12px">{e(p.get("title_en", ""))}</span></div>' if p.get('eyebrow') else ''
        svg = '<svg viewBox="0 0 100 100" preserveAspectRatio="none"><polygon points="50,24 24,80 76,80" fill="none" stroke="#b9ab9a" stroke-width=".3" vector-effect="non-scaling-stroke"/></svg>'
        return f'<section class="pg concept"{attrs}>{vlabel(hp)}<div class="inner">{head_block(hp)}<div class="tri">{svg}{center}{nodes}</div></div></section>'
    if t == 'split':
        im = ph(I, imgs[0], '(min-width:900px) 44vw, 100vw', lazy, cls='ph simg') if imgs else ''
        lis = ''
        for b in p.get('body', []):
            m = re.match(r'^([A-Za-z0-9\-]{1,8})[：:](.*)$', b)
            lis += f'<li><b>{e(m.group(1))}</b>　{e(m.group(2))}</li>' if m else f'<li>{e(b)}</li>'
        return f'<section class="pg split"{attrs}><div class="inner">{im}<div class="stext">{head_block(p)}<ol>{lis}</ol></div></div></section>'
    if t == 'plan':
        im = ph(I, imgs[0], '(min-width:900px) 70vw, 100vw', lazy, cls='ph pframe', plan=True)
        w0, h0 = imgs[0]['w'], imgs[0]['h']
        im = im.replace('class="ph pframe zoom"', f'class="ph pframe zoom" style="aspect-ratio:{w0}/{h0}"', 1)
        rooms = p.get('rooms') or []
        mode = p.get('plan_mode') or cfg.get('plan_mode') or 'concept'
        def tgt_of(r):
            if mode != 'render': return None
            if r.get('page') is not None: return SLIDE_IDX.get(r['page'])
            return ROOM_PAGE.get((p.get('floor'), r['name']), ROOM_PAGE.get(r['name']))
        def dot(r):
            pos = f'left:calc(8px + (100% - 16px) * {r["x"]} / 100);top:calc(8px + (100% - 16px) * {r["y"]} / 100)'
            chk = ' chk' if r.get('check') else ''
            tg = tgt_of(r)
            if tg is not None: return f'<button class="rdot go{chk}" data-n="{r["n"]}" data-go="{tg}" style="{pos}" aria-label="{e(r["name"])}">{r["n"]}</button>'
            return f'<span class="rdot{chk}" data-n="{r["n"]}" style="{pos}">{r["n"]}</span>'
        dots = ''.join(dot(r) for r in rooms)
        im = im.replace('</figure>', dots + ('<span class="ztip">点击放大 ⤢</span>' if not rooms else '<span class="ztip">⤢</span>') + '</figure>')
        rl = ''
        if rooms:
            lis = ''
            for r in rooms:
                tgt = tgt_of(r)
                act = f'data-go="{tgt}"' if tgt is not None else f'data-room="{r["n"]}"'
                lis += f'<li><button {act}><i>{r["n"]}</i><span>{e(r["name"])}</span>{"<em>→</em>" if tgt is not None else ""}</button></li>'
            rl = f'<ol class="rooms">{lis}</ol>'
        body = ''.join(f'<p>{nl(b)}</p>' for b in p.get('body', []))
        floors = ''
        if p.get('_floors') and len(p['_floors']) > 1:
            floors = '<div class="floors">' + ''.join(f'<button data-go="{k}"{" class=on" if k == i else ""}>{e(lab)}</button>' for k, lab in p['_floors']) + '</div>'
        note = '' if rooms else '<div class="pnote">点击图纸可放大，双指缩放查看细节</div>'
        return (f'<section class="pg plan{" has-rooms" if rooms else ""}" data-mode="{mode}" data-slide="{p.get("slide") or ""}"{attrs}><div class="inner">{head_block(p, num)}<div class="pwrap">{im}{floors}{rl}'
                f'{("<div class=body style=margin-top:14px>" + body + "</div>") if body else ""}{note}</div></div></section>')
    if t == 'full':
        im = ph(I, imgs[0], '100vw', lazy)
        return (f'<section class="pg full" data-dark data-darkbot{attrs}>{im}<div class="ftxt">{head_block(p)}'
                + ''.join(f'<p>{nl(b)}</p>' for b in p.get('body', [])) + '</div></section>')
    if t == 'grid':
        cols = I.palette([x['src'] for x in imgs]) if p.get('palette') else []
        tall = imgs and sum(x['h'] / max(1, x['w']) for x in imgs) / len(imgs) > 1.5
        if p.get('layout') == 'strip' or (tall and p.get('layout') != 'grid'):
            strip = ''.join(ph(I, x, '(min-width:900px) 22vw, 62vw', lazy) for x in imgs)
            return (f'<section class="pg grid"{attrs}><div class="inner">{head_block(p, num)}<div class="gwrap">'
                    f'<div class="strip">{strip}</div><div class="swipe-tip">← 左右滑动 · 点击看大图 →</div>{pal_html(cols)}</div></div></section>')
        shown = imgs[:8]
        rows, spec = GRID[len(shown)]
        tiles = ''
        for k, (x, (c, cs, r, rs)) in enumerate(zip(shown, spec)):
            big = cs >= 4
            st = f'grid-column:{c}/span {cs};grid-row:{r}/span {rs}'
            tile = ph(I, x, '(min-width:900px) 40vw, 66vw' if big else '(min-width:900px) 20vw, 33vw', lazy, style=st)
            if k == 3 and len(imgs) > 4:
                tile = tile.replace('<figure ', f'<figure data-rest="+{len(imgs) - 4}" ', 1)
            if k == len(shown) - 1 and len(imgs) > 8:
                tile = tile.replace('</figure>', f'<span class="more">+{len(imgs) - 8}</span></figure>')
            tiles += tile
        extra = ''
        if len(imgs) > 8:
            ex = [dict(src=I.get(x['src'])['l'][0], cap=x.get('caption', '')) for x in imgs[8:]]
            extra = f" data-extra='{e(json.dumps(ex, ensure_ascii=False))}'"
        body = ''.join(f'<p>{nl(b)}</p>' for b in p.get('body', []))
        return (f'<section class="pg grid g{len(shown)}"{attrs}{extra}>{vlabel(p)}<div class="inner">{head_block(p, num)}'
                f'<div class="gwrap">'
                f'<div class="g" style="grid-template-rows:repeat({rows},minmax(0,1fr))">{tiles}</div>'
                f'{("<div class=body style=margin-top:12px>" + body + "</div>") if body else ""}{pal_html(cols)}</div></div></section>')
    if t == 'material':
        items = p.get('items') or [dict(title='', text=x.get('caption', ''), images=[x]) for x in imgs]
        allimgs = [x for it in items for x in it.get('images', [])]
        cols = I.palette([x['src'] for x in allimgs]) if p.get('palette') else []
        dense = len(items) > 4
        h = ''
        for it in items:
            ims = it.get('images', [])
            wide = len(ims) > 1 or (len(items) % 2 == 1 and it is items[0] and not dense)
            im_html = ''.join(ph(I, x, '(min-width:900px) 25vw, 50vw', lazy) for x in ims)
            txt = (f'<h4>{nl(it["title"])}</h4>' if it.get('title') else '') + (f'<p>{nl(it["text"])}</p>' if it.get('text') else '')
            if it.get('text') and not it.get('title'): txt = f'<h4>{nl(it["text"])}</h4>'
            h += f'<div class="it{" wide" if wide else ""}{" multi" if len(ims) > 1 else ""}"><div class="imgs">{im_html}</div>{txt}</div>'
        body = ''.join(f'<p>{nl(b)}</p>' for b in p.get('body', []))
        ncols = min(6, max(2, len(items) + sum(1 for it in items if len(it.get('images', [])) > 1)))
        return (f'<section class="pg material{" dense" if dense else ""}"{attrs} style="--cols:{ncols}"><div class="inner">{head_block(p, num)}'
                f'<div class="stext"><div class="items">{h}</div>{("<div class=body>" + body + "</div>") if body else ""}{pal_html(cols)}</div></div></section>')
    if t == 'studio':
        part = p.get('part')                      # 'studio' 工作室介绍 / 'designer' 设计师；不写 = 旧版单页
        ab = about_part(cfg, part)
        for k in ('title', 'title_en', 'body', 'items', 'name', 'role', 'tagline', 'heading', 'heading_en', 'items_label'):
            if p.get(k): ab[k] = p[k]
        if not imgs and ab.get('image'): imgs = [ab['image']]
        im = ph(I, imgs[0], '(min-width:900px) 40vw, 100vw', lazy, cls='ph stimg' + (' stp' if part == 'designer' else '')) if imgs else ''
        hon = ''.join(f'<li>{e(x)}</li>' for x in ab.get('items') or [])
        who = (f'<div class="who"><b>{e(ab["name"])}</b>{("<span>" + e(ab["role"]) + "</span>") if ab.get("role") else ""}</div>') if ab.get('name') and part != 'designer' else ''
        hp = dict(p, title=ab.get('title') or '关于我们', title_en=ab.get('title_en') or 'About Us')
        tag = f'<p class="tagl">{e(ab["tagline"])}</p>' if ab.get('tagline') else ''
        hd = (f'<div class="sth"><b>{e(ab["heading"])}</b>{("<i>" + e(ab["heading_en"]) + "</i>") if ab.get("heading_en") else ""}</div>') if ab.get('heading') else ''
        lab = f'<div class="honl">{e(ab["items_label"])}</div>' if ab.get('items_label') and hon else ''
        return (f'<section class="pg studio{(" " + part) if part else ""}"{attrs}>{im}<div class="inner">{head_block(hp, num)}{badge_html(p)}{who}{tag}{hd}'
                + ''.join(f'<p>{nl(b)}</p>' for b in ab.get('body') or [])
                + lab + (f'<ul class="hon">{hon}</ul>' if hon else '') + '</div></section>')
    if t == 'issues':
        CIRC = '①②③④⑤⑥⑦⑧⑨⑩'
        pl = ''
        if imgs:
            w0, h0 = imgs[0]['w'], imgs[0]['h']
            pl = ph(I, imgs[0], '(min-width:900px) 60vw, 100vw', lazy, cls='ph pframe', plan=True)
            pl = pl.replace('class="ph pframe zoom"', f'class="ph pframe zoom" style="aspect-ratio:{w0}/{h0}"', 1)
            dots = ''.join(f'<span class="rdot" data-n="{q["n"]}" style="left:calc(8px + (100% - 16px) * {q["x"]} / 100);top:calc(8px + (100% - 16px) * {q["y"]} / 100)">{q["n"]}</span>' for q in p.get('points') or [])
            pl = pl.replace('</figure>', dots + '</figure>')
        probs = ''.join(f'<li><i>{CIRC[k] if k < 10 else k + 1}</i><span>{e(x)}</span></li>' for k, x in enumerate(p.get('problems') or []))
        photos = p.get('photos') or []
        ph_html = ''.join(ph(I, x, '(min-width:900px) 15vw, 30vw', lazy) for x in photos[:3])
        return (f'<section class="pg issues"{attrs}><div class="inner">{head_block(p, num)}{badge_html(p)}{pl}'
                f'{("<ol class=probs>" + probs + "</ol>") if probs else ""}'
                f'{("<div class=photos>" + ph_html + "</div>") if ph_html else ""}</div></section>')
    if t == 'goals':
        im = ph(I, imgs[0], '(min-width:900px) 40vw, 100vw', lazy, cls='ph gimg') if imgs else ''
        rows = ''
        for g in p.get('goals') or []:
            fl = g.get('floor', ''); nm = g.get('floor_name') or floor_name(fl)
            rows += (f'<li><div class="fl"><b>{e(fl)}</b>{("<span>" + e(nm) + "</span>") if nm else ""}</div>'
                     f'<div class="gt">{("<h4>" + e(g["title"]) + "</h4>") if g.get("title") else ""}{("<p>" + nl(g["text"]) + "</p>") if g.get("text") else ""}</div></li>')
        return (f'<section class="pg goals"{attrs}><div class="inner">{head_block(p, num)}{badge_html(p)}{im}<ol class="glist">{rows}</ol></div></section>')
    if t == 'swipe':
        sl = p.get('slides') or []
        r = p.get('ratio') or (max((x['image']['h'] / max(1, x['image']['w']) for x in sl if x.get('image')), default=.75))
        tabs = ''.join(f'<button data-k="{k}"{" class=on" if k == 0 else ""}>{e(x.get("label") or str(k + 1))}</button>' for k, x in enumerate(sl))
        slides = ''
        for k, x in enumerate(sl):
            im = ph(I, x['image'], '(min-width:900px) 60vw, 100vw', lazy, cls='ph swf', plan=bool(p.get('plan', True))) if x.get('image') else ''
            notes = ''.join(f'<li><i>{q + 1}</i>{e(t_)}</li>' for q, t_ in enumerate(x.get('notes') or []))
            leg = ''.join(f'<span><i style="background:{e(c.get("color", "var(--accent)"))}"></i>{e(c.get("label", ""))}</span>' for c in x.get('legend') or [])
            slides += (f'<div class="sws" data-k="{k}">{im}<div class="swc">'
                       f'{("<div class=leg>" + leg + "</div>") if leg else ""}'
                       f'{("<p>" + nl(x["caption"]) + "</p>") if x.get("caption") else ""}'
                       f'{("<ol>" + notes + "</ol>") if notes else ""}</div></div>')
        dots = ''.join(f'<i{" class=on" if k == 0 else ""}></i>' for k in range(len(sl)))
        return (f'<section class="pg swipe"{attrs} style="--swr:{r:.4f}"><div class="inner">{head_block(p, num)}{badge_html(p)}'
                f'<div class="swtabs" role="tablist">{tabs}</div><div class="swtrack">{slides}</div>'
                f'<div class="swdots">{dots}</div></div></section>')
    if t == 'vertical':
        fls = p.get('floors') or [dict(id=f.get('id'), name=f.get('name', ''), level=f.get('level', '')) for f in reversed(FLOORS)]
        ids = [f['id'] for f in fls]
        nrow = len(fls)
        rows = ''.join(f'<div class="vr" style="grid-row:{k + 1}"><div class="vl"><b>{e(f["id"])}</b>'
                       f'{("<span>" + e(f.get("name", "")) + "</span>") if f.get("name") else ""}'
                       f'{("<em>" + e(f["level"]) + "</em>") if f.get("level") else ""}</div><div class="vs"></div></div>' for k, f in enumerate(fls))
        cores = ''
        for c in p.get('cores') or []:
            if c.get('draw') is False: continue  # 只列说明、不画（位置未知）
            a_ = ids.index(c.get('to', ids[0])) if c.get('to') in ids else 0
            b_ = ids.index(c.get('from', ids[-1])) if c.get('from') in ids else nrow - 1
            top, bot = min(a_, b_), max(a_, b_)
            cores += (f'<div class="vc {e(c.get("type", "stair"))}" style="left:{c.get("x", 30)}%;width:{c.get("w", 10)}%;'
                      f'top:calc(100% * {top} / {nrow});height:calc(100% * {bot - top + 1} / {nrow})"><i>{e(str(c.get("n", "")))}</i></div>')
        notes = ''.join(f'<li><i>{e(str(c.get("n", "")))}</i><div><b>{e(c.get("name", ""))}</b>{("<span>" + e(c["note"]) + "</span>") if c.get("note") else ""}</div></li>' for c in p.get('cores') or [])
        diag = f'<div class="vdiag" style="--rows:{nrow}">{rows}<div class="vcores">{cores}</div></div>' if p.get('cores') else ''
        sec = ph(I, imgs[0], '(min-width:900px) 50vw, 100vw', lazy, cls='ph vimg', plan=True) if imgs and not p.get('cores') else ''
        return (f'<section class="pg vertical"{attrs}><div class="inner">{head_block(p, num)}{badge_html(p)}{diag}{sec}'
                f'{("<ol class=vnotes>" + notes + "</ol>") if notes else ""}</div></section>')
    if t == 'contents':
        def chips(fls):
            if len(fls) < 2 and not (fls and p.get('show_single_floor')): return ''
            return '<div class="cfl">' + ''.join(f'<button data-go="{k}">{e(f)}</button>' for f, k in fls) + '</div>'
        lis = ''.join(f'<li><button data-go="{i}"><b>{e(nu)}</b><span>{e(zh)}</span><em>{e(en)}</em><i>{i + 1:02d}</i></button>{chips(fls)}</li>'
                      for i, nu, zh, en, fls in CHAPTERS)
        return (f'<section class="pg contents"{attrs}><div class="inner">{head_block(p)}<ol class="clist{" compact" if len(CHAPTERS) > 5 else ""}{" tight" if len(CHAPTERS) + sum(1 for c in CHAPTERS if len(c[4]) > 1) > 9 else ""}">{lis}</ol>'
                f'<div class="ctip">点击章节直接跳转</div></div></section>')
    if t == 'strategy':
        probs = ''.join(f'<li><i>{k + 1:02d}</i><span>{e(x)}</span></li>' for k, x in enumerate((p.get('problems') or [])[:3]))
        def step(d, dflt):
            if not d: return ''
            im = ph(I, d['image'], '(min-width:900px) 40vw, 92vw', lazy) if d.get('image') else ''
            return f'<div class="st">{im}<div class="lab">{e(d.get("label") or dflt)}{("<em>" + e(d["label_en"]) + "</em>") if d.get("label_en") else ""}</div></div>'
        kw = (f'<div class="kw"><b>{e(p.get("keyword", ""))}</b>{("<span>" + e(p["keyword_en"]) + "</span>") if p.get("keyword_en") else ""}</div>')
        return (f'<section class="pg strategy"{attrs}><div class="inner">{head_block(p, num)}{badge_html(p)}'
                f'{("<ol class=probs>" + probs + "</ol>") if probs else ""}'
                f'<div class="flow">{step(p.get("before"), "原方案")}<div class="arr"></div>{kw}<div class="arr"></div>{step(p.get("after"), "调整方案")}</div></div></section>')
    if t == 'persona':
        band = ph(I, imgs[0], '100vw', lazy, cls='ph band') if imgs else ''
        lis = ''.join(f'<li><i>{k + 1:02d}</i><div><q>{e(it.get("need", ""))}</q><div class="ans"><span></span>{e(it.get("response", ""))}</div></div></li>'
                      for k, it in enumerate((p.get('needs') or [])[:4]))
        return (f'<section class="pg persona"{" data-dark" if band else ""}{attrs}>{band}<div class="inner">{head_block(p, num)}{badge_html(p)}'
                f'<div class="plab"><span>您说的</span><span>我们这样做</span></div><ol class="needs">{lis}</ol></div></section>')
    if t == 'render':
        main = ph(I, imgs[0], '100vw', lazy, cls='ph rmain') if imgs else ''
        det = ph(I, imgs[1], '(min-width:900px) 20vw, 36vw', lazy, cls='ph rdet') if len(imgs) > 1 else ''
        return (f'<section class="pg render" data-dark{attrs}>{main}<div class="rcard"><div class="rtx">{badge_html(p)}'
                f'<div class="ren">{e((p.get("title_en") or "").upper())}</div><h2>{e(p.get("title", ""))}</h2><hr>'
                f'<p>{e(p.get("caption") or (p.get("body") or [""])[0])}</p></div>{det}</div></section>')
    if t == 'selection':
        cols = int(p.get('cols') or 2)
        h = ''
        for it in p.get('items', []):
            img = it.get('image')
            fig = ph(I, img, '(min-width:900px) 30vw, ' + ('92vw' if cols == 1 else '46vw'), lazy) if img else '<figure class="ph"></figure>'
            meta = [x for x in (it.get('brand'), it.get('kind'), it.get('size')) if x]
            pend = '<span class="pend"><i></i>待定</span>' if it.get('pending') else ''
            h += (f'<div class="si">{fig}<div class="sit"><h4>{e(it.get("name", ""))}{pend}</h4>'
                  f'{("<div class=sen>" + e(it["name_en"]) + "</div>") if it.get("name_en") else ""}<hr>'
                  f'<div class="meta">{"".join(f"<span>{e(m)}</span>" for m in meta)}</div>'
                  f'{("<p>" + nl(it["note"]) + "</p>") if it.get("note") else ""}</div></div>')
        return (f'<section class="pg selection c{cols}"{attrs}><div class="inner">{head_block(p, num)}{badge_html(p)}'
                f'<div class="sel">{h}</div></div></section>')
    if t == 'text':
        body = ''.join(f'<p>{nl(b)}</p>' for b in p.get('body', []))
        im = ''.join(ph(I, x, '(min-width:900px) 60vw, 100vw', lazy, style='margin-top:16px;aspect-ratio:%d/%d' % (x['w'], x['h'])) for x in imgs)
        return f'<section class="pg text"{attrs}><div class="inner">{head_block(p, num)}<div><div class="body">{body}</div>{im}</div></div></section>'
    if t == 'about':
        bg = ph(I, dict(src=p['bg']), '(min-width:900px) 55vw, 62vw', lazy, cls='ph aimg') if p.get('bg') else ''
        c = cfg.get('contact', {})
        dl = ''.join(f'<dt>{lab}</dt><dd>{e(c[k])}</dd>' for k, lab in (('phone', '电话 TEL'), ('wechat', '微信 WECHAT'), ('address', '地址 ADDRESS'), ('note', '')) if c.get(k))
        body = ''.join(f'<div class="slogan">{nl(b)}</div>' for b in p.get('body', []))
        title = nl(p.get('title_en') or 'Thank you.').replace(' ', '<br>', 1) if ' ' in (p.get('title_en') or '') else nl(p.get('title_en') or 'Thank you.')
        return (f'<section class="pg about"{attrs}>{bg}<div class="atext"><h2>{title}</h2>{("<div class=serif style=margin-top:8px;letter-spacing:.3em>" + e(p["title"]) + "</div>") if p.get("title") else ""}{body}'
                f'{("<dl>" + dl + "</dl>") if dl else ""}{qr_html(cfg)}<div class="studio">{e(cfg["studio"])}<small>{e(cfg["studio_en"]).upper()}</small></div>{("<div class=afoot>" + e(cfg["footer"]) + "</div>") if cfg.get("footer") else ""}'
                f'<button class="back" data-go="0">回到封面 ↑</button></div></section>')
    raise ValueError(f'未知版式 {t}（第 {p.get("slide")} 页）')


def font_source(spec):
    """字体来源：FONT_FILES 里的代号，或字体文件路径（.ttc 可写 路径#序号）。"""
    if spec in FONT_FILES: return FONT_FILES[spec]
    path, _, num = spec.partition('#')
    return path, (int(num) if num else (0 if path.lower().endswith('.ttc') else None))


def subset_fonts(texts, out, theme, override=None):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    os.makedirs(os.path.join(out, 'assets'), exist_ok=True)
    chars = set(''.join(texts))
    cjk = ''.join(sorted(c for c in chars if ord(c) > 0x2E80)) + '·—“”‘’…，。、：；！？（）《》'
    latin = ''.join(chr(c) for c in range(0x20, 0x7f)) + '·—“”‘’…éèàü'
    opts = subset.Options(); opts.flavor = 'woff2'; opts.layout_features = ['*']; opts.name_IDs = []; opts.notdef_outline = True
    css, preload = '', []
    override = override or {}
    for f in THEMES[theme]['fonts']:
        spec = override.get(f['family'] + ' Italic' if f.get('italic') else f['family'], '')
        path, num = font_source(spec or f['file'])
        fn = 'xf-' + re.sub(r'[^a-z0-9]+', '-', os.path.splitext(os.path.basename(spec))[0].lower()) + ('-i' if f.get('italic') else '') + '.woff2' if spec else f'xf-{f["file"]}.woff2'
        ft = TTFont(path, fontNumber=num) if num is not None else TTFont(path)
        sub = subset.Subsetter(opts); sub.populate(text=cjk if f.get('cjk') else latin); sub.subset(ft)
        ft.flavor = 'woff2'; ft.save(os.path.join(out, 'assets', fn))
        rng = 'U+2E80-FFFF,U+00B7,U+2014,U+201C-201D' if f.get('cjk') else 'U+0020-007E,U+00E0-00FC,U+2014'
        css += ('@font-face{font-family:"%s";src:url(%s) format("woff2");font-weight:300 700;font-style:%s;font-display:swap;unicode-range:%s}'
                % (f['family'], fn, 'italic' if f.get('italic') else 'normal', rng))
        if f.get('cjk'): preload.append('assets/' + fn)
    return css, preload


import numpy as np


def make_softlight(out, W=300, H=533, seed=7):
    path = os.path.join(out, 'assets', 'softlight.webp')
    from PIL import ImageDraw, ImageFilter
    """柔光层：斜投的窗格光（窗棂很模糊）× 叶隙斑驳，大半径模糊到认不出形状；白色 + 透明度，叠在暖灰底上。"""
    S = 3; w, h = W * S, H * S
    rs = np.random.default_rng(seed)
    win = Image.new('L', (w, h), 0); d = ImageDraw.Draw(win)
    # 斜投的窗光：一大块平行四边形，从右上方斜落
    d.polygon([(w * .42, h * .10), (w * 1.1, h * -.05), (w * 1.1, h * .62), (w * .30, h * .78)], fill=255)
    # 窗棂：两竖一横的暗条，穿过光块
    for t in (.58, .80):
        d.line([(w * t, h * .02), (w * (t - .17), h * .80)], fill=0, width=int(w * .035))
    d.line([(w * .3, h * .43), (w * 1.1, h * .30)], fill=0, width=int(w * .03))
    win = win.filter(ImageFilter.GaussianBlur(w * .035))
    # 叶隙：低频噪声阈值后模糊，调制光块（只在光里出现）
    n = Image.fromarray((rs.random((h // 40, w // 40)) * 255).astype('uint8')).resize((w, h), Image.BICUBIC)
    n2 = Image.fromarray((rs.random((h // 14, w // 14)) * 255).astype('uint8')).resize((w, h), Image.BICUBIC)
    leaf = (np.asarray(n, 'float32') * .6 + np.asarray(n2, 'float32') * .4) / 255
    leaf = np.clip((leaf - .35) * 2.2, 0, 1)
    a = np.asarray(win, 'float32') / 255 * (.45 + .55 * leaf)
    A = Image.fromarray((a * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(w * .03)).resize((W, H), Image.LANCZOS)
    a = np.asarray(A, 'float32') / 255; a = a / max(a.max(), 1e-3) * .66
    rgba = np.zeros((H, W, 4), 'uint8'); rgba[..., :3] = (252, 249, 243); rgba[..., 3] = (a * 255).astype('uint8')
    Image.fromarray(rgba, 'RGBA').save(path, 'WEBP', lossless=True, method=6)

def collect_texts(obj):
    if isinstance(obj, str): return [obj]
    if isinstance(obj, list): return [t for x in obj for t in collect_texts(x)]
    if isinstance(obj, dict): return [t for k, v in obj.items() if k not in ('src', 'bg', 'shape', 'template') for t in collect_texts(v)]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--out', help='输出目录，默认 out/<project>')
    ap.add_argument('--lite', action='store_true', help='轻量版：图片只出一个尺寸（约 10MB 以内），适合免费托管')
    ap.add_argument('--theme', choices=sorted(THEMES), help='风格：zen 新中式禅意 / wabi 侘寂木质 / mono 黑白极简 / french 法式杂志（默认读 config.json 的 style，没有则 wabi）')
    ap.add_argument('--brand', help='品牌目录名（brands/<名>）或路径；默认读 config.json 的 brand，再默认 default')
    ap.add_argument('--plan-mode', choices=['concept', 'render'], help='平面图模式：concept 概念提案（编号+列表，不跳转，默认）/ render 效果图汇报（点房间跳到该房间效果图页）')
    ap.add_argument('--accent', help='点缀色，例如 法式用 #26375f 藏青 或 #b88a8a 灰粉')
    ap.add_argument('--skip-preview-check', action='store_true', help='不提示缺少 pages_confirmed.json')
    a = ap.parse_args()
    work = os.path.join(ROOT, 'work', a.project)
    cfg = json.load(open(os.path.join(work, 'config.json'), encoding='utf-8'))
    # 套用 overrides.json（版式预览确认 / 手改）
    ovp = os.path.join(work, 'overrides.json')
    if os.path.exists(ovp):
        try:
            import sys as _sys
            _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from preview import apply_overrides_to_config
            from pathlib import Path as _P
            cfg = apply_overrides_to_config(cfg, _P(work))
            print('已套用 overrides.json')
        except Exception as _e:
            print('overrides 套用失败:', _e)
    conf_path = os.path.join(work, 'pages_confirmed.json')
    if not os.path.exists(conf_path) and not getattr(a, 'skip_preview_check', False):
        print('提示：还没有 pages_confirmed.json。正式交付前请先：python3 tools/preview.py --project', a.project)
    from brand import load_brand, merge
    cfg = merge(cfg, load_brand(a.brand or cfg.get('brand')))
    if a.plan_mode: cfg['plan_mode'] = a.plan_mode
    out = a.out or os.path.join(ROOT, 'out', a.project)
    os.makedirs(out, exist_ok=True)
    theme = a.theme or cfg.get('style') or 'wabi'
    TH.clear(); TH.update(THEMES[theme]); TH['id'] = theme
    shutil.rmtree(os.path.join(out, 'assets'), ignore_errors=True)
    I = Images(work, out, a.lite)
    pages = [p for p in cfg['pages'] if not p.get('hidden')]
    FLOORS.clear(); FLOORS.extend(cfg.get('floors') or [])
    brand_about = (cfg.get('_brand') or {}).get('about') or {}
    def has_content(p):
        t = p['template']
        if t == 'studio': return bool(p.get('body') or about_part(cfg, p.get('part')).get('body'))
        if t == 'issues': return bool(p.get('images') or p.get('problems'))
        if t == 'goals': return bool(p.get('goals'))
        if t == 'swipe': return bool(p.get('slides'))
        if t == 'vertical': return bool(p.get('cores') or p.get('images'))
        return True
    pages = [p for p in pages if has_content(p)]
    # 没有内容的章节（章节页后面直到下一个章节页都没有内容页）自动隐藏
    keep = []
    for k, p in enumerate(pages):
        if p['template'] == 'section':
            nxt = next((q for q in pages[k + 1:] if q['template'] in ('section', 'about')), None)
            body_pages = pages[k + 1:pages.index(nxt) if nxt else len(pages)]
            if not body_pages: continue
        keep.append(p)
    pages = keep
    # 内容页没写 chapter 的，继承前一个章节页的标题；楼层页自动加小标题（B1F · 花园层）
    cur = ''
    for p in pages:
        if p['template'] == 'section': cur = p.get('title') or ''
        elif p['template'] in ('cover', 'about'): cur = ''
        elif not p.get('chapter') and cur: p['chapter'] = cur
        if p.get('floor') and not p.get('eyebrow') and p['template'] not in ('section', 'cover'):
            nm = floor_name(p['floor']); p['eyebrow'] = p['floor'] + (' · ' + nm if nm else '')
    # 目录页（第 2 页）：章节 ≥2 时自动插入，config 里 "contents": false 可关闭
    secs_ = [p for p in pages if p['template'] == 'section']
    if cfg.get('contents', True) and len(secs_) >= 2 and not any(p['template'] == 'contents' for p in pages):
        pos = 1 if pages and pages[0]['template'] == 'cover' else 0
        pages.insert(pos, dict(slide=None, template='contents', title='目录', title_en='Contents', chapter='目录', images=[]))
    n = len(pages)
    # 楼层切换按钮：同一章节里的平面图页（写了 floor 的按楼层顺序；没写的沿用「连续平面图页」规则）
    groups, ch = {}, 0
    for k, p in enumerate(pages):
        if p['template'] in ('section', 'cover', 'about'): ch += 1
        if p['template'] == 'plan': groups.setdefault(ch, []).append(k)
    for grp in groups.values():
        if all(pages[x].get('floor') for x in grp):
            grp = sorted(grp, key=lambda x: floor_order(pages[x]['floor']))
            labels = [pages[x]['floor'] for x in grp]
            for x in grp: pages[x]['_floors'] = list(zip(grp, labels))
            continue
        runs, run = [], [grp[0]]
        for x in grp[1:]:
            if x == run[-1] + 1: run.append(x)
            else: runs.append(run); run = [x]
        runs.append(run)
        for run in runs:
            titles = [pages[x].get('title') or str(x + 1) for x in run]
            pre = os.path.commonprefix(titles)
            labels = [(t[len(pre):].strip() or t) if len(run) > 1 else t for t in titles]
            for x in run: pages[x]['_floors'] = list(zip(run, labels))
    SLIDE_IDX.clear(); SLIDE_IDX.update({p['slide']: i for i, p in enumerate(pages) if p.get('slide') is not None})
    resolve_locators(pages, work)
    ROOM_PAGE.clear()
    for pri in (('render',), ('selection',), None):      # 优先效果图页，其次选品页，再其次任何填了 room 的页
        for i, p in enumerate(pages):
            rm = p.get('room') or (p.get('_loc') or {}).get('rooms') or (p.get('_loc') or {}).get('room')
            for nm in (rm if isinstance(rm, list) else [rm]):
                if not nm: continue
                fl, nm2 = split_room(nm, p.get('floor'))
                for key in ((fl, nm2), nm2):
                    if key not in ROOM_PAGE and (pri is None or p['template'] in pri): ROOM_PAGE[key] = i
    # 章节（给小圆点导航用）
    chapters, ci = [], -1
    for i, p in enumerate(pages):
        if p['template'] in ('cover', 'section', 'about'):
            ci += 1; chapters.append((i, p.get('title') or p.get('title_en') or ''))
        p['_ci'] = max(ci, 0)
    # 章节编号：壹贰叁肆（目录页、章节页、底部细条共用）
    CHAPTERS.clear(); k = 0; curnum = ''
    for i, p in enumerate(pages):
        if p['template'] == 'section':
            curnum = CN_NUM[k] if k < len(CN_NUM) else str(k + 1); k += 1
            p['_num'] = curnum
            CHAPTERS.append([i, curnum, p.get('title') or '', p.get('title_en') or '', []])
        elif p['template'] in ('cover', 'contents', 'about'):
            curnum = ''
        p['_chnum'] = curnum
        if curnum and p.get('floor') and CHAPTERS:
            fls = CHAPTERS[-1][4]
            if p['floor'] not in [f for f, _ in fls]: fls.append((p['floor'], i))
    for c in CHAPTERS: c[4].sort(key=lambda x: floor_order(x[0]))
    make_qr(cfg, work, out); copy_brand_assets(cfg, out)
    # 底部细条左侧的小字：房间名优先，否则章节名；附英文大写
    chap_en = {}
    for p in pages:
        if p['template'] == 'section': chap_en[p.get('title') or p.get('title_en')] = p.get('title_en', '')
    for p in pages:
        if p['template'] == 'cover': p['_flabel'] = cfg.get('footer') or ''; continue
        rl = [split_room(x)[1] for x in ((p.get('_loc') or {}).get('rooms') or [])] or ([p['room']] if isinstance(p.get('room'), str) and p['room'] else p.get('room') or [])
        zh = '·'.join(rl) if rl else (p.get('chapter') or p.get('title') or '')
        en = ' / '.join(x for x in (translate(n, GLOSS) for n in rl) if x) if rl else chap_en.get(zh, '') or translate(zh, GLOSS)
        if p['template'] == 'about': zh, en = cfg['studio'], cfg['studio_en']
        p['_flabel'] = (p['_chnum'] + ' · ' if p.get('_chnum') else '') + zh + (' · ' + en.upper() if en else '') + (' · ' + p['floor'] if p.get('floor') and not rl else '')
    print(f'构建 {n} 页 · 风格 {theme}（{TH["name"]}）…')
    secs = [render_page(p, i, n, I, cfg, i == 0) for i, p in enumerate(pages)]
    # 目录
    toc = ''
    for i, p in enumerate(pages):
        label = p.get('title') or p.get('title_en') or p['template']
        if p['template'] == 'cover': label = (p.get('title') or cfg['title']) + ' · 封面'
        cls = ' class="chap"' if p['template'] in ('section', 'cover', 'about') else ''
        toc += f'<li data-i="{i}"{cls}><i>{i + 1:02d}</i><span>{e(label)}</span><em>{e(p.get("title_en", "") if cls else "")}</em></li>'
    th = dict(cfg.get('theme_vars', {}).get(theme, {}))   # 每套风格可在 config.json 的 theme_vars.<风格> 里覆盖颜色
    acc = a.accent or cfg.get('theme_accent') or TH.get('accent')
    if acc: th['accent'] = acc
    css_vars = (':root{' + ''.join(f'--{k}:{v};' for k, v in th.items()) + '}') if th else ''
    fonts, preload = subset_fonts(collect_texts(cfg) + [p.get('_flabel') or '' for p in pages] + ['壹贰叁肆伍陆柒捌玖拾点击章节直接跳转您说的我们这样做原方案调整方案微信二维码占位待替换长按识别添加待定示例数据目录上滑浏览回到封面点击放大左右滑动看大图双指拖动查看细节切换双击电话微信地址图纸可缩放一张设计方案汇报'], out, theme, cfg.get('_fonts'))
    if TH.get('softlight'): make_softlight(out)
    css = open(os.path.join(TPL, 'theme.css'), encoding='utf-8').read() + open(os.path.join(TPL, 'themes', theme + '.css'), encoding='utf-8').read()
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S); css = re.sub(r'\s*\n\s*', '', css)
    js = open(os.path.join(TPL, 'app.js'), encoding='utf-8').read()
    with open(os.path.join(out, 'assets', 'app.js'), 'w', encoding='utf-8') as f: f.write(js)
    with open(os.path.join(out, 'assets', 'style.css'), 'w', encoding='utf-8') as f: f.write(fonts + css + css_vars)
    VER = hashlib.md5((fonts + css + css_vars + js).encode()).hexdigest()[:8]   # 防缓存：样式/脚本一变，网址就变（微信内置浏览器缓存很顽固）
    title = f'{cfg["title"]} · {cfg.get("report_name", "设计方案汇报")} | {cfg["studio"]}'
    first_img = re.search(r'<img src="([^"]+)"', secs[0])
    doc = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
{'<meta name="robots" content="noindex,nofollow,noarchive,nosnippet,noimageindex">' if cfg.get('noindex', True) else ''}
<meta name="referrer" content="same-origin"><meta name="format-detection" content="telephone=no">
<link rel="icon" href="data:,"><meta name="theme-color" content="{th.get('bg', '#f4f1ec')}">
<title>{e(title)}</title>
<meta name="description" content="{e(cfg['studio'])} · {e(cfg['title'])} {e(cfg.get('report_name', ''))}">
{''.join(f'<link rel="preload" href="{x}" as="font" type="font/woff2" crossorigin>' for x in preload)}
<link rel="stylesheet" href="assets/style.css?v={VER}">
</head><body class="t-{theme}{' protect' if cfg.get('protect', True) else ''}{' link-wipe' if cfg.get('link_wipe', True) else ''} on-cover">
{('<img src="' + first_img.group(1) + '" alt="" style="position:absolute;width:1px;height:1px;opacity:0">') if first_img else ''}
{('<div class="urlwipe" aria-hidden="true"></div>') if cfg.get('link_wipe', True) else ''}
<header class="bar top"><div class="brand">{(f'<img class="logo" src="{cfg["_logo_src"]}" alt="{e(cfg["studio"])}">') if cfg.get('_logo_src') else (e(cfg['studio']) + '<b>' + e(cfg['studio_en']).upper() + '</b>')}</div><button class="tocbtn" id="tocbtn" aria-label="目录">目录 <i>☰</i></button></header>
<main>
{chr(10).join(secs)}
</main>
<div class="prog"><i id="prog"></i></div>
<footer class="bar bot"><div class="chap" id="chap"></div><div class="num" id="num"></div></footer>
<nav class="dots" id="dots">{''.join(f'<button data-go="{i}" data-ci="{k}" aria-label="{e(lab)}"><span>{e(lab)}</span></button>' for k, (i, lab) in enumerate(chapters))}</nav>
<div class="nav"><button id="up" aria-label="上一页">︿</button><button id="down" aria-label="下一页">﹀</button></div>
<aside class="toc" id="toc"><button class="x" aria-label="关闭">×</button><div class="cap">CONTENTS</div><h3>目录</h3><ol>{toc}</ol></aside>
<div class="lb" id="lb"><div class="stage"><img alt=""></div><div class="lbtop"><span class="lbcount"></span><button class="close" aria-label="关闭">×</button></div>
<button class="arr prev" aria-label="上一张">‹</button><button class="arr next" aria-label="下一张">›</button><div class="lbtip"></div><div class="lbcap"></div></div>
<script src="assets/app.js?v={VER}" defer></script>
</body></html>'''
    with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as f: f.write(doc)
    with open(os.path.join(out, 'robots.txt'), 'w') as f: f.write('User-agent: *\nDisallow: /\n')
    # 清理不再使用的旧图片
    for fn in os.listdir(I.dir):
        if fn not in I.used: os.remove(os.path.join(I.dir, fn))
    total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(out) for f in fs)
    print(f'完成 → {out}  （{len(I.used)} 张图，共 {total / 1e6:.1f} MB）')
    for m in LOC_LOG: print('  [角标平面图] ' + m)
    for m in SUGGEST: print('  [待填 room] ' + m)


if __name__ == '__main__':
    main()
