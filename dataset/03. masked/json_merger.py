# 폴더랑 파일 이름 정하면 병합해주는 프로그램입니다

import json
from pathlib import Path

input_dir = Path("phishing") #병합을 원하는 폴더 경로
output_file = Path("phishing_merged.jsonl") #완료 파일 저장 경로

with open(output_file, "w", encoding="utf-8") as out:
    for file_path in sorted(input_dir.glob("*.jsonl")):

        print(f"합치는 중: {file_path.name}")

        with open(file_path, "r", encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)

                out.write(
                    json.dumps(data, ensure_ascii=False) + "\n"
                )

print("병합 완료")