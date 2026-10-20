#!/usr/bin/env python3
"""Local adapter for a separately installed NotebookLM PPT Editor app.

Python standard library only. No model, engine, credential store or downloader.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import plistlib
import re
import signal
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

MIN_BUILD = 185
APP_NAME = "NotebookLM PPT Editor.app"
SYSTEM_ENV = {"PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "LC_CTYPE", "__CF_USER_TEXT_ENCODING"}


def require_platform():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("本版本的转换引擎仅支持 Apple 芯片 Mac；不支持 Windows、Linux 或 Intel Mac。")


def find_app(explicit=None):
    configured = explicit or os.environ.get("NLM_PPT_APP")
    candidates = [Path(configured).expanduser()] if configured else [Path("/Applications") / APP_NAME, Path.home() / "Applications" / APP_NAME]
    for candidate in candidates:
        worker = candidate / "Contents/Resources/worker/notebooklm-ppt-worker"
        if worker.is_file() and os.access(worker, os.X_OK):
            return candidate.resolve()
    raise ValueError("未找到完整的转换 App。请先从维护者处获取引擎，再通过 --app 指定 .app 路径；Skill 不包含引擎，也不会自动下载。")


def app_resources(app):
    try:
        with (app / "Contents/Info.plist").open("rb") as handle:
            info = plistlib.load(handle)
        build = int(info["CFBundleVersion"])
    except (OSError, ValueError, KeyError, plistlib.InvalidFileException) as error:
        raise ValueError("无法读取 App 构建版本，请使用维护者提供的完整安装包。") from error
    if build < MIN_BUILD:
        raise ValueError(f"需要 build {MIN_BUILD} 或更新版本，当前是 {build}。")
    resources = app / "Contents/Resources"
    if not (resources / "runtime-assets").is_dir():
        raise ValueError("App 缺少 runtime-assets；不能只复制可执行文件。")
    return resources, build


def worker_environment(original, resources, online=False):
    # Do not forward shell credentials, Python injection settings or experimental
    # engine switches. Presence of a key is not consent to send document text.
    env = {key: value for key, value in original.items() if key in SYSTEM_ENV}
    env.update({
        "DEEPSEEK_API_KEY": "",
        "NOTEBOOKLM_PPT_RESOURCES": str(resources / "runtime-assets"),
        "NOTEBOOKLM_PPT_VISION_HELPER": str(resources / "vision-verify"),
        "NOTEBOOKLM_PPT_SHAPE_MODE": "fidelity",
        "NOTEBOOKLM_PPT_DEEPSEEK_ON_FAILURE": "stop",
    })
    if online:
        key = original.get("DEEPSEEK_API_KEY", "").strip()
        endpoint = original.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
        parsed = urlparse(endpoint)
        if not key:
            raise ValueError("--online 需要用户自行设置 DEEPSEEK_API_KEY；不要把密钥写进命令参数、对话或仓库。")
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("在线增强只接受不含账号密码的 HTTPS 接口地址。")
        env["DEEPSEEK_API_KEY"] = key
        env["DEEPSEEK_BASE_URL"] = endpoint
        if original.get("DEEPSEEK_MODEL", "").strip():
            env["DEEPSEEK_MODEL"] = original["DEEPSEEK_MODEL"].strip()
    return env


def validate_pages(value):
    value = value.replace("，", ",").replace(" ", "")
    if not value:
        return ""
    if not re.fullmatch(r"[1-9][0-9]*(?:-[1-9][0-9]*)?(?:,[1-9][0-9]*(?:-[1-9][0-9]*)?)*", value):
        raise ValueError("页码格式应为 1 或 1,3-5，不能包含 0、负数或空项。")
    for part in value.split(","):
        limits = [int(number) for number in part.split("-")]
        if max(limits) > 10000 or (len(limits) == 2 and limits[1] < limits[0]):
            raise ValueError("页码必须在 1–10000 内，区间按从小到大填写。")
    return value


def _stop(process):
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.communicate()
    except ProcessLookupError:
        process.communicate()


def run_worker(command, env, timeout):
    # Argument lists preserve paths with spaces and prevent shell evaluation.
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, encoding="utf-8", errors="replace", env=env,
                          start_new_session=os.name == "posix") as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            _stop(process)
            raise ValueError("转换组件超时，已停止本次进程组。未将任务标记为成功。") from error
        except KeyboardInterrupt:
            _stop(process)
            raise
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def event_of_type(output, kind):
    found = None
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == kind:
            found = event
    return found


def require_self_test(code, output):
    event = event_of_type(output, "self-test")
    if code != 0 or not event or event.get("ok") is not True:
        details = [str(item.get("detail") or item.get("name")) for item in (event or {}).get("checks", []) if not item.get("ok")]
        raise ValueError("环境自检未通过：" + ("；".join(details) or "没有有效的成功结果"))
    return event


def conversion_result(code, output):
    event = event_of_type(output, "completed")
    if code not in (0, 4) or not event:
        error = event_of_type(output, "error") or {}
        raise ValueError(f"转换未完成（退出码 {code}）：{error.get('message', '缺少有效完成事件')}")
    verdict = event.get("result_status")
    if verdict not in ("通过", "可用但有提醒", "需修正"):
        raise ValueError("转换结果缺少可识别的质量状态，不能交付为成功。")
    path = event.get("output_pptx")
    if path:
        if not Path(path).is_file() or not zipfile.is_zipfile(path):
            raise ValueError("完成事件中的 PPTX 不存在或格式无效。")
        with zipfile.ZipFile(path) as archive:
            if not {"[Content_Types].xml", "ppt/presentation.xml"}.issubset(archive.namelist()):
                raise ValueError("输出不是有效的 PPTX 包。")
    elif not (code == 4 and event.get("status") == "incomplete"):
        raise ValueError("没有生成可交付的 PPTX 文件。")
    needs_review = code == 4 or verdict == "需修正" or event.get("status") != "passed"
    # Return all coverage, report links and retained-image warnings unchanged.
    if needs_review:
        event["result_status"] = "需修正"
    event["adapter_version"] = "0.1.0"
    return event, 4 if needs_review else 0


def parser():
    result = argparse.ArgumentParser(description="NotebookLM PPT Skill：调用本地安装的转换引擎，不包含引擎本身。")
    commands = result.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="检查 App、资源和渲染依赖")
    convert = commands.add_parser("convert", help="转换 PDF / PPTX / PNG / JPG")
    for command in (doctor, convert):
        command.add_argument("--app", help="NotebookLM PPT Editor.app 的完整路径，或设置 NLM_PPT_APP")
        command.add_argument("--timeout", type=float, default=7200, help="最长运行秒数（默认 7200）")
    doctor.add_argument("--quick", action="store_true", help="仅检查资源和依赖；不代表实际渲染通过")
    convert.add_argument("source", type=Path)
    convert.add_argument("--output-dir", type=Path, default=Path.home() / "Downloads")
    convert.add_argument("--work-root", type=Path, default=Path.home() / "Library/Caches/NotebookLM PPT Editor Skill/Runs")
    convert.add_argument("--pages", default="", help="原文件页码，例如 1 或 1,3-5；默认全部")
    convert.add_argument("--online", action="store_true", help="明确允许把文字和坐标发往配置的 DeepSeek 兼容接口；可能产生费用")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    secret = os.environ.get("DEEPSEEK_API_KEY", "")
    try:
        if args.timeout <= 0 or args.timeout > 86400:
            raise ValueError("超时秒数必须大于 0 且不超过 86400。")
        if args.command == "convert":
            source = args.source.expanduser().resolve(strict=True)
            if not source.is_file() or source.suffix.lower() not in {".pdf", ".pptx", ".png", ".jpg", ".jpeg"}:
                raise ValueError("输入须是现有的 PDF、PPTX、PNG 或 JPG 文件。")
            pages = validate_pages(args.pages)
        require_platform()
        app = find_app(args.app)
        resources, build = app_resources(app)
        env = worker_environment(os.environ, resources, online=getattr(args, "online", False))
        worker = str(resources / "worker/notebooklm-ppt-worker")
        check = [worker, "worker", "self-test", "--resources-root", str(resources / "runtime-assets")]
        if args.command == "convert" or args.quick:
            check.append("--quick")
        print(json.dumps({"type": "adapter-start", "build": build, "mode": "online" if getattr(args, "online", False) else "local", "message": "正在检查运行环境；转换可能需要数分钟，请勿重复启动。"}, ensure_ascii=False), flush=True)
        checked = run_worker(check, env, min(args.timeout, 300))
        report = require_self_test(checked.returncode, checked.stdout)
        if args.command == "doctor":
            report.update({"app": str(app), "build": build, "quick": args.quick})
            code = 0
        else:
            destination = args.output_dir.expanduser().resolve()
            work = args.work_root.expanduser().resolve()
            if destination.exists() and not destination.is_dir():
                raise ValueError("输出位置必须是文件夹。")
            command = [worker, "worker", "convert", str(source), "--destination-dir", str(destination), "--work-root", str(work), "--resources-root", str(resources / "runtime-assets")]
            if pages:
                command += ["--pages", pages]
            converted = run_worker(command, env, args.timeout)
            report, code = conversion_result(converted.returncode, converted.stdout)
        payload = json.dumps(report, ensure_ascii=False)
        print(payload.replace(secret, "***") if secret else payload, flush=True)
        return code
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        message = str(error)
        if secret:
            message = message.replace(secret, "***")
        print(json.dumps({"type": "adapter-error", "message": message}, ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('{"type":"adapter-error","message":"用户已取消；未标记为成功。"}', file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
