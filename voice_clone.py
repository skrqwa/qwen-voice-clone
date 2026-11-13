"""使用 Qwen3-TTS Base 在本机建立音色模板和生成配音。"""

import argparse
from dataclasses import fields
import math
from pathlib import Path
import re
import tempfile


DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"


def read_text(path):
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise ValueError(f"文本为空：{path}")
    return text


def write_new(path, writer):
    path.parent.mkdir(parents=True, exist_ok=True)
    # 同一目录写完后再发布文件；硬链接在目标已存在时会失败。
    with tempfile.TemporaryDirectory(dir=path.parent) as temp_dir:
        temporary = Path(temp_dir) / path.name
        writer(temporary)
        path.hardlink_to(temporary)


def create_template(args, model, torch, reference, transcript):
    prompt = model.create_voice_clone_prompt(
        ref_audio=reference, ref_text=transcript, x_vector_only_mode=False
    )
    # 只保存普通字段和 CPU 张量，沿用已有模板可安全加载的结构。
    item, = prompt
    values = {field.name: getattr(item, field.name) for field in fields(item)}
    payload = {
        name: value.detach().cpu() if isinstance(value, torch.Tensor) else value
        for name, value in values.items()
    }
    write_new(args.output, lambda path: torch.save([payload], path))


def synthesize(args, model, torch, paragraphs, prompt):
    import numpy as np
    import soundfile as sf

    def write_audio(path):
        from contextlib import ExitStack

        with ExitStack() as files:
            output = None
            for index, text in enumerate(paragraphs, start=1):
                torch.manual_seed(args.seed)
                waves, rate = model.generate_voice_clone(
                    text=text,
                    language=args.language,
                    voice_clone_prompt=prompt,
                    non_streaming_mode=True,
                    max_new_tokens=max(160, int(len(text) * 5.5 + 73)),
                    do_sample=True,
                    subtalker_dosample=True,
                    temperature=0.9,
                    top_k=50,
                    top_p=1.0,
                    repetition_penalty=1.05,
                )
                wave = waves[0]
                if rate <= 0 or wave.ndim != 1 or not wave.size or not np.isfinite(wave).all():
                    raise ValueError(f"第 {index} 段音频格式或采样值异常")
                if output is None:
                    output = files.enter_context(
                        sf.SoundFile(path, mode="w", samplerate=rate, channels=1, subtype="PCM_16", format="WAV")
                    )
                else:
                    if rate != output.samplerate:
                        raise ValueError(f"第 {index} 段采样率与首段不一致")
                    output.write(np.zeros(round(args.gap * rate), dtype=np.float32))
                output.write(wave)
                print(f"已生成 {index}/{len(paragraphs)} 段", flush=True)

    write_new(args.output, write_audio)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--model", default=DEFAULT_MODEL, help="Qwen3-TTS Base 模型目录或 Hugging Face ID")
    common.add_argument("--offline", action="store_true", help="仅使用本地模型文件或已有缓存")
    common.add_argument("--threads", type=int, default=8, help="CPU 推理线程数")
    common.add_argument("--seed", type=int, default=23)
    commands = parser.add_subparsers(dest="command", required=True)

    template = commands.add_parser("template", parents=[common], help="用参考音频和逐字稿生成模板")
    template.add_argument("--reference", type=Path, required=True, help="参考音频，例如 WAV 或 FLAC")
    template.add_argument("--transcript", type=Path, required=True, help="与参考音频对应的 UTF-8 逐字稿")
    template.add_argument("--output", type=Path, required=True, help="输出 .pt 音色模板")

    speech = commands.add_parser("speak", parents=[common], help="用模板生成 WAV 配音")
    speech.add_argument("--template", type=Path, required=True, help="已有的 .pt 音色模板")
    speech.add_argument("--text", type=Path, required=True, help="UTF-8 口播稿，空行分段")
    speech.add_argument("--output", type=Path, required=True, help="输出 .wav 音频")
    speech.add_argument("--language", default="Chinese", help="Qwen3-TTS 支持的语言名称，可用 Auto")
    speech.add_argument("--gap", type=float, default=0.3, help="段间静音秒数")
    return parser, parser.parse_args()


def main():
    parser, args = parse_args()
    suffix = ".pt" if args.command == "template" else ".wav"
    try:
        if args.output.suffix.lower() != suffix:
            raise ValueError(f"输出文件须使用 {suffix} 扩展名")
        if args.output.exists():
            raise FileExistsError(f"输出文件已存在：{args.output}")
        if args.threads < 1 or not 0 <= args.seed < 2**64:
            raise ValueError("线程数须为正整数，随机种子须在 0 到 2^64-1 之间")

        if args.command == "template":
            import numpy as np
            import soundfile as sf

            transcript = read_text(args.transcript)
            wave, rate = sf.read(args.reference, dtype="float32", always_2d=True)
            wave = wave.mean(axis=1)
            if not wave.size or not np.isfinite(wave).all() or not wave.any():
                raise ValueError("参考音频为空、静音或包含无效采样值")
        else:
            if not math.isfinite(args.gap) or args.gap < 0:
                raise ValueError("段间静音须为有限的非负秒数")
            paragraphs = re.split(r"\n[^\S\n]*\n", read_text(args.text))
            paragraphs = [" ".join(paragraph.splitlines()).strip() for paragraph in paragraphs]
            paragraphs = [paragraph for paragraph in paragraphs if paragraph]

        import torch
        from qwen_tts import Qwen3TTSModel
        from qwen_tts.inference.qwen3_tts_model import VoiceClonePromptItem

        if args.command == "speak":
            payload = torch.load(args.template, map_location="cpu", weights_only=True)
            if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
                raise ValueError("需要包含单个说话人的音色模板")
            prompt = [VoiceClonePromptItem(**payload[0])]

        torch.set_num_threads(args.threads)
        torch.manual_seed(args.seed)
        model = Qwen3TTSModel.from_pretrained(
            args.model, device_map="cpu", dtype=torch.float32,
            attn_implementation="eager", local_files_only=args.offline,
        )
        if args.command == "template":
            create_template(args, model, torch, (wave, rate), transcript)
        else:
            synthesize(args, model, torch, paragraphs, prompt)
    except (OSError, ValueError, RuntimeError, ImportError, TypeError) as error:
        parser.exit(1, f"运行失败：{error}\n")
    print(f"已保存：{args.output}")


if __name__ == "__main__":
    main()
