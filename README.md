# NotebookLM PPT Skill

把 NotebookLM 导出的图片型 PDF、PPTX 或幻灯片截图交给 AI 助手，调用本地 **NotebookLM PPT Editor**，生成可编辑文字的 PowerPoint，并保留质量检查提示。

> **v0.1.0 公开测试版 · 需要单独安装转换引擎。**
> 只想在窗口里转换文件？请直接使用 [NotebookLM PPT Editor 桌面 App](https://github.com/taomin8879/notebooklm-ppt-editor)，无需安装本 Skill。
> 本仓库只包含 Skill 和调用脚本，不是完整转换软件，不包含桌面 App、OCR 模型或 API Key。与 Google / NotebookLM 无官方关联。

## 适合做什么

- 把已有图片型演示文稿恢复为可编辑文字的 PPTX。
- 默认采用本地处理；可由用户明确选择 DeepSeek 在线增强。
- 先试转单页，再转换全篇；可以指定页码和输出目录。
- 将“通过”“可用但有提醒”“需修正”原样交给用户，不把生成文件等同于完全还原。

**不承诺：** 100% 还原、全部图形可编辑、字体完全一致。复杂图形、背景和部分文字区域可能仍以图片保留。最终交付前应人工对照源页。

## 使用条件

| 项目 | 要求 |
| --- | --- |
| 电脑 | Apple 芯片 Mac，macOS 13 或更新 |
| 转换引擎 | 完整 `NotebookLM PPT Editor.app`，build 185+，[下载公开测试版](https://github.com/taomin8879/notebooklm-ppt-editor#下载) |
| 其他依赖 | Python 3.9+、LibreOffice |
| 助手 | 能加载 `SKILL.md` 并执行本地命令的环境 |
| API | 默认不需要；在线增强需用户自己的 API 配置 |

目前不支持 Windows、Linux、Intel Mac 的转换，也不支持仅在网页聊天中安装后直接运行。已验证的是 macOS 上的脚本调用；不同助手对 Skill 的发现和权限管理可能不同。

## 快速开始

### 1. 获取 Skill

从 [Releases](https://github.com/taomin8879/notebooklm-ppt-skill/releases) 下载 `notebooklm-ppt-skill-v0.1.0.zip`，解压得到 `notebooklm-ppt` 文件夹。或者克隆：

```bash
git clone https://github.com/taomin8879/notebooklm-ppt-skill.git
cd notebooklm-ppt-skill/skills/notebooklm-ppt
```

不要只复制 `SKILL.md`，需要一起保留 `scripts/`、`references/` 和 `agents/`。

### 2. 准备引擎

已安装用户可以直接指定 `.app` 路径。尚未安装的用户，请从 [App 发布页](https://github.com/taomin8879/notebooklm-ppt-editor/releases/tag/v0.1.0-build186-public1) 下载完整测试包。该包仅支持 Apple 芯片 Mac、macOS 13+，需另装 LibreOffice，尚未 Apple 公证。请先阅读 [安装说明](https://github.com/taomin8879/notebooklm-ppt-editor/blob/main/docs/INSTALL.zh-CN.md)。本 Skill 仓库不包含 App，也不提供支付或授权激活服务。

确保 LibreOffice 可正常启动。在解压后的 Skill 目录执行：

```bash
python3 scripts/convert.py doctor \
  --app "/Applications/NotebookLM PPT Editor.app"
```

自检通过后，试转第一页：

```bash
python3 scripts/convert.py convert "/absolute/path/slides.pdf" \
  --app "/Applications/NotebookLM PPT Editor.app" \
  --pages 1 --output-dir "$HOME/Downloads"
```

输出默认直接放入下载文件夹，中间工作文件另放缓存。实际文件名以最终结果为准。全篇转换去掉 `--pages 1`。

### 3. 交给 AI 助手使用

将 `notebooklm-ppt` 整个文件夹放入助手支持的 Skill 目录，重新加载技能。在支持显式调用的 Codex 环境中可以说：

> 使用 $notebooklm-ppt 将这个 PDF 转成可编辑 PPT。先试转第一页，默认本地处理，输出到下载文件夹，并告诉我有哪些质量提醒。

也可以把本地 `SKILL.md` 路径交给能够读文件、执行命令的助手，让它按说明操作。不授予终端执行权限的环境不能运行本工具。

完整参数、在线模式与故障处理见 [中文版运行说明](skills/notebooklm-ppt/references/usage.md)。

## 隐私与质量边界

- 转换脚本默认不把环境中的 DeepSeek Key 传给引擎；`--online` 才明确启用。
- 在线模式可能把抽取的文字和坐标发给配置的服务，并产生费用。不要在聊天或 Issue 中发送 Key。
- “本地模式”指转换引擎的调用方式，不代表宿主 AI 助手、电脑或所有依赖完全断网。
- 结果的文字可编辑覆盖率不等于视觉相似度；未编辑区域可能仍是图片，并不一定丢失。
- 退出码 `4` 表示需复核，不能按成功验收；部分失败可能没有最终 PPTX。
- 提交问题时请脱敏，不上传工作单位材料、原始报告或个人信息。

## 开发与验证

适配器仅使用 Python 标准库：

```bash
python3 -m unittest discover -s tests -v
```

自动测试验证调用边界、API 显式授权、退出状态、超时和输出包检查，不验证 OCR 准确率或每一页的视觉效果。真实转换需在满足条件的 Mac 上额外执行 `doctor` 和样本转换。

## 公开范围与授权

本仓库公开调用层，核心引擎、模型、桌面 App 和商业授权不在其中。**公开可见不等于已授予开源许可证。** 当前未指定开源许可证；商业使用、再分发及引擎授权请先联系维护者确认。软件效果以实际试转及报告为准，不作收益承诺。
