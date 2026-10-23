"""品牌配置：工作室名称、联系方式、二维码、logo/印章、页脚文字、点缀色、字体 —— 全部只在 brands/<品牌>/brand.json 里。
模板和代码里不写死任何工作室信息。项目 config.json 里填了的同名字段优先（用于个别项目临时改）。"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = dict(
    studio='设计工作室', studio_en='Design Studio', aliases=[],
    report_name='设计方案汇报', report_name_en='Design Proposal',
    contact=dict(phone='', wechat='', address='', note=''),
    qr='', logo='', seal='', seal_image='', footer='',
    theme='wabi', accent='', theme_vars={}, fonts={})


def brand_dir(name):
    if name and os.path.isdir(name): return os.path.abspath(name)
    return os.path.join(ROOT, 'brands', name or 'default')


def load_brand(name=None):
    """name: brands/ 下的目录名，或任意目录路径；不给则读环境变量 XF_BRAND，再不行用 default。"""
    name = name or os.environ.get('XF_BRAND') or 'default'
    d = brand_dir(name)
    b = json.loads(json.dumps(DEFAULT))
    p = os.path.join(d, 'brand.json')
    if os.path.exists(p):
        user = json.load(open(p, encoding='utf-8'))
        for k, v in user.items():
            if k.startswith('_'): continue
            if isinstance(v, dict) and isinstance(b.get(k), dict): b[k].update(v)
            else: b[k] = v
    b['_dir'] = d; b['_id'] = os.path.basename(d.rstrip('/'))
    for k in ('qr', 'logo', 'seal_image'):     # 图片路径相对品牌目录；qr 可写 "placeholder" 预览占位图
        if b.get(k) and b[k] != 'placeholder' and not os.path.isabs(b[k]): b[k] = os.path.join(d, b[k])
    return b


def merge(cfg, b):
    """品牌值做底，项目 config 里非空的值覆盖。返回新的 cfg。"""
    out = dict(cfg)
    for k in ('studio', 'studio_en', 'report_name', 'report_name_en', 'footer', 'seal'):
        if not out.get(k): out[k] = b.get(k, '')
    c = dict(b.get('contact') or {}); c.update({k: v for k, v in (cfg.get('contact') or {}).items() if v})
    out['contact'] = c
    if not c.get('qr') and b.get('qr'): c['qr'] = b['qr']
    for k in ('logo', 'seal_image'):
        if not out.get(k) and b.get(k): out[k] = b[k]
    if not out.get('style') and b.get('theme'): out['style'] = b['theme']
    if not out.get('theme_accent') and b.get('accent'): out['theme_accent'] = b['accent']
    tv = json.loads(json.dumps(b.get('theme_vars') or {}))
    for th, vs in (cfg.get('theme_vars') or {}).items(): tv.setdefault(th, {}).update(vs)
    out['theme_vars'] = tv
    out['_fonts'] = b.get('fonts') or {}
    out['_brand'] = b
    return out
