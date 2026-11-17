# Actual-source function guide

AST로 실제 소스에서 경로·행·signature·호출·검증식을 추출했다. 검증 실패는 GateError/ValueError 또는 해당 IO 예외로 전파한다.

### [v3_lite/build_research_data.py:12 — parse](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/build_research_data.py#L12)

- 입력: `role`
- 반환식: `cs`
- 호출 관계: `authored.read_text`, `authored.read_text(encoding='utf-8-sig').splitlines`, `bool`, `cs.append`, `current['utterances'].append`, `dict`, `len`, `line.split`, `line.startswith`, `line.strip`, `read_json`, `require`, `role.upper`, `sha`, `sorted`, `validate_research`
- 검증/예외: `require(len(cs) == len(plan), 'Prospective scenario count mismatch')`; `validate_research(cs, role)`; `require(family in expected, 'Unknown prospective family')`

### [v3_lite/check_phase2.py:18 — regression](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/check_phase2.py#L18)

- 입력: `out`
- 반환식: `record`
- 호출 관계: `(out / 'regression.log').write_text`, `code_inventory`, `create_json`, `dict`, `digest`, `io.StringIO`, `len`, `print`, `require`, `result.wasSuccessful`, `str`, `stream.getvalue`, `time.monotonic`, `unittest.TextTestRunner`, `unittest.TextTestRunner(stream=stream, verbosity=2).run`, `unittest.defaultTestLoader.discover`
- 검증/예외: `require(record['status'] == 'PASS', 'Regression failed; real training remains blocked')`

### [v3_lite/check_phase2.py:37 — parent_smoke](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/check_phase2.py#L37)

- 입력: `out`
- 반환식: `record`
- 호출 관계: `abs`, `all`, `bootstrap`, `create_json`, `dict`, `json.dumps`, `len`, `list`, `load_v2_start`, `max`, `model.eval`, `model.named_parameters`, `model.state_dict`, `module.raw_logits`, `new_optimizer`, `parent_state[k].data_ptr`, `print`, `record.items`, `require`, `resources`, `runtime`, `set`, `state.items`, `str`, `time.monotonic`, `torch.equal`, `torch.load`, `torch.set_num_threads`, `value.data_ptr`, `verify_parent`, `zip`
- 검증/예외: `require(set(state) == set(parent_state), 'Parent state keys changed')`; `require(equal and independent, 'Warm-start parameters not equal/independent')`; `require(delta <= 1e-06, 'CPU inference is not repeatable')`

### [v3_lite/check_phase2.py:79 — preservation](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/check_phase2.py#L79)

- 입력: `out`
- 반환식: `record`
- 호출 관계: `(ROOT / name).is_file`, `(ROOT / name).stat`, `before['files'].items`, `create_json`, `dict`, `json.dumps`, `len`, `phase1_hashes.items`, `print`, `read_json`, `require`, `sha`, `subprocess.check_output`, `subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip`, `subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=V2, text=True).strip`
- 검증/예외: `require(not changed and root_head == before['root_head'] and (v2_head == before['v2_head']), 'Preexisting files/HEAD changed')`; `require(not hash_changes, 'Existing required v2 documents changed')`

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:17 — require](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L17)

- 입력: `ok, message`
- 반환식: 명시 반환값 없음
- 호출 관계: `ValueError`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:21 — sha](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L21)

- 입력: `path`
- 반환식: `value.hexdigest()`
- 호출 관계: `Path`, `Path(path).open`, `hashlib.sha256`, `iter`, `stream.read`, `value.hexdigest`, `value.update`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:28 — read](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L28)

- 입력: `path`
- 반환식: `json.loads(Path(path).read_text(encoding='utf-8-sig'))`
- 호출 관계: `Path`, `Path(path).read_text`, `json.loads`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:32 — relative_file](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L32)

- 입력: `root, spec`
- 반환식: `path`
- 호출 관계: `(root / name).resolve`, `Path`, `Path(name).is_absolute`, `Path(root).resolve`, `isinstance`, `path.is_file`, `path.is_relative_to`, `require`, `sha`
- 검증/예외: `require(isinstance(name, str) and (not Path(name).is_absolute()) and (':' not in name) and ('\\' not in name), 'Relative artifact path required')`; `require(path.is_relative_to(root) and path.is_file(), 'Missing/escaping bundle artifact')`; `require(sha(path) == spec['sha256'], 'Bundle artifact SHA mismatch')`

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:41 — compatible_tokenizer](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L41)

- 입력: `metadata, tokenizer`
- 반환식: 명시 반환값 없음
- 호출 관계: `actual.pop`, `dict`, `expected.pop`, `require`, `tokenizer_behavior`, `tokenizer_metadata`
- 검증/예외: `require(expected == actual, 'Tokenizer content/contract mismatch')`; `require(metadata['tokenizer_behavior'] == tokenizer_behavior(tokenizer), 'Tokenizer probe mismatch')`

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:51 — load_model](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L51)

- 입력: `path, expected_sha, tokenizer, *, arm=None, seed=None, bindings=None, legacy=False`
- 반환식: `(model, metadata)`
- 호출 관계: `ElectraConfig.from_dict`, `ElectraModel`, `RiskSpeechClassifier`, `checkpoint.get`, `compatible_tokenizer`, `config.to_dict`, `ext.get`, `list`, `metadata['encoder_config'].get`, `model.eval`, `model.load_state_dict`, `model.modules`, `module._buffers.items`, `require`, `sha`, `torch.arange`, `torch.arange(tensor.shape[-1], dtype=tensor.dtype).expand`, `torch.arange(tensor.shape[-1], dtype=tensor.dtype).expand(tensor.shape).clone`, `torch.device`, `torch.load`, `torch.zeros`, `validate_checkpoint_metadata`, `validate_model_config`
- 검증/예외: `require(sha(path) == expected_sha, 'Checkpoint SHA mismatch')`; `validate_checkpoint_metadata(checkpoint)`; `require(ext.get('schema') == 'exploratory-checkpoint/1' and ext['arm'] == arm and (ext['seed'] == seed) and (ext['epoch'] == 3), 'Wrong frozen research checkpoint')`; `require(ext['bindings'] == bindings, 'Checkpoint data bindings mismatch')`; `require(ext['policy']['human_approved'] is False and ext['policy']['deployment_approved'] is False, 'Research checkpoint approval mismatch')`; `require(name in ('position_ids', 'token_type_ids') and name in module._non_persistent_buffers_set, 'Unexpected meta buffer')`

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:81 — raw_logits](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L81)

- 입력: `model, tokenizer, inputs, *, batch_size=8`
- 반환식: `values`
- 호출 관계: `build_model_input`, `features.append`, `getattr`, `joined.tolist`, `len`, `model`, `range`, `require`, `tokenizer.pad`, `torch.cat`, `torch.inference_mode`, `torch.isfinite`, `torch.isfinite(joined).all`, `torch.isfinite(joined).all().item`, `values.extend`
- 검증/예외: `require(joined.shape == (len(features), 9) and torch.isfinite(joined).all().item(), 'Invalid model logits')`

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:99 — validate_request](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L99)

- 입력: `request`
- 반환식: `(history, current)`
- 호출 관계: `all`, `current.strip`, `isinstance`, `len`, `request.get`, `require`, `set`, `t.strip`
- 검증/예외: `require(isinstance(request, dict) and set(request) <= {'history_texts', 'current_text'}, 'Unknown request fields')`; `require(isinstance(history, list) and len(history) <= 100 and all((isinstance(t, str) and t.strip() and (len(t) <= 32000) for t in history)), 'Invalid history_texts')`; `require(isinstance(current, str) and current.strip() and (len(current) <= 32000), 'Invalid current_text')`

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:107 — output_response](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L107)

- 입력: `values, thresholds, *, seed, model_sha`
- 반환식: `dict(ok=True, status='success', http_status=200, result=dict(risk_probability=p[0], risk_score=100 * p[0], is_phishing=p[0] >= thresholds[0], type_probabilities=dict(zip(LABELS, p[1:])), detected_types=[l for i, l in enumerate(LABELS, 1) if`
- 호출 관계: `all`, `dict`, `enumerate`, `len`, `math.exp`, `math.isfinite`, `require`, `type`, `zip`
- 검증/예외: `require(len(values) == 9 and all((math.isfinite(v) for v in values)), 'Invalid logits')`; `require(len(thresholds) == 9 and all((type(v) in (float, int) and math.isfinite(v) and (0 <= v <= 1) for v in thresholds)), 'Invalid thresholds')`

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:139 — serve_request](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L139)

- 입력: `predictor, request`
- 반환식: `dict(ok=False, status='error', http_status=status, result=None, error=dict(code=code))`; `failure('NOT_READY', 503)`; `predictor.predict(request)`; `failure('INVALID_REQUEST', 400)`; `failure('INPUT_TOO_LONG', 422)`; `failure('TOKENIZER_CONTRACT', 500)`; `failure('MODEL_INFERENCE_ERROR', 500)`
- 호출 관계: `dict`, `failure`, `predictor.predict`, `validate_request`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:119 — ResearchPredictor.__init__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L119)

- 입력: `self, bundle=HERE, seed=42, *, expected_manifest_sha=None`
- 반환식: 명시 반환값 없음
- 호출 관계: `AutoTokenizer.from_pretrained`, `Path`, `Path(bundle).resolve`, `isinstance`, `list`, `load_model`, `read`, `relative_file`, `require`, `sha`, `str`, `type`
- 검증/예외: `require(isinstance(expected_manifest_sha, str) and sha(self.bundle / 'bundle_manifest.json') == expected_manifest_sha, 'Trusted bundle manifest SHA required')`; `require(m['schema'] == 'research-server-bundle/1' and m['deployment_approved'] is False and (m['human_approved'] is False), 'Not a research bundle')`; `require(type(seed) is int and str(seed) in m['models'], 'Unregistered seed')`; `require(m['label_order'] == list(LABELS) and m['thresholds'] == [0.5] * 9, 'Frozen inference contract changed')`

### [v3_lite/handoff/research_20261117_v1/core_runtime.py:134 — ResearchPredictor.predict](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/core_runtime.py#L134)

- 입력: `self, request`
- 반환식: `output_response(raw_logits(self.model, self.tokenizer, [(history, current)])[0], self.thresholds, seed=self.seed, model_sha=self.model_sha)`
- 호출 관계: `output_response`, `raw_logits`, `validate_request`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/join_model.py:8 — require](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/join_model.py#L8)

- 입력: `condition, message`
- 반환식: 명시 반환값 없음
- 호출 관계: `ValueError`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/join_model.py:12 — join](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/join_model.py#L12)

- 입력: `manifest_path, output`
- 반환식: `dict(path=str(target), bytes=size, sha256=total.hexdigest(), parts=len(m['parts']))`
- 호출 관계: `(path.parent / part['name']).resolve`, `FileExistsError`, `Path`, `Path(manifest_path).resolve`, `Path(output).resolve`, `check.hexdigest`, `check.update`, `dict`, `enumerate`, `f.read`, `hashlib.sha256`, `iter`, `json.loads`, `len`, `os.fsync`, `os.rename`, `path.read_text`, `require`, `source.open`, `str`, `stream.fileno`, `stream.flush`, `stream.write`, `target.exists`, `target.parent.mkdir`, `target.with_name`, `temp.open`, `total.hexdigest`, `total.update`
- 검증/예외: `require(m['schema'] == 'lossless-model-parts/1', 'Wrong transfer schema')`; `require(size == m['bytes'] and total.hexdigest() == m['sha256'], 'Full model mismatch')`; `require(part['index'] == index and Path(part['name']).name == part['name'], 'Unsafe part name/order')`; `require(source.parent == path.parent, 'Part escapes transfer directory')`; `require(n == part['bytes'] and check.hexdigest() == part['sha256'], 'Part mismatch: ' + part['name'])`

### [v3_lite/handoff/research_20261117_v1/runtime.py:50 — serve_request](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/runtime.py#L50)

- 입력: `predictor, request`
- 반환식: `core.serve_request(predictor, request)`
- 호출 관계: `core.serve_request`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/runtime.py:16 — V3Predictor.__init__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/runtime.py#L16)

- 입력: `self, bundle=HERE, *, expected_manifest_sha`
- 반환식: 명시 반환값 없음
- 호출 관계: `AutoTokenizer.from_pretrained`, `Path`, `Path(bundle).resolve`, `core.load_model`, `core.read`, `core.relative_file`, `core.require`, `core.sha`, `envelope.get`, `ext.get`, `list`, `str`, `torch.load`
- 검증/예외: `core.require(core.sha(self.bundle / 'bundle_manifest.json') == expected_manifest_sha, 'Trusted manifest SHA mismatch')`; `core.require(m['schema'] == 'v3-lite-inference-bundle/1' and m['label_order'] == list(LABELS) and (m['thresholds'] == [0.5] * 9) and (m['purpose'] == 'internal_experiment') and (m['human_reviewed'] is False) and (m['deployment_allowed'] is False), 'Invalid research bundle')`; `core.require(envelope.get('inference_only') is True and envelope.get('optimizer_state_dict') == {} and (ext.get('schema') == 'v3-lite-checkpoint/1') and (ext.get('parent_sha256') == m['parent_sha256']) and (ext.get('epoch') == m['epoch']) and (ext.get('human_reviewed') is False), 'Invalid v3 inference lineage')`

### [v3_lite/handoff/research_20261117_v1/runtime.py:40 — V3Predictor.predict](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/runtime.py#L40)

- 입력: `self, request`
- 반환식: `response`
- 호출 관계: `core.output_response`, `core.raw_logits`, `core.validate_request`, `response['result'].update`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py:31 — input_contract](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py#L31)

- 입력: ``
- 반환식: `{'version': INPUT_CONTRACT_VERSION, 'max_history_utterances': MAX_HISTORY_UTTERANCES, 'max_sequence_length': MAX_SEQUENCE_LENGTH, 'sequence_format': '[CLS] history [SEP] current [SEP]', 'history_separator': '\n', 'overflow_rule': 'drop_olde`
- 호출 관계:
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py:43 — tokenizer_metadata](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py#L43)

- 입력: `tokenizer: Any`
- 반환식: `{'name': getattr(tokenizer, 'name_or_path', None), 'class_name': type(tokenizer).__module__ + '.' + type(tokenizer).__qualname__, 'vocab_size': getattr(tokenizer, 'vocab_size', len(vocabulary)), 'vocab_sha256': hashlib.sha256(serialized_voc`
- 호출 관계: `ValueError`, `callable`, `dict`, `getattr`, `getattr(tokenizer, 'init_kwargs', {}).get`, `hashlib.sha256`, `hashlib.sha256(serialized_vocab).hexdigest`, `isinstance`, `json.dumps`, `json.dumps(dict(vocabulary), sort_keys=True, ensure_ascii=False).encode`, `json.loads`, `len`, `tokenizer.get_vocab`, `type`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py:68 — tokenizer_behavior](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py#L68)

- 입력: `tokenizer: Any`
- 반환식: `[{'text': probe, 'input_ids': prepared.input_ids, 'attention_mask': prepared.attention_mask, 'token_type_ids': prepared.token_type_ids} for probe in TOKENIZER_PROBES for prepared in [build_model_input([], probe, tokenizer=tokenizer)]]`
- 호출 관계: `build_model_input`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py:85 — encoder_config](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py#L85)

- 입력: `model: Any`
- 반환식: `result`
- 호출 관계: `config.to_json_string`, `json.loads`, `result.pop`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py:95 — read_checkpoint](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py#L95)

- 입력: `path: str | Path, *, map_location: str | torch.device='cpu'`
- 반환식: `checkpoint`
- 호출 관계: `CheckpointCompatibilityError`, `isinstance`, `torch.load`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py:102 — _required](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py#L102)

- 입력: `mapping: Mapping[str, Any], names: tuple[str, ...], location: str`
- 반환식: 명시 반환값 없음
- 호출 관계: `', '.join`, `CheckpointCompatibilityError`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py:108 — validate_checkpoint_metadata](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py#L108)

- 입력: `checkpoint: Mapping[str, Any]`
- 반환식: `metadata`
- 호출 관계: `CheckpointCompatibilityError`, `_required`, `any`, `checkpoint.get`, `input_contract`, `isinstance`, `len`, `list`, `metadata.get`, `metadata['data_version'].strip`, `result.get`, `type`, `value.strip`, `zip`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py:185 — validate_model_config](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py#L185)

- 입력: `metadata: Mapping[str, Any], model: Any`
- 반환식: 명시 반환값 없음
- 호출 관계: `CheckpointCompatibilityError`, `encoder_config`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py:190 — validate_tokenizer](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py#L190)

- 입력: `metadata: Mapping[str, Any], tokenizer: Any`
- 반환식: 명시 반환값 없음
- 호출 관계: `CheckpointCompatibilityError`, `isinstance`, `metadata.get`, `tokenizer_behavior`, `tokenizer_metadata`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py:202 — load_training_checkpoint](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/checkpoint.py#L202)

- 입력: `path: str | Path, model: Any, *, tokenizer: Any, optimizer: torch.optim.Optimizer | None=None, map_location: str | torch.device='cpu', checkpoint: dict[str, Any] | None=None`
- 반환식: `loaded`
- 호출 관계: `CheckpointCompatibilityError`, `copy.deepcopy`, `model.load_state_dict`, `optimizer.load_state_dict`, `read_checkpoint`, `temporary_model.load_state_dict`, `temporary_model.state_dict`, `validate_checkpoint_metadata`, `validate_model_config`, `validate_tokenizer`
- 검증/예외: `validate_checkpoint_metadata(loaded)`

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py:75 — make_training_dataloader](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py#L75)

- 입력: `dataset: RiskSpeechDataset, *, tokenizer: Any, batch_size: int, shuffle: bool=True, seed: int=42`
- 반환식: `DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, collate_fn=DynamicPaddingCollator(tokenizer), generator=generator, num_workers=0)`
- 호출 관계: `DataLoader`, `DynamicPaddingCollator`, `ValueError`, `isinstance`, `torch.Generator`, `torch.Generator().manual_seed`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py:19 — RiskSpeechDataset.__init__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py#L19)

- 입력: `self, samples: Sequence[TrainingSample], *, tokenizer: Any`
- 반환식: 명시 반환값 없음
- 호출 관계: `TypeError`, `ValueError`, `any`, `build_model_input`, `float`, `isinstance`, `len`, `self.items.append`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py:41 — RiskSpeechDataset.__len__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py#L41)

- 입력: `self`
- 반환식: `len(self.items)`
- 호출 관계: `len`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py:44 — RiskSpeechDataset.__getitem__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py#L44)

- 입력: `self, index: int`
- 반환식: `self.items[index]`
- 호출 관계:
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py:49 — DynamicPaddingCollator.__init__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py#L49)

- 입력: `self, tokenizer: Any`
- 반환식: 명시 반환값 없음
- 호출 관계: `TokenizerContractError`, `getattr`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py:54 — DynamicPaddingCollator.__call__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/dataset.py#L54)

- 입력: `self, items: list[dict[str, Any]]`
- 반환식: `{'input_ids': batch['input_ids'], 'attention_mask': batch['attention_mask'], 'token_type_ids': batch['token_type_ids'], 'risk_target': torch.tensor([[item['risk_target']] for item in items], dtype=torch.float32), 'type_targets': torch.tenso`
- 호출 관계: `ValueError`, `self.tokenizer.pad`, `torch.tensor`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py:35 — sha256_file](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py#L35)

- 입력: `path: Path`
- 반환식: `digest.hexdigest()`
- 호출 관계: `digest.hexdigest`, `digest.update`, `hashlib.sha256`, `iter`, `path.open`, `stream.read`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py:43 — _write_json](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py#L43)

- 입력: `path: Path, value: object`
- 반환식: 명시 반환값 없음
- 호출 관계: `json.dumps`, `path.write_text`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py:47 — _git](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py#L47)

- 입력: `*args: str`
- 반환식: `result.stdout.strip() if result.returncode == 0 else 'not_recorded'`
- 호출 관계: `result.stdout.strip`, `subprocess.run`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py:52 — _duplicates](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py#L52)

- 입력: `label_rows: list[dict], tuned_rows: list[dict]`
- 반환식: `{'identical_text_groups': len(repeated), 'utterances_in_identical_text_groups': sum(map(len, repeated)), 'same_conversation_groups': sum((len({row['conversation_id'] for row in rows}) == 1 for rows in repeated)), 'conflicting_risk_groups': `
- 호출 관계: `by_text.values`, `by_text[row['tuned_text']].append`, `defaultdict`, `len`, `map`, `sum`, `tuple`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py:66 — _restore_history](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py#L66)

- 입력: `report_dir: Path, checkpoint: dict, observation_path: Path`
- 반환식: `{'batch_cumulative_observations': observations['batch_cumulative'], 'epoch_losses': epoch_losses, 'batch_specific_losses': 'not_recorded', 'training_started_at': 'not_recorded', 'training_finished_at': 'not_recorded', 'training_duration_sec`
- 호출 관계: `csv.DictWriter`, `json.loads`, `observation_path.read_text`, `path.open`, `writer.writeheader`, `writer.writerow`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py:98 — _latency_summary](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py#L98)

- 입력: `values: list[float]`
- 반환식: `{'n': len(values), 'mean_ms': statistics.mean(values), 'median_ms': statistics.median(values), 'p50_ms': float(np.percentile(values, 50)), 'p95_ms': float(np.percentile(values, 95)), 'min_ms': min(values), 'max_ms': max(values)}`
- 호출 관계: `float`, `len`, `max`, `min`, `np.percentile`, `statistics.mean`, `statistics.median`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py:106 — _write_csv](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py#L106)

- 입력: `path: Path, per_label: dict`
- 반환식: 명시 반환값 없음
- 호출 관계: `csv.DictWriter`, `json.dumps`, `path.open`, `writer.writeheader`, `writer.writerow`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py:118 — _svg_charts](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py#L118)

- 입력: `report_dir: Path, metrics: dict, history: dict`
- 반환식: 명시 반환값 없음
- 호출 관계: `' '.join`, `''.join`, `(report_dir / 'loss_trend.svg').write_text`, `(report_dir / 'per_label_f1.svg').write_text`, `(report_dir / 'risk_confusion.svg').write_text`, `enumerate`, `max`, `min`, `range`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py:150 — _markdown](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py#L150)

- 입력: `metrics: dict, benchmark: dict, reproducibility: dict, history: dict`
- 반환식: `f"# KoELECTRA v1 정량 평가\n\n**평가 집합: TRAIN (IN-SAMPLE), {risk['n']}발화.** 모델이 학습한 발화를 다시 평가한 결과이며 독립 검증·테스트 성능이 아닙니다.\n\n## 학습 기록\n\n- 68개 대화, {risk['n']}발화; 피싱 {risk['positive']}, 정상 {risk['negative']}.\n- 1 epoch, 183 optimizer steps, AdamW,`; `'N/A' if value is None else f'{value:.4f}'`
- 호출 관계: `chr`, `chr(10).join`, `fmt`, `types['per_label'].items`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py:209 — main](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/evaluate_cli.py#L209)

- 입력: `argv: list[str] | None=None`
- 반환식: `0`
- 호출 관계: `(args.prepared_dir / 'provenance.json').read_text`, `(args.report_dir / 'metrics_report.md').write_text`, `InferenceInput`, `Path`, `Path(CHECKPOINT_PATH).resolve`, `ValueError`, `__import__`, `__import__('os').cpu_count`, `_duplicates`, `_git`, `_latency_summary`, `_markdown`, `_restore_history`, `_svg_charts`, `_write_csv`, `_write_json`, `actual_risk.append`, `actual_types.append`, `any`, `argparse.ArgumentParser`, `args.checkpoint.resolve`, `args.checkpoint.stat`, `args.report_dir.mkdir`, `batch_latency.append`, `batch_length.append`, `binary_metrics`, `bool`, `build_model_input`, `build_safe_training_samples`, `by_length[name].append`, `dict`, `gc.collect`, `int`, `json.dumps`, `json.loads`, `len`, `list`, `load_checkpoint_inference`, `load_koelectra_tokenizer`, `max`, `multilabel_metrics`, `np.argmax`, `np.argmin`, `np.argsort`, `observed_memory.append`, `parser.add_argument`, `parser.error`, `parser.parse_args`, `platform.python_version`, `predicted_risk.append`, `predicted_types.append`, `print`, `range`, `read_checkpoint`, `read_jsonl`, `session.predict`, `sha256_file`, `statistics.mean`, `str`, `sum`, `time.perf_counter`, `torch.get_num_threads`, `validate_checkpoint_metadata`, `warm_timings.append`, `working_set_bytes`, `zip`
- 검증/예외: `validate_checkpoint_metadata(checkpoint)`

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/inference.py:63 — logits_to_outputs](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/inference.py#L63)

- 입력: `output: ModelOutput, thresholds: ThresholdConfig | None=None`
- 반환식: `results`
- 호출 관계: `InferenceOutput`, `ThresholdConfig`, `ValueError`, `dict`, `results.append`, `risk.detach`, `torch.isfinite`, `torch.isfinite(risk).all`, `torch.isfinite(types).all`, `torch.sigmoid`, `torch.sigmoid(risk.detach()).cpu`, `torch.sigmoid(risk.detach()).cpu().tolist`, `torch.sigmoid(types.detach()).cpu`, `torch.sigmoid(types.detach()).cpu().tolist`, `types.detach`, `zip`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/inference.py:93 — infer_batch](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/inference.py#L93)

- 입력: `model: RiskSpeechClassifier, inputs: Sequence[InferenceInput], *, tokenizer: Any, thresholds: ThresholdConfig | None=None, device: str | torch.device | None=None`
- 반환식: `logits_to_outputs(output, thresholds)`; `[]`
- 호출 관계: `TypeError`, `batch['attention_mask'].to`, `batch['input_ids'].to`, `batch['token_type_ids'].to`, `build_model_input`, `features.append`, `isinstance`, `logits_to_outputs`, `model`, `model.eval`, `model.parameters`, `model.to`, `next`, `tokenizer.pad`, `torch.device`, `torch.no_grad`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/inference.py:143 — load_checkpoint_inference](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/inference.py#L143)

- 입력: `checkpoint_path: str | Path, *, tokenizer: Any, thresholds: ThresholdConfig | None=None, device: str | torch.device | None=None, model: RiskSpeechClassifier | None=None`
- 반환식: `CheckpointInference(classifier, tokenizer, selected_thresholds, dict(metadata), chosen_device, selected_thresholds.version)`
- 호출 관계: `CheckpointInference`, `RiskSpeechClassifier`, `ThresholdConfig`, `classifier.eval`, `classifier.to`, `dict`, `load_training_checkpoint`, `metadata.get`, `read_checkpoint`, `torch.cuda.is_available`, `torch.device`, `validate_checkpoint_metadata`, `validate_tokenizer`
- 검증/예외: `validate_checkpoint_metadata(checkpoint)`

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/inference.py:30 — ThresholdConfig.__post_init__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/inference.py#L30)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `MappingProxyType`, `ValueError`, `any`, `float`, `isinstance`, `math.isfinite`, `normalized.values`, `object.__setattr__`, `self.version.strip`, `set`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/inference.py:136 — CheckpointInference.predict](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/inference.py#L136)

- 입력: `self, inputs: Sequence[InferenceInput]`
- 반환식: `infer_batch(self.model, inputs, tokenizer=self.tokenizer, thresholds=self.thresholds, device=self.device)`
- 호출 관계: `infer_batch`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/labels.py:20 — to_multi_hot](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/labels.py#L20)

- 입력: `labels: Iterable[str]`
- 반환식: `targets`
- 호출 관계: `ValueError`, `isinstance`, `iter`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/metrics.py:10 — _auc](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/metrics.py#L10)

- 입력: `y: np.ndarray, p: np.ndarray`
- 반환식: `float((positive_ranks - positive * (positive + 1) / 2) / (positive * negative))`; `None`
- 호출 관계: `float`, `int`, `len`, `np.arange`, `np.argsort`, `np.unique`, `ranks[np.argsort(order)][y == 1].sum`, `y.sum`, `zip`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/metrics.py:25 — _average_precision](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/metrics.py#L25)

- 입력: `y: np.ndarray, p: np.ndarray`
- 반환식: `float(total)`; `None`
- 호출 관계: `float`, `int`, `len`, `np.argsort`, `sorted_y[start:end].sum`, `y.sum`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/metrics.py:46 — binary_metrics](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/metrics.py#L46)

- 입력: `targets: object, probabilities: object, threshold: float=0.5`
- 반환식: `result`
- 호출 관계: `((p < 0) | (p > 1)).any`, `((y == 0) & (predicted == 0)).sum`, `((y == 0) & (predicted == 1)).sum`, `((y == 1) & (predicted == 0)).sum`, `((y == 1) & (predicted == 1)).sum`, `(p >= threshold).astype`, `ValueError`, `_auc`, `_average_precision`, `float`, `int`, `len`, `mask.any`, `mask.sum`, `np.asarray`, `np.isfinite`, `np.isfinite(p).all`, `np.isin`, `np.isin(y, [0, 1]).all`, `np.max`, `np.mean`, `np.median`, `np.min`, `np.std`, `result['undefined_reasons'].update`, `y.astype`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/metrics.py:94 — multilabel_metrics](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/metrics.py#L94)

- 입력: `targets: object, probabilities: object, threshold: float=0.5`
- 반환식: `{'n': len(y), 'threshold': threshold, 'per_label': per_label, 'micro': {'precision': micro_precision, 'recall': micro_recall, 'f1': micro_f1, **counts}, 'macro': {'precision': defined_mean('precision'), 'recall': defined_mean('recall'), 'f1`; `float(np.mean(values)) if values else None`
- 호출 관계: `ValueError`, `binary_metrics`, `defined_mean`, `enumerate`, `float`, `len`, `np.all`, `np.asarray`, `np.mean`, `per_label.items`, `per_label.values`, `sum`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/model.py:24 — RiskSpeechClassifier.__init__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/model.py#L24)

- 입력: `self, encoder: ElectraModel | None=None, *, model_revision: str | None=None`
- 반환식: 명시 반환값 없음
- 호출 관계: `ElectraModel.from_pretrained`, `ValueError`, `nn.Linear`, `super`, `super().__init__`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/model.py:35 — RiskSpeechClassifier.forward](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/model.py#L35)

- 입력: `self, input_ids: torch.Tensor, attention_mask: torch.Tensor, token_type_ids: torch.Tensor`
- 반환식: `ModelOutput(risk_logits=self.risk_classifier(cls_state), type_logits=self.type_classifier(cls_state))`
- 호출 관계: `ModelOutput`, `ValueError`, `self.encoder`, `self.risk_classifier`, `self.type_classifier`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py:31 — row_hash](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py#L31)

- 입력: `row: dict[str, Any]`
- 반환식: `hashlib.sha256(encoded.encode('utf-8')).hexdigest()`
- 호출 관계: `encoded.encode`, `hashlib.sha256`, `hashlib.sha256(encoded.encode('utf-8')).hexdigest`, `json.dumps`, `row.get`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py:38 — _index](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py#L38)

- 입력: `rows: list[dict[str, Any]]`
- 반환식: `indexed`
- 호출 관계: `ValueError`, `row.get`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py:48 — _source_rows](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py#L48)

- 입력: `commit: str, path: str, conversation_id: str`
- 반환식: `[row for row in rows if row.get('conversation_id') == conversation_id]`
- 호출 관계: `FileNotFoundError`, `ValueError`, `json.loads`, `line.strip`, `path.endswith`, `path.startswith`, `result.stdout.decode`, `result.stdout.decode('utf-8-sig').splitlines`, `row.get`, `subprocess.run`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py:58 — _decision](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py#L58)

- 입력: `row: dict[str, Any], approval: dict[str, Any] | None, correction: dict[str, Any] | None, commit: str`
- 반환식: `None`; `'utterance_approval_missing'`; `'approval_scope_or_version_unverified'`; `'invalid_labels'`; `'backend_correction_missing'`; `'masked_text_missing'`; `'backend_correction_unverified'`; `'backend_correction_unverified'`; `'backend_mask_contract_mismatch'`; `'risk_type_unresolved'`; `'invalid_approval_status_or_labels'`
- 호출 관계: `TOKEN_PATTERN.findall`, `any`, `approval.get`, `approval['evidence_url'].strip`, `approval['reviewer'].strip`, `bool`, `correction.get`, `correction['tuned_text'].count`, `correction['tuned_text'].strip`, `correction['validation_source'].strip`, `isinstance`, `item.strip`, `len`, `masked.strip`, `row.get`, `row_hash`, `type`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py:110 — prepare](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py#L110)

- 입력: `manifest: list[dict[str, Any]], approvals: list[dict[str, Any]], corrections: list[dict[str, Any]], commit: str`
- 반환식: `(labels_out, tuned_out, pending)`
- 호출 관계: `ValueError`, `_decision`, `_index`, `_source_rows`, `approval_by_key.get`, `approval_by_key.get(key, {}).get`, `conversation_id.startswith`, `correction_by_key.get`, `int`, `labels_out.append`, `len`, `pending.append`, `range`, `row.get`, `row_hash`, `seen.add`, `set`, `tuned_out.append`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py:171 — prepare_team_approved](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py#L171)

- 입력: `manifest: list[dict[str, Any]], commit: str`
- 반환식: `(labels_out, tuned_out, pending)`
- 호출 관계: `EMAIL_PATTERN.search`, `PHONE_PATTERN.search`, `RRN_PATTERN.search`, `TOKEN_PATTERN.findall`, `ValueError`, `_source_rows`, `any`, `entry.get`, `entry['source'].strip`, `isinstance`, `labels_out.append`, `len`, `map`, `masked.strip`, `pending.append`, `pending.extend`, `range`, `re.fullmatch`, `row.get`, `row_hash`, `seen.add`, `set`, `tuned_out.append`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py:245 — _write_jsonl](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py#L245)

- 입력: `path: Path, rows: list[dict[str, Any]]`
- 반환식: 명시 반환값 없음
- 호출 관계: `''.join`, `json.dumps`, `path.write_text`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py:249 — _file_sha256](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py#L249)

- 입력: `path: Path | None`
- 반환식: `hashlib.sha256(path.read_bytes()).hexdigest() if path is not None else None`
- 호출 관계: `hashlib.sha256`, `hashlib.sha256(path.read_bytes()).hexdigest`, `path.read_bytes`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py:253 — main](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/prepare_training_inputs.py#L253)

- 입력: `argv: list[str] | None=None`
- 반환식: `0`
- 호출 관계: `(args.output_dir / 'provenance.json').write_text`, `Counter`, `Path`, `_file_sha256`, `_write_jsonl`, `argparse.ArgumentParser`, `args.manifest.read_text`, `args.output_dir.mkdir`, `dict`, `json.dumps`, `json.loads`, `len`, `parser.add_argument`, `parser.error`, `parser.parse_args`, `prepare`, `prepare_team_approved`, `print`, `re.fullmatch`, `read_jsonl`, `row.get`, `str`, `sum`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/splits.py:10 — plan_conversation_splits](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/splits.py#L10)

- 입력: `label_rows: Sequence[Mapping], tuned_rows: Sequence[Mapping], *, data_version: str, ratios: tuple[float, float, float]=(0.8, 0.1, 0.1), seed: int=42, group_by_source: bool=True`
- 반환식: `{'data_version': data_version, 'seed': seed, 'requested_ratios': dict(zip(names, ratios)), 'group_by_source': group_by_source, 'component_count': len(components), 'conversation_to_split': assignment, 'utterance_counts': {name: counts[name] `; `value`
- 호출 관계: `Counter`, `ValueError`, `abs`, `any`, `components.sort`, `defaultdict`, `dict`, `enumerate`, `find`, `groups.values`, `groups[find(conversation)].add`, `isinstance`, `join`, `len`, `list`, `max`, `random.Random`, `random.Random(seed).shuffle`, `row.get`, `sorted`, `sum`, `text.strip`, `value.strip`, `zip`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/tokenization.py:43 — load_koelectra_tokenizer](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/tokenization.py#L43)

- 입력: `revision: str | None=None`
- 반환식: `tokenizer`
- 호출 관계: `AutoConfig.from_pretrained`, `AutoTokenizer.from_pretrained`, `RuntimeError`, `TokenizerContractError`, `ValueError`, `isinstance`, `revision.strip`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/tokenization.py:68 — _encode_pair](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/tokenization.py#L68)

- 입력: `tokenizer: Any, history_texts: Sequence[str], current_text: str`
- 반환식: `TokenizedInput(input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids, used_history_texts=list(history_texts), dropped_history_count=0, token_count=size)`
- 호출 관계: `'\n'.join`, `TokenizedInput`, `TokenizerContractError`, `any`, `len`, `list`, `token_type_ids.index`, `tokenizer`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/tokenization.py:119 — build_model_input](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/tokenization.py#L119)

- 입력: `history_texts: Sequence[str], current_text: str, *, tokenizer: Any`
- 반환식: `TokenizedInput(input_ids=result.input_ids, attention_mask=result.attention_mask, token_type_ids=result.token_type_ids, used_history_texts=list(used), dropped_history_count=dropped, token_count=result.token_count)`
- 호출 관계: `InputTooLongError`, `TokenizedInput`, `TokenizerContractError`, `ValueError`, `_encode_pair`, `any`, `current_text.strip`, `getattr`, `isinstance`, `len`, `list`, `text.strip`, `used.pop`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/tokenization.py:20 — InputTooLongError.__init__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/tokenization.py#L20)

- 입력: `self, token_count: int, dropped_history_count: int`
- 반환식: 명시 반환값 없음
- 호출 관계: `super`, `super().__init__`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/train_cli.py:17 — read_jsonl](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/train_cli.py#L17)

- 입력: `path: Path`
- 반환식: `rows`
- 호출 관계: `ValueError`, `enumerate`, `isinstance`, `json.loads`, `line.strip`, `path.open`, `rows.append`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/train_cli.py:33 — build_safe_training_samples](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/train_cli.py#L33)

- 입력: `label_rows: list[Mapping[str, Any]], tuned_rows: list[Mapping[str, Any]]`
- 반환식: `(build_training_samples(label_rows, safe_tuned), initial.statistics)`
- 호출 관계: `build_training_samples`, `row.get`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/train_cli.py:44 — main](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/train_cli.py#L44)

- 입력: `argv: list[str] | None=None`
- 반환식: `0`; `0`
- 호출 관계: `FileExistsError`, `Path`, `TrainingConfig`, `ValueError`, `argparse.ArgumentParser`, `build_safe_training_samples`, `create_training_model`, `json.dumps`, `load_koelectra_tokenizer`, `parser.add_argument`, `parser.parse_args`, `path.exists`, `print`, `read_jsonl`, `train_model`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py:90 — set_training_seed](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py#L90)

- 입력: `seed: int`
- 반환식: 명시 반환값 없음
- 호출 관계: `random.seed`, `torch.cuda.is_available`, `torch.cuda.manual_seed_all`, `torch.manual_seed`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py:97 — create_training_model](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py#L97)

- 입력: `config: TrainingConfig`
- 반환식: `RiskSpeechClassifier(**{'model_revision': config.model_revision} if config.model_revision is not None else {})`
- 호출 관계: `RiskSpeechClassifier`, `set_training_seed`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py:106 — compute_losses](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py#L106)

- 입력: `output: ModelOutput, risk_target: torch.Tensor, type_targets: torch.Tensor, *, lambda_risk: float=1.0, lambda_type: float=1.0`
- 반환식: `LossOutput(risk_loss=risk_loss, type_loss=type_loss, total_loss=lambda_risk * risk_loss + lambda_type * type_loss)`
- 호출 관계: `LossOutput`, `TypeError`, `ValueError`, `criterion`, `isinstance`, `math.isfinite`, `nn.BCEWithLogitsLoss`, `risk_target.is_floating_point`, `type_targets.is_floating_point`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py:131 — _metadata](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py#L131)

- 입력: `model: RiskSpeechClassifier, tokenizer: Any, config: TrainingConfig, device: torch.device`
- 반환식: `{'checkpoint_schema_version': CHECKPOINT_SCHEMA_VERSION, 'model_name': BASE_MODEL_NAME, 'python_version': platform.python_version(), 'torch_version': str(torch.__version__), 'transformers_version': transformers_version, 'base_model': BASE_M`
- 호출 관계: `asdict`, `encoder_config`, `getattr`, `input_contract`, `list`, `platform.python_version`, `str`, `tokenizer_behavior`, `tokenizer_metadata`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py:164 — train_model](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py#L164)

- 입력: `model: RiskSpeechClassifier, samples: Sequence[TrainingSample], tokenizer: Any, config: TrainingConfig, *, checkpoint_path: str | Path, device: str | torch.device | None=None, log_dir: str | Path | None=None`
- 반환식: `TrainingResult(epoch_losses, len(dataset), step_count, path, journal.path)`
- 호출 관계: `EpochLoss`, `FloatingPointError`, `Path`, `RiskSpeechDataset`, `TrainingJournal`, `TrainingResult`, `ValueError`, `_metadata`, `any`, `asdict`, `batch.items`, `compute_losses`, `enumerate`, `epoch_losses.append`, `journal.log_batch`, `journal.log_epoch`, `len`, `list`, `losses.risk_loss.detach`, `losses.risk_loss.detach().item`, `losses.total_loss.backward`, `losses.total_loss.detach`, `losses.total_loss.detach().item`, `losses.type_loss.detach`, `losses.type_loss.detach().item`, `make_training_dataloader`, `model`, `model.parameters`, `model.state_dict`, `model.to`, `model.train`, `optimizer.state_dict`, `optimizer.step`, `optimizer.zero_grad`, `path.parent.mkdir`, `print`, `range`, `set_training_seed`, `str`, `time.perf_counter`, `torch.cuda.is_available`, `torch.device`, `torch.isfinite`, `torch.optim.AdamW`, `torch.save`, `value.to`, `working_set_bytes`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py:43 — TrainingConfig.__post_init__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training.py#L43)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `ValueError`, `getattr`, `isinstance`, `math.isfinite`, `self.data_version.strip`, `value.strip`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_data.py:38 — _key](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_data.py#L38)

- 입력: `row: Mapping[str, Any]`
- 반환식: `(conversation_id, utterance_id)`
- 호출 관계: `ValueError`, `_order`, `conversation_id.strip`, `isinstance`, `row.get`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_data.py:47 — _order](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_data.py#L47)

- 입력: `utterance_id: object`
- 반환식: `utterance_id`; `int(match.group(1))`
- 호출 관계: `ValueError`, `_STRING_ID.fullmatch`, `int`, `isinstance`, `match.group`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_data.py:57 — _index](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_data.py#L57)

- 입력: `rows: Iterable[Mapping[str, Any]], statistics: Counter[str]`
- 반환식: `indexed`
- 호출 관계: `ValueError`, `_key`, `_order`, `ambiguous.add`, `indexed.pop`, `isinstance`, `set`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_data.py:83 — _targets](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_data.py#L83)

- 입력: `row: Mapping[str, Any]`
- 반환식: `(float(phishing), types)`
- 호출 관계: `ValueError`, `any`, `float`, `isinstance`, `row.get`, `to_multi_hot`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_data.py:105 — build_training_samples](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_data.py#L105)

- 입력: `label_rows: Iterable[Mapping[str, Any]], tuned_rows: Iterable[Mapping[str, Any]]`
- 반환식: `BuildResult(samples=samples, statistics=dict(statistics))`
- 호출 관계: `BuildResult`, `Counter`, `TrainingSample`, `_index`, `_order`, `_targets`, `defaultdict`, `dict`, `entries.sort`, `histories.values`, `histories[conversation_id].append`, `isinstance`, `label_row.get`, `len`, `row.get`, `samples.append`, `set`, `sorted`, `statistics.setdefault`, `str`, `tuned.items`, `value.strip`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py:13 — working_set_bytes](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py#L13)

- 입력: ``
- 반환식: `None`; `int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)`; `int(counters.working_set_size)`; `None`
- 호출 관계: `MemoryCounters`, `ctypes.byref`, `ctypes.sizeof`, `get_memory`, `get_process`, `int`, `resource.getrusage`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py:47 — TrainingJournal.__init__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py#L47)

- 입력: `self, base_dir: Path, metadata: dict`
- 반환식: 명시 반환값 없음
- 호출 관계: `(self.path / 'batches.jsonl').open`, `(self.path / 'epochs.jsonl').open`, `(self.path / 'run.json').open`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `datetime.now(timezone.utc).strftime`, `json.dump`, `os.fsync`, `self.path.mkdir`, `stream.fileno`, `stream.flush`, `uuid4`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py:60 — TrainingJournal._append](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py#L60)

- 입력: `stream, row: dict`
- 반환식: 명시 반환값 없음
- 호출 관계: `json.dumps`, `os.fsync`, `stream.fileno`, `stream.flush`, `stream.write`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py:65 — TrainingJournal.log_batch](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py#L65)

- 입력: `self, row: dict`
- 반환식: 명시 반환값 없음
- 호출 관계: `self._append`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py:68 — TrainingJournal.log_epoch](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py#L68)

- 입력: `self, row: dict`
- 반환식: 명시 반환값 없음
- 호출 관계: `self._append`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py:71 — TrainingJournal.close](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py#L71)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `self.batch.close`, `self.epoch.close`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py:75 — TrainingJournal.__enter__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py#L75)

- 입력: `self`
- 반환식: `self`
- 호출 관계:
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py:78 — TrainingJournal.__exit__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/training_log.py#L78)

- 입력: `self, exc_type, exc_value, traceback`
- 반환식: 명시 반환값 없음
- 호출 관계: `self.close`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py:29 — file_hash](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py#L29)

- 입력: `path: Path`
- 반환식: `digest.hexdigest()`
- 호출 관계: `digest.hexdigest`, `digest.update`, `hashlib.sha256`, `iter`, `path.open`, `stream.read`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py:37 — threshold_rows](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py#L37)

- 입력: `targets: np.ndarray, probabilities: np.ndarray, label: str`
- 반환식: `rows`
- 호출 관계: `binary_metrics`, `range`, `rows.append`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py:50 — distribution_row](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py#L50)

- 입력: `targets: np.ndarray, probabilities: np.ndarray, label: str`
- 반환식: `row`
- 호출 관계: `binary_metrics`, `float`, `int`, `len`, `np.count_nonzero`, `np.max`, `np.mean`, `np.median`, `np.min`, `np.percentile`, `np.sqrt`, `np.std`, `np.var`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py:77 — write_csv](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py#L77)

- 입력: `path: Path, rows: list[dict]`
- 반환식: 명시 반환값 없음
- 호출 관계: `csv.DictWriter`, `list`, `path.open`, `writer.writeheader`, `writer.writerows`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py:84 — svg_plots](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py#L84)

- 입력: `output_dir: Path, sweep: list[dict], targets: np.ndarray, probabilities: np.ndarray`
- 반환식: 명시 반환값 없음
- 호출 관계: `' '.join`, `''.join`, `(output_dir / 'probability_histograms.svg').write_text`, `(output_dir / 'threshold_f1.svg').write_text`, `enumerate`, `escape`, `int`, `max`, `neg.max`, `np.histogram`, `np.linspace`, `parts.append`, `pos.max`, `range`, `sum`, `zip`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py:133 — main](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/handoff/research_20261117_v1/vendor/risk_speech_ai/type_diagnostics.py#L133)

- 입력: ``
- 반환식: 명시 반환값 없음
- 호출 관계: `(output / 'diagnostic_metadata.json').write_text`, `InferenceInput`, `Path`, `ValueError`, `argparse.ArgumentParser`, `build_safe_training_samples`, `distribution_row`, `enumerate`, `file_hash`, `json.dumps`, `len`, `load_checkpoint_inference`, `load_koelectra_tokenizer`, `max`, `np.asarray`, `np.empty`, `output.mkdir`, `parser.add_argument`, `parser.error`, `parser.parse_args`, `paths.items`, `print`, `range`, `read_jsonl`, `session.predict`, `svg_plots`, `threshold_rows`, `tuple`, `write_csv`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/join_model.py:8 — require](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/join_model.py#L8)

- 입력: `condition, message`
- 반환식: 명시 반환값 없음
- 호출 관계: `ValueError`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/join_model.py:12 — join](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/join_model.py#L12)

- 입력: `manifest_path, output`
- 반환식: `dict(path=str(target), bytes=size, sha256=total.hexdigest(), parts=len(m['parts']))`
- 호출 관계: `(path.parent / part['name']).resolve`, `FileExistsError`, `Path`, `Path(manifest_path).resolve`, `Path(output).resolve`, `check.hexdigest`, `check.update`, `dict`, `enumerate`, `f.read`, `hashlib.sha256`, `iter`, `json.loads`, `len`, `os.fsync`, `os.rename`, `path.read_text`, `require`, `source.open`, `str`, `stream.fileno`, `stream.flush`, `stream.write`, `target.exists`, `target.parent.mkdir`, `target.with_name`, `temp.open`, `total.hexdigest`, `total.update`
- 검증/예외: `require(m['schema'] == 'lossless-model-parts/1', 'Wrong transfer schema')`; `require(size == m['bytes'] and total.hexdigest() == m['sha256'], 'Full model mismatch')`; `require(part['index'] == index and Path(part['name']).name == part['name'], 'Unsafe part name/order')`; `require(source.parent == path.parent, 'Part escapes transfer directory')`; `require(n == part['bytes'] and check.hexdigest() == part['sha256'], 'Part mismatch: ' + part['name'])`

### [v3_lite/package_research.py:12 — package](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/package_research.py#L12)

- 입력: `run_path`
- 반환식: `out`
- 호출 관계: `(out / 'models').mkdir`, `all`, `create_json`, `data['model_state_dict'].items`, `dest.stat`, `dict`, `f.fileno`, `f.flush`, `gc.collect`, `inside`, `json.dumps`, `len`, `list`, `os.fsync`, `os.rename`, `out.mkdir`, `out.rglob`, `p.is_file`, `p.relative_to`, `p.relative_to(out).as_posix`, `path.stat`, `payload.update`, `pending.open`, `pending.with_suffix`, `print`, `r.get`, `read_json`, `require`, `sha`, `shutil.copyfile`, `shutil.copytree`, `shutil.ignore_patterns`, `sorted`, `str`, `torch.equal`, `torch.load`, `torch.save`
- 검증/예외: `require(r.get('training_executed') is True and r.get('checkpoints'), 'No actual trained checkpoint')`; `require(sha(path) == selected['sha256'], 'Training checkpoint changed')`; `require(data['v3_lite_metadata']['parent_sha256'] == PARENT_SHA and data['step_count'] > 0, 'Missing real update lineage')`; `require(all((torch.equal(v, check['model_state_dict'][k]) for k, v in data['model_state_dict'].items())), 'Inference export changed weights')`

### [v3_lite/portable_runtime.py:50 — serve_request](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/portable_runtime.py#L50)

- 입력: `predictor, request`
- 반환식: `core.serve_request(predictor, request)`
- 호출 관계: `core.serve_request`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/portable_runtime.py:16 — V3Predictor.__init__](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/portable_runtime.py#L16)

- 입력: `self, bundle=HERE, *, expected_manifest_sha`
- 반환식: 명시 반환값 없음
- 호출 관계: `AutoTokenizer.from_pretrained`, `Path`, `Path(bundle).resolve`, `core.load_model`, `core.read`, `core.relative_file`, `core.require`, `core.sha`, `envelope.get`, `ext.get`, `list`, `str`, `torch.load`
- 검증/예외: `core.require(core.sha(self.bundle / 'bundle_manifest.json') == expected_manifest_sha, 'Trusted manifest SHA mismatch')`; `core.require(m['schema'] == 'v3-lite-inference-bundle/1' and m['label_order'] == list(LABELS) and (m['thresholds'] == [0.5] * 9) and (m['purpose'] == 'internal_experiment') and (m['human_reviewed'] is False) and (m['deployment_allowed'] is False), 'Invalid research bundle')`; `core.require(envelope.get('inference_only') is True and envelope.get('optimizer_state_dict') == {} and (ext.get('schema') == 'v3-lite-checkpoint/1') and (ext.get('parent_sha256') == m['parent_sha256']) and (ext.get('epoch') == m['epoch']) and (ext.get('human_reviewed') is False), 'Invalid v3 inference lineage')`

### [v3_lite/portable_runtime.py:40 — V3Predictor.predict](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/portable_runtime.py#L40)

- 입력: `self, request`
- 반환식: `response`
- 호출 관계: `core.output_response`, `core.raw_logits`, `core.validate_request`, `response['result'].update`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/checkpoint.py:14 — runtime](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/checkpoint.py#L14)

- 입력: ``
- 반환식: `module`
- 호출 관계: `bootstrap`, `importlib.util.module_from_spec`, `importlib.util.spec_from_file_location`, `spec.loader.exec_module`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/checkpoint.py:22 — verify_parent](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/checkpoint.py#L22)

- 입력: ``
- 반환식: `(path, m)`
- 호출 관계: `inside`, `list`, `read_json`, `require`, `sha`
- 검증/예외: `require(sha(BUNDLE / 'bundle_manifest.json') == BUNDLE_SHA, 'Parent manifest SHA changed')`; `require(m['label_order'] == list(LABELS) and m['default_seed'] == 42 and (m['epoch'] == 3) and (m['candidate_arm'] == 'B_ratio') and (m['thresholds'] == [0.5] * 9) and (m['model_revision'] == m['tokenizer_revision'] == REVISION), 'Wrong parent contract')`; `require(spec['path'] == 'models/B_ratio/seed_42.pt' and spec['sha256'] == PARENT_SHA, 'Wrong parent identity')`; `require(sha(path) == PARENT_SHA, 'Parent checkpoint SHA changed')`

### [v3_lite/src/checkpoint.py:35 — load_v2_start](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/checkpoint.py#L35)

- 입력: ``
- 반환식: `(model, tokenizer, deepcopy(metadata), manifest)`
- 호출 관계: `AutoTokenizer.from_pretrained`, `deepcopy`, `model.parameters`, `module.load_model`, `param.detach`, `param.detach().clone`, `runtime`, `str`, `torch.no_grad`, `verify_parent`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/checkpoint.py:52 — restore_state](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/checkpoint.py#L52)

- 입력: `model, state`
- 반환식: `model`
- 호출 관계: `model.load_state_dict`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/checkpoint.py:58 — save_v3_checkpoint](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/checkpoint.py#L58)

- 입력: `path, model, optimizer, *, metadata, lineage, epoch, history, artifact_kind='research_model'`
- 반환식: `dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size, artifact_kind=artifact_kind, epoch=epoch)`
- 호출 관계: `FileExistsError`, `all`, `bootstrap`, `deepcopy`, `dict`, `gc.collect`, `inside`, `lineage.get`, `list`, `metadata.get`, `model.state_dict`, `optimizer.state_dict`, `os.fsync`, `os.rename`, `path.exists`, `path.parent.mkdir`, `path.stat`, `path.with_suffix`, `payload['model_state_dict'].items`, `pending.open`, `require`, `set`, `sha`, `str`, `stream.fileno`, `stream.flush`, `torch.load`, `torch.save`, `validate_checkpoint_metadata`, `validate_model_config`
- 검증/예외: `require(path.suffix == '.pt', 'Checkpoint extension must be .pt')`; `require(metadata.get('label_order') == list(LABELS), 'Checkpoint label order mismatch')`; `require(epoch in (1, 2) and lineage.get('parent_sha256') == PARENT_SHA and (lineage.get('optimizer_reset') is True), 'Checkpoint lineage invalid')`; `require(artifact_kind in ('research_model', 'unit_test_fixture'), 'Unknown artifact kind')`; `require(lineage.get('artifact_kind') == artifact_kind, 'Artifact kind mismatch')`; `require(artifact_kind == 'unit_test_fixture' or lineage.get('training_authorized') is True, 'Unapproved data cannot produce a research-model checkpoint')`; `validate_checkpoint_metadata(payload)`; `validate_checkpoint_metadata(checked)`; `require(set(checked['model_state_dict']) == set(payload['model_state_dict']) and all((checked['model_state_dict'][k].shape == v.shape and checked['model_state_dict'][k].dtype == v.dtype for k, v in payload['model_state_dict'].items())), 'Serialized tensor contract differs')`

### [v3_lite/src/checkpoint.py:103 — load_v3_state](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/checkpoint.py#L103)

- 입력: `path, model, expected_sha, *, tokenizer`
- 반환식: `p`
- 호출 관계: `bootstrap`, `inside`, `list`, `model.eval`, `require`, `restore_state`, `runtime`, `runtime().compatible_tokenizer`, `sha`, `torch.load`, `validate_checkpoint_metadata`, `validate_model_config`
- 검증/예외: `require(sha(path) == expected_sha, 'Saved v3 hash mismatch')`; `require(p['label_order'] == list(LABELS) and p['v3_lite_metadata']['schema'] == 'v3-lite-checkpoint/1', 'Wrong v3 schema')`; `validate_checkpoint_metadata(p)`

### [v3_lite/src/common.py:30 — require](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/common.py#L30)

- 입력: `condition, reason`
- 반환식: 명시 반환값 없음
- 호출 관계: `GateError`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/common.py:35 — sha](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/common.py#L35)

- 입력: `path`
- 반환식: `value.hexdigest()`
- 호출 관계: `Path`, `Path(path).open`, `hashlib.sha256`, `iter`, `stream.read`, `value.hexdigest`, `value.update`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/common.py:43 — digest](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/common.py#L43)

- 입력: `value`
- 반환식: `hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()`
- 호출 관계: `hashlib.sha256`, `hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest`, `json.dumps`, `json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/common.py:48 — read_json](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/common.py#L48)

- 입력: `path`
- 반환식: `json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(GateError(f'Nonfinite JSON: {x}')))`; `result`
- 호출 관계: `(_ for _ in ()).throw`, `GateError`, `Path`, `Path(path).read_text`, `json.loads`, `require`
- 검증/예외: `require(key not in result, f'Duplicate JSON key: {key}')`

### [v3_lite/src/common.py:59 — inside](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/common.py#L59)

- 입력: `path, root`
- 반환식: `path`
- 호출 관계: `Path`, `Path(path).resolve`, `Path(root).absolute`, `Path(root).resolve`, `V3.absolute`, `V3.resolve`, `path.is_relative_to`, `raw_root.is_relative_to`, `require`, `root.is_relative_to`
- 검증/예외: `require(path.is_relative_to(root) and path != root, f'Path outside required root: {root}')`; `require(root.is_relative_to(V3.resolve()), 'v3 root redirects outside its workspace')`

### [v3_lite/src/common.py:68 — create_json](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/common.py#L68)

- 입력: `path, value, *, root=V3`
- 반환식: 명시 반환값 없음
- 호출 관계: `inside`, `json.dumps`, `path.open`, `path.parent.mkdir`, `stream.write`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/common.py:79 — bootstrap](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/common.py#L79)

- 입력: ``
- 반환식: 명시 반환값 없음
- 호출 관계: `Path`, `Path(labels.__file__).resolve`, `Path(labels.__file__).resolve().is_relative_to`, `Path(sys.modules['risk_speech_ai'].__file__).resolve`, `REFERENCE.resolve`, `importlib.import_module`, `inside`, `location.is_relative_to`, `manifest['code'].items`, `read_json`, `require`, `sha`, `str`, `sys.path.insert`, `tuple`
- 검증/예외: `require(sha(BUNDLE / 'bundle_manifest.json') == BUNDLE_SHA, 'Bundle manifest changed')`; `require(tuple(labels.LABELS) == LABELS, 'Canonical label order changed')`; `require(Path(labels.__file__).resolve().is_relative_to(REFERENCE.resolve()), 'Wrong pinned core')`; `require(sha(inside(V2 / name, V2)) == expected, f'Pinned source changed: {name}')`; `require(sha(inside(BUNDLE / item['path'], BUNDLE)) == item['sha256'], 'Bundle support changed')`; `require(location.is_relative_to(REFERENCE.resolve()), 'Wrong risk_speech_ai already imported; use a fresh process')`

### [v3_lite/src/data.py:22 — allowed_role](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L22)

- 입력: `role`
- 반환식: 명시 반환값 없음
- 호출 관계: `require`
- 검증/예외: `require(role in FILES, 'Only TRAIN/VALIDATION allowed; TEST denied before IO')`

### [v3_lite/src/data.py:26 — evidence_file](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L26)

- 입력: `base, spec`
- 반환식: `path`
- 호출 관계: `Path`, `Path(base).resolve`, `Path(name).is_absolute`, `inside`, `isinstance`, `name.lower`, `path.is_file`, `path.is_relative_to`, `require`, `set`, `sha`
- 검증/예외: `require(isinstance(spec, dict) and set(spec) == {'path', 'sha256'}, 'Evidence needs path/SHA')`; `require(isinstance(name, str) and ':' not in name and ('\\' not in name) and (not Path(name).is_absolute()) and ('..' not in Path(name).parts) and ('test' not in name.lower()) and ('.sealed' not in name.lower()), 'Forbidden evidence path')`; `require(path.is_relative_to(Path(base).resolve()), 'Evidence escapes its version directory')`; `require(path.is_file() and sha(path) == spec['sha256'], f'Evidence missing/hash mismatch: {name}')`

### [v3_lite/src/data.py:38 — jsonl](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L38)

- 입력: `path`
- 반환식: `[json.loads(line, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(GateError('Nonfinite JSONL'))) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]`; `result`
- 호출 관계: `(_ for _ in ()).throw`, `GateError`, `Path`, `Path(path).read_text`, `Path(path).read_text(encoding='utf-8-sig').splitlines`, `json.loads`, `line.strip`, `require`
- 검증/예외: `require(k not in result, 'Duplicate JSONL key')`

### [v3_lite/src/data.py:51 — load_manifest](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L51)

- 입력: `path`
- 반환식: `m`
- 호출 관계: `FILES.items`, `inside`, `list`, `m.get`, `read_json`, `require`, `set`
- 검증/예외: `require(path.name == 'manifest.json', 'Use a versioned manifest.json')`; `require(m.get('schema') == 'v3-lite-data/1' and m.get('purpose') == 'internal_experiment', 'Wrong data schema/purpose')`; `require(m.get('artifact_kind') == 'research_corpus', 'Fixtures cannot authorize real training')`; `require(m.get('label_order') == list(LABELS), 'Data label order mismatch')`; `require(m.get('production_training_authorized') is False and m.get('deployment_approved') is False, 'This entry point never authorizes production training')`; `require(set(m.get('splits', {})) == {'train', 'validation'}, 'No TEST references permitted')`; `require(m.get('no_v2_test_derivation') is True, 'No TEST derivation declaration missing')`; `require(m['splits'][role]['path'] == name, f'Unexpected {role} filename')`

### [v3_lite/src/data.py:67 — utterance_binding](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L67)

- 입력: `c, u`
- 반환식: `digest(dict(conversation_id=c['conversation_id'], family_id=c.get('family_id', c.get('scenario_family_id')), utterance_id=u['utterance_id'], speaker=u['speaker'], text=u['text'], is_phishing=u['is_phishing'], labels=u['labels']))`
- 호출 관계: `c.get`, `dict`, `digest`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/data.py:73 — validate_reviews](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L73)

- 입력: `conversations, reviews, *, required_keys=None`
- 반환식: 명시 반환값 없음
- 호출 관계: `a.get`, `a['reviewer_id'].strip`, `all`, `bool`, `datetime.fromisoformat`, `decision.get`, `dict`, `isinstance`, `len`, `r.get`, `require`, `review.get`, `set`, `sorted`, `type`, `utterance_binding`
- 검증/예외: `require(key not in by_key, 'Duplicate review key')`; `require(key in by_key, f'Missing independent review: {key}')`; `require(review.get('record_type') == 'human_review' and review.get('status') == 'resolved', 'Human review unresolved/fixture-only')`; `require(review.get('content_sha256') == utterance_binding(c, u), 'Review does not bind current content/labels')`; `require(len(raters) == 2 and len({a.get('reviewer_id') for a in raters}) == 2, 'Two distinct reviewers required')`; `require(isinstance(a.get('reviewer_id'), str) and a['reviewer_id'].strip() and (a.get('human') is True) and (a.get('independent') is True) and a.get('reviewed_at'), 'Human/independence/time attestation absent')`; `require(datetime.fromisoformat(a['reviewed_at']).tzinfo is not None, 'Review timestamp needs timezone')`; `require(isinstance(al, list) and all((l in LABELS for l in al)) and (type(a.get('is_phishing')) is bool) and (al == sorted(set(al), key=LABELS.index)) and (a['is_phishing'] == bool(al)), 'Reviewer labels invalid')`; `require(decision.get('adjudicator_id') and decision.get('reason') and decision.get('resolved_at') and (decision.get('is_phishing') == actual['is_phishing']) and (decision.get('labels') == actual['labels']), 'Disagreement lacks a bound resolution')`; `require(datetime.fromisoformat(decision['resolved_at']).tzinfo is not None, 'Resolution needs timezone')`

### [v3_lite/src/data.py:111 — validate_rights](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L111)

- 입력: `c, record, role`
- 반환식: 명시 반환값 없음
- 호출 관계: `datetime.fromisoformat`, `record.get`, `require`
- 검증/예외: `require(record.get('record_type') == 'data_use_authorization' and record.get('status') == 'confirmed' and (c['source'] in record.get('source_ids', [])) and (role in record.get('permitted_uses', [])) and record.get('authorized_by') and record.get('authorized_at') and record.get('basis'), 'Source rights evidence lacks authority/scope/source binding')`; `require(datetime.fromisoformat(record['authorized_at']).tzinfo is not None, 'Rights timestamp needs timezone')`

### [v3_lite/src/data.py:119 — validate_schema](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L119)

- 입력: `conversations, role`
- 반환식: `statistics(conversations)`
- 호출 관계: `' '.join`, `all`, `allowed_role`, `bool`, `c.get`, `c['source'].strip`, `cid.startswith`, `cid.upper`, `enumerate`, `families.add`, `family.upper`, `ids.add`, `isinstance`, `len`, `normalized`, `provenance.get`, `re.findall`, `re.search`, `require`, `rights.get`, `set`, `sorted`, `statistics`, `str`, `str(provenance['origin_id']).upper`, `text.strip`, `texts.add`, `type`, `u.get`
- 검증/예외: `require(bool(conversations), 'Empty corpus')`; `require(isinstance(cid, str) and cid.startswith('V3-') and ('TEST' not in cid.upper()), 'New V3 conversation ID required')`; `require(cid not in ids and isinstance(family, str) and family and (family not in families) and ('TEST' not in family.upper()), 'Duplicate/invalid conversation/family')`; `require(c.get('split') == role and c.get('review_status') == 'reviewed', 'Wrong split/unreviewed conversation')`; `require(isinstance(c.get('source'), str) and c['source'].strip(), 'Source missing')`; `require(all((provenance.get(k) for k in ['method', 'author_or_generator', 'created_at', 'origin_id', 'semantic_family_id'])), 'Provenance missing')`; `require('TEST' not in origin and 'SYN2-' not in origin and ('SYN3-' not in origin) and (provenance.get('test_derived', False) is False), 'New data must not derive from v2 examples/TEST')`; `require(rights.get('status') == 'documented' and role in rights.get('permitted_uses', []) and rights.get('evidence'), 'Use rights missing')`; `require(c.get('category') in CATEGORIES, 'Hard-negative/scenario category missing')`; `require(len(us) == 8, 'Each new conversation needs eight utterances')`; `require(textkey not in texts, 'Duplicate conversation text under different IDs')`; `require(type(u.get('utterance_id')) is int and u['utterance_id'] == i, 'Duplicate/reordered utterance ID')`; `require(u.get('speaker') in ('speaker_A', 'speaker_B'), 'Unknown speaker')`; `require(isinstance(text, str) and text.strip() and ('history' not in u), 'Only current text; histories are computed')`; `require(not re.search('(?:\\d[ -]?){7,}|[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}|https?://', text), 'Unmasked numeric/contact/URL candidate')`; `require(all((t in MASKS for t in re.findall('\\[([A-Z_]+)\\]', text))), 'Unknown masking token')`; `require(u.get('masking_reviewed') is True, 'Masking requires explicit human check')`; `require(isinstance(labels, list) and all((t in LABELS for t in labels)) and (labels == sorted(set(labels), key=LABELS.index)), 'Labels/order invalid')`; `require(type(u.get('is_phishing')) is bool and u['is_phishing'] == bool(labels), 'Risk/type mismatch')`

### [v3_lite/src/data.py:157 — statistics](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L157)

- 입력: `conversations`
- 반환식: `dict(conversations=len(conversations), families=len({c.get('family_id', c.get('scenario_family_id')) for c in conversations}), utterances=len(rows), risk_positive=sum((u['is_phishing'] for u in rows)), normal_conversations=sum((not any((u['`
- 호출 관계: `any`, `c.get`, `dict`, `len`, `sum`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/data.py:166 — normalized](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L166)

- 입력: `text`
- 반환식: `''.join((c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum()))`
- 호출 관계: `''.join`, `c.isalnum`, `unicodedata.normalize`, `unicodedata.normalize('NFKC', text).casefold`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/data.py:170 — check_disjoint](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L170)

- 입력: `*partitions`
- 반환식: 명시 반환값 없음
- 호출 관계: `' '.join`, `SequenceMatcher`, `SequenceMatcher(None, x, y, autojunk=False).ratio`, `c.get`, `c.get('provenance', {}).get`, `enumerate`, `len`, `normalized`, `require`, `set`
- 검증/예외: `require(not ids & seen_ids and (not families & seen_family) and (not semantic & seen_semantic), 'Conversation/family/semantic-family overlap')`; `require(len(semantic) == len(cs), 'Multiple conversations claim the same semantic family')`; `require(SequenceMatcher(None, x, y, autojunk=False).ratio() < 0.8, 'Cross-partition near-duplicate: revise or independently adjudicate before freezing')`

### [v3_lite/src/data.py:207 — load_split](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L207)

- 입력: `role, manifest_path`
- 반환식: `Partition(role, tuple(cs), sha(file), str(file))`
- 호출 관계: `Partition`, `allowed_role`, `evidence_file`, `inside`, `jsonl`, `load_manifest`, `read_json`, `sha`, `str`, `tuple`, `validate_reviews`, `validate_rights`, `validate_schema`
- 검증/예외: `validate_reviews(cs, reviews)`

### [v3_lite/src/data.py:221 — load_legacy](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L221)

- 입력: `role`
- 반환식: `Partition(role, tuple(jsonl(path)), sha(path), str(path))`
- 호출 관계: `Partition`, `allowed_role`, `bootstrap`, `jsonl`, `read_json`, `require`, `sha`, `str`, `tuple`
- 검증/예외: `require(sha(path) == bundle['bindings'][role + '_sha256'], 'Original v2 data changed')`

### [v3_lite/src/data.py:230 — load_training_inputs](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L230)

- 입력: `manifest_path`
- 반환식: `(Partition('train', all_train, digest(bindings), str(path)), validation, old_val, bindings)`
- 호출 관계: `Counter`, `Partition`, `all`, `any`, `check_disjoint`, `dict`, `dict.fromkeys`, `digest`, `evidence_file`, `inside`, `jsonl`, `len`, `list`, `load_legacy`, `load_manifest`, `load_split`, `read_json`, `require`, `required_categories.items`, `set`, `split_review.get`, `statistics`, `str`, `sum`, `tuple`, `validate_reviews`
- 검증/예외: `validate_reviews(cs, jsonl(evidence_file(path.parent, m['reviews']['legacy_focus'])), required_keys=required)`; `require(split_review.get('record_type') == 'human_split_review' and split_review.get('status') == 'resolved' and split_review.get('reviewed_at') and (split_review.get('bindings') == bindings) and (split_review.get('no_test_derivation') is True) and (split_review.get('semantic_independence_reviewed') is True) and (len(set(split_review.get('human_reviewer_ids'`; `require(sum((len(c['utterances']) for c in all_train)) == 848, 'TRAIN budget changed')`; `require((s['conversations'], s['utterances'], s['normal_conversations']) == (nc, nu, normal), 'Planned corpus counts not met')`; `require(all((categories[k] >= n for k, n in required_categories.items())), 'Normal scenario category coverage insufficient')`; `require(new_stats['types'][l]['positive'] > 0, 'Validation lacks an output label')`; `require(s['types'][l]['positive'] >= 18 and s['types'][l]['positive_families'] >= 6, 'Focus support insufficient')`

### [v3_lite/src/data.py:196 — Partition.rows](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L196)

- 입력: `self`
- 반환식: `[dict(u, conversation_id=c['conversation_id'], scenario_family_id=c.get('family_id', c.get('scenario_family_id')), source_id=c.get('source', 'V2_INHERITED_SYNTHETIC'), category=c.get('category', 'legacy'), hard_negative=not any((v['is_phish`
- 호출 관계: `any`, `c.get`, `dict`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/data.py:201 — Partition.samples](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/data.py#L201)

- 입력: `self`
- 반환식: `causal_samples(self.conversations)`
- 호출 관계: `bootstrap`, `causal_samples`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/diagnostics.py:13 — type_losses](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/diagnostics.py#L13)

- 입력: `output, risk, types`
- 반환식: `dict(risk=float(risk_loss.detach()), types_unweighted=unweighted.detach().mean(0).tolist(), types_weighted=weighted.detach().mean(0).tolist())`
- 호출 관계: `F.binary_cross_entropy_with_logits`, `dict`, `float`, `risk_loss.detach`, `torch.full`, `unweighted.detach`, `unweighted.detach().mean`, `unweighted.detach().mean(0).tolist`, `weighted.detach`, `weighted.detach().mean`, `weighted.detach().mean(0).tolist`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/diagnostics.py:25 — normal_groups](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/diagnostics.py#L25)

- 입력: `rows, probabilities`
- 반환식: `groups`
- 호출 관계: `dict`, `enumerate`, `int`, `len`, `sorted`, `sum`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/diagnostics.py:34 — score_logits](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/diagnostics.py#L34)

- 입력: `partition, logits`
- 반환식: `metrics`
- 호출 관계: `allowed_role`, `bool`, `bootstrap`, `dict`, `enumerate`, `evaluate_logits`, `float`, `len`, `list`, `normal_groups`, `partition.rows`, `probabilities`, `ps.max`, `ps.mean`, `ps.min`, `require`
- 검증/예외: `require(len(rows) == len(values), 'Prediction row alignment differs')`

### [v3_lite/src/diagnostics.py:53 — evaluate_split](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/diagnostics.py#L53)

- 입력: `model, tokenizer, partition`
- 반환식: `dict(role=partition.role, data_sha256=partition.data_sha256, row_keys=[f'{s.conversation_id}:{s.utterance_id}' for s in samples], logits=logits, metrics=metrics)`
- 호출 관계: `RiskSpeechDataset`, `allowed_role`, `bootstrap`, `dict`, `logits.extend`, `make_training_dataloader`, `model`, `model.eval`, `model.train`, `partition.samples`, `score_logits`, `torch.cat`, `torch.cat([output.risk_logits, output.type_logits], dim=1).tolist`, `torch.inference_mode`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/diagnostics.py:77 — _defined](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/diagnostics.py#L77)

- 입력: `value`
- 반환식: `type(value) in (int, float) and math.isfinite(value)`
- 호출 관계: `math.isfinite`, `type`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/diagnostics.py:81 — safety](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/diagnostics.py#L81)

- 입력: `baseline, candidate`
- 반환식: `reasons`
- 호출 관계: `_defined`, `all`, `bs.append`, `cs.append`, `len`, `reasons.append`, `sum`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/diagnostics.py:105 — apply_gates](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/diagnostics.py#L105)

- 입력: `baseline, candidate, old_baseline, old_candidate, *, epoch`
- 반환식: `dict(epoch=epoch, safe=safe, safety_failures=reasons, targets_passed=bool(target), adopt=bool(safe and target), allow_epoch2=bool(allow), normal_fp_outcome='zero_maintained_not_improved' if not bfp and (not cfp) else 'compare_counts', final`
- 호출 관계: `_defined`, `all`, `any`, `bool`, `dict`, `require`, `safety`
- 검증/예외: `require(epoch in (1, 2), 'Maximum two epochs')`

### [v3_lite/src/diagnostics.py:128 — family_paired_uncertainty](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/diagnostics.py#L128)

- 입력: `partition, baseline, candidate, *, repetitions=1000`
- 반환식: `dict(unit='scenario_family_id', families=len(family), repetitions=repetitions, seed=42, delta_f1={l: dict(valid=len(v), ci95=np.percentile(v, [2.5, 97.5]).tolist() if v else None) for l, v in deltas.items()}, limitation='Small selection set`; `2 * tp / (2 * tp + fp + fn)`
- 호출 관계: `(pred & y).sum`, `(pred & ~y).sum`, `(~pred & y).sum`, `LABELS.index`, `allowed_role`, `bootstrap`, `deltas.items`, `deltas[l].append`, `dict`, `enumerate`, `f1`, `int`, `len`, `np.asarray`, `np.percentile`, `np.percentile(v, [2.5, 97.5]).tolist`, `np.random.default_rng`, `partition.rows`, `probabilities`, `range`, `require`, `rng.choice`, `sorted`, `y.all`, `y.any`
- 검증/예외: `require(baseline['row_keys'] == candidate['row_keys'] and baseline['data_sha256'] == candidate['data_sha256'] == partition.data_sha256, 'Unpaired predictions')`; `require(baseline['row_keys'] == [f"{r['conversation_id']}:{r['utterance_id']}" for r in rows], 'Prediction keys do not match partition order')`

### [v3_lite/src/research_data.py:14 — test_origin](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/research_data.py#L14)

- 입력: `value`
- 반환식: `bool(re.search('(?:^|[-_])TEST(?:[-_]|$)', str(value), flags=re.I))`
- 호출 관계: `bool`, `re.search`, `str`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/research_data.py:18 — validate_research](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/research_data.py#L18)

- 입력: `conversations, role`
- 반환식: `statistics(conversations)`
- 호출 관계: `' '.join`, `POLICY_FIELDS.items`, `all`, `allowed_role`, `bool`, `c.get`, `cid.startswith`, `enumerate`, `families.add`, `ids.add`, `isinstance`, `len`, `normalized`, `p.get`, `re.findall`, `re.search`, `require`, `set`, `sorted`, `statistics`, `test_origin`, `text.strip`, `texts.add`, `type`, `u.get`
- 검증/예외: `require(bool(conversations), 'Research corpus empty')`; `require(all((c.get(k) == v and type(c.get(k)) == type(v) for k, v in POLICY_FIELDS.items())), 'Research provenance/approval flags invalid')`; `require(c.get('review_status') == 'ai_provisional' and c.get('label_status') == 'provisional', 'Never assert human-reviewed labels')`; `require(isinstance(cid, str) and cid.startswith('V3-') and (not test_origin(cid)) and (cid not in ids), 'Invalid/duplicate research ID')`; `require(isinstance(fam, str) and fam and (not test_origin(fam)) and (fam not in families), 'Invalid/duplicate family')`; `require(c.get('split') == role and c.get('category') in CATEGORIES, 'Wrong role/category')`; `require(all((p.get(k) for k in ['author_or_generator', 'method', 'origin_id', 'semantic_family_id', 'authored_sha256'])), 'Missing generated provenance')`; `require(p['method'] == 'session_authored_dialogue_literals' and p.get('actual_call') is False and (p.get('third_party_transcript') is False) and (not test_origin(p['origin_id'])), 'Unapproved source origin')`; `require(c.get('rights_basis') == 'user_authorized_self_authored_internal_synthetic_research', 'Source use basis invalid')`; `require(len(us) == 8, 'Eight new utterances per family required')`; `require(key not in texts, 'Duplicate whole dialogue')`; `require(type(u.get('utterance_id')) is int and u['utterance_id'] == i, 'Utterance IDs out of order/duplicated')`; `require(u.get('speaker') in ('speaker_A', 'speaker_B'), 'Speaker invalid')`; `require(isinstance(text, str) and text.strip() and ('history_texts' not in u), 'Current text required; history is computed')`; `require(not re.search('(?:\\d[ -]?){7,}|[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}|https?://', text), 'Unmasked contact/identifier/link')`; `require(all((t in MASKS for t in re.findall('\\[([A-Z_]+)\\]', text))), 'Unknown mask')`; `require(isinstance(ls, list) and all((l in LABELS for l in ls)) and (ls == sorted(set(ls), key=LABELS.index)), 'Label order/duplicates invalid')`; `require(type(u.get('is_phishing')) is bool and u['is_phishing'] == bool(ls), 'Risk/type mismatch')`

### [v3_lite/src/research_data.py:52 — load_research_split](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/research_data.py#L52)

- 입력: `role, manifest_path`
- 반환식: `Partition(role, tuple(cs), sha(target), str(target))`
- 호출 관계: `POLICY_FIELDS.items`, `Partition`, `all`, `allowed_role`, `evidence_file`, `inside`, `jsonl`, `list`, `m.get`, `m.get('authorization', {}).get`, `m['authorization'].get`, `re.fullmatch`, `read_json`, `require`, `set`, `sha`, `str`, `tuple`, `validate_research`
- 검증/예외: `require(path.name == 'research_manifest.json', 'Separate research manifest required')`; `require(m.get('schema') == 'research-synthetic-v3/1' and all((m.get(k) == v for k, v in POLICY_FIELDS.items())), 'Not a synthetic research manifest')`; `require(m.get('label_order') == list(LABELS) and m.get('mode') == 'research_synthetic_v3', 'Wrong research mode/labels')`; `require(m.get('authorization', {}).get('scope') == 'explicit_user_internal_synthetic_generation_and_training' and re.fullmatch('[0-9a-f]{64}', m['authorization'].get('request_sha256', '')), 'Explicit research authorization missing')`; `require(set(m['splits']) == {'train', 'validation'}, 'No TEST role permitted')`; `require(m['splits'][role]['path'] == {'train': 'train_additions.jsonl', 'validation': 'validation_new.jsonl'}[role], 'Unexpected research file')`; `validate_research(cs, role)`

### [v3_lite/src/research_data.py:68 — load_research_inputs](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/research_data.py#L68)

- 입력: `manifest_path`
- 반환식: `(Partition('train', old.conversations + train.conversations, digest(bindings), str(manifest_path)), val, old_val, bindings)`
- 호출 관계: `Counter`, `Partition`, `all`, `any`, `check_disjoint`, `dict`, `dict(financial=3, official=2, identity=3, app=2, quotation=2).items`, `digest`, `load_legacy`, `load_research_split`, `read_json`, `require`, `sha`, `statistics`, `str`
- 검증/예외: `require(policy['purpose'] == 'internal_experiment' and policy['source_kind'] == 'llm_synthetic' and (policy['human_approved'] is False) and (policy['production_training_authorized'] is False), 'Inherited research use basis changed')`; `require(s['conversations'] == n and s['utterances'] == n * 8 and (s['normal_conversations'] == norm), 'Planned counts not met')`; `require(all((s['types'][l]['positive'] > 0 for l in LABELS)) if p.role == 'validation' else True, 'Validation label missing')`; `require(all((cats[k] >= v for k, v in dict(financial=3, official=2, identity=3, app=2, quotation=2).items())), 'Normal categories missing')`; `require(s['types'][l]['positive'] >= 18 and s['types'][l]['positive_families'] >= 6, 'Focus support not met')`

### [v3_lite/src/train.py:22 — code_inventory](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/train.py#L22)

- 입력: ``
- 반환식: `{p.relative_to(V3).as_posix(): sha(p) for folder in ['src', 'tests', 'configs'] for p in sorted((V3 / folder).rglob('*')) if p.is_file() and p.suffix in ('.py', '.json')}`
- 호출 관계: `(V3 / folder).rglob`, `p.is_file`, `p.relative_to`, `p.relative_to(V3).as_posix`, `sha`, `sorted`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/train.py:27 — load_config](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/train.py#L27)

- 입력: ``
- 반환식: `c`
- 호출 관계: `dict`, `list`, `read_json`, `require`
- 검증/예외: `require(c == fixed, 'Fixed phase-one config changed; no search/overrides allowed')`

### [v3_lite/src/train.py:38 — resources](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/train.py#L38)

- 입력: ``
- 반환식: `result`
- 호출 관계: `Memory`, `bool`, `ctypes.byref`, `ctypes.sizeof`, `ctypes.windll.kernel32.GlobalMemoryStatusEx`, `getattr`, `int`, `os.cpu_count`, `require`, `result.update`, `shutil.disk_usage`
- 검증/예외: `require(os.name == 'nt', 'Resource preflight implemented for the specified Windows host')`; `require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)), 'Cannot inspect Windows memory')`

### [v3_lite/src/train.py:54 — preflight](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/train.py#L54)

- 입력: `manifest_path, regression_receipt, *, data_mode='reviewed'`
- 반환식: `(config, train, validation, old_val, bindings, res)`
- 호출 관계: `code_inventory`, `digest`, `inside`, `load_config`, `load_research_inputs`, `load_training_inputs`, `read_json`, `receipt.get`, `require`, `resources`, `verify_parent`
- 검증/예외: `require(data_mode in ('reviewed', 'research_synthetic_v3'), 'Unknown data route')`; `require(receipt.get('schema') == 'v3-lite-regression/1' and receipt.get('status') == 'PASS' and (receipt.get('tests_run', 0) > 0) and (receipt.get('failures') == 0) and (receipt.get('errors') == 0) and (receipt.get('skipped') == 0) and (receipt.get('code_sha256') == digest(code_inventory())), 'Fresh passing regression receipt required')`; `require(res['training_capacity_ok'], 'Insufficient CPU/memory/commit/disk headroom')`

### [v3_lite/src/train.py:74 — new_optimizer](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/train.py#L74)

- 입력: `model`
- 반환식: `optimizer`
- 호출 관계: `model.parameters`, `require`, `torch.optim.AdamW`
- 검증/예외: `require(not optimizer.state, 'Warm start must use a new empty optimizer')`

### [v3_lite/src/train.py:81 — train_one_epoch](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/train.py#L81)

- 입력: `model, loader, optimizer, *, epoch, step_offset=0, step_limit=212, progress=None`
- 반환식: `dict(epoch=epoch, optimizer_steps=step_offset + steps, epoch_steps=steps, samples=seen, train_loss=total_sum / seen, risk_loss=risk_sum / seen, type_loss=type_sum / seen, per_type_unweighted=dict(zip(LABELS, [v / seen for v in unweighted]))`
- 호출 관계: `all`, `bootstrap`, `dict`, `float`, `len`, `losses`, `model`, `model.parameters`, `model.train`, `optimizer.step`, `optimizer.zero_grad`, `progress`, `range`, `require`, `resources`, `risk.detach`, `time.monotonic`, `torch.isfinite`, `torch.isfinite(p).all`, `torch.isfinite(p).all().item`, `torch.isfinite(p.grad).all`, `torch.isfinite(p.grad).all().item`, `torch.isfinite(total).item`, `total.backward`, `total.detach`, `type_losses`, `types.detach`, `zip`
- 검증/예외: `require(epoch in (1, 2) and step_offset + len(loader) <= step_limit, 'Epoch/update budget exceeded')`; `require(seen > 0, 'Empty training loader')`; `require(torch.isfinite(total).item(), 'Nonfinite loss')`; `require(all((p.grad is None or torch.isfinite(p.grad).all().item() for p in model.parameters())), 'Nonfinite gradient')`; `require(all((torch.isfinite(p).all().item() for p in model.parameters())), 'Nonfinite parameter')`

### [v3_lite/src/train.py:116 — state_inventory](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/train.py#L116)

- 입력: `model`
- 반환식: `{k: dict(shape=list(v.shape), dtype=str(v.dtype), sha256=hashlib.sha256(v.detach().cpu().contiguous().numpy().tobytes()).hexdigest()) for k, v in model.state_dict().items()}`
- 호출 관계: `dict`, `hashlib.sha256`, `hashlib.sha256(v.detach().cpu().contiguous().numpy().tobytes()).hexdigest`, `list`, `model.state_dict`, `model.state_dict().items`, `str`, `v.detach`, `v.detach().cpu`, `v.detach().cpu().contiguous`, `v.detach().cpu().contiguous().numpy`, `v.detach().cpu().contiguous().numpy().tobytes`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/src/train.py:121 — run_lite](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/src/train.py#L121)

- 입력: `manifest_path, *, run_id, regression_receipt, purpose='internal_experiment', data_mode='reviewed'`
- 반환식: `result`
- 호출 관계: `(path / 'progress.jsonl').open`, `RiskSpeechDataset`, `TrainingConfig`, `_metadata`, `abs`, `all`, `apply_gates`, `bootstrap`, `code_inventory`, `create_json`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `dict`, `digest`, `evaluate_split`, `f.flush`, `f.write`, `family_paired_uncertainty`, `history.append`, `inside`, `isinstance`, `json.dumps`, `k.startswith`, `len`, `load_research_inputs`, `load_training_inputs`, `load_v2_start`, `load_v3_state`, `make_training_dataloader`, `max`, `model.encoder.gradient_checkpointing_enable`, `new_optimizer`, `path.exists`, `path.mkdir`, `preflight`, `print`, `re.fullmatch`, `record['changed_groups'].values`, `references.append`, `require`, `runtime`, `runtime().raw_logits`, `save_v3_checkpoint`, `set_training_seed`, `sha`, `state_inventory`, `sum`, `tensors.items`, `torch.device`, `torch.set_num_threads`, `train.samples`, `train_one_epoch`, `val.samples`, `verify_parent`, `zip`
- 검증/예외: `require(purpose == 'internal_experiment', 'Unapproved legacy model cannot enter production/formal training')`; `require(isinstance(run_id, str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{2,63}', run_id), 'Safe new run ID required')`; `require(not path.exists(), 'Never overwrite/retry an existing run')`; `require(len(loader) == 106, 'Expected 106 updates per epoch')`; `require(sha(manifest_path) == lineage['manifest_sha256'], 'Manifest changed during baseline')`; `require(current_bindings == bindings and digest(code_inventory()) == lineage['code_sha256'], 'Inputs/code changed before first update')`; `require(all(record['changed_groups'].values()), 'Encoder and both heads must actually update')`; `require(replay_delta <= 1e-06, 'Saved checkpoint CPU replay differs')`

### [v3_lite/tests/fixtures.py:7 — conversation](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/fixtures.py#L7)

- 입력: `cid='V3-FIXTURE-TRAIN-001', family='fixture-phone-inquiry', role='train'`
- 반환식: `dict(conversation_id=cid, family_id=family, split=role, source='automated_unit_test_fixture', category='identity', review_status='reviewed', provenance=dict(method='unit_fixture', author_or_generator='automated_test', created_at='2026-11-17`
- 호출 관계: `bool`, `dict`, `enumerate`, `us.append`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/fixtures.py:24 — simulated_reviews](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/fixtures.py#L24)

- 입력: `cs`
- 반환식: `[dict(record_type='human_review', status='resolved', conversation_id=c['conversation_id'], utterance_id=u['utterance_id'], content_sha256=utterance_binding(c, u), reviewers=[dict(reviewer_id=f'SIMULATED_TEST_RATER_{i}', human=True, independ`
- 호출 관계: `deepcopy`, `dict`, `utterance_binding`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/fixtures.py:33 — metrics](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/fixtures.py#L33)

- 입력: `f1=0.5, ap=0.5, normal_fp=1`
- 반환식: `dict(binary=dict(recall=0.9, f1=0.9), per_type={l: dict(f1=f1, recall=0.8, average_precision=ap) for l in LABELS}, conversations=dict(normal=12, normal_false_alerts=normal_fp))`
- 호출 관계: `dict`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_data_guards.py:16 — DataGuards.test_schema_and_risk_type_contract](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L16)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `conversation`, `self.assertEqual`, `self.assertRaises`, `validate_schema`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_data_guards.py:21 — DataGuards.test_label_order_duplicate_ids_and_unknowns](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L21)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `c['utterances'][0].update`, `c['utterances'][1].update`, `conversation`, `fn`, `self.assertRaises`, `validate_schema`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_data_guards.py:30 — DataGuards.test_test_role_denied_before_any_io](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L30)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `load_split`, `patch`, `reader.assert_not_called`, `self.assertRaises`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_data_guards.py:36 — DataGuards.test_test_and_traversal_paths_denied_before_content_read](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L36)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `evidence_file`, `self.assertRaises`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_data_guards.py:40 — DataGuards.test_rights_masking_and_history_rejected](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L40)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `c.update`, `c['provenance'].update`, `c['utterances'][0].update`, `conversation`, `fn`, `self.assertRaises`, `validate_schema`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_data_guards.py:50 — DataGuards.test_rights_evidence_requires_source_scope_and_authority](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L50)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `conversation`, `deepcopy`, `dict`, `self.assertRaises`, `validate_rights`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_data_guards.py:59 — DataGuards.test_review_bindings_two_people_and_resolution](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L59)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `conversation`, `deepcopy`, `dict`, `disagree[1]['reviewers'][0].update`, `self.assertRaises`, `simulated_reviews`, `validate_reviews`
- 검증/예외: `validate_reviews(cs, rs)`; `validate_reviews(cs, disagree)`; `validate_reviews(cs, one)`; `validate_reviews(cs, same)`; `validate_reviews(cs, disagree)`; `validate_reviews(stale, rs)`; `validate_reviews(cs, bad)`

### [v3_lite/tests/test_data_guards.py:77 — DataGuards.test_family_and_near_duplicate_split](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L77)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `check_disjoint`, `conversation`, `self.assertRaises`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_data_guards.py:86 — DataGuards.test_causal_history_uses_only_past_five_turns](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L86)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `Partition`, `conversation`, `enumerate`, `max`, `p.samples`, `self.assertEqual`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_data_guards.py:93 — DataGuards.test_fixture_manifest_cannot_authorize_training](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L93)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `DATA.mkdir`, `Path`, `dict`, `json.dumps`, `load_manifest`, `loader.assert_not_called`, `p.write_text`, `patch`, `run_lite`, `self.assertRaises`, `tempfile.TemporaryDirectory`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_data_guards.py:103 — DataGuards.test_unapproved_formal_training_and_missing_data_block_before_model](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_data_guards.py#L103)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `loader.assert_not_called`, `patch`, `run_lite`, `self.assertRaises`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_diagnostics.py:13 — Diagnostics.setUpClass](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_diagnostics.py#L13)

- 입력: `cls`
- 반환식: 명시 반환값 없음
- 호출 관계: `bootstrap`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_diagnostics.py:16 — Diagnostics.test_weighted_loss_has_expected_hand_calculated_value](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_diagnostics.py#L16)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `ModelOutput`, `float`, `losses`, `math.log`, `risk.detach`, `self.assertAlmostEqual`, `self.assertTrue`, `torch.isfinite`, `torch.isfinite(o.type_logits.grad).all`, `torch.zeros`, `total.backward`, `type_losses`, `types.detach`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_diagnostics.py:29 — Diagnostics.test_known_logits_metrics_and_type_false_alerts](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_diagnostics.py#L29)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `Partition`, `conversation`, `float`, `json.dumps`, `score_logits`, `self.assertEqual`, `self.assertRaises`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_diagnostics.py:43 — Diagnostics.test_normal_binary_and_type_fp_are_distinct](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_diagnostics.py#L43)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `Partition`, `conversation`, `range`, `score_logits`, `self.assertEqual`, `u.update`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_diagnostics.py:52 — Diagnostics.test_adopt_when_both_targets_and_normal_fp_improve](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_diagnostics.py#L52)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `apply_gates`, `metrics`, `self.assertFalse`, `self.assertTrue`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_diagnostics.py:57 — Diagnostics.test_epoch2_requires_ap_progress_and_safety](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_diagnostics.py#L57)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `apply_gates`, `metrics`, `self.assertFalse`, `self.assertTrue`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_diagnostics.py:65 — Diagnostics.test_binary_or_old_validation_regression_stops](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_diagnostics.py#L65)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `apply_gates`, `deepcopy`, `metrics`, `self.assertFalse`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_diagnostics.py:71 — Diagnostics.test_normal_increase_or_other_type_recall_stops](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_diagnostics.py#L71)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `apply_gates`, `metrics`, `self.assertFalse`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_diagnostics.py:77 — Diagnostics.test_undefined_support_never_passes_and_zero_fp_is_not_improvement](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_diagnostics.py#L77)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `apply_gates`, `metrics`, `self.assertEqual`, `self.assertFalse`, `self.assertTrue`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_diagnostics.py:85 — Diagnostics.test_paired_family_interval_and_alignment](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_diagnostics.py#L85)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `Partition`, `bad['row_keys'].reverse`, `conversation`, `deepcopy`, `dict`, `family_paired_uncertainty`, `self.assertEqual`, `self.assertRaises`, `u.update`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_research_data.py:10 — ResearchData.test_explicit_research_route_and_counts](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_research_data.py#L10)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `len`, `load_manifest`, `load_research_inputs`, `manifest.exists`, `old.samples`, `self.assertEqual`, `self.assertFalse`, `self.assertRaises`, `self.skipTest`, `train.samples`, `val.samples`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_research_data.py:21 — ResearchData.test_test_role_refused_before_read](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_research_data.py#L21)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `load_research_split`, `patch`, `read.assert_not_called`, `self.assertRaises`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_research_data.py:26 — ResearchData.test_research_never_claims_human_or_production_approval](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_research_data.py#L26)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `deepcopy`, `load_research_split`, `manifest.exists`, `self.assertRaises`, `self.skipTest`, `validate_research`
- 검증/예외: `validate_research([c], 'train')`; `validate_research([bad], 'train')`

### [v3_lite/tests/test_research_data.py:36 — ResearchData.test_exact_test_origin_token_not_contest_word](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_research_data.py#L36)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `self.assertFalse`, `self.assertTrue`, `test_origin`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_warm_start.py:13 — tiny_model](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_warm_start.py#L13)

- 입력: ``
- 반환식: `RiskSpeechClassifier(ElectraModel(config))`
- 호출 관계: `ElectraConfig`, `ElectraModel`, `RiskSpeechClassifier`, `bootstrap`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_warm_start.py:25 — WarmStart.setUpClass](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_warm_start.py#L25)

- 입력: `cls`
- 반환식: 명시 반환값 없음
- 호출 관계: `AutoTokenizer.from_pretrained`, `bootstrap`, `str`, `torch.set_num_threads`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_warm_start.py:32 — WarmStart.loader](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_warm_start.py#L32)

- 입력: `self`
- 반환식: `make_training_dataloader(RiskSpeechDataset(p.samples(), tokenizer=self.tok), tokenizer=self.tok, batch_size=8, seed=42, shuffle=False)`
- 호출 관계: `Partition`, `RiskSpeechDataset`, `conversation`, `make_training_dataloader`, `p.samples`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_warm_start.py:38 — WarmStart.test_restore_all_weights_and_empty_new_optimizer](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_warm_start.py#L38)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `a.state_dict`, `a.state_dict().items`, `all`, `b.state_dict`, `bad.pop`, `deepcopy`, `len`, `new_optimizer`, `restore_state`, `self.assertEqual`, `self.assertRaises`, `self.assertTrue`, `state.items`, `tiny_model`, `torch.equal`, `v.detach`, `v.detach().clone`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_warm_start.py:49 — WarmStart.test_loss_and_one_actual_tiny_optimizer_update](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_warm_start.py#L49)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `len`, `m.type_classifier.weight.detach`, `m.type_classifier.weight.detach().clone`, `new_optimizer`, `self.assertAlmostEqual`, `self.assertEqual`, `self.assertFalse`, `self.assertGreater`, `self.loader`, `set`, `tiny_model`, `torch.equal`, `train_one_epoch`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_warm_start.py:59 — WarmStart.test_budget_and_nonfinite_update_blocked](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_warm_start.py#L59)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `float`, `len`, `m.type_classifier.bias.fill_`, `new_optimizer`, `self.assertEqual`, `self.assertRaises`, `self.loader`, `tiny_model`, `torch.no_grad`, `train_one_epoch`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_warm_start.py:68 — WarmStart.test_separate_save_cpu_reload_and_never_overwrite](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_warm_start.py#L68)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `Path`, `RUNS.mkdir`, `TrainingConfig`, `_metadata`, `dict`, `iter`, `load_v3_state`, `m`, `m.eval`, `new_optimizer`, `next`, `restored`, `save_v3_checkpoint`, `self.assertFalse`, `self.assertRaises`, `self.assertTrue`, `self.loader`, `tempfile.TemporaryDirectory`, `tiny_model`, `torch.device`, `torch.equal`, `torch.inference_mode`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_warm_start.py:91 — WarmStart.test_v2_path_and_unapproved_checkpoint_save_rejected](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_warm_start.py#L91)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `dict`, `list`, `new_optimizer`, `reversed`, `save_v3_checkpoint`, `self.assertRaises`, `tiny_model`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_warm_start.py:99 — WarmStart.test_actual_tokenizer_input_contract](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_warm_start.py#L99)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `build_model_input`, `len`, `self.assertEqual`, `self.assertIn`, `self.assertLessEqual`, `self.assertRaises`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/tests/test_warm_start.py:110 — WarmStart.test_fixed_config_has_no_search](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/tests/test_warm_start.py#L110)

- 입력: `self`
- 반환식: 명시 반환값 없음
- 호출 관계: `load_config`, `self.assertEqual`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/verify_handoff.py:12 — sha](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/verify_handoff.py#L12)

- 입력: `path`
- 반환식: `h.hexdigest()`
- 호출 관계: `Path`, `Path(path).open`, `f.read`, `h.hexdigest`, `h.update`, `hashlib.sha256`, `iter`
- 검증/예외: 하위 검증·IO 예외를 전파

### [v3_lite/verify_handoff.py:19 — probe](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v3-lite/v3_lite/verify_handoff.py#L19)

- 입력: `bundle, training, training_sha, output, parent_inventory=None`
- 반환식: 명시 반환값 없음
- 호출 관계: `Path`, `Path(bundle).resolve`, `Path(output).open`, `Path(parent_inventory).read_text`, `abs`, `all`, `changes['groups'].values`, `dict`, `enumerate`, `hashlib.sha256`, `hashlib.sha256(v.detach().contiguous().numpy().tobytes()).hexdigest`, `importlib.util.module_from_spec`, `importlib.util.spec_from_file_location`, `inference_state.items`, `json.dump`, `json.dumps`, `json.loads`, `k.startswith`, `len`, `math.exp`, `max`, `module.V3Predictor`, `module.core.raw_logits`, `module.serve_request`, `payload['model_state_dict'].items`, `predictor.model.eval`, `predictor.model.load_state_dict`, `predictor.model.state_dict`, `print`, `record.items`, `sha`, `spec.loader.exec_module`, `str`, `sum`, `sys.path.insert`, `torch.equal`, `torch.load`, `torch.set_num_threads`, `v.detach`, `v.detach().contiguous`, `v.detach().contiguous().numpy`, `v.detach().contiguous().numpy().tobytes`, `zip`
- 검증/예외: 하위 검증·IO 예외를 전파
