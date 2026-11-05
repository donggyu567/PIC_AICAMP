#!/usr/bin/env python3
"""Serialize newly authored TRAIN dialogues and a mixed-review candidate.

Does not read VALIDATION dialogue text. Only the reserved scenario registry is
consulted for exclusion. Existing artifacts are never overwritten on mismatch.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import prepare_pilot_review as review
from restore_pilot import LABELS

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "dataset/04. processed/v2_train_expansion"
REPORTS = ROOT / "reports/v2_train_expansion"
CSV = ROOT / "dataset/review/v2_train_expansion/human_review_new8.csv"
PILOT = ROOT / "dataset/04. processed/v2_pilot/pilot_canonical.jsonl"
PREVIOUS = PILOT.parent / "training_candidate/pilot_single_review_train_candidate.jsonl"
RESERVED = ROOT / "dataset/04. processed/v2_validation/scenario_registry.json"
NEW = OUT / "train_0017_0024_generated.jsonl"
MERGED = OUT / "train_24_mixed_review_candidate.jsonl"
MODEL = "GPT-6 (Codex)"
CODES = dict(zip(("I", "M", "P", "A", "S", "T", "L", "F"), LABELS))
CONVERSATIONS, DESIGNS = [], []


def add(slug, primary, summary, mechanism, distinction, focus, dialogue):
    number = 17 + len(CONVERSATIONS)
    cid = f"SYN2-TRAIN-{number:04}"
    utterances = []
    for position, line in enumerate(dialogue.strip().splitlines(), 1):
        speaker, codes, text, rationale = line.strip().split("|", 3)
        risks = [CODES[k] for k in codes if k != "-"]
        utterances.append(dict(utterance_id=position, speaker=f"speaker_{speaker}", text=text,
                               is_phishing=bool(risks), labels=[label for label in LABELS if label in risks],
                               label_rationale=rationale))
    CONVERSATIONS.append(dict(
        synthetic_id=cid, is_synthetic=True, source_kind="llm_simulation", actual_call=False,
        split="train", split_version="v2-train-expansion-1", scenario_family_id=f"FAM2-TRAIN-{number:04}",
        scenario_id=f"SCN2-TRAIN-EXPANSION-{slug.upper()}-001", variant_id="original", primary_type=primary,
        scenario_summary=summary, generation_model=MODEL, prompt_version="v2-train-expansion-1",
        review_status="generated", review_flags=["김해린·임정윤 독립 검수 및 최종 합의 필요", focus,
            "VALIDATION 본문은 생성 후 독립성 검사에만 사용", "실제 v1 학습 입력과의 중복 미검증"],
        revision_history=[dict(revision_id="train-expansion-initial-generation-1", revision_model=MODEL,
            changed_utterance_ids=list(range(1, len(utterances)+1)),
            reason="기존 TRAIN의 상대적 부족 유형과 정상 문맥을 보완한 신규 작성", human_approved=False)],
        utterances=utterances))
    DESIGNS.append(dict(synthetic_id=cid, scenario_family_id=f"FAM2-TRAIN-{number:04}",
        scenario_id=CONVERSATIONS[-1]["scenario_id"], primary_type=primary, entirely_normal=primary is None,
        situation=summary, mechanism=mechanism, distinction_from_existing_train=distinction,
        human_review_focus=focus, split="train", human_review_complete=False))


add("supplier-bank-switch", "money_transfer",
    "가게의 자재 대금 결제 직전 가짜 납품업체 회계 담당자가 수취 계좌 변경을 주장하고 기존 영업 담당자 확인을 막는다.",
    "거래처 청구서의 수취 계좌 바꿔치기 및 지급 담당자 계좌정보 수집",
    "기존 TRAIN의 요금 미납·대환 보증금과 달리 이미 승인된 사업상 청구서의 지급 상대만 바꾸려 한다.",
    "거래처 사칭·명의 떠보기·정확한 계좌정보·송금과 은폐의 동시 요구를 분리 검토",
    """
B|-|자재 납품서의 금액은 맞춰 놨는데, 오늘 결제할 거래처에서 오신 연락인가요?|지급 예정 거래의 연락 출처를 묻는 정상 반응이다.
A|I|가상 업체 들찬자재의 회계 담당입니다. 이번 납품 대금 수취 변경을 맡았습니다.|거래 상대 업체의 회계 직원 신분을 사칭한다.
A|F|평소 대금은 사장님 개인 통장에서 보내시나요, 가게 명의 통장에서 보내시나요?|계좌의 정확한 값 대신 지급 계좌의 명의 유형을 떠본다.
B|-|사업용으로 처리하고 있어요. 납품서에 변경 안내가 없던데요.|기존 문서와 다른 점을 지적하며 정확한 계좌정보를 제공하지 않는다.
A|M|기존 청구서의 계좌로 보내지 말고 이번 잔금 8만 원은 제가 지정하는 개인 수금 계좌로 입금하세요.|기존 지급 대상을 사기범의 별도 계좌로 바꾸어 송금하도록 요구한다.
B|-|늘 거래하던 영업 담당자에게 수취인이 바뀐 게 맞는지 물어보겠습니다.|기존 거래 상대에게 독립 확인을 시도한다.
A|MS|잔금은 제 수금 계좌로 이체하고, 기존 영업 담당자에게는 계좌 변경 이야기를 하지 마세요.|현재 발화에서 금전 이전과 제3자에게 사실을 숨기라는 요구가 동시에 나타난다.
B|-|납품업체 안에서도 숨겨야 하는 변경이면 지급 승인부터 멈추겠습니다.|은폐 조건에 반대하며 지급을 보류한다.
A|P|그러면 지급인 등록을 고치도록 돈을 보낼 계좌번호 전체와 예금주 성함을 알려 주세요.|정확한 계좌 식별정보와 성명을 직접 수집하려 한다.
B|-|계좌정보도 드리지 않겠습니다. 원래 담당자가 변경한 적이 없다고 답했어요.|정보 제공을 거절하고 기존 담당자의 확인 결과를 알린다.
""")

add("sleep-study-screening", "information_probing",
    "수면 연구 참여 의향을 남긴 이용자가 가짜 연구 담당자에게 보험 가입 형태와 과거 신분증 제출 이력을 질문받고 연구와 무관한 식별정보 요구를 받는다.",
    "연구 지원자 선별을 가장한 보험·신분증 제출 이력 탐색 후 정확한 개인식별정보 수집",
    "기존 TRAIN의 보험 청구 서류 보완과 달리 보험 계약자가 아닌 연구 지원자의 이력부터 탐색하며 보험 청구·환급 절차가 없다.",
    "보험 형태·신분증 제출 이력의 떠보기와 생년월일·주민번호 수집의 경계 확인",
    """
B|-|수면 습관 연구에 관심 있다고 남겼는데 참여 안내를 보내 주시는 건가요?|이용자가 자신이 남긴 의향과 연락의 관계를 질문한다.
A|I|가상 기관 누운별행동연구소의 지원자 등록 담당입니다. 참여 자격을 확인하겠습니다.|연구 기관의 지원자 등록 직원을 사칭한다.
A|F|실손보험은 본인 이름으로 가입한 게 있으시죠, 아니면 가족 계약에 묶여 있으신가요?|특정 보험 명의 형태를 먼저 제시하여 반응으로 가입 상태를 떠본다.
B|-|수면 일지를 쓰는 연구라던데 보험 가입이 왜 필요한지 모르겠어요.|연구 목적과 무관한 질문에 의문을 제기한다.
A|F|전에 다른 연구에 신분증 사진을 제출한 적도 있으신가요?|과거 신분증 제출 이력을 질문으로 탐색하며 정확한 번호를 직접 요구하지 않는다.
B|-|그 이력은 답하지 않겠습니다. 연구 설명서를 먼저 보고 싶습니다.|정보 탐색에 응하지 않고 서면 설명을 요청한다.
A|P|설명서를 발송할 명단에 성함과 생년월일을 넣어야 하니 두 항목을 말씀해 주세요.|기만적인 연구 등록 맥락에서 정확한 성명과 생년월일을 직접 요구한다.
B|-|모집 게시판에는 가입 없이 설명서를 볼 수 있다고 적혀 있어요.|원래 모집 안내와 발신자의 주장을 대조한다.
A|P|그럼 등록 중복 여부만 보게 주민등록번호 전체를 불러 주시겠어요?|중복 등록 확인을 빌미로 민감한 전체 식별번호를 요구한다.
B|-|모집 게시판의 관리자가 이 등록 절차는 없다고 합니다. 제 의향 접수만 취소하겠습니다.|독립 확인 결과를 근거로 참여 의향을 철회한다.
""")

add("scholarship-loan-conversion", "loan_fraud",
    "장학 상담 광고를 본 휴학생이 학자금 대출을 받으면 자동으로 장학금이 되어 상환이 없다는 허위 설명과 학교 계정 비밀번호 요구를 받는다.",
    "신규 학자금 채무의 장학금 자동 전환을 보장해 학교 계정 자격증명을 탈취",
    "기존 TRAIN의 대환·이자 환급·선보증금과 달리 새 학자금 채무를 무상 장학금처럼 설명하며 금전 선입금이나 앱 요구가 없다.",
    "허위 상환면제·승인 보장과 학교 계정 비밀번호 수집의 멀티라벨 근거 확인",
    """
B|-|장학 상담 광고를 보고 문의했습니다. 휴학 중인 사람도 장학금을 신청할 수 있나요?|광고의 신청 자격을 묻는 이용자 발화다.
A|I|가상 조직 온마루장학연결센터의 학교 연계 담당입니다. 해당 학교 접수를 맡고 있습니다.|학교와 연계된 조직의 접수 담당자라는 허위 소속과 권한을 주장한다.
B|-|학교 공지에서는 이 센터 이름을 못 봤는데 어떤 지원 방식인가요?|주장의 근거와 상품 성격을 질문한다.
A|L|휴학생도 심사 없이 등록금 전액을 대출받고 학기 말에 전부 장학금으로 바뀌어 상환할 돈이 없습니다.|무심사 대출 및 채무 전액의 장학금 전환이라는 허위 조건을 미끼로 제시한다.
B|-|대출 약정서에 제 빚으로 적힌다면 상환 면제를 누가 보장하나요?|대출의 책임과 보장 근거를 되묻는다.
A|LP|대출 승인과 전액 장학 전환이 보장된 특별 대상이니 학교 계정 비밀번호를 알려 주세요.|허위 대출 특혜와 정확한 계정 비밀번호 수집을 한 발화에서 함께 수행한다.
B|-|대신 로그인하지 마세요. 장학 담당 부서에 상품 설명을 가져가 보겠습니다.|계정 접근을 거절하고 별도 확인을 선택한다.
A|L|성적이나 기존 연체와 상관없이 대출은 확정되고 이자는 한 푼도 부담하지 않게 됩니다.|조건 없는 승인과 무이자 부담을 보장하는 허위 대출 설명이다.
B|-|학교에서는 대출을 장학금으로 자동 전환해 주는 연계가 없다고 하네요.|확인한 사실로 허위 연계를 반박한다.
B|-|신청은 멈추겠습니다. 장학 광고와 상담 내용을 학교에 전달할게요.|위험한 신청을 중단하고 관련 부서에 알리려 한다.
""")

add("investment-recovery-wallet", "personal_information",
    "투자 손실 피해자가 가짜 자산회수실의 연락을 받고 이용 거래소 떠보기, 지갑 복구 비밀번호 수집 및 가짜 출금 잔액 해제 송금 요구를 받는다.",
    "회수 자산 잔고를 조작하여 지갑 자격증명과 출금 해제 예치금을 노리는 재피해 사기",
    "기존 TRAIN의 대출 환급 및 미납 요금과 달리 투자 피해 회수를 미끼로 가상의 회수 잔액을 제시하며 지갑 접근까지 요구한다.",
    "가상자산 이전의 money_transfer 적용과 지갑 복구 비밀번호·손실 시한을 확인",
    """
A|I|가상 기관 유리물결자산회수실 조사 담당입니다. 투자 피해 자산을 찾아 연락했습니다.|자산 회수 권한이 있는 기관의 조사 직원을 사칭한다.
B|-|손실 상담은 남긴 적 있지만 회수를 맡긴 적은 없는데요. 무슨 자산인가요?|기존 상담과 수임 여부를 구분하며 연락 근거를 묻는다.
A|F|예전 투자는 거래소 계정으로 하셨죠? 개인 지갑만 쓰신 건 아니고요?|이용 방식 후보를 제시해 계정·지갑 보유 형태를 떠본다.
B|-|보유 방식부터 알려 드리지는 않겠습니다. 회수 근거 자료를 보여 주세요.|정보 탐색에 응하지 않고 증거를 요청한다.
A|P|지갑에 설정한 복구 비밀번호 전체를 말씀해 주시면 회수 내역을 연결하겠습니다.|지갑 접근에 쓰이는 정확한 비밀번호를 직접 요구한다.
B|-|복구 비밀번호를 넘기는 방식은 받지 않겠습니다. 출금된다는 잔액은 뭔가요?|자격증명 제공을 거절하고 발신자의 주장을 질문한다.
A|M|회수 잔액을 출금하려면 보유한 가상자산 일부를 저희가 지정하는 다른 지갑으로 먼저 보내세요.|가짜 자산 회수를 빌미로 상대 지갑에 자산을 이전하도록 직접 요구한다.
B|-|제 자산을 추가로 보낼 수는 없습니다. 서면 위임 계약도 없어요.|추가 지급을 거절하고 계약 부재를 지적한다.
A|MT|10분 안에 출금 해제금을 보내지 않으면 회수 잔액이 소멸하니 바로 송금하세요.|명시적 시한과 잔액 손실을 내세워 금전 이전을 강요한다.
B|-|회수 잔액 화면도 신뢰하지 않겠습니다. 접수했던 피해 상담 창구에 이 연락을 확인할게요.|허위 화면에 따르지 않고 기존 상담 창구에 확인한다.
""")

add("normal-coin-exchange", None,
    "고객이 지점 게시물의 문의처로 기념주화 교환 가능 수량을 문의하고 방문 예약용 이름과 연락처만 남긴다.",
    "정상: 지점 방문을 위한 주화 수량 확인, 선입금이나 인증정보 발설 없음",
    "기존 TRAIN의 앱 이용·구독 청구와 달리 현물 주화 교환 수량과 방문 예약을 다룬다.",
    "최소한의 예약자 정보와 정상 현금 교환 안내를 피싱으로 오인하지 않는지 확인",
    """
B|-|가상 은행 모닥돌은행 지점 게시물을 보고 연락했습니다. 기념주화 한 묶음을 교환할 수 있나요?|고객이 기존 지점 안내에 따라 시작한 정상 상담이다.
A|-|오늘 남은 수량이 있어 방문 예약이 가능합니다. 교환할 액면 금액은 창구에서 확인하시면 됩니다.|정상적인 현물 교환 수량과 방문 절차를 설명한다.
B|-|예약만 하려면 먼저 송금해야 하는 줄 알았어요.|고객이 예약 비용을 되묻는 발화다.
A|-|예약 선입금은 받지 않습니다. 연락받을 성함과 전화번호만 남겨 주실 수 있나요?|정상 고객 요청에 필요한 최소 예약 정보를 수집하며 별도 송금을 요구하지 않는다.
B|-|예약자는 [PERSON]이고 연락처는 [PHONE_NUMBER]입니다.|허용 토큰으로 처리한 안전한 더미 예약 정보다.
A|-|그 정보는 방문 연락용으로만 접수하겠습니다. 계좌 비밀번호나 인증번호는 필요 없습니다.|정상적인 정보 사용 범위와 최소화를 설명한다.
B|-|찾아가기 전에 수량이 달라지면 연락을 부탁드립니다.|정상적인 예약 연락 요청이다.
A|-|변경되면 접수한 연락처로 수량만 안내하겠습니다. 확인 후 방문하셔도 됩니다.|고객의 확인 기회를 보장하는 정상 예약 안내다.
""")

add("normal-clinic-certificate", None,
    "환자가 기존 병원 안내문의 문서 창구로 진료확인서 수령을 문의하고 최소 본인 확인 뒤 대리 수령의 서면 동의 필요 여부를 확인한다.",
    "정상: 고객이 요청한 문서 발급에서 성명·생년월일 확인 및 수령 범위 안내",
    "기존 TRAIN의 보험사 서류 보완 전화와 달리 환자가 병원 문서 창구에 발신하며 보험 청구·전체 주민번호·인증번호 수집이 없다.",
    "정상 본인 확인 요청과 가족 대리수령 시 정보 보호를 위험 라벨로 오인하지 않는지 검수",
    """
B|-|별언덕의원 안내문의 문서 창구로 전화했어요. 제가 요청한 진료확인서를 언제 찾을 수 있나요?|환자가 기존 안내에 따라 문서 수령을 문의하는 정상 상담이다.
A|-|본인 신청 건을 찾도록 성함과 생년월일을 여쭙겠습니다. 주민번호 전체는 말씀하지 않으셔도 됩니다.|요청한 문서 조회에 필요한 최소 본인 확인이며 사기성 수집이 아니다.
B|-|성함은 [PERSON], 생년월일은 [BIRTH]로 접수돼 있을 거예요.|허용 마스킹 토큰만 사용한 더미 본인 확인 응답이다.
A|-|발급 준비가 끝난 문서가 있습니다. 본인이 오시면 접수 창구에서 수령 확인을 진행합니다.|정상적인 문서 수령 상태와 절차를 설명한다.
B|-|가족이 대신 가는 경우에 제 전화 인증번호를 전해 줘야 하나요?|대리 수령 시 인증번호 공유 여부를 묻는 정상 질문이다.
A|-|인증번호를 전달하실 필요는 없습니다. 대리 수령에 필요한 서면 동의 목록을 안내문에서 확인해 주세요.|인증정보 공유 대신 공식 서면 동의를 안내한다.
B|-|안내문을 가족과 같이 읽어 보고 제가 갈지 정하겠습니다.|가족과 함께 절차를 확인하려는 정상 반응이다.
A|-|그렇게 결정하셔도 됩니다. 가족 관계나 진료 내용을 여기서 더 설명하지 않으셔도 됩니다.|숙고와 정보 최소화를 허용하는 정상 안내다.
""")

add("normal-safety-drill", None,
    "주민이 받은 사전 안내에 따라 방재 훈련 경보의 의미와 출입 제한 구역을 문의하고 실제 재난 경보와 구분한다.",
    "정상: 사전 공지된 모의 훈련의 안전 통제 설명, 금전·정보 요구 없음",
    "기존 TRAIN의 공공요금 서비스 중단 압박과 달리 불이익을 미끼로 행동을 강제하지 않고 사전 공지된 현장 안전 통제를 설명한다.",
    "경보·출입 통제 표현이 있어도 사기성 threat_pressure가 아닌 정상 안전 안내인지 확인",
    """
B|-|가람방재센터의 주민 훈련 안내문을 받았습니다. 훈련 때 휴대전화 경보가 울리는 건가요?|사전 안내문에 따라 주민이 시작한 정상 문의다.
A|-|이번 모의 훈련에서는 현장 방송으로 훈련 시작을 알립니다. 실제 상황 안내와 구분해 공지합니다.|가상의 사전 공지된 훈련 절차를 설명한다.
B|-|안내문에 출입 통제라고 적혀 있어서 평소 가던 길을 못 쓰는지 궁금해요.|주민이 안전 통제의 범위를 질문한다.
A|-|장비 시연 구역만 통제하고 옆 보행로는 열어 둡니다. 현장 요원의 우회 안내를 확인해 주세요.|정상적인 현장 안전 범위 안내이며 사기성 처벌·손실 강요가 아니다.
B|-|개인정보를 등록하거나 참가비를 내야 알림을 받을 수 있나요?|정상 문의 중 등록 비용의 유무를 확인한다.
A|-|둘 다 필요 없습니다. 훈련 시간과 장소는 이미 받은 안내문에서 확인하실 수 있습니다.|불필요한 정보 수집과 비용을 요구하지 않는다.
B|-|동네 모임에도 그 안내문을 공유하겠습니다.|공개 훈련 안내를 주변에 공유하려 한다.
A|-|공유하셔도 좋습니다. 알림 문구가 혼동되면 같은 문의처로 다시 확인하셔도 됩니다.|제3자 공유 및 별도 확인을 허용하는 정상 상담이다.
""")

add("normal-rental-data-wipe", None,
    "이용자가 대여 노트북의 반납 전 개인정보 삭제 방법을 기존 대여업체 창구에 문의하고 로컬 초기화 및 반납 상태 확인을 안내받는다.",
    "정상: 반납 기기의 데이터 삭제 선택, 파일·계정 비밀번호를 상담자에게 넘기지 않음",
    "기존 TRAIN의 공식 앱 설치·접근 안내와 달리 반납할 기기의 저장자료 삭제와 검수 범위를 다루며 새 앱 설치가 없다.",
    "정보를 말하지 말라는 개인정보 보호 안내와 제3자 비밀 유지 요구를 구분",
    """
B|-|대여 계약서의 다락책상 고객센터로 문의합니다. 노트북 반납 전에 자료를 지워도 되나요?|이용자가 기존 계약 문의처로 시작한 정상 반납 상담이다.
A|-|개인 파일을 먼저 백업하신 뒤 기기 기본 설정의 초기화 안내를 확인하시면 됩니다.|고객 소유 정보 보호를 위한 정상적인 기기 반납 안내다.
B|-|지우려는 파일 이름이나 로그인 비밀번호를 여기서 알려 드릴까요?|고객이 정보 전달 필요 여부를 질문한다.
A|-|파일 목록이나 비밀번호는 말씀하지 마세요. 상담원이 개인 자료를 받아 대신 지우지 않습니다.|개인정보 발설을 막는 안내이며 제3자에게 통화 사실을 숨기라는 요구가 아니다.
B|-|초기화하다가 어려우면 화면을 보내야 하나요?|지원 과정의 정보 공유 범위를 묻는다.
A|-|내용이 보이는 화면을 보낼 필요는 없습니다. 어려운 단계의 메뉴 이름만 설명해 주셔도 됩니다.|불필요한 화면·자료 수집을 피하는 정상 지원이다.
B|-|초기화를 마친 상태로 반납하면 직원이 자료를 다시 읽어보지는 않겠죠?|고객이 반납 검수의 범위를 확인한다.
A|-|반납 검수는 기기 작동과 외관을 확인합니다. 개인 자료를 복원해 제출하실 필요는 없습니다.|정상 반납 검수 범위를 설명하며 개인정보 복원을 요구하지 않는다.
""")


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, content, *, bom=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8-sig" if bom else "utf-8")
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"Refuse to overwrite existing artifact: {path}")
    else:
        with path.open("xb") as stream:
            stream.write(data)


def dump_jsonl(path, rows):
    write_new(path, "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":"))+"\n" for r in rows))


def review_rows(conversations):
    rows = []
    for c in conversations:
        focus = next(d["human_review_focus"] for d in DESIGNS if d["synthetic_id"] == c["synthetic_id"])
        for u in c["utterances"]:
            row = dict(zip(review.SOURCE_COLUMNS, [c["synthetic_id"], f"{c['synthetic_id']}-{u['utterance_id']}",
                str(u["utterance_id"]), u["speaker"], c["scenario_summary"], u["text"], str(u["is_phishing"]).lower(),
                json.dumps(u["labels"], ensure_ascii=False), u["label_rationale"], "예", focus, *review.REVIEWERS, "미반영"]))
            for name in review.REVIEWERS:
                row.update({f"검수_결과_{name}": "미승인", f"수정_의견_{name}": "", f"검수_일시_{name}": ""})
            row.update(최종_합의_결과="미승인", 합의_수정안="", 최종_합의_일시="")
            rows.append(row)
    return rows


def main():
    original, previous = jsonl(PILOT), jsonl(PREVIOUS)
    if [{k: v for k, v in c.items() if k != "review_preparation"} for c in previous] != original:
        raise ValueError("Existing candidate differs from canonical")
    reserved = json.loads(RESERVED.read_text(encoding="utf-8"))
    if {c["scenario_family_id"] for c in CONVERSATIONS} & {s["scenario_family_id"] for s in reserved["scenarios"]}:
        raise ValueError("Reserved VALIDATION family collision")
    if {c["scenario_id"] for c in CONVERSATIONS} & {s["scenario_id"] for s in reserved["scenarios"]}:
        raise ValueError("Reserved VALIDATION scenario collision")
    assert len(CONVERSATIONS) == 8
    dump_jsonl(NEW, CONVERSATIONS)
    # Copy old candidate records exactly at the byte level; no approval edits.
    previous_bytes = PREVIOUS.read_bytes()
    assert previous_bytes.endswith(b"\n")
    merged_bytes = previous_bytes + NEW.read_bytes()
    write_new(MERGED, merged_bytes.decode("utf-8"))
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=review.COLUMNS)
    writer.writeheader()
    writer.writerows(review_rows(CONVERSATIONS))
    write_new(CSV, buf.getvalue(), bom=True)
    baseline = json.loads((REPORTS / "protected_baseline.json").read_text(encoding="utf-8"))
    from collections import Counter
    provenance = dict(model=MODEL, exact_backend_model_id=None,
        model_note="확인 가능한 Codex 모델 계열만 기록; 권장 GPT-6.1 Sol을 실제 모델로 추정하지 않음",
        authoring_started_at=baseline["recorded_at"], prompt_version="v2-train-expansion-1",
        authoring="Codex session authored literals; Python serializes without LLM API calls",
        generation_inputs={p.relative_to(ROOT).as_posix(): sha(p) for p in (PILOT, PREVIOUS, RESERVED, ROOT / "dataset/label_guide_v3.2.md")},
        design_basis="Existing TRAIN distribution and guide only; VALIDATION registry is an exclusion list, not a training target",
        original_train_positive_labels=dict(Counter(l for c in original for u in c["utterances"] for l in u["labels"])),
        validation_dialogue_use="Post-generation duplicate/independence audit only; no label-distribution targeting",
        new8_sha256_before_post_generation_validation_audit=sha(NEW),
        merged24_sha256_before_post_generation_validation_audit=sha(MERGED),
        original_16_bytes_preserved=True, training_authorized=False, final_approved=False,
        source_schema="Existing canonical conversation fields, plus untouched review_preparation on old 16 only",
        actual_v1_duplicate_check="NOT_VERIFIED_INPUTS_UNAVAILABLE", scenarios=DESIGNS)
    write_new(OUT / "generation_and_scenarios.json", json.dumps(provenance, ensure_ascii=False, indent=2)+"\n")
    lines = ["# TRAIN 0017~0024 신규 시나리오", "",
        "기존 TRAIN 분포를 기준으로 4개 복합 피싱 상황과 4개 정상 상담을 신규 작성했습니다. VALIDATION 본문은 생성 후 중복 검사에만 사용합니다.",
        "VALIDATION registry는 재사용 금지 목록으로만 확인했습니다. 의미적 중복은 자동 문자열 검사와 별도로 사람 확인이 필요합니다.", "",
        "|ID / 가족|주요 유형|상황·기제|기존 TRAIN과 다른 전개|검수 초점|", "|---|---|---|---|---|"]
    for d in DESIGNS:
        lines.append(f"|{d['synthetic_id']} / {d['scenario_family_id']}|{d['primary_type'] or '완전 정상'}|{d['situation']} {d['mechanism']}|{d['distinction_from_existing_train']}|{d['human_review_focus']}|")
    write_new(REPORTS / "scenario_design.md", "\n".join(lines)+"\n")
    print(json.dumps(dict(new_conversations=8, new_utterances=sum(len(c["utterances"]) for c in CONVERSATIONS),
                         merged_conversations=len(previous)+8, new_sha256=sha(NEW)), ensure_ascii=False))


if __name__ == "__main__":
    main()
