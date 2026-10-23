#!/usr/bin/env python3
"""汇报网页 · 版式预览确认（正式构建前的必做步骤）。

生成 out/<项目>-preview/：
  - 列表：缩略图 + 版式下拉 + 备注 +「看效果」
  - 点缩略图/看效果 → 设备框（手机/iPad/电脑可切换），iframe 真实版式 HTML（复用 build 渲染）
  - 换下拉立刻换 iframe（预生成各版式变体，静态托管也能用）
  - 设备切换：iframe 设为对应 CSS 像素宽高，整框 CSS transform 缩放；电脑档为浏览器窗口(~1020)；侧栏毛玻璃浮层不挤偏居中框
  - 保存 → overrides.json + pages_confirmed.json

用法:
  python3 tools/preview.py --project formal-template
  python3 tools/preview.py --project formal-template --serve
  python3 tools/preview.py --project formal-template --apply overrides.json
"""
from __future__ import annotations
import argparse, json, os, shutil, datetime, http.server, functools, copy, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
LAYOUTS = json.loads((ROOT / 'templates' / 'layouts.json').read_text(encoding='utf-8'))
KINDS = LAYOUTS['kinds']
ALIAS = LAYOUTS['alias_to_template']
TPL_TO_KIND = {k['template']: k['kind'] for k in KINDS}
# 预生成这些版式变体（下拉切换即可看效果；静态托管无需后端）
VARIANT_TEMPLATES = [
    'cover', 'text', 'section', 'split', 'full', 'grid', 'issues', 'plan',
    'swipe', 'concept', 'material', 'studio', 'about', 'goals', 'vertical',
    'selection', 'strategy', 'persona', 'render', 'contents',
]


def work_dir(project: str) -> Path:
    return ROOT / 'work' / project


def out_dir(project: str, custom: str | None = None) -> Path:
    return Path(custom) if custom else ROOT / 'out' / f'{project}-preview'


def load_cfg(project: str) -> dict:
    p = work_dir(project) / 'config.json'
    if not p.exists():
        raise SystemExit(f'找不到 {p}，先跑 classify 或手写 config.json')
    return json.loads(p.read_text(encoding='utf-8'))


def first_image_src(page: dict) -> str | None:
    if page.get('bg'):
        return page['bg'] if isinstance(page['bg'], str) else (page['bg'] or {}).get('src')
    for im in page.get('images') or []:
        if isinstance(im, dict) and im.get('src'):
            return im['src']
        if isinstance(im, str):
            return im
    for sl in page.get('slides') or []:
        im = (sl or {}).get('image') or {}
        if isinstance(im, dict) and im.get('src'):
            return im['src']
    for it in page.get('items') or []:
        im = (it or {}).get('image') or {}
        if isinstance(im, dict) and im.get('src'):
            return im['src']
    return None


def brand_thumb_for(page: dict, cfg: dict) -> Path | None:
    """studio / about 页：用品牌 about 图做缩略图。"""
    brand = cfg.get('brand') or 'default'
    bdir = ROOT / 'brands' / brand
    t = page.get('template')
    part = page.get('part')
    if t == 'studio':
        name = 'about-designer.jpg' if part == 'designer' else 'about-studio.jpg'
        p = bdir / name
        return p if p.exists() else None
    if t == 'about':
        for name in ('about-studio.jpg', 'about-designer.jpg', 'qr.png'):
            p = bdir / name
            if p.exists() and p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
                return p
    return None


def resolve_thumb_source(work: Path, page: dict, index: int, cfg: dict) -> Path | None:
    slide = page.get('slide')
    candidates = []
    if slide is not None:
        for name in (f'p{int(slide):02d}.jpg', f'p{int(slide):02d}.png', f'slide-{int(slide)}.jpg'):
            candidates.append(work / 'render' / name)
    candidates += [work / 'render' / f'p{index + 1:02d}.jpg']
    for c in candidates:
        if c.exists():
            return c
    src = first_image_src(page)
    if src:
        p = Path(src)
        if not p.is_absolute():
            p = work / src
        if p.exists():
            return p
    return brand_thumb_for(page, cfg)


def make_thumb(src: Path, dst: Path, max_side: int = 420) -> bool:
    try:
        from PIL import Image
        im = Image.open(src).convert('RGB')
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, 'JPEG', quality=78, optimize=True)
        return True
    except Exception as e:
        print('  thumb skip', src.name, e)
        return False


def apply_overrides_to_config(cfg: dict, work: Path) -> dict:
    ov_path = work / 'overrides.json'
    if not ov_path.exists():
        return cfg
    ov = json.loads(ov_path.read_text(encoding='utf-8'))
    for k, v in (ov.get('global') or {}).items():
        if k.startswith('_'):
            continue
        cfg[k] = v
    by_slide, by_index = {}, {}
    for i, p in enumerate(cfg.get('pages') or []):
        if p.get('slide') is not None:
            by_slide[int(p['slide'])] = p
        by_index[i + 1] = p
    for sl, patch in (ov.get('pages') or {}).items():
        if str(sl).startswith('_'):
            continue
        try:
            n = int(sl)
        except ValueError:
            continue
        target = by_slide.get(n) or by_index.get(n)
        if target is not None:
            clean = {k: v for k, v in patch.items() if not str(k).startswith('_')}
            if 'template' in clean:
                clean['template'] = ALIAS.get(clean['template'], clean['template'])
            target.update(clean)
    return cfg


def merge_overrides(work: Path, patch_pages: dict, notes: dict | None = None, confirmed_meta: dict | None = None):
    ov_path = work / 'overrides.json'
    ov = {'_说明': '手改项：global 改全局字段，pages 按 PPT 页码（或页序）改单页。classify --force 与 build 都会套用。',
          'global': {}, 'pages': {}}
    if ov_path.exists():
        try:
            ov = json.loads(ov_path.read_text(encoding='utf-8'))
        except Exception:
            pass
    ov.setdefault('pages', {})
    ov.setdefault('global', {})
    for key, tpl in patch_pages.items():
        slot = ov['pages'].setdefault(str(key), {})
        slot['template'] = ALIAS.get(tpl, tpl)
        if notes and str(key) in notes and notes[str(key)] is not None:
            slot['preview_note'] = notes[str(key)]
    ov_path.write_text(json.dumps(ov, ensure_ascii=False, indent=2), encoding='utf-8')

    confirmed = {
        'confirmed_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
        'project': work.name,
        'pages': [],
    }
    if confirmed_meta:
        confirmed.update(confirmed_meta)
    confirmed['pages'] = [
        {'key': str(k), 'template': ALIAS.get(t, t), 'note': (notes or {}).get(str(k), '')}
        for k, t in patch_pages.items()
    ]
    (work / 'pages_confirmed.json').write_text(json.dumps(confirmed, ensure_ascii=False, indent=2), encoding='utf-8')
    return ov_path, work / 'pages_confirmed.json'


def page_rows(cfg: dict, work: Path, thumbs_out: Path) -> list[dict]:
    rows = []
    for i, page in enumerate(cfg.get('pages') or []):
        if page.get('hidden'):
            continue
        slide = page.get('slide')
        key = str(slide if slide is not None else i + 1)
        tpl = page.get('template') or 'text'
        kind = TPL_TO_KIND.get(tpl, tpl)
        thumb_name = f't{key}.jpg'
        src = resolve_thumb_source(work, page, i, cfg)
        has_thumb = bool(src and make_thumb(src, thumbs_out / thumb_name))
        nimg = len(page.get('images') or [])
        if page.get('bg'):
            nimg = max(nimg, 1)
        nimg += sum(1 for s in (page.get('slides') or []) if (s or {}).get('image'))
        variants = sorted(set(VARIANT_TEMPLATES + [tpl]))
        rows.append({
            'index': i,
            'key': key,
            'slide': slide,
            'title': page.get('title') or page.get('name') or (page.get('part') and f"studio · {page['part']}") or f'第 {key} 页',
            'title_en': page.get('title_en') or '',
            'template': tpl,
            'kind': kind,
            'floor': page.get('floor') or '',
            'nimg': nimg,
            'thumb': f'thumbs/{thumb_name}' if has_thumb else '',
            'note': page.get('preview_note') or page.get('note') or '',
            'chapter': page.get('chapter') or '',
            'variants': variants,
            'phone': f'phone/slide-{key}.html?tpl={tpl}',
        })
    return rows


def _prepare_cfg_for_build(project: str):
    import build as B
    from brand import load_brand, merge
    work = work_dir(project)
    cfg = apply_overrides_to_config(load_cfg(project), work)
    cfg = merge(cfg, load_brand(cfg.get('brand')))
    theme = cfg.get('style') or 'french'
    B.TH.clear(); B.TH.update(B.THEMES[theme]); B.TH['id'] = theme
    B.FLOORS.clear(); B.FLOORS.extend(cfg.get('floors') or [])
    pages = [p for p in cfg['pages'] if not p.get('hidden')]
    # minimal chapter numbering so head_block works
    B.CHAPTERS.clear()
    k = 0
    curnum = ''
    CN = getattr(B, 'CN_NUM', list('壹贰叁肆伍陆柒捌玖拾'))
    for p in pages:
        if p['template'] == 'section':
            curnum = CN[k] if k < len(CN) else str(k + 1)
            k += 1
            p['_num'] = curnum
            B.CHAPTERS.append([0, curnum, p.get('title') or '', p.get('title_en') or '', []])
        elif p['template'] in ('cover', 'contents', 'about'):
            curnum = ''
        p['_chnum'] = curnum
        p['_ci'] = 0
        p['_flabel'] = p.get('title') or ''
    return cfg, pages, theme, work


def build_phone_deck(project: str, phone_out: Path, theme: str | None = None) -> tuple[list[dict], str]:
    """先正式 lite build 到 phone/，再为每页×版式写单页 HTML（同 assets，下拉可秒切）。"""
    work = work_dir(project)
    cfg0 = apply_overrides_to_config(load_cfg(project), work)
    th = theme or cfg0.get('style') or 'french'
    if phone_out.exists():
        shutil.rmtree(phone_out)
    phone_out.mkdir(parents=True)
    cmd = [
        sys.executable, str(ROOT / 'tools' / 'build.py'),
        '--project', project, '--lite', '--theme', th,
        '--out', str(phone_out), '--skip-preview-check',
    ]
    print('  构建手机预览底稿…')
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit('phone deck build failed')
    print('  ', (r.stdout or '').strip().splitlines()[-1] if r.stdout else 'ok')

    import build as B
    from brand import load_brand, merge
    cfg = apply_overrides_to_config(load_cfg(project), work)
    cfg = merge(cfg, load_brand(cfg.get('brand')))
    B.TH.clear(); B.TH.update(B.THEMES[th]); B.TH['id'] = th
    B.FLOORS.clear(); B.FLOORS.extend(cfg.get('floors') or [])
    B.CHAPTERS.clear()
    pages = [p for p in cfg['pages'] if not p.get('hidden')]
    CN = getattr(B, 'CN_NUM', list('壹贰叁肆伍陆柒捌玖拾'))
    k = 0
    curnum = ''
    for p in pages:
        if p.get('template') == 'section':
            curnum = CN[k] if k < len(CN) else str(k + 1); k += 1
            p['_num'] = curnum
            B.CHAPTERS.append([0, curnum, p.get('title') or '', p.get('title_en') or '', []])
        elif p.get('template') in ('cover', 'contents', 'about'):
            curnum = ''
        p['_chnum'] = curnum
        p['_ci'] = 0
        p['_flabel'] = p.get('title') or ''

    # resolve locators once (best-effort)
    try:
        B.resolve_locators(pages, str(work))
    except Exception:
        pass

    I = B.Images(str(work), str(phone_out), lite=True)
    n = len(pages)
    shell_css = (
        'html,body{margin:0;height:100%;background:var(--bg,#f7f3ec)}'
        'body{overflow:auto}'
        'main{display:block}'
        '.pg{min-height:100vh!important;height:auto!important;scroll-snap-align:none!important}'
        '.bar,.dots,.nav,.toc,.prog,.lb,.hint{display:none!important}'
    )

    def wrap(section_html: str) -> str:
        return (
            '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="robots" content="noindex">'
            f'<link rel="stylesheet" href="assets/style.css">'
            f'<style>{shell_css}</style></head>'
            f'<body class="t-{th} protect">'
            f'<main>{section_html}</main>'
            '<script src="assets/app.js" defer></script>'
            '</body></html>'
        )

    built = 0
    switch_js = r"""
<script>
(function(){
  function show(){
    var tpl = new URLSearchParams(location.search).get('tpl') || document.body.dataset.defaultTpl || 'text';
    document.querySelectorAll('.variant').forEach(function(el){
      var on = el.getAttribute('data-tpl') === tpl;
      el.hidden = !on;
      el.style.display = on ? '' : 'none';
    });
    document.body.dataset.tpl = tpl;
  }
  show();
  window.addEventListener('hashchange', show);
  window.addEventListener('popstate', show);
})();
</script>
"""
    def wrap_multi(sections_html: str, default_tpl: str) -> str:
        return (
            '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="robots" content="noindex">'
            f'<link rel="stylesheet" href="assets/style.css">'
            f'<style>{shell_css}'
            '.variant[hidden],.variant[style*="display: none"]{display:none!important}</style></head>'
            f'<body class="t-{th} protect" data-default-tpl="{default_tpl}">'
            f'<main>{sections_html}</main>'
            '<script src="assets/app.js" defer></script>'
            f'{switch_js}'
            '</body></html>'
        )

    for i, page in enumerate(pages):
        key = str(page.get('slide') if page.get('slide') is not None else i + 1)
        cur = page.get('template') or 'text'
        chunks = []
        for tpl in sorted(set(VARIANT_TEMPLATES + [cur])):
            pp = copy.deepcopy(page)
            pp['template'] = tpl
            try:
                html = B.render_page(pp, i, n, I, cfg, i == 0)
            except Exception as ex:
                html = (
                    f'<section class="pg text"><div class="inner">'
                    f'<h2>无法预览「{tpl}」</h2><p>{B.e(str(ex))}</p></div></section>'
                )
            # mark as variant; keep section.pg + original classes (cover/cf/…) for theme CSS
            def _variant_tag(m, _tpl=tpl):
                return f'<section class="pg variant{m.group(1)}" data-tpl="{_tpl}"'
            html2, nsub = re.subn(r'<section\s+class="pg([^"]*)"', _variant_tag, html, count=1)
            if nsub:
                html = html2
            elif f'data-tpl="{tpl}"' not in html:
                html = f'<div class="variant" data-tpl="{tpl}">{html}</div>'
            chunks.append(html)
            built += 1
        path = phone_out / f'slide-{key}.html'
        path.write_text(wrap_multi('\n'.join(chunks), cur), encoding='utf-8')
    # remove old per-variant files if any leftover from prior runs (we rmtree phone_out already)
    print(f'  单页文件 {len(pages)} 个（内含变体共 {built}）→ {phone_out}/slide-*.html')
    return pages, th


def build_preview(project: str, out: Path | None = None) -> Path:
    work = work_dir(project)
    cfg = apply_overrides_to_config(load_cfg(project), work)
    dest = out_dir(project, str(out) if out else None)
    if dest.exists():
        shutil.rmtree(dest)
    thumbs = dest / 'thumbs'
    thumbs.mkdir(parents=True)

    phone_out = dest / 'phone'
    pages_built, theme = build_phone_deck(project, phone_out)

    rows = page_rows(cfg, work, thumbs)
    # ensure phone path matches
    for r in rows:
        r['phone'] = f"phone/slide-{r['key']}.html?tpl={r['template']}"

    payload = {
        'project': project,
        'title': cfg.get('title') or project,
        'title_en': cfg.get('title_en') or '',
        'style': theme,
        'kinds': KINDS,
        'pages': rows,
        'variant_templates': VARIANT_TEMPLATES,
    }
    (dest / 'preview-data.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (dest / 'index.html').write_text(PREVIEW_HTML, encoding='utf-8')
    (dest / 'preview.css').write_text(PREVIEW_CSS, encoding='utf-8')
    (dest / 'preview.js').write_text(PREVIEW_JS, encoding='utf-8')
    print(f'预览站 → {dest}  （{len(rows)} 页，主题 {theme}）')
    print(f'  本机：python3 tools/preview.py --project {project} --serve')
    return dest


# ---------- UI ----------
PREVIEW_CSS = r"""
:root{--bg:#f7f3ec;--panel:#fff;--ink:#1e2430;--muted:#7a7368;--line:#e4ddd2;--accent:#1e3a5f;--ok:#2f6b4f}
*{box-sizing:border-box}
body{margin:0;font:14px/1.5 -apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans SC",sans-serif;background:var(--bg);color:var(--ink)}
header{position:sticky;top:0;z-index:20;background:rgba(247,243,236,.94);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:12px 18px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;justify-content:space-between}
header h1{margin:0;font-size:16px;font-weight:600}
header .meta{color:var(--muted);font-size:12px}
header .actions{display:flex;gap:8px;flex-wrap:wrap}
button,select,input[type=text]{font:inherit}
button{appearance:none;border:1px solid var(--accent);background:var(--accent);color:#fff;padding:8px 14px;border-radius:4px;cursor:pointer}
button.secondary{background:#fff;color:var(--accent)}
button.ok{background:var(--ok);border-color:var(--ok)}
button:disabled{opacity:.45;cursor:not-allowed}
.batch{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 18px;border-bottom:1px solid var(--line);background:#fff}
.batch label{color:var(--muted);font-size:12px}
.hint{font-size:12px;color:var(--muted);padding:8px 18px;max-width:1100px;margin:0 auto}
.list{padding:12px 18px 100px;display:flex;flex-direction:column;gap:12px;max-width:1100px;margin:0 auto}
.card{display:grid;grid-template-columns:112px 1fr;gap:14px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;align-items:start}
.card.dirty{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.thumb-wrap{position:relative;cursor:pointer;border:0;background:transparent;padding:0}
.thumb{width:112px;height:150px;object-fit:contain;background:#efe8dc;border-radius:4px;display:block;border:1px solid var(--line)}
.thumb.ph{display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:11px;text-align:center;padding:8px;width:112px;height:150px}
.thumb-wrap .play{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);background:rgba(30,58,95,.88);color:#fff;font-size:11px;padding:4px 8px;border-radius:99px;pointer-events:none}
.info{min-width:0}
.row1{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.idx{font-variant-numeric:tabular-nums;color:var(--muted);font-size:12px}
.title{font-size:15px;font-weight:600}
.en{color:var(--muted);font-style:italic;font-size:12px}
.floor{font-size:11px;padding:1px 6px;border:1px solid var(--line);border-radius:99px;color:var(--muted)}
.fields{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;margin-top:8px;align-items:end}
@media(max-width:720px){.card{grid-template-columns:1fr}.fields{grid-template-columns:1fr}}
label.f{display:flex;flex-direction:column;gap:4px;font-size:11px;color:var(--muted)}
label.f select,label.f input{padding:7px 8px;border:1px solid var(--line);border-radius:4px;background:#fff;color:var(--ink)}
.check{display:flex;align-items:center;gap:6px;margin-top:8px;font-size:12px;color:var(--muted)}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;padding:10px 16px;border-radius:6px;font-size:13px;opacity:0;pointer-events:none;transition:.2s;z-index:50}
.toast.show{opacity:1}
/* device modal — stage full-bleed, glass side floats over */
.modal{position:fixed;inset:0;background:rgba(18,22,30,.62);z-index:40;display:none;padding:0}
.modal.open{display:block}
.device-stage{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:24px;overflow:hidden;/* 侧栏浮层不占位，设备框相对整个视口居中 */}
.device-fit{position:relative;flex-shrink:0}
.device-scale{position:absolute;left:0;top:0;transform-origin:top left}
.device{background:#1a1d24;box-shadow:0 24px 64px rgba(0,0,0,.4);display:flex;flex-direction:column;overflow:hidden}
.device[data-device="phone"]{border-radius:28px;padding:12px}
.device[data-device="ipad"]{border-radius:22px;padding:14px;background:#2a2e36}
.device[data-device="desktop"]{border-radius:10px;padding:0;background:#e8e6e3;box-shadow:0 28px 70px rgba(0,0,0,.38)}
.device-chrome-top{display:none;align-items:center;gap:10px;padding:8px 12px;background:linear-gradient(180deg,#f3f1ef,#e5e3e0);border-bottom:1px solid #d4d0cb;flex:none}
.device[data-device="desktop"] .device-chrome-top{display:flex}
.traffic{display:flex;gap:6px;flex:none}
.traffic i{width:10px;height:10px;border-radius:50%;display:block}
.traffic i:nth-child(1){background:#ff5f57}
.traffic i:nth-child(2){background:#febc2e}
.traffic i:nth-child(3){background:#28c840}
.addr{flex:1;min-width:0;background:#fff;border:1px solid #d0ccc6;border-radius:6px;padding:4px 10px;font-size:11px;color:#6a6570;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.device .bezel{flex:1;background:#fff;overflow:hidden;position:relative;min-height:0}
.device[data-device="phone"] .bezel{border-radius:18px}
.device[data-device="ipad"] .bezel{border-radius:8px}
.device[data-device="desktop"] .bezel{border-radius:0 0 10px 10px;overflow:auto}
.device iframe{border:0;display:block;background:#f7f3ec;width:100%;height:100%}
.device-base{display:none}
/* glass side panel — overlays, does not push frame */
.phone-side{position:absolute;z-index:5;right:16px;top:16px;width:min(268px,calc(100vw - 32px));max-height:calc(100vh - 32px);overflow:auto;padding:12px 14px;display:flex;flex-direction:column;gap:9px;border-radius:14px;background:rgba(255,255,255,.42);backdrop-filter:blur(18px) saturate(1.25);-webkit-backdrop-filter:blur(18px) saturate(1.25);border:1px solid rgba(255,255,255,.5);box-shadow:0 12px 40px rgba(0,0,0,.14);pointer-events:auto}
.phone-side h2{margin:0;font-size:15px;color:var(--ink)}
.phone-side .sub{color:var(--muted);font-size:12px}
.phone-side label{font-size:11px;color:var(--muted);display:flex;flex-direction:column;gap:4px}
.phone-side select,.phone-side input{padding:8px;border:1px solid rgba(30,36,48,.14);border-radius:6px;background:rgba(255,255,255,.72);color:var(--ink)}
.phone-side .row{display:flex;gap:8px;flex-wrap:wrap}
.device-switch{display:flex;gap:6px;flex-wrap:wrap}
.device-switch .dev-btn{flex:1;min-width:72px;padding:8px 10px;border:1px solid rgba(30,36,48,.16);background:rgba(255,255,255,.65);color:var(--ink);border-radius:6px;font-size:13px}
.device-switch .dev-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}
.phone-side button.secondary{background:rgba(255,255,255,.7)}
@media(max-width:720px){
  .phone-side{right:10px;left:10px;top:auto;bottom:10px;width:auto;max-height:42vh}
  .device-stage{padding:12px 12px 46vh}
}
"""

PREVIEW_JS = r"""
async function boot(){
  const data = await (await fetch('preview-data.json')).json();
  const $ = (s,el=document)=>el.querySelector(s);
  const $$ = (s,el=document)=>[...el.querySelectorAll(s)];
  $('#proj').textContent = data.title + (data.title_en ? ' · ' + data.title_en : '');
  $('#meta').textContent = data.project + ' · ' + data.pages.length + ' 页 · 预览主题 ' + (data.style||'wabi') + ' · 点缩略图或「看效果」· 可切 手机/iPad/电脑';

  const kindOpts = data.kinds.map(k =>
    `<option value="${k.template}">${k.label} · ${k.kind}</option>`).join('');
  const batch = $('#batch-tpl');
  data.kinds.forEach(k=>{ const o=document.createElement('option'); o.value=k.template; o.textContent=k.label+' · '+k.kind; batch.appendChild(o); });

  const list = $('#list');
  const state = {};

  // desktop: magazine-friendly browser window (~1020), not stretched 1280
  const DEVICES = {
    phone:   {w:390,  h:844, pad:12, padBottom:12, chrome:0,  base:0, label:'手机 390×844'},
    ipad:    {w:768,  h:1024,pad:14, padBottom:14, chrome:0,  base:0, label:'iPad 768×1024（竖屏）'},
    desktop: {w:1020, h:780, pad:0,  padBottom:0,  chrome:38, base:0, label:'电脑 · 浏览器约 1020×780'},
  };
  function outerSize(d){
    return {w: d.w + d.pad * 2, h: d.h + d.pad + d.padBottom + d.chrome + d.base};
  }
  let currentDevice = 'phone';

  data.pages.forEach(p=>{
    state[p.key] = {template:p.template, note:p.note||'', origTpl:p.template, origNote:p.note||'', title:p.title, title_en:p.title_en||'', variants:p.variants||[]};
    const card = document.createElement('article');
    card.className = 'card';
    card.dataset.key = p.key;
    const thumbInner = p.thumb
      ? `<img class="thumb" src="${p.thumb}" alt="">`
      : `<div class="thumb ph">无缩略图<br>点右侧看效果</div>`;
    card.innerHTML = `
      <button type="button" class="thumb-wrap" data-open title="看效果">
        ${thumbInner}<span class="play">看效果</span>
      </button>
      <div class="info">
        <div class="row1">
          <span class="idx">#${p.key}</span>
          <span class="title"></span>
          <span class="en"></span>
          ${p.floor?`<span class="floor">${p.floor}</span>`:''}
        </div>
        <div class="fields">
          <label class="f">版式（会立刻反映到设备预览）
            <select class="tpl">${kindOpts}</select>
          </label>
          <label class="f">备注
            <input type="text" class="note" placeholder="为什么换 / 待补图…">
          </label>
          <button type="button" class="secondary open-btn">看效果</button>
        </div>
        <label class="check"><input type="checkbox" class="pick"> 批量选中</label>
      </div>`;
    card.querySelector('.title').textContent = p.title || '';
    card.querySelector('.en').textContent = p.title_en || '';
    card.querySelector('.tpl').value = p.template;
    card.querySelector('.note').value = p.note || '';
    const mark = ()=>{
      const st = state[p.key];
      st.template = card.querySelector('.tpl').value;
      st.note = card.querySelector('.note').value || '';
      card.classList.toggle('dirty', st.template !== st.origTpl || st.note !== st.origNote);
      if(modalKey === p.key) loadPhone(p.key);
    };
    card.querySelector('.tpl').addEventListener('change', mark);
    card.querySelector('.note').addEventListener('input', mark);
    card.querySelector('.thumb-wrap').onclick = ()=>openModal(p.key);
    card.querySelector('.open-btn').onclick = ()=>openModal(p.key);
    list.appendChild(card);
  });

  let modalKey = null;
  const modal = $('#modal');
  const frame = $('#phone-frame');
  const deviceEl = $('#device');
  const deviceFit = $('#device-fit');
  const deviceScale = $('#device-scale');
  const deviceStage = $('#device-stage');
  const sideTpl = $('#side-tpl');
  const sideNote = $('#side-note');
  const sideTitle = $('#side-title');
  const sideSub = $('#side-sub');
  const deviceHint = $('#device-hint');
  const addrText = $('#addr-text');

  function phoneUrl(key){
    const st = state[key];
    return `phone/slide-${key}.html?tpl=${encodeURIComponent(st.template)}`;
  }

  function applyDeviceChrome(){
    const d = DEVICES[currentDevice];
    const {w: outerW, h: outerH} = outerSize(d);
    deviceEl.dataset.device = currentDevice;
    deviceEl.setAttribute('aria-label', d.label);
    frame.style.width = d.w + 'px';
    frame.style.height = d.h + 'px';
    deviceEl.style.width = outerW + 'px';
    deviceEl.style.height = outerH + 'px';
    deviceScale.style.width = outerW + 'px';
    deviceScale.style.height = outerH + 'px';
    deviceHint.textContent = d.label + ' · 正式汇报同一套 CSS。电脑档为浏览器窗口（约杂志阅读宽度），避免拉成细长多列。';
    $$('.dev-btn').forEach(btn=>{
      btn.classList.toggle('active', btn.dataset.device === currentDevice);
    });
    fitDevice();
  }

  function fitDevice(){
    const d = DEVICES[currentDevice];
    const {w: outerW, h: outerH} = outerSize(d);
    const availW = Math.max(120, deviceStage.clientWidth - 24);
    const availH = Math.max(120, deviceStage.clientHeight - 24);
    const s = Math.min(1, availW / outerW, availH / outerH);
    deviceFit.style.width = Math.round(outerW * s) + 'px';
    deviceFit.style.height = Math.round(outerH * s) + 'px';
    deviceScale.style.transform = 'scale(' + s + ')';
  }

  function syncAddr(key){
    const st = state[key] || {};
    if(addrText) addrText.textContent = 'preview / #' + key + ' · ' + (st.title || 'slide');
  }

  function loadPhone(key){
    const st = state[key];
    sideTitle.textContent = `#${key} · ${st.title}`;
    sideSub.textContent = st.title_en || '';
    sideTpl.value = st.template;
    sideNote.value = st.note || '';
    syncAddr(key);
    applyDeviceChrome();
    const url = phoneUrl(key);
    if(frame.getAttribute('src') === url){
      try{ frame.contentWindow.location.reload(); }catch(e){ frame.src = url; }
    }else{
      frame.src = url;
    }
  }

  function setDevice(id){
    if(!DEVICES[id]) return;
    const changed = id !== currentDevice;
    currentDevice = id;
    applyDeviceChrome();
    if(modalKey && changed) loadPhone(modalKey);
  }

  function openModal(key){
    modalKey = key;
    sideTpl.innerHTML = kindOpts;
    modal.classList.add('open');
    applyDeviceChrome();
    loadPhone(key);
    requestAnimationFrame(()=>{ fitDevice(); requestAnimationFrame(fitDevice); });
  }
  function closeModal(){
    modal.classList.remove('open');
    modalKey = null;
    frame.src = 'about:blank';
  }
  $('#modal-close').onclick = closeModal;
  modal.addEventListener('click', e=>{ if(e.target === modal || e.target === deviceStage) closeModal(); });
  document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeModal(); });
  window.addEventListener('resize', ()=>{ if(modal.classList.contains('open')) fitDevice(); });

  $$('.dev-btn').forEach(btn=>{
    btn.addEventListener('click', ()=> setDevice(btn.dataset.device));
  });

  sideTpl.addEventListener('change', ()=>{
    if(!modalKey) return;
    state[modalKey].template = sideTpl.value;
    const card = $$(`.card[data-key="${modalKey}"]`)[0];
    if(card){ card.querySelector('.tpl').value = sideTpl.value; card.classList.add('dirty'); }
    loadPhone(modalKey);
  });
  sideNote.addEventListener('input', ()=>{
    if(!modalKey) return;
    state[modalKey].note = sideNote.value || '';
    const card = $$(`.card[data-key="${modalKey}"]`)[0];
    if(card){ card.querySelector('.note').value = sideNote.value; card.classList.add('dirty'); }
  });

  function collect(){
    const pages={}, notes={};
    Object.keys(state).forEach(k=>{ pages[k]=state[k].template; notes[k]=state[k].note||''; });
    return {pages, notes};
  }
  function toast(msg){
    const t=$('#toast'); t.textContent=msg; t.classList.add('show');
    setTimeout(()=>t.classList.remove('show'), 2200);
  }
  function download(name, text){
    const a=document.createElement('a');
    a.href=URL.createObjectURL(new Blob([text],{type:'application/json'}));
    a.download=name; a.click(); URL.revokeObjectURL(a.href);
  }

  $('#batch-apply').onclick = ()=>{
    const tpl = $('#batch-tpl').value; if(!tpl) return;
    let n=0;
    $$('.card').forEach(c=>{
      if(c.querySelector('.pick').checked){
        c.querySelector('.tpl').value = tpl;
        state[c.dataset.key].template = tpl;
        c.classList.add('dirty'); n++;
      }
    });
    if(modalKey) loadPhone(modalKey);
    toast(n?`已批量改 ${n} 页`:'先勾选要改的页');
  };
  $('#select-all').onclick = ()=> $$('.pick').forEach(x=>x.checked=true);
  $('#select-none').onclick = ()=> $$('.pick').forEach(x=>x.checked=false);

  async function save(){
    const {pages, notes} = collect();
    const body = {pages, notes, project: data.project};
    try{
      const r = await fetch('/__save', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      if(r.ok){ const j=await r.json(); toast('已写回 '+(j.overrides||'overrides.json')); return; }
    }catch(e){}
    const ov = {_说明:'由版式预览站导出', global:{}, pages:{}};
    Object.keys(pages).forEach(k=>{
      ov.pages[k]={template:pages[k]};
      if(notes[k]) ov.pages[k].preview_note=notes[k];
    });
    const conf = {confirmed_at:new Date().toISOString(), project:data.project,
      pages:Object.keys(pages).map(k=>({key:k,template:pages[k],note:notes[k]||''}))};
    download('overrides.json', JSON.stringify(ov,null,2));
    download('pages_confirmed.json', JSON.stringify(conf,null,2));
    toast('已下载 overrides.json + pages_confirmed.json');
  }
  $('#save').onclick = save;
}
boot();
"""

PREVIEW_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>版式预览确认</title>
<link rel="stylesheet" href="preview.css">
</head>
<body>
<header>
  <div>
    <h1 id="proj">版式预览</h1>
    <div class="meta" id="meta"></div>
  </div>
  <div class="actions">
    <button type="button" class="ok" id="save">保存 / 下载 overrides</button>
  </div>
</header>
<p class="hint">每一页都可以点缩略图或「看效果」，在设备框里看<strong>真实排版</strong>。可切换<strong>手机 / iPad / 电脑</strong>：电脑是浏览器窗口（杂志阅读宽度）。换版式会马上刷新。确认后点右上角保存。托管链接上保存会下载 JSON；本机 <code>--serve</code> 会直接写回工程。</p>
<div class="batch">
  <button type="button" class="secondary" id="select-all">全选</button>
  <button type="button" class="secondary" id="select-none">清空</button>
  <label>批量设为 <select id="batch-tpl"><option value="">—</option></select></label>
  <button type="button" id="batch-apply">应用到选中</button>
</div>
<div class="list" id="list"></div>

<div class="modal" id="modal" role="dialog" aria-modal="true">
  <div class="device-stage" id="device-stage">
    <div class="device-fit" id="device-fit">
      <div class="device-scale" id="device-scale">
        <div class="device" id="device" data-device="phone" aria-label="手机 390×844">
          <div class="device-chrome-top" aria-hidden="true">
            <div class="traffic"><i></i><i></i><i></i></div>
            <div class="addr" id="addr-text">preview</div>
          </div>
          <div class="bezel"><iframe id="phone-frame" title="slide preview"></iframe></div>
          <div class="device-base" aria-hidden="true"></div>
        </div>
      </div>
    </div>
  </div>
  <aside class="phone-side" aria-label="预览控制">
    <h2 id="side-title">预览</h2>
    <div class="sub" id="side-sub"></div>
    <div class="device-switch" role="group" aria-label="预览设备">
      <button type="button" class="dev-btn active" data-device="phone">手机</button>
      <button type="button" class="dev-btn" data-device="ipad">iPad</button>
      <button type="button" class="dev-btn" data-device="desktop">电脑</button>
    </div>
    <label>换版式（立即刷新）
      <select id="side-tpl"></select>
    </label>
    <label>备注
      <input type="text" id="side-note" placeholder="可选">
    </label>
    <div class="row">
      <button type="button" class="secondary" id="modal-close">关闭</button>
    </div>
    <p class="sub" id="device-hint">手机 390×844 · 正式汇报同一套 CSS。</p>
  </aside>
</div>

<div class="toast" id="toast"></div>
<script src="preview.js"></script>
</body>
</html>
"""


class PreviewHandler(http.server.SimpleHTTPRequestHandler):
    project = ''
    work = None

    def log_message(self, *a):
        pass

    def do_POST(self):
        if self.path.rstrip('/') != '/__save':
            self.send_error(404); return
        n = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw.decode('utf-8'))
        except Exception:
            self.send_error(400, 'bad json'); return
        pages = body.get('pages') or {}
        notes = body.get('notes') or {}
        ov, conf = merge_overrides(self.work, pages, notes, {'source': 'preview-serve'})
        cfg = load_cfg(self.project)
        apply_overrides_to_config(cfg, self.work)
        (self.work / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
        data = json.dumps({'ok': True, 'overrides': str(ov), 'confirmed': str(conf)}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(project: str, dest: Path, port: int = 0):
    PreviewHandler.project = project
    PreviewHandler.work = work_dir(project)

    def factory(*args, **kwargs):
        return PreviewHandler(*args, directory=str(dest), **kwargs)

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), factory)
    _host, pnum = srv.server_address
    print(f'本机预览 http://127.0.0.1:{pnum}/  （Save 写回 work/{project}/）')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')


def main():
    ap = argparse.ArgumentParser(description='版式预览确认')
    ap.add_argument('--project', required=True)
    ap.add_argument('--out', help='默认 out/<project>-preview')
    ap.add_argument('--serve', action='store_true')
    ap.add_argument('--port', type=int, default=0)
    ap.add_argument('--apply', help='合并 overrides.json 到 work/<项目>/')
    a = ap.parse_args()

    if a.apply:
        work = work_dir(a.project)
        data = json.loads(Path(a.apply).read_text(encoding='utf-8'))
        if 'pages' not in data:
            raise SystemExit('无法识别的 overrides 格式')
        dst = work / 'overrides.json'
        cur = json.loads(dst.read_text(encoding='utf-8')) if dst.exists() else {'_说明': '', 'global': {}, 'pages': {}}
        cur.setdefault('pages', {}); cur.setdefault('global', {})
        for k, v in (data.get('global') or {}).items():
            cur['global'][k] = v
        for k, v in (data.get('pages') or {}).items():
            slot = cur['pages'].setdefault(str(k), {})
            if isinstance(v, dict):
                slot.update(v)
            else:
                slot['template'] = v
        dst.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding='utf-8')
        pages = {k: (v.get('template') if isinstance(v, dict) else v) for k, v in data['pages'].items()}
        notes = {k: (v.get('preview_note') or '') for k, v in data['pages'].items() if isinstance(v, dict)}
        merge_overrides(work, {k: v for k, v in pages.items() if v}, notes, {'source': 'preview-apply'})
        cfg = apply_overrides_to_config(load_cfg(a.project), work)
        (work / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
        print('已合并到', dst)
        return

    dest = build_preview(a.project, Path(a.out) if a.out else None)
    if a.serve:
        serve(a.project, dest, a.port)


if __name__ == '__main__':
    main()
