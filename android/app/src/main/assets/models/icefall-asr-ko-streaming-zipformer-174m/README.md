# Korean streaming STT model used by the Android app

Source: https://huggingface.co/kangkyu/icefall-asr-ko-streaming-zipformer-174m
Revision: f0e73b1653c3ea75898c6d949dd71c690c9121da
Publisher: kangkyu
License: Apache-2.0 (see LICENSE and the unmodified UPSTREAM_README.md).

This app packages only the INT8 chunk-16, left-context-128 encoder, decoder,
joiner, and their matching tokens.txt. The published model graph metadata
identifies Zipformer2 and a decoder vocabulary of 2,460 tokens.

App settings: 16 kHz mono audio, 80 feature bins, CPU with 2 threads,
modified_beam_search with maxActivePaths=8, 0.8 seconds trailing silence
for endpoint detection. A manual stop retains the existing 1-second synthetic
silence padding; this is audio supplied to the recognizer, not a timed sleep.
Manual stop explicitly finalizes remaining text, even if automatic endpoint
detection is still false. Public Korean smoke samples produce text without
word spacing; spacing restoration is not part of this model migration.

The publisher's 320 ms chunk latency is not an end-to-end latency guarantee.
The 1-1.5 second finalization target and recognition accuracy must be measured
on the target Android device with representative audio.

UPSTREAM_SHA256SUMS is the publisher's original checksum list; it includes
other variants and the publisher's 174m_streaming/ path prefix. The following
four files were verified before integration:

| File | SHA256 |
| --- | --- |
| encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx | e595e2e37f46078387868ffa656b775de787fa511cf851cf8e1892d7dbdabe54 |
| decoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx | f5dfa6c8609b29da86c739d4904889475c33b62e28e70c619952a0ee6c31416f |
| joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx | 64efd9aeb71fb2278c713b3d5eb5ec45edf6b2ccd8716d3709044f17723c13fd |
| tokens.txt | 435dfb9e0a2b6a79124f1a4d8f0f33a951b25384726e2e0d854f081533e6ec9d |

The previous 2024-06-16 model was moved out of assets to the local ignored
android/.gradle-work/model-backups/ directory, so it is not included in the APK.
It remains there for local comparison or rollback; the previous files are also
part of the repository's prior Git/LFS history.