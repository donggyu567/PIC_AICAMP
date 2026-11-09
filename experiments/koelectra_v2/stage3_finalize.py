"""Publish metadata and research-path specification without opening sealed TEST content."""
from collections import Counter
import json
from pathlib import Path
import subprocess

from expanded_common import ROOT, LABELS, read, sha, require, write_json, publish
from stage3_data import BASE, REPORT, AUTHORED, V1_LABELS, V1_TEXT, AUX, MODEL, jsonl
from stage3_research import load_research


def main():
    receipt = read(BASE/'test_seal_receipt.json')
    require(receipt['sealed'] and receipt['plaintext_authoring_removed'], 'Unsealed TEST')
    require(not list(AUTHORED.glob('test_*.txt')), 'Plaintext TEST authoring remains')
    identity = subprocess.check_output(['whoami'], text=True, errors='replace').strip()
    require('codexsandbox' in identity.lower(), 'Development access probe must use sandbox identity')
    try:
        # Open only; never read the encrypted bytes, let alone TEST body or labels.
        with Path(receipt['vault_path']).open('rb'):
            denied = False
    except PermissionError:
        denied = True
    require(denied, 'Development identity can open TEST vault; sealing is incomplete')
    write_json(REPORT/'vault_access_probe.json', dict(status='PASS_DENIED', identity=identity,
        attempted_operation='open ciphertext, no read', permission_error=True, test_body_read=False,
        plaintext_authoring_files_remaining=0, custody_identity=receipt['custodian_windows_identity']))

    train, val = jsonl(BASE/'train_80_candidate.jsonl'), jsonl(BASE/'validation_32_synthetic.jsonl')
    members = [dict(conversation_id=c['conversation_id'], scenario_family_id=c['scenario_family_id'], role=c['split'])
               for c in train+val] + receipt['split_membership']
    for key in ['conversation_id', 'scenario_family_id']:
        require(len({m[key] for m in members}) == 152, 'Cross-role identifier overlap')
    write_json(BASE/'split_manifest.json', dict(schema='internal-research-split/1', purpose='internal_experiment',
        members=members, unique_conversations=152, unique_family_ids=152,
        train_sha256=sha(BASE/'train_80_candidate.jsonl'), validation_sha256=sha(BASE/'validation_32_synthetic.jsonl'),
        test_receipt_sha256=sha(BASE/'test_seal_receipt.json'),
        automated_checks='ID/family-key separation and lexical screening only',
        semantic_independence='NOT_HUMAN_VERIFIED', common_ai_author=True, production_approved=False))
    histories = [dict(batch=p.stem, authoring_path=p.relative_to(ROOT).as_posix(), source_sha256=sha(p),
        output_sha256=sha(BASE/'batches'/f'{p.stem}.jsonl'), **MODEL)
        for p in sorted(AUTHORED.glob('*.txt'))]
    histories += [dict(batch=x['name'], source_sha256=x['sha256'], source_storage='encrypted TEST payload only', **MODEL)
                  for x in receipt['source_batches']]
    write_json(BASE/'generation_history.json', dict(schema='synthetic-generation-ledger/1', batches=histories,
        new_conversations=128, legacy_train_conversations=24, legacy_metadata='Per-record legacy_provenance; source approval histories preserved',
        actual_human_review_events_created=0, label_status='provisional', purpose='internal_experiment',
        timestamp_note='Per-record authored_event_at is the batch serialization event, not a provider API timestamp',
        backend_identity_limit=MODEL['identity_limit']))

    # Verify the explicit research adapter using the real CPU tokenizer/DataLoader.
    from expanded_assets import load_tokenizer
    from risk_speech_ai.dataset import RiskSpeechDataset, make_training_dataloader
    import torch
    tok = load_tokenizer(); runs = {}
    for role in ['train', 'validation']:
        part = load_research(role, mode='internal_experiment')
        loader = make_training_dataloader(RiskSpeechDataset(part.samples, tokenizer=tok), tokenizer=tok, batch_size=8, shuffle=False)
        count = batches = width_max = 0
        for b in loader:
            n, width = b['input_ids'].shape
            require(all(t.device.type == 'cpu' for t in b.values()) and width <= 512, 'Research CPU contract')
            require(all(b[k].shape == (n,width) and b[k].dtype == torch.int64 for k in ['input_ids','attention_mask','token_type_ids']), 'Research input shape/dtype')
            require(b['risk_target'].shape == (n,1) and b['type_targets'].shape == (n,8), 'Research output shape')
            require(b['type_targets'].dtype == b['risk_target'].dtype == torch.float32, 'Research target dtype')
            require(torch.equal(b['type_targets'], torch.tensor([s.type_targets for s in part.samples[count:count+n]], dtype=torch.float32)), 'Research target alignment')
            count += n; batches += 1; width_max = max(width_max,width)
        require(count == len(part.samples), 'Incomplete research loader')
        runs[role] = dict(samples=count, batches=batches, maximum_sequence_length=width_max,
            maximum_history=max(len(s.history_texts) for s in part.samples), data_sha256=part.data_sha256)
    write_json(REPORT/'research_preflight.json', dict(status='PASS', roles=runs, model_forward=False,
        optimizer_updates=0, test_access=False, human_approved=False, deployment_approved=False))

    v1 = jsonl(V1_LABELS)
    old_counts = Counter(label for row in v1 for label in row['labels'])
    quality = read(REPORT/'quality.json')
    oldtrain = [c for c in train if 'legacy_provenance' in c]
    newtrain = [c for c in train if 'legacy_provenance' not in c]
    additions = Counter(label for c in newtrain for u in c['utterances'] for label in u['labels'])
    comparison = {label: dict(v1_positive_utterances=old_counts[label], new_train_positive_utterances=additions[label],
        combined_train_positive_utterances=quality['train']['positive_labels'][label],
        registered_train_families=quality['train']['positive_families'][label],
        new_train_families=5, validation_families=3, test_families=receipt['stats']['positive_families'][label]) for label in LABELS}
    normal = {role: [dict(conversation_id=c['conversation_id'], family=c['scenario_family_id'], summary=c.get('scenario_summary'),
        utterances=len(c['utterances'])) for c in records if not any(u['is_phishing'] for u in c['utterances'])]
        for role, records in [('train',train), ('validation',val)]}
    write_json(REPORT/'coverage_and_limits.json', dict(v1_conversations=len({r['conversation_id'] for r in v1}),
        v1_utterances=len(v1), v1_included=False, by_type=comparison, normal_conversations=normal,
        test_normal_conversations=receipt['stats']['entirely_normal_conversations'],
        hard_negative_definition='Entirely normal dialogues selected for app/finance/identity/privacy resemblance; normal turns inside risky dialogues counted separately',
        validation_threshold_eligibility={label: dict(positives=9, required_minimum=10, eligible=False, fallback_threshold=0.5) for label in LABELS},
        semantic_label_accuracy='UNVERIFIED', limitations=[
            'Family IDs are registered separately; semantic separation is not independently certified.',
            'All new records share one AI session author; they are not independent human annotations.',
            'Controlled dialogues, fake institution cues and single-label-heavy scripts can introduce style bias.',
            'Lexical screening is not an embedding or semantic audit; short generic responses may be similar.',
            'Some normal topics resemble old auxiliary validation; auxiliary data is not a new independent benchmark.',
            'Existing TRAIN duplicate and v1-like short response retained to preserve the original 24 dialogues.',
            'Use rights of historical v1 sources remain unverified; v1 is excluded from this research configuration.']))
    paths = dict(schema='phase4-internal-research-inputs/1', purpose='internal_experiment',
        research_mode='internal_experiment', adapter='experiments/koelectra_v2/stage3_research.py:load_research',
        manifest=dict(path=(BASE/'data_use_manifest.json').relative_to(ROOT).as_posix(), sha256=sha(BASE/'data_use_manifest.json')),
        split=dict(path=(BASE/'split_manifest.json').relative_to(ROOT).as_posix(), sha256=sha(BASE/'split_manifest.json')),
        train=dict(path=(BASE/'train_80_candidate.jsonl').relative_to(ROOT).as_posix(), sha256=sha(BASE/'train_80_candidate.jsonl'), conversations=80, utterances=656),
        validation=dict(path=(BASE/'validation_32_synthetic.jsonl').relative_to(ROOT).as_posix(), sha256=sha(BASE/'validation_32_synthetic.jsonl'), conversations=32, utterances=256),
        test=dict(receipt=(BASE/'test_seal_receipt.json').relative_to(ROOT).as_posix(), accessible_to_development=False, role='phase5_only'),
        auxiliary_validation=dict(path=AUX.relative_to(ROOT).as_posix(), role='auxiliary_only_do_not_tune'),
        historical_v1=dict(text_path=V1_TEXT.relative_to(ROOT).as_posix(), labels_path=V1_LABELS.relative_to(ROOT).as_posix(), included=False),
        approval_state=dict(human_review_complete=False, deployment_approved=False, production_gate_unchanged=True),
        phase4_conditions=['Explicit research-only trainer entry point consuming ResearchInput; never spoof production Partition approvals',
            'Bind run/checkpoint metadata to these hashes and record llm_synthetic/provisional/internal_experiment',
            'Optimizer updates use TRAIN only; selection uses new VALIDATION only; no TEST access',
            'Keep per-type thresholds at 0.5 when the existing minimum-positive rule is not met',
            'No v1 source automatically enters a run until source use rights are separately verified'],
        research_training_executed=False)
    write_json(BASE/'phase4_data_paths.json', paths)
    print('METADATA AND RESEARCH PREFLIGHT PASS', flush=True)


if __name__ == '__main__': main()
