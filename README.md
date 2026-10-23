# 方案汇报网页生成器

> 本仓库为开源脱敏版（对应 GitHub：`fengfenglab/desgin-report`）。
> `brands/default` 与示例工程不含真实工作室/客户信息；请复制 `brands/default` 填入自己的品牌后再用于正式项目。
> 示例：`work/formal-template`（正式章节模板）、`work/demo-templates`（版式演示），图片与文案均为占位/虚构。


把方案 PPT / PDF 变成**手机优先**的汇报网页：客户在微信里点开链接，一页一页上滑看完整的设计思路。
代码全部自己写（Python + 原生 JS，没有 React，也不依赖任何第三方前端包）。只借鉴了「提取 → 套版式 → 配置 → 构建」这个流程的思路。

## 效果
- 竖屏整页上滑翻页（scroll-snap）；底部一条细线，左边是章节/房间名（如「叁 · 客厅 · LIVING ROOM」），右边页码 12/38；右上角「目录」
- 第 2 页自动生成目录页（壹贰叁肆 + 中文章节名 + 小号英文，点击跳转），章节页和底部细条用同一套编号
- 意向图/选品/效果图页右上角有小平面图，用点缀色圆点标出当前房间，点开看大图
- 平面图页带编号圆点和房间列表；两种模式：概念提案（点编号只高亮圆点）/ 效果图汇报（点圆点或列表跳到该房间的效果图页）
- 结尾页可放微信二维码（不受长按保护，微信里长按可以识别）；电话、微信号、地址、二维码没填的一律不显示
- 点任意图片看大图，可以左右滑动切换；双指或双击放大，平面图可以拖动看细节
- 平面图页带楼层切换按钮（B1F / 1F / 2F / 3F）
- 四套风格可切换（见下文），中英双语标题，留白多，不对称拼图，带色卡（从页面图片里自动取色）
- 电脑上打开会自动换成横版布局，可以用方向键翻页
- 轻度防复制：禁右键、长按存图、选中文字、拖拽、打印
- 默认 `noindex`，不会被搜索引擎收录

## 目录结构
```
desgin-report/
├─ tools/
│  ├─ extract.py    第 1 步：从 PPTX/PDF 提取文字、图片（保留 PPT 里的裁切）和整页渲染图
│  ├─ classify.py   第 2 步：自动给每页匹配版式，生成可以手改的 config.json
│  ├─ build.py      第 3 步：把 config.json 构建成静态网站
│  ├─ brand.py      读取品牌配置 brands/<品牌>/brand.json
│  ├─ shoot.py      检查：用 Chrome 截手机和电脑效果图，报告控制台错误
│  ├─ shoot_pages.py 截指定页：shoot_pages.py <out下目录> 1,2,25 <前缀>
│  └─ compose.py    把截图拼成对比图
├─ templates/
│  ├─ theme.css     样式（颜色、字体、各版式）
│  ├─ app.js        交互（翻页、目录、看大图、防复制）
│  └─ glossary.json 中文标题 → 英文副标题对照表（可以自己补词）
├─ brands/<品牌>/  品牌配置（工作室名、联系方式、二维码、logo、印章、字体、点缀色）
├─ work/<项目>/     中间文件：raw.json、media/、render/、config.json、overrides.json
├─ out/<项目>/      构建好的网站，整个文件夹上传就能用
└─ shots/           效果截图
```

## 使用步骤
一键运行：`./run.sh 方案.pptx 项目代号 [已导出的.pdf]`（依次执行下面第 1–3 步）。

需要 python3 和这几个库：python-pptx、Pillow、pymupdf、fonttools、brotli。PPTX 输入还需要 LibreOffice。

```bash
cd desgin-report
# 1) 提取（PPTX 会先用 LibreOffice 转 PDF 来生成整页图；已有 PDF 可以用 --pdf 指定，省时间）
python3 tools/extract.py 方案.pptx --project my-project [--pdf 方案.pdf]
# 2) 自动套版式
python3 tools/classify.py --project my-project        # 已有 config 不会覆盖；要重来加 --force
# 3) 版式预览确认（正式构建前必做）
python3 tools/preview.py --project my-project         # → out/my-project-preview/
python3 tools/preview.py --project my-project --serve # 本机打开，Save 直接写回 overrides.json
# 4) 构建
python3 tools/build.py --project my-project --lite    # 轻量版（约 9MB），适合免费托管
python3 tools/build.py --project my-project --out out/my-project-hd   # 高清版（图片多出一档大图）
# 5) 检查截图（需本机装好 playwright + Chrome）
python3 tools/shoot.py out/my-project
```

## 版式（template）
| 版式 | 用途 | 自动识别规则（大致） |
|---|---|---|
| cover | 封面：大图背景，竖排项目名 | 第 1 页 |
| section | 章节页：上图下文，章节号，引语 | 有大引号「“」或大号英文标题、图少 |
| concept | 理念关键词：三张圆图三角排布 | 有 2 张以上圆形图片 |
| split | 图文分栏：图 + 编号要点 | 1 张图 + 较多文字 |
| plan | 平面图：可放大，楼层切换 | 1 张大图且标题含 方案/平面/xF 等 |
| full | 满版大图 | 1 张大图、文字很少 |
| grid | 不对称拼图（2–8 张，超出的放进看大图）；竖长截图自动变成左右滑动条 | 多张图 |
| material | 材料 / 专项：图 + 说明 + 取色 | 标题含 专项/材料/材质/工艺/系统 |
| text | 纯文字页 | 没有图片 |
| about | 结尾：Thank you、品牌、联系方式、微信二维码 | 最后一页或含 THANK YOU |
| contents | 目录：壹贰叁肆 + 章节名 + 英文，点击跳转 | 自动插在封面后（章节 ≥2 时）；`"contents": false` 关闭 |
| selection | 选品页：房间标题 + 角标平面图；每项彩色图、名称、细线、品牌 / 标准品或定制 / 尺寸；待定项一个小点 +「待定」 | 不自动识别，手动配置 |
| strategy | 策略页：最多 3 个编号问题，下面竖排 原方案 → 策略关键词 → 调整方案，细箭头连接 | 手动配置 |
| persona | 需求回应：3–4 条「您说的 → 我们这样做」 | 手动配置 |
| studio | 关于我们：工作室图 + 设计师 + 介绍 + 荣誉 | 手动配置（内容可放 brand.json about） |
| issues | 户型分析：原始平面 + 图上编号 + ①②③ 问题 + 现场照片 | 手动配置 |
| goals | 设计目标：每层一条 | 手动配置 |
| swipe | 单页左右滑动：功能分区/动线/视线/收纳、方案一二三、剖面 | 手动配置 |
| vertical | 垂直交通：楼层剖切示意 + 楼梯/电梯/挑空/采光井 | 手动配置 |
| render | 效果图 + 细节卡：上 60% 效果图，下面英文（拉开字距）+ 中文空间名、一张细节特写、一句说明 | 手动配置 |

后 4 种版式的字段（写在 config.json 对应页里，或写进 overrides.json）：
```jsonc
// selection
{"template":"selection","title":"客厅选品","title_en":"Living Room · Selection","room":"客厅","cols":2,
 "items":[{"name":"模块沙发","name_en":"Modular Sofa","brand":"品牌","kind":"定制","size":"3200×1050×680",
           "pending":true,"note":"可选一句备注","image":{"src":"media/sofa.jpg","w":1200,"h":900}}]}
// strategy
{"template":"strategy","title":"动线策略","problems":["问题一","问题二","问题三"],
 "before":{"image":{...},"label":"原方案","label_en":"Original"},"keyword":"借光","keyword_en":"Borrowed Light",
 "after":{"image":{...},"label":"调整方案","label_en":"Revised"}}
// persona（images 可选，放一张做顶部横条）
{"template":"persona","title":"需求与回应","needs":[{"need":"客户原话","response":"我们的做法"}]}
// render（images[0] 效果图，images[1] 细节特写）
{"template":"render","title":"西厨","title_en":"Western Kitchen","images":[{...},{...}],"caption":"一句说明"}
```
任何页都可以加 `"badge": "示例数据 · EXAMPLE DATA"` 显示一个虚线小标签。

### 平面图编号（rooms）和两种模式（plan_mode）
- 每张平面图页的 `rooms`：`[{"n":1,"name":"客厅","x":52,"y":40,"page":null,"check":true}]`
  - `n` 编号，`name` 房间名（只用图纸上真实出现的名字）
  - `x` / `y`：圆点位置，占**图片本身**宽、高的百分比（左上角 0,0，右下角 100,100）
  - `check: true`：位置是估的默认值，待设计师确认（坐标模式里显示为虚线圈）；确认后删掉这一项
  - `page`：只在 render 模式下用，填 PPT 页码就跳到那一页；不填则自动跳到 `room` 相同的页（优先 render 效果图页，其次 selection，再其次任意填了 room 的页）
- **改坐标最省事的办法：坐标模式**。构建后打开 `index.html?edit`（本地或托管链接都行，后面加 `?edit`），翻到平面图页，点房间中心，顶部会显示 `PPT 第 5 页 "x": 41.2, "y": 27.5`，把这两个数抄进 `rooms`（建议写在 `overrides.json` 的 `pages.<页码>.rooms`），再重新 build。坐标模式下点图不会放大、防复制关闭，正常链接不受影响。
- 模式：config.json 顶部 `"plan_mode": "concept"`（默认，概念提案：编号圆点 + 列表，点了只高亮，不跳转）或 `"render"`（效果图汇报：圆点变实心，点圆点或列表跳到该房间的效果图页）。单张平面图页也可以单独写 `plan_mode`；构建时 `--plan-mode render` 临时覆盖。

### 角标平面图（room）
- 意向图 / 效果图 / 选品页右上角的小平面图，**只在这一页填了 `room` 时才显示**，`room` 填平面图 rooms 里的房间名，比如 `"room": "客厅"`。也可以写列表 `"room": ["上花园", "下花园"]`，角标上同时标出（取包含房间最多的那张平面图；平面图里没有的名字会在终端提示并跳过）。不填或填空字符串就不显示，不会自动猜（比如「花园意向」可能是 B1F 下花园，也可能是 1F 入户花园，由设计师决定）。
- 构建时终端会列出「[待填 room]」提示：标题里出现了房间名但还没填 room 的页。
- 同一个房间名出现在几张平面图上时，用 `"locator": {"plan": 6, "room": "门厅"}` 指定哪一张（plan 是平面图页的 PPT 页码）；`"locator": false` 强制不显示。
- **底部细条文字**：默认取 room，否则取章节名；可以用页面的 `chapter` 字段改。

## 版式预览确认（preview）
正式 build 前必须先过一遍交互预览，避免版式认错。工具：`tools/preview.py`。

1. `python3 tools/preview.py --project <代号>` → 生成 `out/<代号>-preview/`（缩略图 +「看效果」手机框真页 + 下拉即时换版式 + 备注；可批量改）。
2. 本机确认：`--serve`，点「保存」会写 `work/<代号>/overrides.json` 和 `pages_confirmed.json`，并更新 config 里的 `template`。
3. 远程确认（flypod）：对方在网页上改完点保存 → **下载**两个 JSON，交给代理用 `python3 tools/preview.py --project <代号> --apply overrides.json` 合并，再 build。
4. `build.py` 会自动套用 `overrides.json`；若还没有 `pages_confirmed.json` 会打印提示（`--skip-preview-check` 可关掉）。

版式对照（预览 kind ↔ 我们的 template；murmur 列仅思路对照，不共用代码）见 `templates/layouts.json`：

| 预览 kind | template | 用途 | murmur 对照 |
|---|---|---|---|
| cover | cover | 封面 | cover |
| text-center | text | 引言 / 纯文字 | text-center |
| section | section | 章节页 | — |
| split | split | 图文分栏 | split |
| image-full | full | 满版大图 | image-full |
| image-grid | grid | 拼图 / 平面意向 | image-grid |
| image-draw | issues | 分析图 + 说明面板（占位，无玻璃拟态） | image-draw |
| plan / swipe / vertical | 同名 | 平面编号、左右对照、垂直交通 | — |
| about / studio | 同名 | 结尾 / 关于我们 | about |

杂志四套主题（wabi/zen/mono/french）只在正式 `build.py --theme` 时生效；预览站是中性编辑界面。不做角标裁切线、不做 GSAP。

## 正式汇报模板（章节骨架）
正式方案汇报统一按下面的顺序排。每一章都是可选的：某章没有内容（或者整章都被 `hidden`）就自动隐藏，目录和章节号会顺延重排。
示例工程：`python3 tools/make_sample.py` 生成 `work/formal-template`（4 层别墅，全部是**示例数据 + 合成示意图**，不含任何真实项目内容），再 `python3 tools/build.py --project formal-template --lite --theme wabi --out out/formal-template-wabi`。新项目照着它的 config.json 填即可。

| 顺序 | 章节 | 用到的版式 | 按楼层？ |
|---|---|---|---|
| — | 封面 | cover | |
| — | 目录 | contents（自动生成；别墅会在章节下列出楼层小标签，点了直接跳到那一层） | |
| — | 关于我们 | studio（内容默认取 brand.json 的 `about`，页里写了就覆盖） | |
| 壹 | 项目现场 | section + grid（现场照片） | |
| 贰 | 概念解读 | section + concept（关键词）+ grid（意向氛围，彩色） | |
| 叁 | 户型分析 | section + 每层一页 issues（原始平面 + ①②③ 问题 + 现场照片） | 是 |
| 肆 | 设计目标 | section + goals（每层一条目标） | 是 |
| 伍 | 平面布局 | section + 每层 plan，可在某层后面插 swipe（功能分区 / 动线 / 视线 / 收纳，或 方案一/二/三） | 是 |
| 陆 | 垂直交通 | section + vertical（单独一页）+ 可选 swipe（剖面 A-A / B-B） | |
| 柒 | 平面意向 | section + 每个房间一页 grid / render，填 `room` 显示角标平面图 | 按房间 |
| 捌 | 专项 | section + material（绿植、灯光、防水排水、智能化……可以继续加） | |
| — | 结尾 | about（Thank you + 联系方式 + 微信二维码） | |

章节由 `section` 页开头，后面的页都归这一章，直到下一个 section。不需要的章节：删掉 section 和它后面的页，或给它们写 `"hidden": true`。

### 楼层（别墅）
- config.json 顶部写 `"floors": [{"id":"B1F","name":"花园层"},{"id":"1F","name":"入户层"},...]`（从下往上）。平层项目不写 floors、页面不写 floor 就行。
- 按楼层的页写 `"floor": "1F"`。页眉显示「1F · 入户层」，底部细条带楼层；同一章里的平面图自动按 B1F→1F→2F→3F 排成楼层切换标签。
- 某层没有内容（没有图、没有问题、没有目标）就不出那一层的页，目录里也不出那层的小标签。
- 房间编号每层各自从 1 开始（写在该层 plan 的 `rooms` 里）。
- 角标平面图跨楼层：`"room": "1F·老人房"`（指定楼层），或 `"room": ["上花园","下花园"]`（不在同一层也可以，角标上下叠放两层的小平面图，各自标出）。不写楼层前缀时按房间名在所有楼层里找。

### 新版式字段
```jsonc
// studio 关于我们（不写 body 时用 brand.json 的 about；两边都空则整页不显示）
{"template":"studio","images":[{...}],"name":"设计师姓名","role":"创始人","body":["介绍…"],"items":["荣誉 / 经历"]}
// issues 户型分析（每层一页）：images[0] 原始平面；points 是问题编号在图上的位置（% 坐标，可用 ?edit 读）；photos 最多 3 张现场照片
{"template":"issues","floor":"B1F","title":"户型分析 · B1F","images":[{...}],
 "points":[{"n":1,"x":35.6,"y":35.2}],"problems":["采光不足","花园不连通"],"photos":[{...}]}
// goals 设计目标：每层一条，顺序照写
{"template":"goals","title":"设计目标","goals":[{"floor":"3F","title":"主人套房","text":"一句说明"}]}
// swipe 单页左右滑动：上面是标签，下面是小圆点；手指左右滑、点标签都能切换
{"template":"swipe","floor":"B1F","title":"B1F 平面分析","slides":[
  {"label":"功能分区","image":{...},"legend":[{"color":"#d6c4a0","label":"公共区"}],"caption":"一句说明"},
  {"label":"动线","image":{...},"notes":["要点一","要点二"]}]}
// vertical 垂直交通：floors 从上往下（不写就用顶部 floors 倒序）；cores 是贯穿楼层的竖向元素
// type: stair 楼梯（斜线）/ lift 电梯（点缀色）/ void 挑空（虚线）/ light 采光井（渐变）；x、w 是横向位置和宽度（%）
{"template":"vertical","title":"垂直交通","floors":[{"id":"3F","name":"主人层","level":"+9.60"}],
 "cores":[{"n":1,"name":"楼梯","type":"stair","x":34,"w":13,"from":"B1F","to":"3F","note":"一句说明"}],
 "images":[{...}]}   // images 可选：有真实剖面/轴测图时放在示意图下面
```
任何页都可以加 `"badge": "示例数据 · EXAMPLE DATA"`。示例工程里所有页都带这个标签，正式项目不要带。

### 填一个新项目的顺序
1. 复制 `work/formal-template/config.json` 到 `work/<代号>/`，改顶部的 `title`、`floors`、`brand`（默认 `default`；自建品牌写你的目录名）。
2. 把真实图片放进 `work/<代号>/media/`，逐页替换 `images` / `photos` / `slides[].image`（`w`、`h` 填图片真实像素）。
3. 删掉不需要的章节、楼层页、示例 badge 和「示例：」开头的文字；文字只写原稿里真实有的。
4. 平面图 rooms、户型分析 points 的坐标：build 后打开 `index.html?edit` 点图读坐标，写回去。
5. 平面意向页逐页填 `room`（不确定是哪个房间就问设计师，不猜）。
6. build → 截图验收（ERRORS: none）。

## 风格（--theme）
同一套版式，有四种视觉风格可以切换：`python3 tools/build.py --project <代号> --lite --theme zen|wabi|mono|french [--accent #26375f]`
（也可以在 config.json 里写 `"style": "zen"`；法式风格的点缀色可以用 `"theme_accent"` 或 `--accent` 改）。
| 代号 | 风格 | 特点 |
|---|---|---|
| zen | 新中式禅意 | 暖灰细灰泥肌理 + 极淡的模糊窗光（程序生成，约 14KB，认不出具体形状）；宋体竖排标题配细竖线；左侧小圆点章节导航；图片排成竖条；一点朱砂红 |
| wabi | 侘寂木质（默认） | 米白浅灰底配深咖色块；图片满版出血；三色条；字距拉开的衬线大写英文 |
| mono | 黑白极简 | 纯白底、小黑方块标记、大号无衬线英文、竖排英文副标题、大量留白；图片保留彩色（只轻微降饱和），黑白感靠版式 |
| french | 法式杂志 | 奶油白底配单一点缀色（默认藏青）；正体加斜体的英文标题，用细线连接；主图大而居中，小图不对称排布；直角图片外加一圈细线框（留一点空隙，像画框卡纸） |
各风格的样式在 `templates/themes/<代号>.css`，字体配置在 `templates/themes/themes.json`。字体都是 OFL 开源可商用，构建时只截取用到的字。
样张截图：`tools/shoot_themes.py`，对比图在 `shots/themes-compare-v2.png`；新功能对比图 `shots/features-v2.png`、`shots/features-v3.png`。
版式演示项目（全是示例数据）：`work/demo-templates`，`python3 tools/build.py --project demo-templates --lite --theme wabi --out out/demo-wabi`。

## 手动调整
- **改单页**：直接编辑 `work/<项目>/config.json`，改完重新运行 build.py 就行。常用字段：
  `template`（换版式）、`title` / `title_en` / `subtitle` / `body` / `quote`、`images`（调顺序或删图）、
  `items`（理念页和专项页的条目）、`hidden: true`（不显示这一页）、`palette`（色卡开关）、`layout: "strip" | "grid"`（拼图页强制成滑动条或拼图）。
- **想重新自动识别又不丢手改**：把改动写进 `work/<项目>/overrides.json`（按 PPT 页码），
  `classify.py --force` 重新生成时会自动套上。
- **全局信息**：工作室名称、联系方式、二维码等放在品牌配置里（见下一节）。项目 config.json 里填了同名字段（`contact`、`studio` 等）会覆盖品牌配置，只对这个项目生效；`designer`、`date` 写在项目里。
- **配色**：改 config.json 里的 `theme`（bg 底色 / panel 色块 / ink 文字 / muted 次要文字 / line 细线 / accent 点缀色）。
- **英文副标题**：自动翻译只查 `templates/glossary.json`，查不到就留空。常用词补进去，以后的项目都能用。

## 品牌配置 brand.json
模板和代码里没有写死任何工作室信息，所有品牌相关的内容都在 `brands/<品牌>/brand.json`：
```jsonc
{
 "studio": "工作室中文名", "studio_en": "Studio Name",
 "aliases": ["STUDIO NAME INTERIOR DESIGN"],   // PPT 页面上出现这些署名文字时，提取时会去掉
 "report_name": "设计方案汇报", "report_name_en": "Design Proposal",
 "contact": {"phone": "", "wechat": "", "address": "", "note": ""},
 "qr": "qr.png",          // 结尾页微信二维码（相对品牌目录）；空着就不显示；写 "placeholder" 可预览一张「占位」图
 "logo": "logo.svg",      // 左上角 logo；不填就显示文字名称
 "seal": "印章",           // 禅意封面的印章文字；或用 "seal_image": "seal.png"
 "footer": "© 2026 工作室", // 封面底部细条和结尾页的小字
 "theme": "wabi",         // 默认风格
 "accent": "#26375f",     // 点缀色
 "theme_vars": {"wabi": {"bg": "#f4f1ec"}},     // 按风格覆盖颜色变量（bg/panel/ink/muted/line/accent）
 "fonts": {"XF Serif": "/path/字体.ttf", "XF Latin": "cormorant", "XF Latin Italic": "/path/Italic.ttf"}
}
```
- 用哪个品牌：项目 config.json 里写 `"brand": "default"`（或你的品牌目录名），或者构建时 `--brand <目录名或路径>`，或者环境变量 `XF_BRAND`；都没有就用 `brands/default`。classify.py 也接受 `--brand`。
- 字体：`fonts` 按字体角色替换（XF Serif 中文标题、XF Latin 英文衬线、XF Caps 大写标题、XF Grotesk 无衬线；斜体在名称后加 ` Italic`），值可以是内置代号或字体文件路径（.ttc 写 `路径#序号`）。请只用允许商用和网页嵌入的字体。
- `brands/default`（开源示例）里电话、地址、微信号、二维码、关于我们全部留空；复制该目录改名即可换成自己的工作室。
- 新建品牌：复制 `brands/default` 改名，改里面的值，把图片放进同一目录。
- `about` 也可分两部分：`{"career_start_year":2015,"studio":{title,title_en,tagline,image,heading,heading_en,body},"designer":{title,title_en,image,body,items_label,items}}`，页里写 `{"template":"studio","part":"studio"|"designer"}`；文字里 `{years}` 自动换成 当年−career_start_year；image 相对品牌目录。
- `about`（旧单页写法）：「关于我们」页内容 `{"title","title_en","name","role","body":[段落],"items":[荣誉/经历]}`，所有项目共用；全空时这一页不显示。

### 单文件版（双击打开）
`python3 tools/inline.py out/<项目> out/<文件名>.html`：把 CSS、JS、字体、二维码和全部图片打包进一个 .html，发给对方后双击就能在 Chrome 里打开，不需要服务器。同一张图只存一份，`--lite` 构建的项目一般在 15 MB 以内（超过 25 MB 会提示）。



## 链接擦除（link_wipe）
正式汇报默认开启：页顶一条与背景同色的细带，弱化地址栏长链接的突兀感，不影响上下翻页。关闭：在 `work/<项目>/config.json` 设 `"link_wipe": false` 后重新 build。

## 托管
`out/<项目>/` 是纯静态文件夹，传到任何静态托管都能用（以后可以放进小程序的客户项目页 web-view）。
- 免账号临时托管：`npx flypod out/<项目>`，限制是 10MB、200 个文件，**14 天后过期**；运行 `flypod login` 登录后就永久保留。
- 正式使用建议换成国内可备案的对象存储 + CDN，或者放进小程序。

## 注意
- 文字照搬 PPT 原文，不改写。只有英文副标题会自动翻译，翻译不出来的地方留空。
- PPT 里的 EMF/WMF 矢量图解不开，会跳过；遇到这种页，在 config 里把 `template` 改成 `text`，配上整页渲染图（`render/pNN.jpg`）。
- 字体：中文标题用 Noto Serif SC，英文用 Cormorant Garamond / Marcellus / Jost，都是 OFL 开源字体。构建时会只截取页面上用到的字，大约 190KB。
- 结尾页二维码不受防复制限制（否则微信长按识别不了）。电话、微信号、地址、备注、二维码、footer 任何一项为空就整项不显示，不会留空框。
- 示例数据只放在 `work/demo-templates`，不要混进客户项目。

## 跨设备不裁切检查（tools/nocrop.py）
`python tools/nocrop.py <out/项目 或 线上网址> [--shots 23,29] [--only hw-360]`：iPhone WebKit 390×844、390×664（微信），安卓 Chromium 微信 XWEB / 华为浏览器 UA 360×780、393×851、412×915、360×640，DPR 3。逐页逐图比较原始比例和实际显示（object-fit:cover 和祖先 overflow 裁切都算），封面/章节/结尾满版背景除外。有裁切退出码 1。
手机端规则（theme.css 末尾）：内容图一律按原比例完整显示（页面可上下滚动）；WebKit 下 aspect-ratio + 负边距、height:100% 的两个坑已绕开；样式/脚本链接带 ?v=内容哈希防微信缓存。电脑版不受影响。
