---
name: notebooklm-ppt
description: Use when a user wants to convert NotebookLM slide exports, image-based PDF/PPTX, or slide screenshots into an editable PowerPoint using a locally installed NotebookLM PPT Editor engine on an Apple silicon Mac.
---

# NotebookLM 图片转可编辑 PPT

调用用户单独安装的本地引擎，保留原页视觉细节、生成可编辑文字，并如实交付质量报告。本 Skill 不含转换引擎，不是 NotebookLM 官方产品。

## 前置检查

- 仅支持 Apple 芯片 Mac、macOS 13+、Python 3.9+。
- 需要完整的 `NotebookLM PPT Editor.app`（build 185+）以及 LibreOffice。
- 未安装引擎时说明缺少依赖并停止；不编造下载地址，不擅自下载、安装或替换应用。
- 以下路径均相对于本 Skill 的目录。先读取 [运行与质量说明](references/usage.md)，再运行脚本。

## 执行

1. 确认输入文件确实存在。支持 PDF、PPTX、PNG、JPG/JPEG；页码为原文件页码。
2. 首次使用运行完整自检：

   ```bash
   python3 scripts/convert.py doctor --app "/Applications/NotebookLM PPT Editor.app"
   ```

   `--quick` 只检查依赖，不证明实际渲染成功。自检失败先报告原因，不开始批量转换。

3. 默认本地模式。即使环境中已有 API Key，也不自动开启在线增强。只有用户明确允许将文字和坐标发送到配置的接口并接受可能的费用，才加 `--online`。不要索要用户把密钥发进对话。
4. 先试转 1 页检查字体、字号、换行、重影，再转换全篇：

   ```bash
   python3 scripts/convert.py convert "/absolute/path/slides.pdf" \
     --app "/Applications/NotebookLM PPT Editor.app" \
     --pages 1 --output-dir "$HOME/Downloads"
   ```

   全篇转换去掉 `--pages`。默认输出直接进入下载文件夹；中间文件放到独立缓存，不改动输入文件。不要因等待无新日志而重复启动。

## 交付判定

同时读取退出码和最终 JSON；文件生成不等于质量通过。

| 退出码 / 状态 | 行为 |
| --- | --- |
| `0` + `通过` | 交付 PPTX 和报告，说明已验证范围 |
| `0` + `可用但有提醒` | 交付时列出提醒，不改写成完全通过 |
| `4` 或 `需修正` | 标记为待复核；有 PPTX 才给文件链接；保留运行目录和原因 |
| `2` / `130` | 失败 / 取消；不能声称转换完成 |

检查返回的 PPTX、报告、失败页和覆盖率。未转成可编辑文字的区域可能仍以图片保留，**不能仅凭覆盖率分母推断文字丢失**；覆盖率只统计引擎识别范围，不保证识别了全部文字。

保真模式下背景、装饰和复杂图形可能仍是图片，不承诺所有对象可编辑或字体完全一致。对比源页与输出页后再评价视觉质量。无法渲染检查时明确写“未进行视觉复核”。

修正通过桌面 App 完成；本版脚本没有自动修正命令。只运行用户要求的转换，不上传输入、输出、报告、密钥或业务内容到 GitHub。
