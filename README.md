# Qwen Voice Clone

在本机用 Qwen3-TTS 克隆已获授权的声音。用一段参考音频和对应逐字稿生成音色模板，之后可以反复用同一模板给新稿配音。适合视频旁白和分段口播。默认使用 0.6B Base 模型、CPU、float32、eager 和随机种子 23。

## 安装

推荐 Python 3.11。以下命令以 Windows PowerShell 为例。本项目用本地 WAV 和 CPU 路径进行验证，PyTorch 和 torchaudio 应使用配套版本。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

模型默认从 Hugging Face 下载并缓存。已有本地模型时，在两个子命令后追加 `--model "本地模型目录" --offline`。离线运行前需备齐模型及语音 tokenizer。CPU 推理耗时会随稿件长度变化，可用 `--threads` 调整线程数。

## 本地网页

```powershell
.\.venv\Scripts\python.exe web_app.py
```

打开 [声音工作台](http://127.0.0.1:7860)。左侧选择参考音频，填写名称和逐字稿，点击「生成模板」。右侧选择模板、填写文案，生成后可在浏览器试听并下载 WAV。窄屏上两个表单依次排列。

已有模型时可用 `web_app.py --model "本地模型目录" --offline` 启动。服务监听本机回环地址，按 Ctrl+C 停止。生成的模板保存在 `work/web/templates/`。把已有的兼容 `.pt` 文件复制到该目录并刷新网页即可复用，文件名会显示在下拉列表。生成的 WAV 保存在 `work/web/audio/`，参考音频和填写的文字只在生成过程中临时使用。

## 命令行

## 1. 生成音色模板

在 `work/` 下放一段清楚的单人参考录音 `reference.wav`，以及只写实际说出内容的 UTF-8 逐字稿 `reference.txt`。选择连续的语句，尽量避开背景音乐、叠话和截断的字。如果素材来自有配乐的视频，先用人声分离工具导出 vocal 轨，再试听并核对逐字稿。人声分离可能留下残余配乐或伪影。

```powershell
.\.venv\Scripts\python.exe voice_clone.py template --reference work/reference.wav --transcript work/reference.txt --output work/voice.pt
```

## 2. 用同一模板生成新配音

把口播稿存成 `work/script.txt`。按完整语义组织段落，用空行分隔。默认段间增加 0.3 秒静音，使用 `--gap` 调整。建议先试一两句，再合成长稿。每段推理有生成长度上限，长稿可拆成短段并检查每段末尾。

```powershell
.\.venv\Scripts\python.exe voice_clone.py speak --template work/voice.pt --text work/script.txt --output work/narration.wav
```

输出是单声道 PCM WAV。命令保留已有文件，重跑时指定新的输出路径。输出目录需位于支持硬链接的文件系统，例如 Windows 的 NTFS。已有的单说话人「字典列表 + 张量」模板可以直接传给 `--template`。只使用自己生成或来源可信的模板。

仓库包含命令行源码和用法。参考录音、逐字稿、音色模板、模型权重和生成音频放在本机。依赖与模型的来源和许可见 [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) 和 [0.6B Base 模型卡](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base)。
