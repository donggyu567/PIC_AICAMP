"""Explicit offline asset loading, independent of import-time HF environment caches."""
from expanded_common import ROOT, MODEL, REVISION, require, sha

DEFAULT_CACHE = ROOT.parents[1] / '.venv-ai/hf-cache/hub'


def load_tokenizer(cache=DEFAULT_CACHE):
    from transformers import AutoConfig, AutoTokenizer
    cfg = AutoConfig.from_pretrained(MODEL, revision=REVISION, cache_dir=str(cache), local_files_only=True)
    require(cfg.model_type == 'electra' and cfg.type_vocab_size >= 2, 'Wrong cached encoder config')
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, cache_dir=str(cache), local_files_only=True)
    require(tok.padding_side == 'right' and 'token_type_ids' in tok.model_input_names, 'Tokenizer input contract differs')
    return tok


def fresh_public_model(seed, cache=DEFAULT_CACHE):
    from pathlib import Path
    from transformers import ElectraModel
    from risk_speech_ai.model import RiskSpeechClassifier
    from risk_speech_ai.training import set_training_seed
    path = Path(cache) / f'models--monologg--koelectra-base-v3-discriminator/snapshots/{REVISION}/pytorch_model.bin'
    require(sha(path) == 'f3f249cc07826bc2964a2c0dbbd0d239df4fe55efc03ba33e1bd1584cf56c566', 'Public weight hash differs')
    set_training_seed(seed)
    encoder = ElectraModel.from_pretrained(MODEL, revision=REVISION, cache_dir=str(cache), local_files_only=True)
    return RiskSpeechClassifier(encoder)
