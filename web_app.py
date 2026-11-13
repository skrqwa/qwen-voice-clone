"""在本机浏览器中生成音色模板和试听配音。"""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Lock
from uuid import uuid4

from flask import Flask, abort, jsonify, request, send_from_directory, url_for

from voice_clone import DEFAULT_MODEL


ROOT = Path(__file__).resolve().parent
AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg"}
MAX_REQUEST_BYTES = 25 * 1024 * 1024


def create_app(model=DEFAULT_MODEL, offline=False, threads=8, data_dir=ROOT / "work" / "web"):
    app = Flask(__name__, static_folder="web", static_url_path="/assets")
    app.config.update(MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES, TRUSTED_HOSTS=["127.0.0.1", "localhost"])
    templates = data_dir / "templates"
    outputs = data_dir / "audio"
    templates.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    busy = Lock()
    model_args = ["--model", model, "--threads", str(threads)]
    if offline:
        model_args.append("--offline")

    @app.before_request
    def check_local_request():
        # 浏览器跨站表单无法设置这个请求头，服务也不开放跨域访问。
        if request.method == "POST" and request.headers.get("X-Voice-Studio") != "1":
            abort(403)

    @app.errorhandler(413)
    def upload_too_large(_error):
        return jsonify(error="上传请求超过 25 MB，请剪短参考音频再试。"), 413

    def run_cli(command, arguments):
        result = subprocess.run(
            [sys.executable, str(ROOT / "voice_clone.py"), command, *model_args, *map(str, arguments)],
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode:
            # 详细错误留在本机终端，网页提示用户可以采取的下一步。
            app.logger.error("配音命令失败\n%s", result.stderr[-4000:])
            return False
        return True

    def template_files():
        return sorted(
            (path for path in templates.glob("*.pt") if path.is_file() and not path.is_symlink()),
            key=lambda path: path.name.casefold(),
        )

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/api/templates")
    def list_templates():
        return jsonify(templates=[path.stem for path in template_files()])

    @app.post("/api/templates")
    def add_template():
        name = request.form.get("name", "").strip()
        transcript = request.form.get("transcript", "").strip()
        reference = request.files.get("reference")
        if not re.fullmatch(r"[\w -]{1,50}", name) or Path(f"{name}.pt").is_reserved():
            return jsonify(error="模板名称请使用 1–50 个文字、数字、空格、下划线或连字符。"), 400
        if not transcript or len(transcript) > 2000:
            return jsonify(error="请填写与参考录音一致的逐字稿，最多 2000 字。"), 400
        extension = Path(reference.filename or "").suffix.lower() if reference is not None else ""
        if extension not in AUDIO_EXTENSIONS:
            return jsonify(error="请选择 WAV、FLAC、MP3 或 OGG 格式的参考音频。"), 400

        if not busy.acquire(blocking=False):
            return jsonify(error="正在处理另一项任务，请稍后重试。"), 409
        try:
            destination = templates / f"{name}.pt"
            if any(path.stem.casefold() == name.casefold() for path in template_files()) or destination.exists():
                return jsonify(error="已有同名模板，请换一个名称。"), 409
            with TemporaryDirectory() as directory:
                audio = Path(directory) / f"reference{extension}"
                text = Path(directory) / "transcript.txt"
                reference.save(audio)
                text.write_text(transcript, encoding="utf-8")
                if not run_cli("template", ["--reference", audio, "--transcript", text, "--output", destination]):
                    return jsonify(error="模板生成失败。请检查参考音频能否正常播放，以及本机模型是否可用。"), 422
            return jsonify(name=name), 201
        finally:
            busy.release()

    @app.post("/api/speech")
    def make_speech():
        name = request.form.get("template", "")
        script = request.form.get("script", "").strip()
        language = request.form.get("language", "Chinese")
        prompt = next((path for path in template_files() if path.stem == name), None)
        if prompt is None:
            return jsonify(error="请从列表选择一个本机已有的音色模板。"), 400
        if not script or len(script) > 10000:
            return jsonify(error="请填写配音文案，最多 10000 字。"), 400
        if language not in {"Chinese", "English", "Auto"}:
            return jsonify(error="请选择列表中的配音语言。"), 400

        if not busy.acquire(blocking=False):
            return jsonify(error="正在处理另一项任务，请稍后重试。"), 409
        try:
            audio_id = uuid4()
            with TemporaryDirectory() as directory:
                text = Path(directory) / "script.txt"
                text.write_text(script, encoding="utf-8")
                if not run_cli("speak", ["--template", prompt, "--text", text, "--language", language,
                                         "--output", outputs / f"{audio_id}.wav"]):
                    return jsonify(error="配音生成失败。请检查模板与当前模型是否匹配，或先用一段短文案重试。"), 422
            return jsonify(
                audio=url_for("speech_file", audio_id=audio_id),
                download=url_for("speech_file", audio_id=audio_id, download=1),
            ), 201
        finally:
            busy.release()

    @app.get("/api/audio/<uuid:audio_id>.wav")
    def speech_file(audio_id):
        response = send_from_directory(
            outputs, f"{audio_id}.wav", mimetype="audio/wav",
            as_attachment=request.args.get("download") == "1", download_name="配音.wav",
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        return response

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    if args.threads < 1 or not 1 <= args.port <= 65535:
        parser.error("线程数须为正整数，端口范围为 1–65535")
    create_app(args.model, args.offline, args.threads).run(
        host="127.0.0.1", port=args.port, debug=False, use_reloader=False
    )


if __name__ == "__main__":
    main()
