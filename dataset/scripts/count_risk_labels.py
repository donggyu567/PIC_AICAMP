import json
from collections import Counter
from pathlib import Path

#작업한 폴더 절대경로 삽입
input_dir = Path(r"C:\Archive\005.code\PIC_DATA\dataset\03. masked\phishing")

risk_labels = (
    "institution_impersonation",
    "money_transfer",
    "personal_information",
    "app_installation",
    "secrecy",
    "threat_pressure",
    "loan_fraud",
    "information_probing",
)

conversation_labels = {}  # 대화 ID → 해당 대화에서 나온 라벨
utterance_counts = Counter()  # 라벨 → 해당 라벨이 붙은 발화 수

jsonl_files = sorted(input_dir.glob("*.jsonl"))
if not jsonl_files:
    raise FileNotFoundError(f"JSONL 파일이 없습니다: {input_dir}")

for file_path in jsonl_files:
    print(f"읽는 중: {file_path.name}")

    with file_path.open("r", encoding="utf-8-sig") as file:
        for line in file:
            if not line.strip():
                continue

            data = json.loads(line)
            conversation_id = data["conversation_id"]
            labels = set(data.get("labels", []))

            conversation_labels.setdefault(conversation_id, set()).update(labels)
            utterance_counts.update(labels)

print(f"\n읽은 파일: {len(jsonl_files)}개")
print(f"전체 대화: {len(conversation_labels)}개\n")
print(f"{'위험 유형':30} {'대화 수':>8} {'발화 수':>8}")

for label in risk_labels:
    conversation_count = sum(
        label in labels for labels in conversation_labels.values()
    )
    print(f"{label:30} {conversation_count:>8} {utterance_counts[label]:>8}")