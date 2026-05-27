"""
챕터 2 — Claude Haiku 관심도 필터링

챕터 1 이 수집한 뉴스 JSON 을 읽어, 사용자 관심사 프로파일을 기준으로
Claude Haiku 가 각 기사에 1~10 점수를 매기고 8점 이상만 추려 저장합니다.

비용: 기사 50개 기준 약 10~15원 (Haiku 한 번 호출)
"""

import json
import os
import sys
import io
from pathlib import Path
from datetime import datetime

# Windows 콘솔 한글 깨짐 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ---- 의존성 체크 ----
try:
    from dotenv import load_dotenv
except ImportError:
    print("[준비] python-dotenv 가 설치되지 않았습니다.")
    print("       pip install python-dotenv anthropic")
    sys.exit(1)

try:
    from anthropic import Anthropic
except ImportError:
    print("[준비] anthropic 라이브러리가 설치되지 않았습니다.")
    print("       pip install anthropic")
    sys.exit(1)


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"

# 사용 모델 (Haiku 4.5 — 분류·요약에 최적, 매우 저렴)
HAIKU_MODEL = "claude-haiku-4-5"

# 8점 이상만 채택, 최대 N개로 캡 (config.json 의 max_final_articles 로도 조정)
SCORE_THRESHOLD = 8
DEFAULT_MAX_FINAL = 10


def load_api_key() -> str:
    """.env 에서 API 키 로드"""
    load_dotenv(BASE_DIR / ".env", override=True)
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key or key.startswith("sk-ant-여기에"):
        print("[오류] .env 파일에 ANTHROPIC_API_KEY 가 설정되지 않았습니다.")
        print(f"       1) {BASE_DIR / '.env.example'} 를 .env 로 복사")
        print(f"       2) .env 안의 키 값을 실제 API 키로 교체")
        sys.exit(1)
    return key


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def find_latest_raw_json() -> Path:
    """data/news_raw_*.json 중 가장 최신 파일 자동 탐지"""
    files = sorted(DATA_DIR.glob("news_raw_*.json"), reverse=True)
    if not files:
        print("[오류] data/news_raw_*.json 파일이 없습니다.")
        print("       먼저 'python fetch_news.py' 를 실행해 챕터 1 결과를 만들어 주세요.")
        sys.exit(1)
    return files[0]


def build_interest_profile(interests: dict) -> str:
    """config.json 의 interests 를 자연어 프로파일로 변환"""
    lines = []
    for category, kws in interests.items():
        if category.startswith("_"):
            continue
        label = category.replace("_", "/")
        lines.append(f"- {label}: {', '.join(kws)}")
    return "\n".join(lines)


def score_articles(client: Anthropic, articles: list[dict], profile: str) -> list[dict]:
    """Haiku 한 번 호출로 전체 기사에 점수 매김"""
    # 기사 목록을 LLM 이 읽기 좋은 형태로 직렬화
    listing = []
    for idx, a in enumerate(articles):
        listing.append(
            f"[{idx}] 제목: {a['title']}\n"
            f"     출처: {a['source']}  |  요약: {a.get('summary', '')[:150]}"
        )
    listing_text = "\n\n".join(listing)

    system_prompt = (
        "당신은 사용자의 관심사에 기반해 뉴스 기사를 큐레이션하는 큐레이터입니다. "
        "각 기사가 사용자의 관심사와 얼마나 일치하는지를 1~10 점수로 평가합니다.\n\n"
        "채점 기준:\n"
        "- 10점: 관심사 핵심 키워드에 정확히 일치하며, 트렌드·중요 업데이트를 다룸\n"
        "- 8~9점: 관심사 영역에 직접적으로 관련됨\n"
        "- 6~7점: 간접적으로 관련 (확장 분야)\n"
        "- 4~5점: 약하게 연관\n"
        "- 1~3점: 거의 무관 (부음, 일반 산업 뉴스, 단순 사건사고 등)\n\n"
        "반드시 JSON 배열만 출력. 다른 설명 금지."
    )

    user_prompt = (
        f"# 사용자 관심사 프로파일\n{profile}\n\n"
        f"# 평가할 기사 ({len(articles)}개)\n{listing_text}\n\n"
        "# 출력 형식 (JSON 배열만)\n"
        '[{"idx": 0, "score": 9, "reason": "Claude API 업데이트 직접 관련"}, ...]\n'
        "모든 기사를 빠짐없이 평가하세요. idx 는 위 번호 그대로 유지."
    )

    print(f"[Haiku 호출] {len(articles)}개 기사 평가 중...")
    resp = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=16000,  # 기사 100개+ 대응 (이전 4000 한도 초과로 응답 잘림 이슈 해결)
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = resp.content[0].text.strip()
    # JSON 추출 (코드블록으로 감싼 경우 대비)
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        scores = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[오류] Haiku 응답 JSON 파싱 실패: {e}")
        print(f"[원본]\n{raw[:500]}")
        sys.exit(1)

    # 토큰·비용 정보 출력
    usage = resp.usage
    cost_usd = (usage.input_tokens * 1.0 + usage.output_tokens * 5.0) / 1_000_000
    cost_krw = cost_usd * 1380
    print(f"[토큰] 입력 {usage.input_tokens} + 출력 {usage.output_tokens} = 약 {cost_krw:.1f}원")

    return scores


def merge_scores(articles: list[dict], scores: list[dict]) -> list[dict]:
    """원본 기사에 score / reason 필드 추가"""
    score_map = {s["idx"]: s for s in scores}
    merged = []
    for idx, a in enumerate(articles):
        s = score_map.get(idx, {"score": 0, "reason": "(평가 누락)"})
        merged.append({**a, "score": s.get("score", 0), "reason": s.get("reason", "")})
    return merged


def print_top(merged: list[dict], threshold: int, max_final: int) -> list[dict]:
    """점수 기준 정렬 후 상위 출력 + 통과 목록 반환 (최대 max_final 개)"""
    merged_sorted = sorted(merged, key=lambda x: x["score"], reverse=True)
    passed_all = [m for m in merged_sorted if m["score"] >= threshold]
    passed = passed_all[:max_final]   # 상위 N개로 캡

    capped_note = ""
    if len(passed_all) > max_final:
        capped_note = f" → 상위 {max_final}개로 캡"
    print(f"\n[필터링 결과] 총 {len(merged)}개 중 {threshold}점 이상 = {len(passed_all)}개{capped_note}\n")
    print("=" * 70)
    for i, a in enumerate(passed, 1):
        print(f"\n{i}. [{a['score']}점] {a['title']}")
        print(f"   이유: {a['reason']}")
        print(f"   출처: {a['source']}")
        print(f"   링크: {a['link']}")
    print("\n" + "=" * 70)

    # 아쉽게 떨어진 6~7점도 한번 보여줌 (감각 잡기용)
    near = [m for m in merged_sorted if 6 <= m["score"] < threshold][:5]
    if near:
        print(f"\n[참고] 6~{threshold-1}점 (다음 회차에서 임계값 조정 시 참고):")
        for a in near:
            print(f"   {a['score']}점 — {a['title']}")

    return passed


def save_filtered(passed: list[dict], threshold: int) -> Path:
    """필터링 통과 기사를 JSON 으로 저장 (다음 챕터 입력용)"""
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = DATA_DIR / f"news_filtered_{today}.json"
    payload = {
        "filtered_at": datetime.now().isoformat(),
        "score_threshold": threshold,
        "total_count": len(passed),
        "articles": passed,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n[저장] {out_path}")
    return out_path


def main():
    api_key = load_api_key()
    config = load_config()

    # 1) 챕터 1 결과 로드
    raw_path = find_latest_raw_json()
    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)
    articles = raw["articles"]
    print(f"[입력] {raw_path.name}  |  기사 {len(articles)}개")

    # 2) 관심사 프로파일 생성
    profile = build_interest_profile(config["interests"])
    print(f"[프로파일]\n{profile}\n")

    # 3) Haiku 호출
    client = Anthropic(api_key=api_key)
    scores = score_articles(client, articles, profile)

    # 4) 점수 병합 + 출력 (config 의 max_final_articles, 없으면 기본값)
    merged = merge_scores(articles, scores)
    max_final = config.get("settings", {}).get("max_final_articles", DEFAULT_MAX_FINAL)
    passed = print_top(merged, SCORE_THRESHOLD, max_final)

    # 5) 저장
    save_filtered(passed, SCORE_THRESHOLD)

    print("\n[완료] 챕터 2 끝.")
    print("        다음 챕터(3)에서 Claude Sonnet 이 통과 기사에 요약 + 인사이트를 붙입니다.")


if __name__ == "__main__":
    main()
