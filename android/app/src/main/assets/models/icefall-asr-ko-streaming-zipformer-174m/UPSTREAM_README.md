---
language:
- ko
license: apache-2.0
tags:
- automatic-speech-recognition
- zipformer
- transducer
- causal
- icefall
- k2
- korean
datasets:
- ksponspeech
metrics:
- cer
pipeline_tag: automatic-speech-recognition
---

# icefall-asr-ko-streaming-zipformer-174m

📖 [한국어 README 보기 / Korean version](README_ko.md)

A Korean causal ASR built with the [icefall](https://github.com/k2-fsa/icefall) recipe — **155.7M-parameter Zipformer transducer**.

- **Training data**: KsponSpeech + AIHub mix, **~6,500 hours**
- **KsponSpeech eval CER** (no-punctuation, CPU inference)
  - **7.16%** — offline best (chunk=−1 PyTorch + KenLM, RTF 0.081)
  - **7.53%** — streaming best (sherpa-onnx int8 chunk-64, RTF 0.049)
- **Release**: PyTorch `.pt` + sherpa-onnx int8 ONNX (chunk 16/32/64, ready to use out-of-the-box)

## Model

Based on [icefall](https://github.com/k2-fsa/icefall) Zipformer transducer.

- causal architecture (multichunk training: chunk-16 / 32 / 64 / -1)
- Korean syllable vocabulary (2,460 tokens)
- FP16 training
- **Files included**: PyTorch `epoch-99.pt` (3-way state-dict avg, 594 MB) + 9 sherpa-onnx int8 ONNX (chunk 16/32/64 × encoder/decoder/joiner). Ready to use out-of-the-box, no extra export step required

## Performance (KsponSpeech eval, CER %, no-punctuation)

eval_clean 3,000 + eval_other 3,000 = 6,000 cuts. All measurements on the same set, beam=8, 3-way state-dict avg.

### Decoding modes — choose by latency budget

| Mode | chunk | clean | other | **OVR** | RTF | latency |
|---|---|---:|---:|---:|---:|---|
| chunk=−1 PyTorch + KenLM λ=0.05 (offline best) | −1 | 7.18 | 7.14 | **7.16** | 0.081 (CPU 2t) | utterance end |
| sherpa-onnx int8 chunk-64 | 64 | 7.51 | 7.55 | **7.53** | 0.049 (CPU 1t) | 1.28 s |
| sherpa-onnx int8 chunk-32 | 32 | 7.83 | 7.80 | **7.815** | 0.054 (CPU 1t) | 640 ms |
| sherpa-onnx int8 chunk-16 | 16 | 8.36 | 8.15 | **8.255** | 0.073 (CPU 1t) | 320 ms |

streaming numbers measured with 1x trailing padding (`CHUNK * 0.04 s`). RTF averaged over clean/other.

> **chunk=−1 (offline best 7.16%) is PyTorch-only**: sherpa-onnx supports streaming chunks (16/32/64) only. To get the offline best CER, run `epoch-99.pt` directly via the icefall recipe — see "Option 1 — PyTorch (`epoch-99.pt`) with icefall recipe" below.

> **chunk-16 accuracy tip**: increase trailing padding to `CHUNK * 0.04 * 4` (~2.56 s) to gain +0.25%p OVR (8.01 vs 8.255). chunk-32/64 do not benefit from longer padding.

### Quantization safety — fp32 vs int8 ⭐

Direct sweep on the same KsponSpeech 6,000-cut eval set, identical 1x padding, CPU 1-thread:

| chunk | fp32 OVR | int8 OVR | Δ CER | fp32 RTF | int8 RTF | speedup |
|---|---:|---:|---:|---:|---:|---:|
| 16 | 8.25 | 8.255 | +0.005 | 0.134 | 0.073 | **1.84×** |
| 32 | 7.735 | 7.815 | +0.080 | 0.098 | 0.054 | **1.80×** |
| 64 | 7.535 | 7.530 | −0.005 | 0.086 | 0.049 | **1.76×** |

int8 quantization preserves CER (avg Δ +0.03%p, max +0.08) while running **~1.8× faster** on CPU — this is the reason only `.int8.onnx` is shipped. If you need fp32, re-export from `epoch-99.pt` with the icefall recipe.

### Direct comparison on the same eval set (KsponSpeech 6,000 cuts)

| Model | params | clean | other | OVR |
|---|---:|---:|---:|---:|
| **This model (174M)** | **155.7M** | **7.18** | **7.14** | **7.16** |
| sibling 72M baseline | 71.4M | 7.63 | 7.72 | 7.68 |
| Qwen3-ASR-1.7B (Alibaba) | 1,700M | 9.76 | 10.22 | 9.99 |
| OpenAI Whisper-large-v2 | 1,550M | 13.70 | 12.64 | 13.17 |

> All models measured directly on the same KsponSpeech eval set. Whisper / Qwen run with default GPU FP16 transformers options; this model uses chunk=−1 PyTorch + KenLM rescore.

## Decoding stack ablation

| Stack | clean | other | OVR |
|---|---:|---:|---:|
| epoch-30 single, no LM | 7.85 | 7.78 | 7.81 |
| 3-way state-dict avg, no LM | 7.26 | 7.20 | 7.22 |
| **3-way avg + KenLM λ=0.05** (the stack reported above) | **7.18** | **7.14** | **7.16** |

3-way avg = state_dict average of best-valid + best-train + epoch-30.

## Architecture

| | |
|---|---|
| Encoder | Zipformer2 causal, 6 stacks |
| Encoder dim | 192,256,512,768,512,256 |
| Encoder layers | 2,2,4,5,4,2 |
| Feedforward dim | 512,768,1536,2048,1536,768 |
| Heads | 4,4,8,8,8,4 |
| Decoder | Stateless transducer decoder, dim 512 |
| Joiner | dim 512 |
| Vocabulary | Korean syllables, 2,460 tokens |
| Total params | 155.7 M |
| Causal | Yes |
| Training chunk-size | 16, 32, 64, −1 multichunk |

## Training

| | |
|---|---|
| Total data | ~6,500 hours |
| KsponSpeech | 964 hours |
| AIHub mix | ~5,500 hours (multiple datasets) |
| Precision | FP16 |
| Loss | Pruned-RNNT (transducer-only) |
| Augmentation | SpecAugment + musan/RIR |
| Optimizer | ScaledAdam |
| Total epochs | 30 |
| Released checkpoint | 3-way state_dict avg of best-valid + best-train + epoch-30 |

## Usage

### Option 1 — PyTorch (`epoch-99.pt`) with icefall recipe

Load the weights with the icefall recipe (`egs/librispeech/ASR/zipformer`). chunk size, beam, KenLM, ONNX export, quantization etc. can be tuned freely.

**chunk=−1 (offline best 7.16%) example**:
```bash
# Place epoch-99.pt as epoch-99.pt in your icefall exp dir, then:
python zipformer/decode.py \
    --epoch 99 --avg 1 --use-averaged-model 0 \
    --causal 1 --chunk-size -1 --left-context-frames -1 \
    --decoding-method modified_beam_search --beam-size 8
```

Add KenLM rescore (λ=0.05) to reproduce 7.16%. See [icefall docs](https://github.com/k2-fsa/icefall) for detailed options and KenLM usage.

### Option 2 — sherpa-onnx streaming (recommended for CPU deployment)

```python
# Install: pip install sherpa-onnx soundfile
import sherpa_onnx
import soundfile as sf

# Choose chunk: 16 (320ms latency) / 32 / 64
# Choose variant: ".int8" (included in release, ~1/2 size, almost no CER loss)
#                 "" (fp32, NOT included — re-export from epoch-99.pt if needed)
CHUNK = 16
VARIANT = ".int8"

recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
    encoder=f"encoder-epoch-99-avg-1-chunk-{CHUNK}-left-128{VARIANT}.onnx",
    decoder=f"decoder-epoch-99-avg-1-chunk-{CHUNK}-left-128{VARIANT}.onnx",
    joiner=f"joiner-epoch-99-avg-1-chunk-{CHUNK}-left-128{VARIANT}.onnx",
    tokens="tokens.txt",
    num_threads=2,
    sample_rate=16000,
    feature_dim=80,
    decoding_method="modified_beam_search",
    max_active_paths=8,
)

audio, sr = sf.read("speech.wav")
stream = recognizer.create_stream()
stream.accept_waveform(sr, audio)
# Add trailing silence so the last chunk is fully decoded
import numpy as np
stream.accept_waveform(16000, np.zeros(int(CHUNK * 0.04 * 16000), dtype=np.float32))
stream.input_finished()
while recognizer.is_ready(stream):
    recognizer.decode_stream(stream)
print(recognizer.get_result(stream))
```

### Chunk size guide

| chunk | latency | OVR | use case |
|---|---|---:|---|
| 16 | 320 ms | 8.255 | real-time UX, lowest interactive latency |
| 32 | 640 ms | 7.815 | balanced |
| **64** | **1.28 s** | **7.53** | **best streaming CER** (only +0.37 vs offline 7.16) |

## Files

```
epoch-99.pt                                                  # PyTorch 3-way state_dict avg (594 MB)
tokens.txt                                                   # syllable vocab 2,460
README.md / README_ko.md
encoder-epoch-99-avg-1-chunk-{16,32,64}-left-128.int8.onnx   # int8 encoder
decoder-epoch-99-avg-1-chunk-{16,32,64}-left-128.int8.onnx
joiner-epoch-99-avg-1-chunk-{16,32,64}-left-128.int8.onnx
```

## Sibling

→ [icefall-asr-ko-streaming-zipformer-72m](https://huggingface.co/kangkyu/icefall-asr-ko-streaming-zipformer-72m) — 71.4M params, KsponSpeech 1,000h only.

## License

Apache 2.0.

## Citation

```
@misc{ko-zipformer-174m,
  title  = {icefall-asr-ko-streaming-zipformer-174m: Korean ASR (KsponSpeech + AIHub)},
  author = {Ken (kangkyu)},
  year   = {2026},
  howpublished = {\url{https://huggingface.co/kangkyu/icefall-asr-ko-streaming-zipformer-174m}}
}
```

Built on:
- [icefall](https://github.com/k2-fsa/icefall)
- [k2](https://github.com/k2-fsa/k2)
- [KsponSpeech](https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=123)
