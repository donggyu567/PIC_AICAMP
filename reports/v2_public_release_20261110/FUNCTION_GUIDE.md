# 실제 소스 기반 함수·계약 안내

경로·시작/종료 줄·인수·명시 반환식·검증식·호출 관계는 이 제출본 Python AST에서 추출했다. 함수별 처리는 실제 원본 코드를 읽고 정리했다. 명시 반환식이 없으면 부수효과 후 None이다. 검증식이 많으면 핵심 일부와 원문 링크를 제공한다.

## 1. 배치 대화 파싱: `parse_batch`

- 소스: [experiments/koelectra_v2/stage3_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage3_data.py#L45-L73) — **45~73행**.
- 입력: `path`.
- 반환: `conversations`.
- 처리 및 필요성: 구분자 기반 배치 기록을 대화·발화·출처·잠정 라벨 레코드로 변환한다. 대규모 단일 생성 대신 배치별 검사에 연결한다.
- 예외·검증: `require(current is not None, 'Dialogue header missing')`.
- 모듈 연결(실제 호출): `Path(path).read_text(encoding='utf-8-sig').splitlines, Path(path).read_text, Path, raw.strip, line.startswith, line[2:].split, split.upper, int, dict, sha, datetime.now(timezone.utc).isoformat, datetime.now, conversations.append, require, line.split, labels.sort, current['utterances'].append, len`.
- 관련 테스트: [tests/test_stage3_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage3_data.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 2. 데이터 필수 필드·마스킹: `validate`

- 소스: [experiments/koelectra_v2/stage3_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage3_data.py#L76-L101) — **76~101행**.
- 입력: `conversations, *, expected=None`.
- 반환: `stats(conversations)`.
- 처리 및 필요성: 대화와 가족 ID 중복, 8~10발화, 화자·발화 순서, bool 위험 정답과 유형 정답의 일치, canonical 순서, 가짜 승인, 실제 링크·식별자 패턴을 검사하고 stats에 연결한다. 자동 구조 검사가 라벨 의미 정확성을 인증하지는 않는다.
- 예외·검증: `require(len(conversations) == expected, f'Expected {expected} conversations, got {len(conversations)}')`; `require(c['split'] in ('train', 'validation', 'test'), 'Unknown role')`; `require(c['conversation_id'] not in ids and c['scenario_family_id'] not in families, 'Duplicate ID/family')`; `require(c['source_kind'] == 'llm_synthetic' and c['data_purpose'] == 'internal_experiment', 'Provenance/purpose mismatch')`; `require(c['label_status'] == 'provisional' and c['deployment_approved'] is False, 'False approval')`; `require(8 <= len(c['utterances']) <= 10, 'Conversation length outside 8..10')`.
- 모듈 연결(실제 호출): `require, len, set, ids.add, families.add, enumerate, type, bool, sorted, isinstance, text.strip, re.search, re.findall, keys.add, stats`.
- 관련 테스트: [tests/test_stage3_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage3_data.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 3. 정규화 중복·유사도: `compare`

- 소스: [experiments/koelectra_v2/stage3_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage3_data.py#L136-L157) — **136~157행**.
- 입력: `left, right, *, within=False, threshold=0.8`.
- 반환: `dict(pairs=comparisons, threshold=threshold, candidates=candidates, candidate_count=len(candidates), limit='Lexical screen only, not semantic independence proof')`.
- 처리 및 필요성: NFKC·공백·구두점 정규화 후 완전 중복과 문자열 유사도 0.8 후보를 수집한다. TRAIN/VALIDATION/v1의 어휘 누출 점검이며 의미적 독립성의 증명은 아니다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): `enumerate, SequenceMatcher, matcher.real_quick_ratio, matcher.quick_ratio, matcher.ratio, candidates.append, dict, round, len`.
- 관련 테스트: [tests/test_stage3_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage3_data.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 4. 등록 분할 검증: `validate_split`

- 소스: [experiments/koelectra_v2/expanded_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_data.py#L31-L44) — **31~44행**.
- 입력: `split`.
- 반환: `members`.
- 처리 및 필요성: 분할 schema와 frozen 상태, 대화별 role·가족·출처·작성자 계보를 검증한다. 실제 데이터 승인 검사와 결합해 임의 분할 교체를 막는다.
- 예외·검증: `require(split.get('schema') == 'expanded-split/1' and split.get('frozen') is True, 'Split not frozen')`; `require(bool(members), 'Empty split')`; `require(isinstance(cid, str) and cid and (item['role'] in ROLES), 'Invalid split membership')`; `require(isinstance(key, str) and key.strip(), 'Missing source/family/author grouping')`; `require(key not in seen or seen[key] == role, f'Cross-partition {field}: {key}')`.
- 모듈 연결(실제 호출): `require, split.get, bool, members.items, isinstance, groups.items, key.strip`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 5. 정식 승인 데이터 게이트: `load_partition`

- 소스: [experiments/koelectra_v2/expanded_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_data.py#L83-L166) — **83~166행**.
- 입력: `root, manifest_path, role, *, mode='authorized', fixture=False, test_capability=None`.
- 반환: `Partition(root, path, sha(path), role, tuple(ordered), bindings, authorized, fixture)`.
- 처리 및 필요성: 파일 hash·분할·출처 권리·두 검수자·최종 합의·사용 목적 증빙을 확인한 Partition만 만든다. 연구용 합성 자료가 이 게이트를 자동 통과하도록 수정하지 않았다.
- 예외·검증: `require(role in ROLES and mode in ('authorized', 'preflight', 'final-evaluate'), 'Unknown role/mode')`; `require(path.is_relative_to(root) and path.is_file(), 'Required real manifest is absent')`; `require(mode == 'final-evaluate' and test_capability is not None, 'TEST content is sealed')`; `require(manifest.get('schema') == 'expanded-data/1' and manifest.get('role') == role, 'Wrong manifest role/schema')`; `require(manifest.get('fixture', False) is fixture, 'Fixture/production manifest mismatch')`; `require(not root.is_relative_to(ROOT) and root != ROOT, 'Fixture must be outside the project')`.
- 모듈 연결(실제 호출): `Path(root).resolve, Path, Path(manifest_path).resolve, require, path.is_relative_to, path.is_file, validate_test_capability, read, manifest.get, root.is_relative_to, list, isinstance, checked_file, validate_split, json.loads, data_path.read_text(encoding='utf-8').splitlines, data_path.read_text, line.strip`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 6. 분할 간 계보 교차 검사: `check_disjoint`

- 소스: [experiments/koelectra_v2/expanded_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_data.py#L169-L178) — **169~178행**.
- 입력: `*partitions`.
- 반환: `None` (파일 저장/상태 구성 등 부수효과).
- 처리 및 필요성: 권한이 검증된 Partition들의 대화·가족·출처·작성자 중첩을 검사한다. 각 분할의 승인·데이터 바인딩을 유지하고 누출을 거부한다.
- 예외·검증: `require(len({p.bindings['split_sha256'] for p in partitions}) == 1, 'Different frozen splits')`; `require(not {r[field] for r in first.rows} & {r[field] for r in second.rows}, f'Cross-role leakage: {field}')`.
- 모듈 연결(실제 호출): `require, len, enumerate`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 7. 최대 5개 과거 발화 구성: `causal_samples`

- 소스: [experiments/koelectra_v2/stage3_research.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage3_research.py#L27-L31) — **27~31행**.
- 입력: `conversations`.
- 반환: `tuple((TrainingSample(c['conversation_id'], u['utterance_id'], [x['text'] for x in c['utterances'][max(0, i - 5):i]], u['text'], float(u['is_phishing']), to_multi_hot(u['labels'])) for c in conversations for i, u in enumerate(c['utterances'])))`.
- 처리 및 필요성: 각 현재 발화의 이전 max(0,i-5):i 텍스트만 history로 만들고 현재 위험 여부와 canonical multi-hot 정답을 TrainingSample에 넣는다. 미래 정답의 소급 적용을 막는다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): `tuple, TrainingSample, max, float, to_multi_hot, enumerate`.
- 관련 테스트: [tests/test_stage3_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage3_data.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 8. 연구용 데이터 별도 모드: `load_research`

- 소스: [experiments/koelectra_v2/stage3_research.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage3_research.py#L34-L53) — **34~53행**.
- 입력: `role, *, mode, base=BASE`.
- 반환: `ResearchInput(role, sha(data), sha(path), causal_samples(conversations))`.
- 처리 및 필요성: role과 internal_experiment를 파일 IO 전에 제한한다. source_kind·purpose·잠정 라벨·미검수/미배포 상태·hash를 확인한 ResearchInput을 반환하며 정식 authorized Partition으로 위장하지 않는다.
- 예외·검증: `require(role in ('train', 'validation'), 'Research development cannot access TEST')`; `require(mode == 'internal_experiment', 'Explicit internal_experiment mode is required')`; `require(manifest.get('schema') == 'internal-research-data/1', 'Wrong research schema')`; `require(manifest['purpose'] == 'internal_experiment' and manifest['source_kind'] == 'llm_synthetic', 'Research provenance mismatch')`; `require(manifest['human_review_complete'] is False and manifest['deployment_approved'] is False and (manifest['production_training_authorized'] is False), 'Research input must not assert production approval')`; `require(manifest['label_order'] == list(LABELS), 'Canonical label order mismatch')`.
- 모듈 연결(실제 호출): `require, Path(base).resolve, Path, read, manifest.get, list, checked_file, jsonl, validate, all, c.get, ResearchInput, sha, causal_samples`.
- 관련 테스트: [tests/test_stage3_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage3_data.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 9. 기존 v1 라벨·텍스트 결합: `build_training_samples`

- 소스: [artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/training_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/training_data.py#L105-L186) — **105~186행**.
- 입력: `label_rows: Iterable[Mapping[str, Any]], tuned_rows: Iterable[Mapping[str, Any]]`.
- 반환: `BuildResult(samples=samples, statistics=dict(statistics))`.
- 처리 및 필요성: conversation_id와 utterance_id 복합 키로 라벨과 입력을 결합하고 현재 발화의 정답을 구성한다. 중복·누락·형식·상태 문제를 분리해 기록하는 기존 코드이며 임의 정답 정렬을 방지한다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): `Counter, _index, set, len, defaultdict, tuned.items, row.get, isinstance, value.strip, histories[conversation_id].append, _order, histories.values, entries.sort, sorted, label_row.get, _targets, samples.append, TrainingSample`.
- 관련 테스트: [artifacts/v1_reference/pr35_9bab7e383928/tests/test_training_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/tests/test_training_data.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 10. 정답 벡터 라벨 순서: `to_multi_hot`

- 소스: [artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/labels.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/labels.py#L20-L35) — **20~35행**.
- 입력: `labels: Iterable[str]`.
- 반환: `targets`.
- 처리 및 필요성: 등록된 LABELS 순서대로 8차원 벡터를 만든다. 위험 유형 문자열과 학습 head·평가·서버 출력 순서를 일치시키는 공통 계약이다.
- 예외·검증: `raise ValueError('labels must be an iterable of label names')`; `raise ValueError('labels must be an iterable of label names') from error`; `raise ValueError(f'unknown label: {label!r}')`.
- 모듈 연결(실제 호출): `isinstance, ValueError, iter`.
- 관련 테스트: [artifacts/v1_reference/pr35_9bab7e383928/tests/test_training_data.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/tests/test_training_data.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 11. 문장쌍 토큰화: `build_model_input`

- 소스: [artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/tokenization.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/tokenization.py#L119-L153) — **119~153행**.
- 입력: `history_texts: Sequence[str], current_text: str, *, tokenizer: Any`.
- 반환: `TokenizedInput(input_ids=result.input_ids, attention_mask=result.attention_mask, token_type_ids=result.token_type_ids, used_history_texts=list(used), dropped_history_count=dropped, token_count=result.token_count)`.
- 처리 및 필요성: [CLS] history [SEP] current [SEP]와 segment 0/1을 구성한다. 최대 512토큰에 맞추기 위해 가장 오래된 history 발화 전체를 제거하고 현재 단독 초과는 오류로 처리한다.
- 예외·검증: `raise TokenizerContractError('tokenizer padding_side must be right for CLS pooling')`; `raise ValueError('history_texts must be a sequence of strings')`; `raise ValueError('history_texts must contain only non-empty strings')`; `raise ValueError('current_text must be a non-empty string')`; `raise InputTooLongError(result.token_count, dropped)`.
- 모듈 연결(실제 호출): `getattr, TokenizerContractError, isinstance, ValueError, any, text.strip, current_text.strip, list, len, _encode_pair, TokenizedInput, InputTooLongError, used.pop`.
- 관련 테스트: [artifacts/v1_reference/pr35_9bab7e383928/tests/test_tokenization.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/tests/test_tokenization.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 12. Dataset 샘플 텐서: `RiskSpeechDataset.__getitem__`

- 소스: [artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/dataset.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/dataset.py#L44-L45) — **44~45행**.
- 입력: `self, index: int`.
- 반환: `self.items[index]`.
- 처리 및 필요성: TrainingSample을 토큰화해 입력과 risk_target/type_targets를 반환한다. history/current와 해당 발화 라벨을 같은 index에 유지한다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): ``.
- 관련 테스트: [artifacts/v1_reference/pr35_9bab7e383928/tests/test_dataset.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/tests/test_dataset.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 13. 동적 패딩: `DynamicPaddingCollator.__call__`

- 소스: [artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/dataset.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/dataset.py#L54-L72) — **54~72행**.
- 입력: `self, items: list[dict[str, Any]]`.
- 반환: `{'input_ids': batch['input_ids'], 'attention_mask': batch['attention_mask'], 'token_type_ids': batch['token_type_ids'], 'risk_target': torch.tensor([[item['risk_target']] for item in items], dtype=torch.float32), 'type_targets': torch.tensor([item['type_targets'] for item in items], dtype=torch.float32)}`.
- 처리 및 필요성: 배치 내 길이로 right padding한 입력 텐서와 [B,1]/[B,8] 정답 텐서를 묶는다. tokenizer와 CPU DataLoader의 shape 계약을 연결한다.
- 예외·검증: `raise ValueError('cannot collate an empty batch')`.
- 모듈 연결(실제 호출): `ValueError, self.tokenizer.pad, torch.tensor`.
- 관련 테스트: [artifacts/v1_reference/pr35_9bab7e383928/tests/test_dataset.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/tests/test_dataset.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 14. 실제 DataLoader: `make_training_dataloader`

- 소스: [artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/dataset.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/dataset.py#L75-L89) — **75~89행**.
- 입력: `dataset: RiskSpeechDataset, *, tokenizer: Any, batch_size: int, shuffle: bool=True, seed: int=42`.
- 반환: `DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, collate_fn=DynamicPaddingCollator(tokenizer), generator=generator, num_workers=0)`.
- 처리 및 필요성: Dataset·collator·batch_size·shuffle/seed로 PyTorch DataLoader를 만든다. 학습 shuffle과 평가 고정 순서를 구분한다.
- 예외·검증: `raise ValueError('batch_size must be a positive integer')`.
- 모듈 연결(실제 호출): `isinstance, ValueError, torch.Generator().manual_seed, torch.Generator, DataLoader, DynamicPaddingCollator`.
- 관련 테스트: [artifacts/v1_reference/pr35_9bab7e383928/tests/test_dataset.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/tests/test_dataset.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 15. 공유 KoELECTRA와 두 head: `RiskSpeechClassifier.__init__`

- 소스: [artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/model.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/model.py#L24-L33) — **24~33행**.
- 입력: `self, encoder: ElectraModel | None=None, *, model_revision: str | None=None`.
- 반환: `None` (파일 저장/상태 구성 등 부수효과).
- 처리 및 필요성: 공유 ELECTRA encoder에 이진 risk head와 8종 type head를 붙인다. raw logits를 반환하는 forward와 결합하며 모델 내부 sigmoid 중복을 피한다.
- 예외·검증: `raise ValueError('model_revision cannot be used with a supplied encoder')`.
- 모듈 연결(실제 호출): `super().__init__, super, ValueError, ElectraModel.from_pretrained, nn.Linear`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 16. [B,1]·[B,8] logits: `RiskSpeechClassifier.forward`

- 소스: [artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/model.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/model.py#L35-L57) — **35~57행**.
- 입력: `self, input_ids: torch.Tensor, attention_mask: torch.Tensor, token_type_ids: torch.Tensor`.
- 반환: `ModelOutput(risk_logits=self.risk_classifier(cls_state), type_logits=self.type_classifier(cls_state))`.
- 처리 및 필요성: encoder의 첫 토큰 표현을 공유하여 위험 여부와 유형 logits를 별도로 계산한다. 학습 BCE와 서버 sigmoid가 동일 출력을 사용한다.
- 예외·검증: `raise ValueError('input_ids must have non-empty batch shape [B, L]')`; `raise ValueError(f'sequence length must be between 1 and {MAX_SEQUENCE_LENGTH}')`; `raise ValueError('attention_mask and token_type_ids must match input_ids shape [B, L]')`.
- 모듈 연결(실제 호출): `ValueError, self.encoder, ModelOutput, self.risk_classifier, self.type_classifier`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 17. 이진·유형 손실: `losses`

- 소스: [experiments/koelectra_v2/expanded_training.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_training.py#L38-L49) — **38~49행**.
- 입력: `output, risk, types, weights`.
- 반환: `(total, base.risk_loss, weighted)`.
- 처리 및 필요성: 기존 risk BCE에 canonical 8종 pos_weight를 적용한 type BCEWithLogitsLoss를 더한다. binary target·유한 logits·가중치 길이와 손실을 검사해 비정상 수치로 업데이트하지 않는다.
- 예외·검증: `require(len(weights) == 8 and all((math.isfinite(w) and w >= 0 for w in weights)), 'Invalid loss weights')`; `require(all((torch.isfinite(t).all().item() for t in tensors)), 'Non-finite logits/targets')`; `require(all((torch.isin(t, torch.tensor([0.0, 1.0], device=t.device)).all().item() for t in (risk, types))), 'Targets must be binary')`; `require(torch.isfinite(total).item(), 'Non-finite BCE loss')`.
- 모듈 연결(실제 호출): `compute_losses, require, len, all, math.isfinite, torch.isfinite(t).all().item, torch.isfinite(t).all, torch.isfinite, torch.isin(t, torch.tensor([0.0, 1.0], device=t.device)).all().item, torch.isin(t, torch.tensor([0.0, 1.0], device=t.device)).all, torch.isin, torch.tensor, torch.nn.functional.binary_cross_entropy_with_logits, torch.isfinite(total).item`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 18. TRAIN 전용 양성 가중치: `positive_weights`

- 소스: [experiments/koelectra_v2/expanded_training.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_training.py#L19-L35) — **19~35행**.
- 입력: `partition, *, policy='ratio10', label_order=LABELS`.
- 반환: `dict(values=values, label_order=list(LABELS), unsupported=unsupported, source='original_TRAIN_only', train_bindings=partition.bindings, policy=policy)`.
- 처리 및 필요성: 승인된 TRAIN Partition에서 음성/양성 비율을 계산해 ratio10 또는 legacy sqrt5 정책으로 제한한다. 0양성은 1과 unsupported 경고를 기록하며 VALIDATION/TEST를 사용하지 않는다.
- 예외·검증: `require(list(label_order) == list(LABELS), 'Weight label order mismatch')`; `require(policy in ('ratio10', 'sqrt5'), 'Unknown loss-weight recipe')`; `require(all((math.isfinite(v) and v >= 0 for v in values)), 'Non-finite/negative positive weight')`.
- 모듈 연결(실제 호출): `partition.verify, require, list, sum, values.append, unsupported.append, warnings.warn, len, min, max, math.sqrt, all, math.isfinite, dict`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 19. 정식 학습 실행기: `train`

- 소스: [experiments/koelectra_v2/expanded_training.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_training.py#L60-L169) — **60~169행**.
- 입력: `config, base, validation, tokenizer, *, run_id, synthetic=None, receipt=None, store_root=None, fixture_model_factory=None, cache=None`.
- 반환: `result`.
- 처리 및 필요성: 등록 config·승인 Partition·봉인 영수증과 초기화 조건을 검사해 새 모델을 학습하고 RunStore와 평가기로 연결한다. C와 step-matched는 승인 증강/동결 B 설정이 없으면 차단한다. 실제 4차 연구 실행은 아래 별도 train을 사용했다.
- 예외·검증: `require(any((row['is_phishing'] for row in validation.rows)), 'VALIDATION needs risk positives for epoch selection')`; `require(base.fixture == validation.fixture, 'Fixture/production data mixed')`; `require(isinstance(receipt, SealedReceipt), 'External TEST sealing receipt required before training')`; `require(receipt['split_sha256'] == base.bindings['split_sha256'], 'TEST sealing split differs')`; `require(sha(base.manifest_path) == base.manifest_sha256, 'TRAIN manifest changed')`; `require(synthetic is not None, 'C blocked: no approved synthetic TRAIN manifest')`.
- 모듈 연결(실제 호출): `validate_runtime, base.verify, validation.verify, require, any, check_disjoint, isinstance, receipt.verify, sha, base.samples, list, positive_weights, dict, digest, synthetic.verify, validate_frozen_checkpoints, synthetic.samples, step_budget`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 20. 4차 내부 연구 사전 검사: `precheck`

- 소스: [experiments/koelectra_v2/stage4_exploratory.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage4_exploratory.py#L69-L104) — **69~104행**.
- 입력: ``.
- 반환: `(train, val, convs, bindings)`.
- 처리 및 필요성: 3차 완료/품질·TRAIN/VALIDATION의 출처·사용 목적·분할·hash와 기존 권리 미확인 v1 제외를 검증한다. TEST 본문을 읽지 않고 연구용 두 입력과 바인딩을 만든다.
- 예외·검증: `raise ValueError('Development account can open TEST vault')`; `require(read(STAGE3 / 'tests.json')['status'] == 'PASS', 'Stage3 regression incomplete')`; `require(read(STAGE3 / 'preservation.json')['status'] == 'PASS', 'Stage3 preservation incomplete')`; `require(read(STAGE3 / 'cpu_dataloader.json')['status'] == 'PASS', 'Stage3 CPU incomplete')`; `require(receipt['sealed'] and receipt['phase5_release_required'] and (receipt['stats']['conversations'] == 40), 'TEST sealing incomplete')`; `require(sha(BASE / 'test_seal_receipt.json') == split['test_receipt_sha256'], 'Receipt binding changed')`.
- 모듈 연결(실제 호출): `require, read, load_research, sha, list, AUTHORED.glob, Path(receipt['vault_path']).open, Path, ValueError, Counter, len, jsonl, all, convs.items, validate, c.get, dict`.
- 관련 테스트: [tests/test_stage4_exploratory.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage4_exploratory.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 21. 실제 B_ratio 가중치: `weights_from_rows`

- 소스: [experiments/koelectra_v2/stage4_exploratory.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage4_exploratory.py#L145-L147) — **145~147행**.
- 입력: `rows`.
- 반환: `[min(10.0, max(1.0, (len(rows) - p) / p)) if p else 1.0 for p in counts]`.
- 처리 및 필요성: 제공된 TRAIN 행의 유형 양성 비율만 사용해 max 10 가중치를 구성한다. 동일 가중치 계산을 seed마다 적용해 실험 비교 조건을 유지한다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): `sum, min, max, len`.
- 관련 테스트: [tests/test_stage4_exploratory.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage4_exploratory.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 22. 실제 6개 학습 궤적: `train`

- 소스: [experiments/koelectra_v2/stage4_exploratory.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage4_exploratory.py#L176-L254) — **176~254행**.
- 입력: `arm, seed`.
- 반환: `None` (파일 저장/상태 구성 등 부수효과).
- 처리 및 필요성: 공개 encoder 고정 revision과 seed별 새 head에서 시작한다. CPU FP32, batch8, AdamW, gradient checkpointing, 3 epoch를 수행하고 유한 gradient/parameter 확인 후 optimizer.step한다. epoch별 원본 .pt·optimizer·VALIDATION logits·loss·best/last를 별도 저장한다. A0는 첫 epoch hardlink snapshot이다.
- 예외·검증: `require(bindings == manifest['bindings'] and digest(code_inventory()) == manifest['code_sha256'], 'Inputs/code changed after execution registration')`; `require(all((p.grad is None or torch.isfinite(p.grad).all().item() for p in model.parameters())), 'Nonfinite gradient')`; `require(all((torch.isfinite(p).all().item() for p in model.parameters())), 'Nonfinite parameter')`.
- 모듈 연결(실제 호출): `precheck, read, require, digest, code_inventory, research_config, path.mkdir, torch.set_num_threads, torch.set_num_interop_threads, load_tokenizer, resources, time.monotonic, event, fresh_public_model(seed).cpu, fresh_public_model, model.encoder.gradient_checkpointing_enable, t.tolist, model.state_dict().items`.
- 관련 테스트: [tests/test_stage4_exploratory.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage4_exploratory.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 23. 실제 연구 모델 선택·비교: `summarize`

- 소스: [experiments/koelectra_v2/stage4_exploratory.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage4_exploratory.py#L268-L320) — **268~320행**.
- 입력: ``.
- 반환: `None` (파일 저장/상태 구성 등 부수효과).
- 처리 및 필요성: 저장된 VALIDATION 예측의 역할·identity·hash를 검증하고 사전 등록한 epoch/threshold tie 규칙으로 선택한다. B_ratio 후보 정책, 3개 seed와 차단 arm을 기록하며 TEST를 통해 선택하지 않는다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): `precheck, flatten, read, validate_prediction, float, np.mean, evaluate_logits, min, targets, probabilities, range, int, y[:, i].sum, len, enumerate, binary_metrics, thresholds.append, support.append`.
- 관련 테스트: [tests/test_stage4_exploratory.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage4_exploratory.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 24. VALIDATION epoch 선택: `select_epoch`

- 소스: [experiments/koelectra_v2/expanded_selection.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_selection.py#L14-L30) — **14~30행**.
- 입력: `predictions, partition`.
- 반환: `dict(epoch=best, mean_seed_f1=scores, selection_role='validation')`.
- 처리 및 필요성: 동일 VALIDATION의 모든 등록 seed별 epoch 지표를 검증하고 seed 평균 이진 F1 기준을 적용한다. 동률은 이른 epoch로 정하며 seed 하나만 유리하게 고르지 않는다.
- 예외·검증: `require(set(predictions) == {1, 2, 3}, 'Epochs 1,2,3 must all be present')`; `require(set(by_seed) == set(SEEDS), 'All registered seeds required for epoch selection')`; `require(item['seed'] == seed and item['epoch'] == epoch, 'Epoch/seed provenance differs')`; `require(value is not None, 'Validation has no positive risk support')`.
- 모듈 연결(실제 호출): `partition.verify, require, set, targets, predictions.items, by_seed.items, validate_predictions, binary_metrics, probabilities, values.append, float, np.mean, min, dict`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 25. 9개 임계값 선택: `select_thresholds`

- 소스: [experiments/koelectra_v2/expanded_selection.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_selection.py#L33-L56) — **33~56행**.
- 입력: `by_seed, partition`.
- 반환: `dict(values=values, support=support, output_order=['risk'] + list(LABELS))`.
- 처리 및 필요성: 등록된 VALIDATION grid와 tie 규칙을 출력별 적용한다. 선택 출력은 risk+8유형 순서이며 최종 고정값은 모두 0.5다. TEST 임계값 탐색은 없다.
- 예외·검증: `require(set(by_seed) == set(SEEDS), 'All registered seeds required for threshold selection')`; `require(item['seed'] == seed, 'Seed provenance mismatch')`; `require(len({item['epoch'] for item in by_seed.values()}) == 1, 'Thresholds require the same selected epoch')`.
- 모듈 연결(실제 호출): `partition.verify, require, set, by_seed.items, validate_predictions, len, by_seed.values, targets, probabilities, range, int, y[:, index].sum, enumerate, float, np.mean, binary_metrics, min, values.append`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 26. B 선택 동결: `freeze_b`

- 소스: [experiments/koelectra_v2/expanded_selection.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_selection.py#L59-L70) — **59~70행**.
- 입력: `predictions, partition, weights, train_bindings, *, version, checkpoints`.
- 반환: `bundle`.
- 처리 및 필요성: 검증된 epoch·threshold·TRAIN weights·checkpoints·데이터 바인딩을 새 버전 bundle로 고정한다. 후속 C/step 비교가 임의 설정으로 바뀌지 않게 한다.
- 예외·검증: `require(isinstance(version, str) and version and (version != 'initial-0.5'), 'New threshold version required')`; `require(all((p['arm'] == 'B_ratio' for items in predictions.values() for p in items.values())), 'Only B_ratio can freeze C recipe')`.
- 모듈 연결(실제 호출): `require, isinstance, all, predictions.values, items.values, select_epoch, select_thresholds, dict, list, validate_frozen`.
- 관련 테스트: [tests/test_expanded_guards.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_guards.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 27. 새 epoch 체크포인트 저장: `RunStore.epoch`

- 소스: [experiments/koelectra_v2/expanded_checkpoint.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_checkpoint.py#L86-L92) — **86~92행**.
- 입력: `self, checkpoint`.
- 반환: `reference`.
- 처리 및 필요성: 기존 PR35 envelope에 v2 확장 metadata와 optimizer 상태를 포함해 새 epoch 파일을 원자적으로 생성한다. 예약된 run/중복 파일·기존 가중치 덮어쓰기를 거부한다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): `validate_extended, publish, dict, str, sha, write_json, target.with_suffix`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 28. v2 checkpoint 검증·재로딩: `load_v2`

- 소스: [experiments/koelectra_v2/expanded_checkpoint.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_checkpoint.py#L104-L123) — **104~123행**.
- 입력: `path, *, expected_sha256, bindings=None, model=None, tokenizer=None, optimizer=None, fixture=False`.
- 반환: `checkpoint`.
- 처리 및 필요성: 파일 SHA와 schema·model config·tokenizer·확장 metadata·optimizer 상태를 검증하고 재로딩한다. 공식/fixture 혼합과 변조를 거부한다.
- 예외·검증: `require(sha(path) == expected_sha256, 'Checkpoint file hash mismatch')`; `require(tokenizer is not None, 'Tokenizer required for model load')`; `require(set(expected) == set(checkpoint['model_state_dict']), 'Model state keys differ')`; `require(all((expected[k].shape == v.shape for k, v in checkpoint['model_state_dict'].items())), 'State shape mismatch')`.
- 모듈 연결(실제 호출): `require, sha, torch.load, validate_extended, validate_model_config, validate_tokenizer, model.state_dict, set, all, checkpoint['model_state_dict'].items, copy.deepcopy, temporary.load_state_dict, model.load_state_dict, any, model.parameters, materialize_buffers, optimizer.load_state_dict`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 29. v1 envelope 복원: `load_training_checkpoint`

- 소스: [artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/checkpoint.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/checkpoint.py#L202-L222) — **202~222행**.
- 입력: `path: str | Path, model: Any, *, tokenizer: Any, optimizer: torch.optim.Optimizer | None=None, map_location: str | torch.device='cpu', checkpoint: dict[str, Any] | None=None`.
- 반환: `loaded`.
- 처리 및 필요성: 기존 checkpoint schema와 모델·tokenizer 계약을 검사하며 안전한 weights_only 로딩을 수행한다. v2는 이 v1 envelope를 그대로 보존하고 연구 확장을 별도 기록한다.
- 예외·검증: `raise CheckpointCompatibilityError('checkpoint model state_dict is incompatible') from error`.
- 모듈 연결(실제 호출): `read_checkpoint, validate_checkpoint_metadata, validate_model_config, validate_tokenizer, copy.deepcopy, temporary_model.load_state_dict, CheckpointCompatibilityError, model.load_state_dict, temporary_model.state_dict, optimizer.load_state_dict`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 30. 평가 지표 집계: `evaluate_logits`

- 소스: [experiments/koelectra_v2/expanded_evaluation.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/expanded_evaluation.py#L47-L92) — **47~92행**.
- 입력: `rows, logits, thresholds=(0.5,) * 9`.
- 반환: `dict(binary=score_binary(y[:, 0], p[:, 0], t[0]), per_type=per_type, micro=dict(precision=tp / (tp + fp) if tp + fp else None, recall=tp / (tp + fn) if tp + fn else None, f1=2 * tp / (2 * tp + fp + fn) if tp + fn else None, tp=tp, fp=fp, fn=fn), macro=dict(f1=float(np.mean(defined)) if defined else None, defined_labels=len(defined), full8_f1=float(np.mean(defined)) if len(defined) == 8 else None), hard_negative=dict(n=len(hn), fp=int(predicted[hn`.
- 처리 및 필요성: [N,9] logits에 sigmoid를 한 번 적용하고 고정 thresholds로 이진/유형 P/R/F1/AP/ROC-AUC, 정상 대화 오탐·위험 대화 미탐과 support를 계산한다. 누락 양성/정의 불가 지표를 허위 0으로 만들지 않는다.
- 예외·검증: `require(y.shape == p.shape, 'Prediction/target alignment mismatch')`.
- 모듈 연결(실제 호출): `probabilities, threshold_vector, targets, require, enumerate, score_binary, len, sum, per_type.values, defaultdict, conversations[row['conversation_id']].append, conversations.values, y[ids, 0].any, sorted, dict, float, np.mean, int`.
- 관련 테스트: [tests/test_expanded_pipeline.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_expanded_pipeline.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 31. 사용자 범위 TEST 암호화: `dpapi`

- 소스: [experiments/koelectra_v2/stage3_seal.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage3_seal.py#L28-L44) — **28~44행**.
- 입력: `payload, *, check=False`.
- 반환: `ctypes.string_at(target.data, target.size)`.
- 처리 및 필요성: Windows DPAPI를 호출해 메모리의 bytes를 사용자 범위로 보호/복호화한다. 사용자 context가 다르면 복호화를 허용하지 않는다. stage5.decrypt에서 기존 함수만 재사용한다.
- 예외·검증: `require(ok, f'DPAPI failed: {ctypes.get_last_error()}')`.
- 모듈 연결(실제 호출): `ctypes.create_string_buffer, Blob, len, ctypes.cast, ctypes.POINTER, ctypes.WinDLL, fn, ctypes.byref, require, ctypes.get_last_error, ctypes.string_at, kernel.LocalFree`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 32. 동결 평가 계획 검증: `validate_plan`

- 소스: [experiments/koelectra_v2/stage5_custody.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_custody.py#L27-L40) — **27~40행**.
- 입력: `path`.
- 반환: `p`.
- 처리 및 필요성: 고정된 후보/비교 arm·seed·epoch·라벨·9개 threshold·데이터 바인딩·코드 hash·영수증 hash를 기존 선택과 대조한다. 계획이나 모델을 TEST 직전에 바꾸는 것을 거부한다.
- 예외·검증: `require(p['schema'] == 'research-sealed-evaluation-plan/1', 'Wrong plan schema')`; `require(p['primary_candidate'] == 'B_ratio' and p['comparison_arm'] == 'A_epoch' and (p['seeds'] == list(SEEDS)), 'Plan model family changed')`; `require(p['thresholds'] == [0.5] * 9 and p['epoch'] == 3 and (p['label_order'] == list(LABELS)), 'Frozen inference settings changed')`; `require(p['human_approved'] is False and p['deployment_approved'] is False, 'Research plan must remain unapproved for production')`; `require(sha(STAGE4 / 'frozen_selection.json') == p['stage4_selection_sha256'], 'Original selection changed')`; `require(p['bindings'] == selection['bindings'] and p['models'] == {a: selection['checkpoints'][a] for a in ['B_ratio', 'A_epoch']}, 'Plan changes frozen model references')`.
- 모듈 연결(실제 호출): `read, require, list, sha, p['evaluation_code'].items, digest`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 33. 명시 승인 증빙 검증: `validate_approval`

- 소스: [experiments/koelectra_v2/stage5_custody.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_custody.py#L43-L51) — **43~51행**.
- 입력: `release, *, plan_sha, receipt_sha, custodian_sid, now`.
- 반환: `None` (파일 저장/상태 구성 등 부수효과).
- 처리 및 필요성: 실제 custodian SID, 계획/영수증 hash, 명시 승인 근거, timezone 포함 24시간 이하 유효기간과 승인 범위를 검사한다. 평가 승인을 인간 라벨 검수/배포 승인으로 전환하지 않는다.
- 예외·검증: `require(release.get('schema') == 'custodian-explicit-test-release/1', 'Wrong explicit release schema')`; `require(release.get('approved_action') == 'one_time_fixed_plan_test_evaluation', 'Missing explicit one-time evaluation approval')`; `require(release.get('plan_sha256') == plan_sha and release.get('receipt_sha256') == receipt_sha, 'Release not bound to fixed plan and TEST')`; `require(release.get('custodian_sid') == custodian_sid, 'Release custodian mismatch')`; `require(isinstance(release.get('approval_reference'), str) and release['approval_reference'].strip(), 'Real explicit approval reference required')`; `require(stamp.tzinfo is not None and expires.tzinfo is not None and (stamp <= now <= expires) and (expires - stamp <= timedelta(hours=24)), 'Release time window invalid')`.
- 모듈 연결(실제 호출): `require, release.get, isinstance, release['approval_reference'].strip, datetime.fromisoformat, timedelta`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 34. 접근 전 승인 게이트: `gate`

- 소스: [experiments/koelectra_v2/stage5_custody.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_custody.py#L54-L64) — **54~64행**.
- 입력: `plan_path, release_path`.
- 반환: `(plan, receipt, release, vault)`.
- 처리 및 필요성: 승인 누락을 TEST IO 전에 거부하고 실제 Windows SID·보호 vault 안의 release 위치·계획 바인딩·시간을 확인한다. 공개 PR에는 실제 release/영수증/SID 값을 제공하지 않는다.
- 예외·검증: `require(release_path is not None, 'WAITING_EXPLICIT_CUSTODIAN_APPROVAL; TEST remains sealed')`; `require(sid == receipt['custodian_sid'] and 'codexsandbox' not in account.lower(), 'Actual custodian Windows context required')`; `require(release_path.is_relative_to(vault), 'Release must be stored under custodian-only vault ACL')`.
- 모듈 연결(실제 호출): `require, validate_plan, read, identity, account.lower, Path(receipt['vault_path']).parent.resolve, Path, Path(release_path).resolve, release_path.is_relative_to, validate_approval, sha, datetime.now`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 35. 별도 승인 후 접근 파일 발급: `issue_release`

- 소스: [experiments/koelectra_v2/stage5_custody.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_custody.py#L67-L77) — **67~77행**.
- 입력: `plan_path, reference, acknowledge`.
- 반환: `None` (파일 저장/상태 구성 등 부수효과).
- 처리 및 필요성: 명시 acknowledgement와 실제 승인 참조가 있고 등록 보관자 context일 때만 새 release를 기록한다. 준비 명령이나 계정 일치만으로 승인을 꾸미지 않는다. 실제 발급 파일은 공개하지 않는다.
- 예외·검증: `require(acknowledge and isinstance(reference, str) and reference.strip(), 'Separate explicit custodian approval is required; this command is not preparation')`; `require(sid == receipt['custodian_sid'] and 'codexsandbox' not in account.lower(), 'Actual custodian context required')`.
- 모듈 연결(실제 호출): `require, isinstance, reference.strip, validate_plan, read, identity, account.lower, datetime.now, Path, sha, write_json, dict, now.isoformat, (now + timedelta(hours=24)).isoformat, timedelta, print`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 36. 원자적 1회 실행 예약: `reserve_once`

- 소스: [experiments/koelectra_v2/stage5_custody.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_custody.py#L80-L86) — **80~86행**.
- 입력: `vault, plan_sha, release_sha`.
- 반환: `path`.
- 처리 및 필요성: vault 전체에 고정된 claim 파일을 배타 생성하여 다른 계획/seed로 재실행하는 우회를 막는다. 실패해도 claim을 자동 삭제하거나 재시도하지 않는다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): `Path, write_json, dict, datetime.now(timezone.utc).isoformat, datetime.now`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 37. 승인된 최종 1회 평가: `evaluate`

- 소스: [experiments/koelectra_v2/stage5_custody.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_custody.py#L120-L177) — **120~177행**.
- 입력: `plan_path, release_path`.
- 반환: `None` (파일 저장/상태 구성 등 부수효과).
- 처리 및 필요성: 모든 모델 hash 확인 후 단일 claim을 소비하고 TEST를 메모리에서만 해제한다. 영수증 membership/hash/support를 확인하고 A/B 3seed와 v1 하나를 같은 causal 입력으로 평가한다. 원문·정답·개별 logits는 반출하지 않고 집계만 보호 vault에 저장하며 예외는 claim 소비 상태로 남긴다.
- 예외·검증: `raise RuntimeError('Evaluation failed; claim remains consumed. Custodian review required.') from None`; `require(sha(ref['path']) == ref['sha256'], 'Model file changed')`; `require(sha(plan['v1']['checkpoint']['path']) == plan['v1']['checkpoint']['sha256'], 'v1 file changed')`; `require(hashlib.sha256(cipher).hexdigest() == receipt['ciphertext_sha256'], 'Sealed cipher hash mismatch')`; `require(hashlib.sha256(plain).hexdigest() == receipt['payload_sha256'], 'Sealed plaintext payload hash mismatch')`; `require(members == receipt['split_membership'] and all((c['split'] == 'test' for c in records)), 'TEST membership mismatch')`.
- 모듈 연결(실제 호출): `gate, torch.set_num_threads, load_tokenizer, plan['models'].items, models.items, require, sha, reserve_once, Path(receipt['vault_path']).read_bytes, Path, hashlib.sha256(cipher).hexdigest, hashlib.sha256, decrypt, hashlib.sha256(plain).hexdigest, json.loads, validate, dict, all`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 38. 가족 단위 불확실성: `family_bootstrap`

- 소스: [experiments/koelectra_v2/stage5_custody.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_custody.py#L94-L117) — **94~117행**.
- 입력: `rows, logits_by_arm, thresholds, *, repetitions=2000, seed=20261110`.
- 반환: `dict(valid_repetitions=len(v), ci95=np.percentile(v, [2.5, 97.5]).tolist() if v else None)`; `dict(unit='scenario_family_id', families=len(families), repetitions=repetitions, seed=seed, note='Registered families equal conversations in this corpus; semantic independence unverified. Seed-mean metrics, not probability ensembling.', by_arm={a: dict(zip(['risk'] + list(LABELS), [summary(x) for x in v])) for a, v in values.items()}, paired_binary_f1_delta_B_minus_comparator={a: summary(v) for a, v in deltas.items()}, missing_positive_support_po`.
- 처리 및 필요성: 등록 가족별 재표집 2,000회와 고정 seed20261110으로 seed 평균 F1 및 paired B−A/v1 구간을 계산한다. 양성 지원이 사라진 표본은 해당 지표에서 제외하고 실제 유효 반복 수를 기록한다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): `targets, sorted, enumerate, np.asarray, probabilities, seeds.values, logits_by_arm.items, np.random.default_rng, range, rng.choice, len, y[ids].astype, actual.sum, predictions.items, (subset & actual).sum, (subset & ~actual).sum, (~subset & actual).sum, np.divide(2 * tp, denom, out=np.zeros_like(tp, dtype=float), where=denom != 0).mean`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 39. 연구/기존 모델 CPU 로딩: `load_model`

- 소스: [experiments/koelectra_v2/stage5_runtime.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_runtime.py#L51-L78) — **51~78행**.
- 입력: `path, expected_sha, tokenizer, *, arm=None, seed=None, bindings=None, legacy=False`.
- 반환: `(model, metadata)`.
- 처리 및 필요성: 모델 SHA·schema·seed/arm/epoch·연구/배포 상태·bindings·tokenizer 내용과 probe를 검증한다. meta 초기화/assign 로딩 뒤 비직렬화 ELECTRA buffer만 복구해 CPU 메모리를 절약한다.
- 예외·검증: `require(sha(path) == expected_sha, 'Checkpoint SHA mismatch')`; `require(ext.get('schema') == 'exploratory-checkpoint/1' and ext['arm'] == arm and (ext['seed'] == seed) and (ext['epoch'] == 3), 'Wrong frozen research checkpoint')`; `require(ext['bindings'] == bindings, 'Checkpoint data bindings mismatch')`; `require(ext['policy']['human_approved'] is False and ext['policy']['deployment_approved'] is False, 'Research checkpoint approval mismatch')`; `require(name in ('position_ids', 'token_type_ids') and name in module._non_persistent_buffers_set, 'Unexpected meta buffer')`.
- 모듈 연결(실제 호출): `require, sha, torch.load, validate_checkpoint_metadata, compatible_tokenizer, checkpoint.get, ext.get, ElectraConfig.from_dict, metadata['encoder_config'].get, config.to_dict, torch.device, RiskSpeechClassifier, ElectraModel, validate_model_config, model.load_state_dict, model.modules, list, module._buffers.items`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 40. 서버 입력 검사: `validate_request`

- 소스: [experiments/koelectra_v2/stage5_runtime.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_runtime.py#L99-L104) — **99~104행**.
- 입력: `request`.
- 반환: `(history, current)`.
- 처리 및 필요성: history_texts와 current_text 타입·내용·최대 과거 발화 수를 검증한다. 잘못된 입력이 정상 위험 점수로 변환되지 않도록 추론 전에 실패한다.
- 예외·검증: `require(isinstance(request, dict) and set(request) <= {'history_texts', 'current_text'}, 'Unknown request fields')`; `require(isinstance(history, list) and len(history) <= 100 and all((isinstance(t, str) and t.strip() and (len(t) <= 32000) for t in history)), 'Invalid history_texts')`; `require(isinstance(current, str) and current.strip() and (len(current) <= 32000), 'Invalid current_text')`.
- 모듈 연결(실제 호출): `require, isinstance, set, request.get, len, all, t.strip, current.strip`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 41. manifest 신뢰와 서버 초기화: `ResearchPredictor.__init__`

- 소스: [experiments/koelectra_v2/stage5_runtime.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_runtime.py#L119-L132) — **119~132행**.
- 입력: `self, bundle=HERE, seed=42, *, expected_manifest_sha=None`.
- 반환: `None` (파일 저장/상태 구성 등 부수효과).
- 처리 및 필요성: 호출자가 외부에서 신뢰한 manifest SHA를 필수로 받아 support/tokenizer/model 파일과 연구용 false 승인 상태를 검증한다. 기본 seed42는 TEST 이전 기존 기본값으로 유지하며 다른 seed로 자동 fallback하지 않는다.
- 예외·검증: `require(isinstance(expected_manifest_sha, str) and sha(self.bundle / 'bundle_manifest.json') == expected_manifest_sha, 'Trusted bundle manifest SHA required')`; `require(m['schema'] == 'research-server-bundle/1' and m['deployment_approved'] is False and (m['human_approved'] is False), 'Not a research bundle')`; `require(type(seed) is int and str(seed) in m['models'], 'Unregistered seed')`; `require(m['label_order'] == list(LABELS) and m['thresholds'] == [0.5] * 9, 'Frozen inference contract changed')`.
- 모듈 연결(실제 호출): `Path(bundle).resolve, Path, require, isinstance, sha, read, type, str, list, relative_file, AutoTokenizer.from_pretrained, load_model`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 42. 현재 발화 추론: `ResearchPredictor.predict`

- 소스: [experiments/koelectra_v2/stage5_runtime.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_runtime.py#L134-L136) — **134~136행**.
- 입력: `self, request`.
- 반환: `output_response(raw_logits(self.model, self.tokenizer, [(history, current)])[0], self.thresholds, seed=self.seed, model_sha=self.model_sha)`.
- 처리 및 필요성: 검증된 요청을 동일 문장쌍 토큰화로 CPU 추론하고 logits를 확률·표시 점수·독립 유형 판정으로 변환한다. 현재 발화의 신호이며 누적 통화 위험 확률이 아니다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): `validate_request, output_response, raw_logits`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.

## 43. 정상/실패 응답 구분: `serve_request`

- 소스: [experiments/koelectra_v2/stage5_runtime.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/experiments/koelectra_v2/stage5_runtime.py#L139-L148) — **139~148행**.
- 입력: `predictor, request`.
- 반환: `dict(ok=False, status='error', http_status=status, result=None, error=dict(code=code))`; `failure('NOT_READY', 503)`; `failure('INVALID_REQUEST', 400)`; `predictor.predict(request)`; `failure('INPUT_TOO_LONG', 422)`.
- 처리 및 필요성: 입력400, 길이422, 미준비503, tokenizer/inference500을 ok=false/result=null로 구분한다. 로딩/추론 실패를 정상 상담 판정으로 숨기지 않는다.
- 예외·검증: 하위 호출의 타입·입력·파일·모델 검증 예외를 전파한다..
- 모듈 연결(실제 호출): `dict, failure, validate_request, predictor.predict`.
- 관련 테스트: [tests/test_stage5_handoff.py](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/tests/test_stage5_handoff.py). 내부 데이터 의존 항목은 공개 체크아웃에서 명시적으로 skip하며, 원래 작업 트리 240개 검사에서 별도 실행했다.
