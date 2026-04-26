import csv
import os
from datetime import date
from config import OUTPUT_DIR


def save_to_csv(results: list[dict]) -> str:
    """결과 리스트를 CSV로 저장. 저장 경로 반환."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, f"{date.today().isoformat()}.csv")

    fieldnames = ["ticker", "price", "grade", "score", "action",
                  "target_1", "target_2", "stop_loss"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"[Logger] 저장 완료: {filepath} ({len(results)}개 종목)")
    return filepath
