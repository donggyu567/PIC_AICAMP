from copy import deepcopy
import math
import unittest

from v3_lite.src.common import FOCUS,LABELS,GateError,bootstrap
from v3_lite.src.data import Partition
from v3_lite.src.diagnostics import apply_gates,family_paired_uncertainty,score_logits,type_losses
from v3_lite.tests.fixtures import conversation,metrics


class Diagnostics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bootstrap()

    def test_weighted_loss_has_expected_hand_calculated_value(self):
        import torch
        from risk_speech_ai.model import ModelOutput
        from expanded_training import losses
        o=ModelOutput(torch.zeros(2,1,requires_grad=True),torch.zeros(2,8,requires_grad=True))
        y=torch.zeros(2,1); t=torch.zeros(2,8); t[0,2]=1
        total,risk,types=losses(o,y,t,[10.]*8)
        self.assertAlmostEqual(float(risk.detach()),math.log(2),places=6)
        self.assertAlmostEqual(float(types.detach()),25/16*math.log(2),places=6)
        d=type_losses(o,y,t)
        self.assertAlmostEqual(d['types_weighted'][2],5.5*math.log(2),places=6)
        total.backward(); self.assertTrue(torch.isfinite(o.type_logits.grad).all())

    def test_known_logits_metrics_and_type_false_alerts(self):
        c=conversation(role='validation'); p=Partition('validation',(c,),'fixture','fixture')
        zs=[[4 if u['is_phishing'] else -4]+[4 if l in u['labels'] else -4 for l in LABELS] for u in c['utterances']]
        m=score_logits(p,zs)
        import json
        json.dumps(m,allow_nan=False)
        self.assertEqual(m['binary']['f1'],1); self.assertEqual(m['binary']['roc_auc'],1)
        self.assertEqual(m['binary']['average_precision'],1)
        for l in FOCUS: self.assertEqual(m['per_type'][l]['tp'],1)
        with self.assertRaises(ValueError): score_logits(p,[[float('nan')]*9]*8)
        with self.assertRaises(ValueError): score_logits(p,[[0]*8]*8)
        denied=Partition('test',(c,),'fixture','fixture')
        with self.assertRaises(GateError): score_logits(denied,zs)

    def test_normal_binary_and_type_fp_are_distinct(self):
        c=conversation(role='validation')
        for u in c['utterances']: u.update(is_phishing=False,labels=[])
        p=Partition('validation',(c,),'fixture','fixture')
        zs=[[-4]*9 for _ in range(8)]; zs[0][3]=4
        m=score_logits(p,zs)
        self.assertEqual(m['conversations']['normal_false_alerts'],0)
        self.assertEqual(m['normal_categories']['identity']['type_fp']['personal_information'],1)

    def test_adopt_when_both_targets_and_normal_fp_improve(self):
        b=metrics(); c=metrics(f1=.56,ap=.5,normal_fp=0)
        g=apply_gates(b,c,b,b,epoch=1)
        self.assertTrue(g['safe']); self.assertTrue(g['adopt']); self.assertFalse(g['allow_epoch2'])

    def test_epoch2_requires_ap_progress_and_safety(self):
        b=metrics(); c=metrics(normal_fp=1)
        c['per_type'][FOCUS[0]]['f1']=.52
        self.assertTrue(apply_gates(b,c,b,b,epoch=1)['allow_epoch2'])
        self.assertFalse(apply_gates(b,c,b,b,epoch=2)['allow_epoch2'])
        c['per_type'][FOCUS[1]]['average_precision']=.49
        self.assertFalse(apply_gates(b,c,b,b,epoch=1)['allow_epoch2'])

    def test_binary_or_old_validation_regression_stops(self):
        b=metrics(); c=metrics(f1=.7,normal_fp=0); c['binary']['recall']=.879
        self.assertFalse(apply_gates(b,c,b,b,epoch=1)['safe'])
        old=deepcopy(b); old['binary']['f1']=.88
        self.assertFalse(apply_gates(b,metrics(f1=.7,normal_fp=0),b,old,epoch=1)['adopt'])

    def test_normal_increase_or_other_type_recall_stops(self):
        b=metrics(); c=metrics(f1=.7,normal_fp=2)
        self.assertFalse(apply_gates(b,c,b,b,epoch=1)['safe'])
        c=metrics(f1=.7,normal_fp=0); c['per_type'][LABELS[0]]['recall']=.69
        self.assertFalse(apply_gates(b,c,b,b,epoch=1)['safe'])

    def test_undefined_support_never_passes_and_zero_fp_is_not_improvement(self):
        b=metrics(normal_fp=0); c=metrics(f1=.6,normal_fp=0)
        g=apply_gates(b,c,b,b,epoch=1)
        self.assertTrue(g['adopt']); self.assertEqual(g['normal_fp_outcome'],'zero_maintained_not_improved')
        c['per_type'][FOCUS[0]]['average_precision']=None
        g=apply_gates(b,c,b,b,epoch=1)
        self.assertFalse(g['adopt']); self.assertFalse(g['allow_epoch2'])

    def test_paired_family_interval_and_alignment(self):
        a=conversation(role='validation'); b=conversation('V3-FIXTURE-VAL-002','fixture-other','validation')
        for u in b['utterances']: u.update(is_phishing=False,labels=[])
        p=Partition('validation',(a,b),'fixture','fixture')
        zs=[[1 if u['is_phishing'] else -1]+[1 if l in u['labels'] else -1 for l in LABELS] for c in [a,b] for u in c['utterances']]
        prediction=dict(data_sha256='fixture',row_keys=[f"{c['conversation_id']}:{u['utterance_id']}" for c in [a,b] for u in c['utterances']],logits=zs)
        r=family_paired_uncertainty(p,prediction,prediction,repetitions=30)
        self.assertEqual(r['unit'],'scenario_family_id'); self.assertEqual(r['delta_f1']['risk']['ci95'],[0.,0.])
        bad=deepcopy(prediction); bad['row_keys'].reverse()
        with self.assertRaises(GateError): family_paired_uncertainty(p,prediction,bad,repetitions=10)
