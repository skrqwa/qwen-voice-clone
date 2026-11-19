---
name: qwen-voice-clone
description: Clone an authorized voice locally from a reference recording and its exact transcript, then reuse the voice template to generate WAV narration with Qwen Voice Clone. Use for 声音克隆, 音色模板, 配音, or changing the voice of a script with this project.
---

# Qwen Voice Clone

在用户本机用 [Qwen Voice Clone](https://github.com/skrqwa/qwen-voice-clone) 建立可复用的音色模板并生成 WAV。需要可以访问本机文件和终端的 AI 客户端。

## 确认输入

- 建模板需要用户授权用于克隆的单人录音，以及与录音实际说话内容一致的 UTF-8 逐字稿。优先选择清晰、无配乐、无叠话的 WAV。逐字稿缺失时，可以先做转写草稿，交给用户核对。
- 用已有模板配音需要可信的兼容 `.pt` 模板、新文案和输出位置。有模板即可直接生成。首次验证时可以先读一两句；长稿按完整语义段组织，段间用空行分隔。
- 将录音、原话、模板和生成音频留在用户指定的本机目录。任务目录可放在仓库的 `work/`。用户需要分享时，按其指定的文件和渠道处理。

## 运行

1. 从包含 `voice_clone.py` 的仓库根目录运行。用户要求安装且本机还没有工作副本时，用 `git clone https://github.com/skrqwa/qwen-voice-clone.git` 拉取到任务目录。按 [项目 README](https://github.com/skrqwa/qwen-voice-clone#readme) 创建虚拟环境并安装依赖，建议 Python 3.11。下文的 `python` 指项目环境中的解释器，Windows 可用 `.venv/Scripts/python.exe`，macOS 和 Linux 可用 `.venv/bin/python`。只有聊天功能的客户端可以给出本地命令，由用户运行。
2. 将下列示例路径替换为本次实际文件。为模板和配音选择支持硬链接的文件系统及尚未使用的文件名。Windows 的 NTFS 可用。路径有空格时加引号。

   ```text
   python voice_clone.py template --reference "work/reference.wav" --transcript "work/reference.txt" --output "work/voice.pt"
   python voice_clone.py speak --template "work/voice.pt" --text "work/script.txt" --output "work/narration.wav"
   ```

   `voice_clone.py` 默认在 CPU 运行，首次使用会下载模型。用户已有模型和语音 tokenizer 并需要离线时，在对应子命令末尾加 `--model "本地模型目录" --offline`。切换音色时更换 `--template`，改稿时更换 `--text`，各自使用新的输出路径。
3. 核对命令退出状态和实际输出文件。生成 WAV 后检查可读、时长大于零并且有音频信号。向用户给出实际输出路径和时长，按实际情况说明是否试听过。

用户希望在浏览器完成操作时，在仓库根目录运行 `python web_app.py`，按终端显示的本机地址打开声音工作台。可用 `--port` 指定端口。左侧建模板，右侧选模板、填稿、试听并下载。用户只需配音文件时，直接使用命令行。
