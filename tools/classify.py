#!/usr/bin/env python3
"""汇报网页生成器 · 第 2 步：把 raw.json 自动匹配到版式模板，生成可手改的 config.json。

用法:
  python3 tools/classify.py --project my-project [--force]

已有 config.json 时默认不覆盖（防止冲掉你的手改），加 --force 才重新生成。
版式（template）一览：cover 封面 / section 章节页 / concept 理念关键词 / text 文字页 /
split 图文分栏 / full 满版大图 / grid 不对称图组 / plan 平面图（可缩放）/
material 材料·专项（图+说明+取色）/ about 结尾·联系方式
"""
import argparse, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BRAND = {}
BRAND_RE = re.compile(r'^$')   # 由品牌配置 aliases 生成，见 main()
CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def cn2int(s):
    if s.isdigit(): return int(s)
    if s == '十': return 10
    if s.startswith('十'): return 10 + CN_NUM.get(s[1:], 0)
    if s.endswith('十'): return CN_NUM.get(s[0], 0) * 10
    if '十' in s: a, b = s.split('十'); return CN_NUM[a] * 10 + CN_NUM[b]
    return CN_NUM.get(s, 0)


def load_glossary():
    g = json.load(open(os.path.join(ROOT, 'templates', 'glossary.json'), encoding='utf-8'))
    g.pop('_说明', None)
    return g


def translate(zh, G):
    zh = (zh or '').strip()
    if not zh: return ''
    if zh in G: return G[zh]
    for k, v in G.items():
        if not k.startswith('^'): continue
        m = re.match(k, zh)
        if m:
            out = v
            for i, grp in enumerate(m.groups(), 1):
                out = out.replace('{n%d}' % i, '%02d' % cn2int(grp)).replace('{%d}' % i, G.get(grp, grp))
            if re.search(r'[\u4e00-\u9fff]', out):  # 还有没翻译的中文，留空让人工补
                return ''
            return out
    return ''


def is_cjk(s): return bool(re.search(r'[\u4e00-\u9fff]', s))
def area(b): return max(0, b[2]) * max(0, b[3])


def overlap(a, b):
    x = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    y = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return x * y


MEDIA_DIR = None


def mostly_transparent(e):
    if not e.get('transparent') or not MEDIA_DIR: return False
    try:
        from PIL import Image
        a = Image.open(os.path.join(MEDIA_DIR, e['file'])).getchannel('A')
        h = a.histogram(); return sum(h[:20]) / max(1, sum(h)) > 0.8
    except Exception:
        return False


def visible_images(els):
    """去掉被上层图片几乎完全挡住的图、极小的装饰图标、几乎全透明的装饰图（水印/logo 叠层）。"""
    imgs = [e for e in els if e['type'] == 'image' and not mostly_transparent(e)]
    keep = []
    for i, im in enumerate(imgs):
        a = area(im['box'])
        if a < 0.004: continue
        covered = sum(overlap(im['box'], o['box']) for o in imgs[i + 1:])
        if covered / max(a, 1e-6) > 0.7: continue
        keep.append(im)
    return keep


def img_entry(e, caption=''):
    return dict(src='media/' + e['file'], w=e['px'][0], h=e['px'][1], caption=caption,
                shape=e.get('shape', 'rect'), box=[round(v, 3) for v in e['box']])


def classify_slide(s, n_total, G):
    els = s['elements']
    texts = [e for e in els if e['type'] == 'text' and e['text'] and not BRAND_RE.match(e['text'].strip())
             and e['text'].strip() not in ('“', '”', '"', '[图片]')]
    imgs = visible_images(els)
    imgs_sorted = sorted(imgs, key=lambda e: (round(e['box'][1] * 4), e['box'][0]))
    img_area = sum(area(e['box']) for e in imgs)
    big = max(imgs, key=lambda e: area(e['box'])) if imgs else None

    # 标题：靠上的短文本，或「——X——」形式
    title, title_en, eyebrow, used = '', '', '', set()
    for t in sorted(texts, key=lambda e: e['box'][1]):
        txt = t['text']
        m = re.fullmatch(r'[—\-–]{1,}\s*(.+?)\s*[—\-–]*', txt.strip())
        if m and '\n' not in txt:
            title = m.group(1); used.add(id(t)); break
        if t['box'][1] < 0.15 and len(txt) <= 40:
            lines = [l for l in txt.split('\n') if l.strip()]
            zh = [l for l in lines if is_cjk(l)]
            en = [l for l in lines if not is_cjk(l)]
            title = zh[0] if zh else ''
            title_en = ' '.join(en)
            used.add(id(t)); break
    rest = [t for t in texts if id(t) not in used]
    body_texts = sorted(rest, key=lambda e: (e['box'][1], e['box'][0]))
    full_text = '\n'.join(t['text'] for t in texts)

    page = dict(slide=s['index'], template='', chapter='', eyebrow=eyebrow, title=title, title_en=title_en,
                subtitle='', body=[], quote='', items=[], images=[], bg='', palette=False, hidden=False, note='')

    def captions_to_images():
        """把图片下方的短文字配给最近的图片，作为图注。"""
        caps = {}
        leftovers = []
        for t in body_texts:
            if len(t['text']) > 60 or not imgs:
                leftovers.append(t); continue
            cx = t['box'][0] + t['box'][2] / 2
            below = [im for im in imgs if t['box'][1] >= im['box'][1] + im['box'][3] * 0.8]
            if not below:
                leftovers.append(t); continue
            best = min(below, key=lambda im: abs(im['box'][0] + im['box'][2] / 2 - cx))
            caps.setdefault(id(best), []).append(t['text'])
        return caps, leftovers

    # --- 规则匹配 ---
    if s['index'] == 1:
        page['template'] = 'cover'
        big_t = max(texts, key=lambda e: (e['size'] or 0)) if texts else None
        page['title'] = big_t['text'].replace('\n', '') if big_t else ''
        others = [t['text'] for t in texts if t is not big_t]
        page['subtitle'] = ' '.join(o for o in others if len(o) > 6)
        page['title_en'] = ' '.join(o for o in others if len(o) <= 6 and not is_cjk(o))
        if big: page['bg'] = 'media/' + big['file']
        return page
    if s['index'] == n_total or re.search(r'THANK\s*YOU', full_text.replace('\n', ' '), re.I):
        page['template'] = 'about'
        page['title_en'] = re.sub(r'\s+', ' ', next((t['text'] for t in texts if re.search('THANK', t['text'], re.I)), 'Thank you'))
        page['body'] = [t['text'] for t in texts if not re.search('THANK', t['text'], re.I)]
        if big: page['bg'] = 'media/' + big['file']
        return page
    circles = [e for e in imgs if e.get('shape') in ('ellipse', 'roundRect') and abs(e['px'][0] - e['px'][1]) < 30]
    if len(circles) >= 2:
        page['template'] = 'concept'
        words = [t for t in body_texts if len(t['text']) <= 8]
        center = None
        circles.sort(key=lambda c: (round(c['box'][1] + c['box'][3] / 2, 1), c['box'][0]))  # 上 → 左下 → 右下
        for c in circles:
            cx, cy = c['box'][0] + c['box'][2] / 2, c['box'][1] + c['box'][3] / 2
            w = min(words, key=lambda t: (t['box'][0] + t['box'][2] / 2 - cx) ** 2 + (t['box'][1] + t['box'][3] / 2 - cy) ** 2) if words else None
            page['items'].append(dict(title=w['text'] if w else '', title_en=translate(w['text'], G) if w else '',
                                      text='', image=img_entry(c)))
        named = {i['title'] for i in page['items']}
        center = [t['text'] for t in words if t['text'] not in named]
        if center:
            page['eyebrow'], page['eyebrow_en'] = page['title'], (page['title_en'].title() if page['title_en'].isupper() else page['title_en'])
            page['title'] = center[0]; page['title_en'] = translate(center[0], G)
        return page
    has_quote_mark = any(e['type'] == 'text' and e['text'].strip() in ('“', '”') for e in els)
    big_en = [t for t in texts if not is_cjk(t['text']) and (t['size'] or 0) >= 26]
    if (has_quote_mark or big_en) and len(imgs) <= 2 and not re.search(r'\d+F', full_text):
        long_en = [t for t in texts if not is_cjk(t['text']) and len(t['text']) > 30]
        if has_quote_mark or (long_en and len(full_text) < 300 and not any(is_cjk(t['text']) and len(t['text']) > 12 for t in texts)):
            page['template'] = 'section'
            zh = [t['text'] for t in texts if is_cjk(t['text']) and len(t['text']) <= 10]
            en_title = [t['text'] for t in big_en if len(t['text']) <= 40]
            page['title_en'] = re.sub(r'\s+', ' ', en_title[0]) if en_title else page['title_en']
            page['title'] = zh[0] if zh else ''
            if not page['title']:
                inv = {v.lower(): k for k, v in G.items() if not k.startswith('^')}
                page['title'] = inv.get(page['title_en'].lower(), '')
            page['quote'] = next((re.sub(r'\s+', ' ', t['text']) for t in long_en), '')
            page['subtitle'] = next((t['text'] for t in texts if re.search(r'time|日期|时间', t['text'], re.I)), '')
            if big: page['images'] = [img_entry(big)]
            return page
    plan_title = re.search(r'(平面|布置|方案.*\d*F|^\s*B?\d+F|天花|立面|结构)', title + ' ' + full_text)
    if len(imgs) == 1 and big and area(big['box']) > 0.5 and (max(big['px']) >= 2500 or plan_title):
        page['template'] = 'plan' if plan_title else 'full'
        page['images'] = [img_entry(big)]
        page['title_en'] = page['title_en'] or translate(title, G)
        page['body'] = [t['text'] for t in body_texts]
        return page
    if re.search(r'专项|材料|材质|工艺|系统', title):
        # 每段说明文字 + 它正上方的图片 = 一个条目；过宽的文字作为整页说明
        page['template'] = 'material'
        left, used_imgs = [], set()
        for t in body_texts:
            tb = t['box']
            if tb[2] > 0.5 or len(t['text']) > 80:
                left.append(t); continue
            above = [im for im in imgs if tb[1] >= im['box'][1] + im['box'][3] * 0.8 and id(im) not in used_imgs
                     and overlap([tb[0], 0, tb[2], 1], [im['box'][0], 0, im['box'][2], 1]) > 0.25 * min(tb[2], im['box'][2])]
            if not above:
                cx = tb[0] + tb[2] / 2
                cand = [im for im in imgs if id(im) not in used_imgs]
                above = [min(cand, key=lambda im: abs(im['box'][0] + im['box'][2] / 2 - cx))] if cand else []
            lines = t['text'].split('\n')
            for im in above: used_imgs.add(id(im))
            page['items'].append(dict(title=lines[0] if len(lines) > 1 else '', text='\n'.join(lines[1:]) if len(lines) > 1 else lines[0],
                                      images=[img_entry(im) for im in sorted(above, key=lambda e: e['box'][0])],
                                      x=min([im['box'][0] for im in above] or [tb[0]])))
        for im in imgs:
            if id(im) not in used_imgs:
                page['items'].append(dict(title='', text='', images=[img_entry(im)], x=im['box'][0]))
        page['items'].sort(key=lambda i: i['x'])
        for i in page['items']: i.pop('x')
        page['body'] = [t['text'] for t in left]
        page['title_en'] = page['title_en'] or translate(title, G)
        page['palette'] = True
        return page
    long_body = sum(len(t['text']) for t in body_texts)
    if len(imgs) == 1 and long_body > 30:
        page['template'] = 'split'
        lines = []
        for t in body_texts:
            lines += [l for l in t['text'].split('\n') if l.strip()]
        if lines and len(lines[0]) <= 12 and is_cjk(lines[0]) and not page['title']:
            page['title'] = lines.pop(0)
        if not is_cjk(page['title']) and page['title']:
            page['title_en'], page['title'] = page['title'], ''
        if not page['title'] and lines and len(lines[0]) <= 12:
            page['title'] = lines.pop(0)
        page['body'] = lines
        page['images'] = [img_entry(big)]
        return page
    if not imgs:
        page['template'] = 'text'
        page['body'] = [t['text'] for t in body_texts]
        if s.get('render'): page['images'] = [dict(src='render/' + s['render'], w=1800, h=1013, caption='', shape='rect', box=[0, 0, 1, 1])]
        return page
    if len(imgs) == 1:
        page['template'] = 'full'
        page['images'] = [img_entry(big)]
        page['body'] = [t['text'] for t in body_texts]
        page['title_en'] = page['title_en'] or translate(title, G)
        return page
    page['template'] = 'grid'
    caps, left = captions_to_images()
    page['images'] = [img_entry(e, '\n'.join(caps.get(id(e), []))) for e in imgs_sorted]
    short_caps = [c for v in caps.values() for c in v]
    if len(short_caps) == 1 and len(short_caps[0]) <= 12:   # 只有一条短图注 → 当作副标题
        page['subtitle'] = short_caps[0]; caps = {}
    else:
        page['subtitle'] = '\n'.join(t['text'] for t in left if len(t['text']) <= 12)
    page['body'] = [t['text'] for t in left if len(t['text']) > 12]
    page['title_en'] = page['title_en'] or translate(title, G)
    page['palette'] = True
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--brand', help='品牌目录名（brands/<名>），用于识别并去掉页面上的工作室署名')
    a = ap.parse_args()
    global BRAND, BRAND_RE
    from brand import load_brand
    BRAND = load_brand(a.brand)
    al = [x for x in [BRAND.get('studio'), BRAND.get('studio_en')] + list(BRAND.get('aliases') or []) if x]
    BRAND_RE = re.compile('^(' + '|'.join(r'\s*'.join(re.escape(w) for w in x.split()) for x in al) + ')$', re.I) if al else re.compile(r'(?!)')
    work = os.path.join(ROOT, 'work', a.project)
    cfg_path = os.path.join(work, 'config.json')
    if os.path.exists(cfg_path) and not a.force:
        print('config.json 已存在（可能有手改），未覆盖。要重新生成请加 --force'); return
    raw = json.load(open(os.path.join(work, 'raw.json'), encoding='utf-8'))
    global MEDIA_DIR
    MEDIA_DIR = os.path.join(work, 'media')
    G = load_glossary()
    pages = [classify_slide(s, len(raw['slides']), G) for s in raw['slides']]
    # 章节：从章节页开始，后面的页面继承章节名
    chap, chap_en, n = '', '', 0
    for p in pages:
        if p['template'] in ('section',):
            n += 1; chap, chap_en = p['title'] or p['title_en'], p['title_en']
            p['eyebrow'] = p['eyebrow'] or 'PART %02d' % n
        elif p['template'] in ('grid', 'material', 'plan') and p['title'] and not chap:
            chap = p['title']
        p['chapter'] = chap if p['template'] not in ('cover',) else ''
        if not p['title_en'] and p['title']: p['title_en'] = translate(p['title'], G)
        if p['title_en'] and p['title_en'].isupper() and len(p['title_en']) > 4:
            p['title_en'] = p['title_en'].title()
        if p['title_en'] and p['title_en'][:1].isalpha() and p['title_en'].islower() is False and ' ' in p['title_en']:
            p['title_en'] = ' '.join(w if w.lower() in ('of', 'and', 'the') else w[:1].upper() + w[1:] for w in p['title_en'].split(' '))
    cover = pages[0]
    cfg = dict(
        project=a.project, title=cover['title'], title_en=cover.get('title_en', ''),
        report_name=BRAND['report_name'], report_name_en=BRAND['report_name_en'],
        brand=BRAND['_id'], designer='', date='',   # 工作室名称/联系方式/二维码等在 brands/<品牌>/brand.json
        theme=dict(bg='#f4f1ec', panel='#e8e2d9', ink='#3a342e', muted='#8b8075', line='#d8d0c4', accent='#8a7a6a'),
        protect=True, noindex=True, pages=pages)
    # overrides.json：把手改项单独记下来，重新 --force 生成时自动套用，不会丢
    ov_path = os.path.join(work, 'overrides.json')
    if os.path.exists(ov_path):
        ov = json.load(open(ov_path, encoding='utf-8'))
        for k, v in ov.get('global', {}).items(): cfg[k] = v
        bys = {p['slide']: p for p in pages}
        for sl, patch in ov.get('pages', {}).items():
            if int(sl) in bys: bys[int(sl)].update(patch)
        print('已套用 overrides.json')
    json.dump(cfg, open(cfg_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    from collections import Counter
    print('config.json 已生成：', dict(Counter(p['template'] for p in pages)))
    for p in pages:
        print(f"  {p['slide']:>2} {p['template']:<9} {p['title']} | {p['title_en']} | imgs={len(p['images'])} items={len(p['items'])}")


if __name__ == '__main__':
    main()
