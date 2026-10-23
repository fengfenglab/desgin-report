---
name: design-report-web
description: >-
  用这个 skill 的时机：要把室内/建筑方案（排好的 PPT/PDF，或意向图加概念）做成手机优先的客户汇报网页，替换底图和意向图，然后托管成链接发给客户。适用于 Cursor、WorkBuddy 等能读 SKILL.md 并跑本地脚本的智能体。
---

# 方案汇报网页（手机优先）

本仓库是生成器本体（见根目录 `README.md`）。智能体按本 skill 执行；不要改用户没确认的版式与文案。

## 安装（给使用者）

把本仓库放到智能体能访问的目录后，按平台装 skill：

| 平台 | 怎么装 |
|------|--------|
| **Cursor** | clone 本仓；把本文件复制到项目 `.cursor/skills/design-report-web/SKILL.md`，或整仓作为工作区打开后让 Agent 读取根目录 `SKILL.md` |
| **WorkBuddy** | 在「添加技能 / 导入 skill」里选本仓库或本文件；工作目录指向 clone 下来的仓库根 |
| **Grok Bot 等** | 若支持 Bot 模板或自定义 skill，导入本 `SKILL.md`，并把生成器路径指到本仓 |
| **ChatGPT / 纯网页 GPT** | **不能直接跑本仓库脚本**。可把本 skill + README 贴进自定义 GPT 当说明书，指导用户在本机终端执行下面命令；要一键出链接需另做网页托管服务 |

依赖见 README：`python3`、python-pptx、Pillow、pymupdf、fonttools、brotli；PPTX 还需 LibreOffice。

首次使用：复制 `brands/default` 为 `brands/<你的品牌>`，填写 `brand.json`（电话、微信、地址、二维码没填的不会显示）。

## 两种输入

- **排好的 PDF/PPT**（正式汇报）：原样转换，文字不改。
- **意向图加概念**（前期沟通）：先起草汇报文案和页面顺序，发给用户确认后再构建。不要编造设计理由。

## 每个项目都要换图

用户会提供新的底图和意向图。动手前先确认每张图放哪一页、哪个位置，对不上的要问。替换写入 `work/<代号>/overrides.json`，原图放入 `work/<代号>/media/`。

## 步骤（在仓库根目录执行）

1. 定项目代号（拼音），把源文件或图片放到本机/工作区。
2. 提取：`python3 tools/extract.py <源文件> --project <代号> [--pdf 已导出.pdf]`
3. 套版式：`python3 tools/classify.py --project <代号>`，检查打印表格。已有 config 不会覆盖；重来加 `--force`。
4. 版式预览（必做）：`python3 tools/preview.py --project <代号>` → `out/<代号>-preview/`。本机可加 `--serve`，Save 写回 overrides。对照 `templates/layouts.json`。
5. 人工检查，改动只写 `overrides.json`，重点：关键词与图配对、图注、平面图页、模板占位字、英文副标题。
6. 构建：`python3 tools/build.py --project <代号> --lite`（轻量）。高清去掉 `--lite` 并加 `--out out/<代号>-hd`。也可一键：`./run.sh 方案.pptx <代号> [方案.pdf]`。
7. 验收：`python3 tools/shoot.py out/<代号>`（需本机 Chrome / playwright）。无报错、无裂图、无空白页；手机与电脑截图都要看。有 nocrop 检查时按仓库文档跑多端 WebKit/Chromium。
8. 托管：把整个 `out/<代号>/` 上传到任意静态托管（或 `npx -y flypod out/<代号>` 等临时链接）。长期建议国内 OSS/CDN 或自有客户页。
9. 交付：发链接 + 2–3 张手机截图，说明取舍，提醒用户在微信里点开测一遍。

## 风格约定（默认不要擅自改）

- 暖灰底、大量留白、细线、色卡圆点、不对称拼图
- 中英双语标题；四套主题 zen / wabi（默认）/ mono / french，由 brand 或构建参数选择
- 默认防复制与 `noindex`
- 封面 / 章节 / 结尾全屏背景可用 cover；其余内容图不要裁切（contain）

## 开源注意

- 示例工程与 `brands/default` 不含真实工作室/客户信息；正式项目请用自己的品牌目录
- 不要把客户原图、未脱敏的 `brands/`、真实联系方式推进公开 fork
