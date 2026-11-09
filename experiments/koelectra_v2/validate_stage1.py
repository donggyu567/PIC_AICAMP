"""Validate a design contract; never dispatch to the legacy preflight or trainer."""
from __future__ import annotations

import json
from pathlib import Path
from audit_stage1 import LABELS, ROOT, sha

CONFIG = ROOT / 'experiments/koelectra_v2/protocol_20261109_v1.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_path(path):
    require(isinstance(path, str) and '\\' not in path and ':' not in path, 'relative portable path required')
    result = (ROOT / path).resolve()
    require(result.is_relative_to(ROOT.resolve()), 'path escapes repository')
    return result


def validate(cfg):
    require(cfg['schema'] == 'koelectra-expansion-design/1', 'unknown schema')
    require(cfg['execution'] == dict(training_enabled=False, test_prediction_enabled=False, approval_write_enabled=False), 'design cannot authorize execution')
    require(cfg['input'] == dict(max_history_utterances=5, max_sequence_length=512, label_target='current_utterance', label_order=LABELS), 'input contract changed')
    model = cfg['model']
    require(model['name'] == 'monologg/koelectra-base-v3-discriminator' and model['revision'] == '68b30cd259f34a4b5aa8786392612ba2a2617fcc', 'base model changed')
    require(model['shared_encoder'] is True and model['risk_outputs'] == 1 and model['type_outputs'] == 8 and model['original_v1_checkpoint_restored'] is False, 'model contract changed')
    for spec in cfg['existing_inputs'].values():
        path = local_path(spec['path'])
        require(path.is_file() and sha(path) == spec['sha256'], 'input missing or hash mismatch')
    for path in cfg['legacy_configs']:
        require(local_path(path).is_file(), 'legacy reference missing')
    data = cfg['data']
    require(data['synthetic_train_target_conversations'] == 80 and data['additional_train_conversations'] == 56 and data['existing_train_candidate_conversations'] == 24, 'TRAIN targets changed')
    require(data['independent_validation_target_conversations'] == 32 and data['sealed_test_target_conversations'] == 40, 'holdout targets changed')
    require(data['strategy'] == 'eligible_existing_v1_train_plus_new_independent_holdouts', 'strategy changed')
    require(data['legacy_48_10_10_use'] == 'archived_diagnostic_only_never_merge_with_new_holdouts', 'legacy holdouts must stay separate')
    require(data['aux_llm_validation_conversations'] == 24 and data['final_approved_synthetic_train_conversations'] == 0, 'unapproved data promoted')
    require(data['test_content_access_from_development'] is False and data['require_disjoint_conversation_source_family_author_groups'] is True and data['require_rights_and_two_person_final_review'] is True, 'data protections changed')
    require([item['role'] for item in data['future_required']] == ['train', 'synthetic_train', 'validation', 'test_metadata_only'], 'future role registry invalid')
    blocked = []
    for item in data['future_required']:
        path = local_path(item['path'])
        require(item['available'] is False and not path.exists(), 'new artifacts require a new reviewed protocol version')
        blocked.append(dict(role=item['role'], path=item['path'], reason='NOT_YET_SUPPLIED_NOT_APPROVED'))
    training = cfg['training_plan']
    require(training['epoch_candidates'] == [1, 2, 3], 'epoch registration changed')
    require(training['weight_policy']['primary'] == 'min(10,max(1,N_negative/N_positive))' and training['weight_policy']['source'] == 'eligible_original_TRAIN_only' and training['weight_policy']['freeze_B_weights_for_C'] is True, 'TRAIN-only weight contract changed')
    selection = cfg['selection']
    require(selection['source'] == 'independent_validation_only' and selection['test_selection_allowed'] is False, 'TEST selection forbidden')
    require(selection['threshold_grid'] == [round(.1 + .05 * i, 2) for i in range(17)], 'threshold grid changed')
    require(selection['minimum_positive_and_negative_each'] == 10 and selection['minimum_positive_conversations'] == 3 and selection['unsupported_threshold'] == .5, 'rare-label safeguards changed')
    require(selection['freeze_same_thresholds_across_seeds_and_B_C'] is True, 'comparison threshold policy changed')
    output = cfg['output_plan']
    require(local_path(output['root']) == ROOT / 'artifacts/v2_comparison_runs' and output['namespace'] == 'expansion_20261109_v1' and output['overwrite'] is False, 'unsafe output')
    return dict(status='PASS_DESIGN_VALIDATION_EXECUTION_BLOCKED', missing_inputs=blocked,
                training_authorized=False, test_evaluated=False, config_sha256=sha(CONFIG))


if __name__ == '__main__':
    result = validate(json.loads(CONFIG.read_text(encoding='utf-8')))
    target = ROOT / 'reports/v2_stage1_20261109/protocol_validation.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(result['status'])
