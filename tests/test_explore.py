import sys
import os
import json
sys.path.append(os.getcwd())

from services.explore_service import run_explore_analysis

def test_explore():
    print("Testing Explore Service for AAPL...")
    result = run_explore_analysis(tickers_override=["AAPL"])
    
    # 텍스트가 너무 길면 보기 힘드니 핵심만 출력
    for r in result["results"]:
        print(f"\n[{r['ticker']}] {r['short_name']}")
        print(f"Price: ${r['price']}")
        print(f"Foundation: {r['foundation']['grade']} ({r['foundation']['score']}/{r['foundation']['max_score']})")
        print(f"Timing: {r['timing']['signal_grade']} ({r['timing']['signal_score']})")
        print(f"NL Summary: {r['nl_summary']}")
        
    print("\nFull Data Structure (Sample):")
    if result["results"]:
        print(json.dumps(result["results"][0], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_explore()
