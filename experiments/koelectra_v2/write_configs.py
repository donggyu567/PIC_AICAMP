"""Create explicit A/B/C experiment plans, never train or approve data."""
import copy
import hashlib
import json
from pathlib import Path
from plan_splits import ROOT,OUTPUT,INPUT,LABELS,sha,load,write


def main():
    plan_path=OUTPUT/'split_review_candidate.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    labels=load(INPUT/'labels.jsonl')
    train=[r for r in labels if plan['conversation_to_split'][r['conversation_id']]=='train']
    positives=[sum(l in r['labels'] for r in train) for l in LABELS]
    weights=[min(5.0,((len(train)-n)/n)**.5) if n else 1.0 for n in positives]
    weight_plan=dict(policy='sqrt_negative_positive_capped_5_training_only',label_order=list(LABELS),
        values=weights,positives=positives,train_utterances=len(train),source_sha256=sha(INPUT/'labels.jsonl'),
        split_candidate_sha256=sha(plan_path),computed_from='original v1 TRAIN partition only; C reuses B values without recomputation',
        zero_positive_policy='weight=1; mark label unlearnable/unreliable; never infer from validation/test',
        status='PROVISIONAL_UNTIL_SPLIT_AND_LABEL_REVIEW_FREEZE')
    write(OUTPUT/'type_loss_weight_plan.json',weight_plan)
    common=dict(config_schema_version=1,status='DESIGN_ONLY_TRAINING_NOT_AUTHORIZED',
        execution=dict(allowed_mode='preflight',training_enabled=False,test_prediction_enabled=False),
        model=dict(name='monologg/koelectra-base-v3-discriminator',revision='68b30cd259f34a4b5aa8786392612ba2a2617fcc',
            tokenizer_revision='68b30cd259f34a4b5aa8786392612ba2a2617fcc',init='pinned_public_pretrained_encoder_fresh_seeded_heads',
            original_v1_checkpoint_required=False,original_v1_checkpoint_restored=False,
            risk_head=1,type_head=8,activation='raw logits; sigmoid once at inference'),
        data=dict(labels_path='artifacts/v1_recovered_8faa6a7eebfe/prepared/labels.jsonl',labels_sha256=sha(INPUT/'labels.jsonl'),
            text_path='artifacts/v1_recovered_8faa6a7eebfe/prepared/tuned.jsonl',text_sha256=sha(INPUT/'tuned.jsonl'),
            split_manifest='experiments/koelectra_v2/split_review_candidate.json',split_sha256=sha(plan_path),
            synthetic_train=None,synthetic_validation_role='supplementary_diagnostic_only_after_human_review_never_TEST'),
        input=dict(preprocessing='masked_source_text_no_llm_correction_identity',max_history_utterances=5,max_sequence_length=512,
            sequence_format='[CLS] history [SEP] current [SEP]',history_separator='\n',padding_side='right',
            overflow='drop_oldest_whole_history_then_fail_current_only',label_order=list(LABELS)),
        training=dict(epochs=1,batch_size=8,learning_rate=2e-5,weight_decay=.01,optimizer='AdamW',
            seeds=[42,43,44],device='cpu',torch_threads=2,num_workers=0,shuffle=True,
            checkpoint_rule='last_epoch',early_stopping=False,trainable='encoder_and_both_heads',
            deterministic_algorithms_planned=True,precision='float32',scheduler=None,
            historical_optimizer_betas_eps='NOT_RECORDED; current pinned AdamW defaults are a future explicit choice'),
        loss=dict(binary='BCEWithLogitsLoss_mean',types='BCEWithLogitsLoss_mean',lambda_risk=1.0,lambda_type=1.0,type_pos_weight=None),
        evaluation=dict(common_roles=['validation','test'],gold_labels_verified=False,split_frozen=False,
            risk_threshold=.5,type_thresholds=[.5]*8,threshold_policy='fixed_primary_no_tuning',
            type_decision='independent_thresholds_not_gated_by_binary_prediction',
            metrics=['binary_precision','binary_recall','binary_f1','binary_roc_auc','confusion_matrix',
                     'per_type_precision_recall_f1','micro_f1','macro_defined_labels_f1','defined_label_count'],
            undefined='null_with_reason; no-positive recall/F1/AUC undefined; full8_macro_not_estimable_if_any_undefined',
            test_policy='seal after human split/QA review; no model/threshold selection; one final registered evaluation batch for all arms/seeds',
            bootstrap=dict(unit='independent_component',paired=True,repetitions=2000,seed=20261107,confidence=.95),
            model_selection='single preregistered recipe, last epoch; no selection on TEST',
            error_analysis='FP/FN by conversation/source/type after final test, no same-test retuning'),
        output=dict(root='artifacts/v2_comparison_runs',checkpoint_name='model.pt',overwrite=False,
            run_directory_rule='{experiment_id}/seed_{seed}/{run_id}',run_id_required=True),
        budget=dict(primary='epoch_matched; report samples/steps/time per arm',base_train_samples=len(train),
            base_steps_per_epoch=(len(train)+7)//8,confound='C adds optimizer updates at equal epochs; not isolated data-quality causation',
            control='After approved C size known, additional B_step_matched cycles original TRAIN for exactly C steps; same LR/loss/seed; never choose budget from TEST'))
    for letter,name,weighted in [('A','A_v1_retrained_baseline',False),('B','B_v2_loss_balanced',True),('C','C_v2_approved_synthetic',True)]:
        cfg=copy.deepcopy(common);cfg.update(experiment_id=name,arm=letter)
        cfg['output']['experiment_id']=name
        if weighted:
            cfg['loss']['type_pos_weight']=dict(manifest='experiments/koelectra_v2/type_loss_weight_plan.json',
                sha256=sha(OUTPUT/'type_loss_weight_plan.json'),reuse_for_C_without_recompute=True)
        if letter=='C':
            src=ROOT/'dataset/04. processed/v2_train_expansion/train_24_mixed_review_candidate.jsonl'
            cfg['data']['synthetic_train']=dict(path=str(src.relative_to(ROOT)).replace('\\','/'),sha256=sha(src),
                available_candidate_utterances=208,currently_final_approved=0,include_unapproved=False,
                required_gate='dataset/scripts/v2_pipeline_gate.py: two-person final review + explicit training-use decision + no overlap with common holdouts',
                cross_holdout_semantic_review_required=True)
            cfg['budget']['planned_only_if_all208_approved']=dict(total_train_samples=len(train)+208,steps_per_epoch=(len(train)+208+7)//8)
        write(OUTPUT/'configs'/f'{letter}.json',cfg)
    historical=dict(verified_from_PR35=dict(model=common['model']['name'],revision=common['model']['revision'],
        epochs=1,batch_size=8,learning_rate=2e-5,weight_decay=.01,seed=42,optimizer='AdamW',
        lambda_risk=1.,lambda_type=1.,loss='unweighted mean BCE for each head, summed',
        history=5,max_tokens=512,thresholds=.5,checkpoint='last_epoch',historical_steps=183,historical_samples=1460,
        evaluation='TRAIN IN-SAMPLE only; sample_count/data_version bound by old evaluate_cli'),
        not_verified_or_not_recorded=['actual v1 checkpoint metadata/weights','exact uncommitted training code snapshot',
            'historical optimizer betas/eps explicit values','exact device/thread settings beyond recorded CPU','per-batch loss and total duration',
            'resolved tokenizer revision; vocabulary fingerprint is recorded'],
        planned_differences=['new A identity v1_retrained_baseline; never recovered original weights',
            'fair comparison A/B train only common proposed TRAIN subset, not all1460',
            'optional full1460 recipe replay is separate in-sample-only exercise and cannot be scored on internal holdouts',
            'current Python3.12.14 differs from historical3.11.16; exact bitwise replication not promised'],
        original_input_quality='Historical team training-use permission is not independent utterance-level gold review')
    write(ROOT/'reports/v2_experiment_design/historical_recipe.json',historical)
    print(json.dumps(dict(configs=['A.json','B.json','C.json'],base_train_samples=len(train),type_pos_weight=weights),indent=2))


if __name__=='__main__':main()
