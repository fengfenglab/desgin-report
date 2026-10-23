#!/usr/bin/env python3
"""生成「正式汇报模板」示例项目 work/formal-template：4 层别墅，全部是程序画的示例平面/示意图/插画，标注「示例数据」。
用法：python3 tools/make_sample.py  然后  python3 tools/build.py --project formal-template --lite"""
import json, math, os, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work', 'formal-template'); M = os.path.join(W, 'media'); os.makedirs(M, exist_ok=True)
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def font(sz): return ImageFont.truetype(FONT, sz, index=2)
PW, PH = 1600, 1024
INK, WALL, FILL = (70, 64, 58), (58, 54, 50), (247, 245, 241)

# ---------------- 示例别墅：每层房间矩形（像素坐标，1600×1024 画布） ----------------
CORE = dict(stair=(700, 560, 820, 900), lift=(820, 640, 900, 780))
FLOORS = {
 'B1F': dict(garden=('下花园', (40, 160, 330, 900)), rooms=[
   ('客厅', (360, 160, 780, 560)), ('茶室', (780, 160, 1100, 400)), ('餐厅', (1100, 160, 1500, 560)),
   ('西厨', (780, 400, 1100, 560)), ('影音室', (360, 560, 700, 900)), ('中厨', (900, 560, 1200, 900)), ('设备间', (1200, 560, 1500, 900))]),
 '1F': dict(garden=('上花园', (40, 160, 330, 900)), rooms=[
   ('家庭厅', (360, 160, 860, 560)), ('老人房', (860, 160, 1200, 560)), ('阳台', (1200, 160, 1500, 400)),
   ('次卫', (1200, 400, 1500, 560)), ('亲子区', (360, 560, 700, 900)), ('门厅', (900, 560, 1200, 900)), ('衣帽间', (1200, 560, 1500, 900))]),
 '2F': dict(garden=None, rooms=[
   ('儿子房', (360, 160, 800, 560)), ('学习区', (800, 160, 1100, 560)), ('次卧', (1100, 160, 1500, 560)),
   ('次卫', (360, 560, 700, 900)), ('衣帽间', (900, 560, 1200, 900)), ('家政间', (1200, 560, 1500, 900))]),
 '3F': dict(garden=None, rooms=[
   ('主卧', (360, 160, 900, 560)), ('起居室', (900, 160, 1500, 560)), ('书房', (360, 560, 700, 900)),
   ('主卫', (900, 560, 1200, 900)), ('衣帽间', (1200, 560, 1500, 900))]),
}
GROUP = {'客厅': 0, '茶室': 0, '餐厅': 0, '西厨': 2, '影音室': 0, '中厨': 2, '设备间': 2, '家庭厅': 0, '老人房': 1, '阳台': 0, '次卫': 2,
         '亲子区': 0, '门厅': 3, '衣帽间': 1, '儿子房': 1, '学习区': 1, '次卧': 1, '家政间': 2, '主卧': 1, '起居室': 1, '书房': 1, '主卫': 2}
GCOL = [((214, 196, 160), '公共区'), ((176, 190, 206), '私密区'), ((206, 178, 168), '服务区'), ((196, 206, 180), '交通 / 门厅')]
def pct(box): return round((box[0] + box[2]) / 2 / PW * 100, 1), round((box[1] + box[3]) / 2 / PH * 100, 1)

def base_plan(fl, labels=True, furniture=True, fills=True, raw=False, scheme=0):
    im = Image.new('RGB', (PW, PH), 'white'); d = ImageDraw.Draw(im, 'RGBA')
    g = FLOORS[fl]['garden']
    if g:
        x0, y0, x1, y1 = g[1]; d.rectangle(g[1], fill=(214, 224, 204))
        rnd = random.Random(fl)
        for _ in range(9):
            cx, cy, r = rnd.uniform(x0 + 40, x1 - 40), rnd.uniform(y0 + 40, y1 - 40), rnd.uniform(26, 48)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(150, 168, 140), width=3, fill=(196, 210, 186))
        if labels: d.text(((x0 + x1) / 2, y0 + 40), g[0], font=font(30), fill=(90, 110, 84), anchor='mm')
    else:
        d.rectangle((40, 160, 330, 900), outline=(205, 200, 192), width=2)
        for k in range(0, 900, 28): d.line([(40 + k, 160), (40 + k - 290, 450)], fill=(225, 221, 214), width=1) if 40 + k - 290 < 330 else None
        if labels: d.text((185, 200), '露台' if fl == '2F' else '屋面', font=font(24), fill=(150, 144, 136), anchor='mm')
    rooms = FLOORS[fl]['rooms']
    if scheme:      # 方案二 / 三：内部隔墙位置不同（示意）
        rooms = [(n, (b[0] + (scheme * 40 if b[0] > 400 and b[0] < 1400 else 0), b[1], b[2], b[3])) for n, b in rooms]
    for n, b in rooms:
        if fills and not raw: d.rectangle(b, fill=FILL)
        d.rectangle(b, outline=WALL, width=5)
        if furniture and not raw:
            rnd = random.Random(n + fl + str(scheme)); x0, y0, x1, y1 = b
            fw, fh = (x1 - x0) * rnd.uniform(.3, .5), (y1 - y0) * rnd.uniform(.2, .35)
            fx, fy = x0 + (x1 - x0 - fw) / 2, y0 + (y1 - y0) * .55
            d.rounded_rectangle([fx, fy, fx + fw, fy + fh], radius=10, outline=(170, 162, 152), width=2, fill=(236, 232, 226))
        if labels:
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            d.text((cx, cy - 26), n, font=font(26), fill=INK, anchor='mm')
            if not raw: d.text((cx, cy + 4), f'约 {abs(b[2] - b[0]) * abs(b[3] - b[1]) // 4000} ㎡', font=font(17), fill=(140, 132, 124), anchor='mm')
    s = CORE['stair']; d.rectangle(s, fill='white', outline=WALL, width=5)
    for y in range(s[1] + 20, s[3], 26): d.line([(s[0], y), (s[2], y)], fill=(150, 144, 136), width=2)
    d.line([(s[0] + 60, s[3] - 10), (s[0] + 60, s[1] + 20)], fill=(150, 144, 136), width=2)
    l = CORE['lift']; d.rectangle(l, fill=(236, 233, 228), outline=WALL, width=5); d.line([l[:2], l[2:]], fill=(150, 144, 136), width=2); d.line([(l[0], l[3]), (l[2], l[1])], fill=(150, 144, 136), width=2)
    if labels: d.text(((s[0] + s[2]) / 2, s[1] - 18), '楼梯', font=font(18), fill=INK, anchor='mm'); d.text(((l[0] + l[2]) / 2, l[3] + 20), '电梯', font=font(18), fill=INK, anchor='mm')
    d.rectangle((360, 160, 1500, 900), outline=WALL, width=12)
    d.text((PW - 40, PH - 36), f'{fl} · 示例平面 EXAMPLE PLAN', font=font(20), fill=(170, 164, 156), anchor='rm')
    return im, d

def save(im, name, q=88):
    path = os.path.join(M, name)
    if name.endswith('.png'): im.save(path, optimize=True)
    else: im.convert('RGB').save(path, quality=q)
    return dict(src='media/' + name, w=im.size[0], h=im.size[1])

def plan_imgs(fl):
    out = {}
    im, d = base_plan(fl); out['plan'] = save(im, f'plan-{fl}.png')
    im, d = base_plan(fl, labels=True, furniture=False, raw=True); out['raw'] = save(im, f'raw-{fl}.png')
    im, d = base_plan(fl, furniture=False)
    for n, b in FLOORS[fl]['rooms']:
        c = GCOL[GROUP.get(n, 0)][0]; d.rectangle([b[0] + 6, b[1] + 6, b[2] - 6, b[3] - 6], fill=c + (150,))
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; d.text((cx, cy - 26), n, font=font(26), fill=INK, anchor='mm')
    out['zone'] = save(im, f'zone-{fl}.png')
    im, d = base_plan(fl, labels=True)
    pts = [(1300, 1000), (1050, 820), (1050, 640), (800, 470), (560, 360), (1300, 360)]
    d.line(pts, fill=(176, 72, 52), width=7, joint='curve')
    for a_, b_ in zip([(560, 980), (760, 720)], [(760, 720), (980, 300)]): d.line([a_, b_], fill=(62, 96, 140), width=5)
    out['flow'] = save(im, f'flow-{fl}.png')
    im, d = base_plan(fl)
    ov = Image.new('RGBA', (PW, PH), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    od.polygon([(1050, 760), (380, 200), (760, 170)], fill=(196, 160, 90, 70)); od.polygon([(1050, 760), (1480, 180), (1180, 170)], fill=(196, 160, 90, 55))
    im = Image.alpha_composite(im.convert('RGBA'), ov.filter(ImageFilter.GaussianBlur(2))); d = ImageDraw.Draw(im)
    d.ellipse([1036, 746, 1064, 774], fill=(176, 72, 52))
    out['view'] = save(im.convert('RGB'), f'view-{fl}.png')
    im, d = base_plan(fl)
    for n, b in FLOORS[fl]['rooms'][:5]:
        d.rectangle([b[0] + 8, b[1] + 8, b[2] - 8, b[1] + 34], fill=(232, 200, 90, 210))
    out['store'] = save(im, f'store-{fl}.png')
    return out

def section(name, cut):
    im = Image.new('RGB', (1600, 1100), 'white'); d = ImageDraw.Draw(im, 'RGBA')
    levels = [('3F', 120), ('2F', 340), ('1F', 560), ('B1F', 780)]; ground = 780
    d.rectangle((0, 560, 300, 1100), fill=(214, 224, 204)) if cut == 'A' else None
    d.rectangle((0, 1000, 1600, 1100), fill=(226, 220, 210))
    for fl, y in levels:
        d.rectangle((300, y + 200, 1500, y + 220), fill=(90, 84, 78))
        d.text((240, y + 120), fl, font=font(34), fill=INK, anchor='mm')
    d.rectangle((300, 120, 316, 1000), fill=(90, 84, 78)); d.rectangle((1484, 120, 1500, 1000), fill=(90, 84, 78))
    d.polygon([(280, 120), (900, 40), (1520, 120)], outline=(90, 84, 78), width=6)
    sx = 760
    for fl, y in levels[1:] + [('B0', 1000)]:
        d.line([(sx, y + 200 if fl != 'B0' else 1000), (sx + 160, y - 20 if fl != 'B0' else 780)], fill=(176, 72, 52), width=6)
    d.rectangle((960, 120, 1040, 1000), outline=(62, 96, 140), width=6, fill=(62, 96, 140, 40)); d.text((1000, 90), '电梯', font=font(24), fill=(62, 96, 140), anchor='mm')
    if cut == 'A':
        d.rectangle((420, 560, 700, 780), fill=(255, 255, 255)); d.rectangle((420, 340, 700, 560), outline=(150, 144, 136), width=3)
        d.text((560, 470), '挑空', font=font(28), fill=(120, 114, 106), anchor='mm')
        d.text((150, 700), '下花园', font=font(28), fill=(90, 110, 84), anchor='mm'); d.text((150, 520), '上花园', font=font(24), fill=(90, 110, 84), anchor='mm')
    else:
        d.rectangle((1200, 120, 1300, 1000), fill=(250, 246, 230)); d.text((1250, 90), '采光井', font=font(24), fill=(150, 130, 90), anchor='mm')
    d.text((840, 70), '楼梯', font=font(24), fill=(176, 72, 52), anchor='mm')
    d.text((1560, 1070), f'{name} · 示例剖面 EXAMPLE SECTION', font=font(20), fill=(170, 164, 156), anchor='rm')
    return save(im, f'section-{cut}.png')

def scene(name, pal, kind, seed=1, size=(1200, 1500)):
    """示例插画：墙 + 地面 + 窗光 + 简单家具色块（不是照片，只为演示版式）。"""
    w, h = size; rnd = random.Random(seed)
    im = Image.new('RGB', size, pal[0]); d = ImageDraw.Draw(im, 'RGBA')
    fy = int(h * rnd.uniform(.62, .7))
    for y in range(h):
        t = y / h; c = tuple(int(pal[0][k] * (1 - t * .25) + pal[1][k] * t * .25) for k in range(3)); d.line([(0, y), (w, y)], fill=c)
    d.rectangle((0, fy, w, h), fill=pal[1])
    if kind != 'site':
        wx = int(w * rnd.uniform(.1, .5)); ww = int(w * .38)
        d.rectangle((wx, int(h * .12), wx + ww, fy - int(h * .08)), fill=(250, 248, 242)); d.line([(wx + ww // 2, int(h * .12)), (wx + ww // 2, fy - int(h * .08))], fill=pal[2], width=6)
        light = Image.new('L', size, 0); ld = ImageDraw.Draw(light)
        ld.polygon([(wx, fy), (wx + ww, fy), (wx + ww + int(w * .25), h), (wx + int(w * .1), h)], fill=110)
        im.paste((255, 250, 238), mask=light.filter(ImageFilter.GaussianBlur(30))); d = ImageDraw.Draw(im, 'RGBA')
    if kind == 'living':
        d.rounded_rectangle((int(w * .15), fy - int(h * .1), int(w * .78), fy + int(h * .05)), 30, fill=pal[3])
        d.rounded_rectangle((int(w * .3), fy + int(h * .1), int(w * .62), fy + int(h * .14)), 12, fill=pal[2])
    elif kind == 'bed':
        d.rectangle((int(w * .1), fy - int(h * .18), int(w * .85), fy - int(h * .04)), fill=pal[2])
        d.rounded_rectangle((int(w * .14), fy - int(h * .06), int(w * .82), fy + int(h * .08)), 20, fill=pal[3])
    elif kind == 'garden':
        for _ in range(10):
            cx, cy, r = rnd.uniform(0, w), rnd.uniform(fy - h * .2, h), rnd.uniform(w * .06, w * .16)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(rnd.randint(110, 140), rnd.randint(140, 165), rnd.randint(100, 120), 230))
    elif kind == 'site':
        d.rectangle((int(w * .2), int(h * .2), int(w * .55), fy), fill=(212, 210, 205)); d.rectangle((0, int(h * .05), w, int(h * .09)), fill=(140, 138, 134))
        for _ in range(4000): x, y = rnd.uniform(0, w), rnd.uniform(0, h); d.point((x, y), fill=(120, 118, 114, 70))
    elif kind == 'plant':
        for _ in range(14):
            cx, cy, r = rnd.uniform(w * .1, w * .9), rnd.uniform(h * .3, h * .9), rnd.uniform(w * .05, w * .12)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(rnd.randint(90, 130), rnd.randint(130, 160), rnd.randint(90, 110), 220))
    elif kind == 'light':
        im.paste((52, 48, 44), (0, 0, w, h)); d = ImageDraw.Draw(im, 'RGBA')
        for _ in range(9):
            cx, cy = rnd.uniform(w * .1, w * .9), rnd.uniform(h * .4, h * .9); glow = Image.new('L', size, 0)
            ImageDraw.Draw(glow).ellipse([cx - 90, cy - 90, cx + 90, cy + 90], fill=170); im.paste((255, 214, 150), mask=glow.filter(ImageFilter.GaussianBlur(40)))
    elif kind == 'drain':
        im.paste((236, 233, 228), (0, 0, w, h)); d = ImageDraw.Draw(im)
        for k, c in enumerate([(120, 150, 110), (150, 120, 90), (190, 186, 178), (90, 110, 140), (210, 206, 198)]):
            d.rectangle((0, int(h * (.3 + k * .12)), w, int(h * (.42 + k * .12))), fill=c)
    elif kind == 'smart':
        im.paste((238, 236, 232), (0, 0, w, h)); d = ImageDraw.Draw(im)
        for k in range(6):
            x, y = (k % 3) * w // 3 + w // 6, (k // 3) * h // 3 + h // 3
            d.rounded_rectangle((x - 90, y - 90, x + 90, y + 90), 30, outline=pal[2], width=6); d.ellipse((x - 25, y - 25, x + 25, y + 25), fill=pal[3])
    d.text((w - 30, h - 30), '示例图片 SAMPLE', font=font(int(w * .028)), fill=(255, 255, 255, 170) if kind == 'light' else (90, 84, 78, 120), anchor='rd')
    return save(im, name, 86)

P = {k: plan_imgs(k) for k in FLOORS}
SA, SB = section('剖面 A-A', 'A'), section('剖面 B-B', 'B')
for k in (1, 2):   # 2F 方案二 / 三
    im, d = base_plan('2F', scheme=k); P['2F'][f's{k + 1}'] = save(im, f'plan-2F-s{k + 1}.png')
PAL = [((232, 226, 216), (196, 180, 160), (150, 128, 104), (214, 204, 188)), ((226, 222, 214), (170, 150, 128), (110, 92, 76), (196, 186, 170)),
       ((236, 230, 220), (204, 190, 170), (172, 120, 92), (226, 214, 196)), ((220, 224, 220), (178, 170, 156), (96, 110, 104), (204, 200, 190))]
def img(name, kind, k, size=(1200, 1500)): return scene(name, PAL[k % 4], kind, k, size)
IM = dict(cover=img('cover.jpg', 'living', 0, (1200, 1800)), studio=img('studio.jpg', 'living', 3, (1500, 1000)),
          site=[img(f'site{k}.jpg', 'site', k, (1200, 900)) for k in range(4)],
          mood=[img(f'mood{k}.jpg', ['living', 'bed', 'living', 'garden'][k % 4], k) for k in range(6)],
          liv=[img(f'liv{k}.jpg', 'living', k + 1) for k in range(3)], bed=[img(f'bed{k}.jpg', 'bed', k) for k in range(3)],
          old=[img(f'old{k}.jpg', 'bed', k + 2) for k in range(3)], gar=[img(f'gar{k}.jpg', 'garden', k) for k in range(3)],
          sec=[img(f'sec{k}.jpg', 'living', k + 5, (1200, 1700)) for k in range(4)],
          plant=img('plant.jpg', 'plant', 1, (1200, 900)), light=img('light.jpg', 'light', 2, (1200, 900)),
          drain=img('drain.jpg', 'drain', 3, (1200, 900)), smart=img('smart.jpg', 'smart', 0, (1200, 900)))

B = '示例数据 · EXAMPLE DATA'
def rooms(fl):
    rs = []
    if FLOORS[fl]['garden']: rs.append(dict(name=FLOORS[fl]['garden'][0], box=FLOORS[fl]['garden'][1]))
    rs += [dict(name=n, box=b) for n, b in FLOORS[fl]['rooms']]
    return [dict(n=k + 1, name=r['name'], x=pct(r['box'])[0], y=pct(r['box'])[1], page=None) for k, r in enumerate(rs)]
def pt(fl, name, n):
    b = dict(FLOORS[fl]['rooms']).get(name) or FLOORS[fl]['garden'][1]; x, y = pct(b); return dict(n=n, x=x, y=y)

pages = []
def add(**k): k.setdefault('slide', len(pages) + 1); k.setdefault('images', []); pages.append(k); return k
add(template='cover', title='示例别墅', title_en='Sample Villa', subtitle='CONCEPT PROPOSAL', bg=IM['cover']['src'])
add(template='studio', images=[IM['studio']], badge=B, name='设计师姓名', role='创始人 / 设计总监',
    body=['这里放工作室和设计师介绍（示例）。正式项目里，这一页的内容写在 brand.json 的 about 里，所有项目共用。', '两到三句话讲清楚：做什么类型的项目、设计主张、服务方式。'],
    items=['示例荣誉 · 行业协会会员', '示例荣誉 · 设计奖项', '示例经历 · 海外进修'])
add(template='section', title='项目现场', title_en='Project Site', eyebrow='PART 01', quote='先看清楚房子本来的样子。', images=[IM['site'][0]])
add(template='grid', title='现场记录', title_en='Site Record', badge=B, images=IM['site'], body=['示例：毛坯现状照片，四层各选一两张。'])
add(template='section', title='概念解读', title_en='Concept', eyebrow='PART 02', quote='自然、舒适、松弛（示例关键词）', images=[IM['mood'][0]])
add(template='concept', title='设计理念', title_en='Design Concept', items=[dict(title='自然', title_en='Nature', image=IM['mood'][3]),
    dict(title='舒适', title_en='Comfort', image=IM['mood'][1]), dict(title='松弛', title_en='Ease', image=IM['mood'][2])])
add(template='grid', title='意向氛围', title_en='Mood', images=IM['mood'][:5], palette=True)
add(template='section', title='户型分析', title_en='Structural Analysis', eyebrow='PART 03', quote='每一层先找问题，再谈方案。', images=[IM['site'][1]])
ISS = {'B1F': (['地下室采光不足，白天也要开灯', '下花园与室内没有直接连通', '入户后缺少过渡和收纳'], ['客厅', '下花园', '西厨']),
       '1F': (['入户门厅进深不够，缺少换鞋收纳', '老人房卫生间尺度偏小', '家庭厅与花园互动少'], ['门厅', '老人房', '家庭厅']),
       '2F': (['过厅面积大但利用率低', '两间卧室尺度偏小'], ['学习区', '儿子房']),
       '3F': (['起居空间层高偏高，缺少包裹感', '主卧面积相对较小'], ['起居室', '主卧'])}
for k, (fl, (probs, rms)) in enumerate(ISS.items()):
    add(template='issues', floor=fl, title=f'户型分析 · {fl}', title_en='Original Plan', badge=B, images=[P[fl]['raw']],
        points=[pt(fl, r, i + 1) for i, r in enumerate(rms)], problems=probs, photos=[IM['site'][k % 4], IM['site'][(k + 1) % 4]])
add(template='section', title='设计目标', title_en='Design Objective', eyebrow='PART 04', quote='一层一个目标。', images=[IM['mood'][4]])
add(template='goals', title='设计目标', title_en='Objectives by Floor', badge=B, goals=[
    dict(floor='3F', title='主人套房', text='示例：卧室、起居、书房连成一体，互不打扰'),
    dict(floor='2F', title='孩子的成长空间', text='示例：卧室 + 学习区，留出未来调整的余地'),
    dict(floor='1F', title='长辈与家庭生活', text='示例：老人房无高差，家庭厅面向上花园'),
    dict(floor='B1F', title='聚会与接待', text='示例：围绕下花园，打造会客、品茶、影音的集合空间')])
add(template='section', title='平面布局', title_en='Layout', eyebrow='PART 05', quote='按楼层，从下往上看。', images=[IM['mood'][1]])
for fl in ('B1F', '1F', '2F', '3F'):
    add(template='plan', floor=fl, title=f'平面布局 · {fl}', title_en='Floor Plan', images=[P[fl]['plan']], rooms=rooms(fl))
    if fl == 'B1F':
        add(template='swipe', floor=fl, title='B1F 平面分析', title_en='Analysis', badge=B, slides=[
            dict(label='功能分区', image=P[fl]['zone'], legend=[dict(color='rgb%s' % (c,), label=l) for c, l in GCOL], caption='示例：公共、私密、服务三类空间分开，交通集中在中部。'),
            dict(label='动线', image=P[fl]['flow'], legend=[dict(color='#b04834', label='家人动线'), dict(color='#3e608c', label='访客 / 家政')], notes=['车库入户直达门厅', '家政动线不穿过会客区']),
            dict(label='视线', image=P[fl]['view'], caption='示例：入户第一眼看到下花园，客厅与餐厅视线互通。'),
            dict(label='收纳', image=P[fl]['store'], caption='示例：黄色为新增柜体，集中在入户、厨房和走道。')])
    if fl == '2F':
        add(template='swipe', floor=fl, title='2F 方案对比', title_en='Schemes', badge=B, slides=[
            dict(label='方案一', image=P[fl]['plan'], caption='示例：两间卧室 + 独立学习区。'),
            dict(label='方案二', image=P[fl]['s2'], caption='示例：学习区并入儿子房，卧室更宽敞。'),
            dict(label='方案三', image=P[fl]['s3'], caption='示例：次卧改为多功能房，可兼作客房。')])
add(template='section', title='垂直交通', title_en='Vertical Circulation', eyebrow='PART 06', quote='楼梯、电梯、挑空，把四层串起来。', images=[IM['mood'][2]])
add(template='vertical', title='垂直交通', title_en='Vertical Circulation', badge=B, floors=[
    dict(id='3F', name='主人层', level='+9.60'), dict(id='2F', name='孩子层', level='+6.30'), dict(id='1F', name='入户层', level='±0.00'), dict(id='B1F', name='花园层', level='-3.30')],
    cores=[dict(n=1, name='楼梯', type='stair', x=34, w=13, **{'from': 'B1F', 'to': '3F'}, note='示例：保留原楼梯位置，踏步改为木饰面'),
           dict(n=2, name='电梯', type='lift', x=50, w=9, **{'from': 'B1F', 'to': '3F'}, note='示例：新增家用电梯，四层直达，方便长辈'),
           dict(n=3, name='挑空', type='void', x=6, w=22, **{'from': '1F', 'to': '2F'}, note='示例：家庭厅上方挑空，两层视线相通'),
           dict(n=4, name='采光井', type='light', x=72, w=12, **{'from': 'B1F', 'to': '1F'}, note='示例：把自然光引到地下室')])
add(template='swipe', title='剖面', title_en='Sections', badge=B, slides=[
    dict(label='剖面 A-A', image=SA, caption='示例：挑空与上下花园的关系。'), dict(label='剖面 B-B', image=SB, caption='示例：采光井把光带到 B1F。')])
add(template='section', title='平面意向', title_en='Spatial Mood', eyebrow='PART 07', quote='每个房间的样子。', images=[IM['mood'][3]])
add(template='grid', floor='B1F', room='客厅', title='客厅', title_en='Living Room', images=IM['liv'])
add(template='grid', floor='1F', room='老人房', title='老人房', title_en='Elder Room', images=IM['old'])
add(template='grid', floor='3F', room='主卧', title='主卧', title_en='Master Bedroom', images=IM['bed'])
add(template='grid', room=['上花园', '下花园'], title='花园意向', title_en='Garden Mood', images=IM['gar'])
add(template='section', title='专项', title_en='Special Systems', eyebrow='PART 08', quote='看不见的部分，决定住得好不好。', images=[IM['plant']])
for t_, en, im, items in (('绿植专项', 'Planting', IM['plant'], ['示例：四季常绿为底，每季有花', '示例：保留原有大树']),
                          ('灯光专项', 'Lighting', IM['light'], ['示例：低位点光，不直射眼睛', '示例：分回路，场景可调']),
                          ('防水排水专项', 'Waterproofing & Drainage', IM['drain'], ['示例：成品排水沟，可开启检修', '示例：花池、鱼池单独防水']),
                          ('智能化专项', 'Smart Home', IM['smart'], ['示例：灯光 / 灌溉 / 安防统一管理', '示例：按需求定制'])):
    add(template='material', title=t_, title_en=en, items=[dict(title=items[0], text=items[1], images=[im])])
add(template='about', title='谢谢观看', title_en='Thank you.')
for p in pages:
    for k in ('chapter', 'eyebrow', 'subtitle', 'quote', 'note', 'bg'): p.setdefault(k, '')
    p.setdefault('body', []); p.setdefault('items', []); p.setdefault('hidden', False); p.setdefault('palette', False)
cfg = dict(project='formal-template', brand='default', title='示例别墅', title_en='Sample Villa', report_name='概念方案汇报', report_name_en='Concept Proposal',
           plan_mode='concept', protect=True, noindex=True,
           floors=[dict(id='B1F', name='花园层'), dict(id='1F', name='入户层'), dict(id='2F', name='孩子层'), dict(id='3F', name='主人层')], pages=pages)
json.dump(cfg, open(os.path.join(W, 'config.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('示例项目已生成：', len(pages), '页 →', W)
