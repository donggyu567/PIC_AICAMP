from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from v3_lite.src.common import BUNDLE,LABELS,PARENT_SHA,RUNS,GateError,bootstrap
from v3_lite.src.checkpoint import load_v3_state,restore_state,save_v3_checkpoint
from v3_lite.src.data import Partition
from v3_lite.src.train import load_config,new_optimizer,train_one_epoch
from v3_lite.tests.fixtures import conversation


def tiny_model():
    bootstrap()
    from transformers import ElectraConfig,ElectraModel
    from risk_speech_ai.model import RiskSpeechClassifier
    config=ElectraConfig(vocab_size=35000,embedding_size=16,hidden_size=16,num_hidden_layers=1,
                         num_attention_heads=2,intermediate_size=32,max_position_embeddings=512,
                         hidden_dropout_prob=0.,attention_probs_dropout_prob=0.)
    return RiskSpeechClassifier(ElectraModel(config))


class WarmStart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bootstrap()
        import torch
        from transformers import AutoTokenizer
        torch.set_num_threads(2)
        cls.tok=AutoTokenizer.from_pretrained(str(BUNDLE/'tokenizer'),local_files_only=True)

    def loader(self):
        from risk_speech_ai.dataset import RiskSpeechDataset,make_training_dataloader
        p=Partition('train',(conversation(),),'fixture','fixture')
        return make_training_dataloader(RiskSpeechDataset(p.samples(),tokenizer=self.tok),tokenizer=self.tok,
                                        batch_size=8,seed=42,shuffle=False)

    def test_restore_all_weights_and_empty_new_optimizer(self):
        import torch
        a=tiny_model(); state={k:v.detach().clone() for k,v in a.state_dict().items()}
        b=tiny_model(); restore_state(b,state)
        self.assertTrue(all(torch.equal(v,b.state_dict()[k]) for k,v in state.items()))
        opt=new_optimizer(b)
        self.assertEqual(len(opt.state),0)
        self.assertEqual(opt.param_groups[0]['lr'],5e-6)
        bad=deepcopy(state); bad.pop('type_classifier.bias')
        with self.assertRaises(RuntimeError): restore_state(b,bad)

    def test_loss_and_one_actual_tiny_optimizer_update(self):
        import torch
        m=tiny_model(); old=m.type_classifier.weight.detach().clone(); opt=new_optimizer(m)
        record=train_one_epoch(m,self.loader(),opt,epoch=1,step_limit=1)
        self.assertEqual(record['samples'],8); self.assertEqual(record['optimizer_steps'],1)
        self.assertFalse(torch.equal(old,m.type_classifier.weight))
        self.assertGreater(len(opt.state),0)
        self.assertAlmostEqual(record['train_loss'],record['risk_loss']+record['type_loss'],places=6)
        self.assertEqual(set(record['per_type_weighted']),set(LABELS))

    def test_budget_and_nonfinite_update_blocked(self):
        import torch
        m=tiny_model(); opt=new_optimizer(m)
        with self.assertRaises(GateError): train_one_epoch(m,self.loader(),opt,epoch=3)
        with self.assertRaises(GateError): train_one_epoch(m,self.loader(),opt,epoch=1,step_offset=212)
        with torch.no_grad(): m.type_classifier.bias.fill_(float('nan'))
        with self.assertRaises(ValueError): train_one_epoch(m,self.loader(),opt,epoch=1)
        self.assertEqual(len(opt.state),0)

    def test_separate_save_cpu_reload_and_never_overwrite(self):
        import torch
        from risk_speech_ai.training import TrainingConfig,_metadata
        m=tiny_model(); opt=new_optimizer(m); batch=next(iter(self.loader()))
        m.eval()
        with torch.inference_mode(): before=m(**{k:batch[k] for k in ('input_ids','attention_mask','token_type_ids')})
        RUNS.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='fixture_',dir=RUNS) as tmp:
            path=Path(tmp)/'unit_fixture.pt'
            lineage=dict(parent_sha256=PARENT_SHA,optimizer_reset=True,artifact_kind='unit_test_fixture')
            metadata=_metadata(m,self.tok,TrainingConfig(data_version='automated-unit-fixture',epochs=1),torch.device('cpu'))
            kwargs=dict(metadata=metadata,lineage=lineage,
                        epoch=1,history=[],artifact_kind='unit_test_fixture')
            ref=save_v3_checkpoint(path,m,opt,**kwargs)
            restored=tiny_model(); payload=load_v3_state(path,restored,ref['sha256'],tokenizer=self.tok)
            self.assertTrue(payload['v3_lite_metadata']['inherited_unreviewed_synthetic_v2'])
            self.assertFalse(payload['v3_lite_metadata']['human_approved'])
            with torch.inference_mode(): after=restored(**{k:batch[k] for k in ('input_ids','attention_mask','token_type_ids')})
            self.assertTrue(torch.equal(before.risk_logits,after.risk_logits))
            self.assertTrue(torch.equal(before.type_logits,after.type_logits))
            with self.assertRaises(FileExistsError): save_v3_checkpoint(path,m,opt,**kwargs)
            with self.assertRaises(GateError): load_v3_state(path,restored,'0'*64,tokenizer=self.tok)

    def test_v2_path_and_unapproved_checkpoint_save_rejected(self):
        m=tiny_model(); opt=new_optimizer(m)
        kwargs=dict(metadata={'label_order':list(LABELS)},lineage=dict(parent_sha256=PARENT_SHA,optimizer_reset=True,artifact_kind='research_model'),epoch=1,history=[])
        with self.assertRaises(GateError): save_v3_checkpoint(BUNDLE/'models/B_ratio/seed_42.pt',m,opt,**kwargs)
        with self.assertRaises(GateError): save_v3_checkpoint(RUNS/'invalid.pt',m,opt,**kwargs)
        kwargs['metadata']['label_order']=list(reversed(LABELS))
        with self.assertRaises(GateError): save_v3_checkpoint(RUNS/'invalid.pt',m,opt,**kwargs)

    def test_actual_tokenizer_input_contract(self):
        from risk_speech_ai.tokenization import InputTooLongError,build_model_input
        p=build_model_input(['이전 안내입니다.'],'현재 확인을 요청합니다.',tokenizer=self.tok)
        self.assertEqual(p.input_ids[0],self.tok.cls_token_id)
        self.assertEqual(p.input_ids[-1],self.tok.sep_token_id)
        self.assertIn(0,p.token_type_ids); self.assertIn(1,p.token_type_ids)
        self.assertEqual(self.tok.padding_side,'right')
        with self.assertRaises(InputTooLongError): build_model_input([],'확인 '*800,tokenizer=self.tok)
        p=build_model_input(['이전 안내 '*200]*5,'현재 문장',tokenizer=self.tok)
        self.assertLessEqual(len(p.input_ids),512)

    def test_fixed_config_has_no_search(self):
        c=load_config()
        self.assertEqual(c['epochs_max'],2); self.assertEqual(c['max_optimizer_steps'],212)
        self.assertEqual(c['thresholds'],[.5]*9); self.assertEqual(c['type_pos_weight'],[10]*8)
