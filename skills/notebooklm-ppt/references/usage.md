# 运行与质量说明

## 引擎与安装边界

Skill 是调用协议和轻量脚本，不含 OCR 模型、桌面 App 或完整转换能力。使用者需自行取得并安装获授权的引擎和 LibreOffice。维护者的入口为 [GitHub 仓库](https://github.com/taomin8879/notebooklm-ppt-skill)；不要从无法核验的链接下载。

脚本按以下顺序寻找 App：`--app` 参数、`NLM_PPT_APP` 环境变量、`/Applications/NotebookLM PPT Editor.app`、`~/Applications/NotebookLM PPT Editor.app`。指定的是完整 `.app` 目录，不是其中的二进制文件。不支持 Windows、Linux 或 Intel Mac；其他平台不能仅靠安装这个 Skill 运行转换。

脚本只使用 Python 标准库。适配器测试可跨平台运行，不代表转换引擎跨平台可用。

## 命令

在 Skill 目录运行，或把 `scripts/convert.py` 替换为绝对路径：

```bash
# 完整自检（包含引擎的实际渲染检查）
python3 scripts/convert.py doctor --app "/Applications/NotebookLM PPT Editor.app"

# 指定页面；默认输出到下载文件夹
python3 scripts/convert.py convert "/absolute/path/slides.pdf" --pages 1,3-5

# 指定输出位置、工作目录和最长转换时间
python3 scripts/convert.py convert "/absolute/path/slides.pdf" \
  --output-dir "$HOME/Downloads" \
  --work-root "$HOME/Library/Caches/NotebookLM PPT Editor Skill/Runs" \
  --timeout 7200
```

无 `--pages` 时转换全部页。数字必须从 1 开始、范围升序。输出文件的命名及冲突处理由引擎负责，以最终 JSON 的路径为准。工作目录由引擎维护，可能自动清理旧任务，不适合作永久档案。

脚本先输出 `adapter-start`，完成后输出结果 JSON；不会实时转发每个处理阶段。等待期间不要重复启动相同任务。超时终止本次子进程组，但中间文件可能保留；退出码 `2`。用户中断为 `130`。

## 在线增强（可选）

默认模式不会向转换子进程传入 DeepSeek 密钥。它不是整个 AI 助手或操作系统的断网保证：宿主助手可能在云端处理对话和工具输出，敏感材料仍需遵守所在组织规定。

在线模式会把引擎抽取的文字和坐标发送给配置的 DeepSeek 兼容 HTTPS 接口，可能产生 API 费用。只有用户明确同意后才使用 `--online`；环境变量中存在密钥不等于同意。

用户通过自己信任的本地环境配置方式设置：

- `DEEPSEEK_API_KEY`：必填；不要写入 Skill、仓库、命令参数或聊天记录。
- `DEEPSEEK_BASE_URL`：可选，默认 `https://api.deepseek.com`。自定义地址会改变数据接收方，需先确认。
- `DEEPSEEK_MODEL`：可选，不填则使用已安装引擎的默认模型；Skill 不承诺任何指定模型永久可用。

然后在原转换命令上添加 `--online`。在线失败默认停止，不悄悄继续成“语义增强成功”。本仓库的测试不要求密钥，也不验证在线 API 可用性。

## 结果与复核

保留最终 JSON 的全部质量字段。重要字段包括 `result_status`、`output_pptx`、`run_dir`，以及引擎返回的报告路径、原因、覆盖率和失败页统计（不同引擎版本可能不同）。

退出码 `4` 可能有待复核 PPTX，也可能因为部分页面失败而没有最终文件。不得构造不存在的输出路径。`status: passed` 只是流程字段，不能覆盖 `result_status: 需修正`。

交付至少说明：

1. 输出 PPTX 的真实路径，或说明未生成。
2. 引擎质量结论及提醒。
3. 哪些区域仍是图片，以及是否实际做过视觉复核。
4. 源文件、输出文件和报告的保留位置。

对比代表性页面的标题和正文大小、字体替代、换行、文字重影、背景擦除痕迹。文字编辑覆盖率不是总内容完整率，也不是视觉相似度。修正时使用桌面 App，保留原文件作为基准。

## 常见问题

| 提示 | 处理 |
| --- | --- |
| 找不到 App | 使用 `--app` 指定完整安装包；Skill 本身不含引擎 |
| 构建版本过旧 | 从维护者取得 build 185+；不要绕过检查 |
| 缺少 LibreOffice / 渲染自检失败 | 修复依赖后重新运行完整 `doctor` |
| 输出需修正 | 看报告、对比原页，在桌面 App 修正后重新验证 |
| 没有持续进度 | 本版脚本缓冲引擎日志，等完成结果；不要重复开任务 |
| 反馈问题 | 只提供脱敏错误和版本，不公开完整报告或业务文档 |
