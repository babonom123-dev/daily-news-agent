"""
챕터 1 — RSS 뉴스 수집기 (Claude API 미사용, 순수 파이썬)

관심사 키워드 기반으로 구글 뉴스 RSS + 한국 IT 매체 RSS 를 모두 긁어와
최근 24시간 기사를 콘솔에 정리해 출력합니다.

다음 챕터(2번)에서 Claude Haiku 가 이 결과를 받아 관심도 점수를 매깁니다.
"""

import json
import re
import sys
import time
import io
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from pathlib import Path

# Windows 콘솔 한글 깨짐 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import feedparser
except ImportError:
    print("[준비] feedparser 가 설치되지 않았습니다.")
    print("       다음 명령으로 설치 후 다시 실행하세요:")
    print("       pip install feedparser")
    sys.exit(1)


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config() -> dict:
    """config.json 로드 및 기본값 보정"""
    if not CONFIG_PATH.exists():
        print(f"[오류] config.json 이 없습니다: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def collect_all_keywords(interests: dict) -> list[str]:
    """카테고리별 키워드를 단일 리스트로 평탄화"""
    keywords = []
    for category, kws in interests.items():
        if category.startswith("_"):
            continue
        keywords.extend(kws)
    return keywords


def parse_entry_time(entry) -> datetime | None:
    """RSS 항목의 발행 시간을 UTC datetime 으로 변환"""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
            except Exception:
                pass
    return None


def fetch_google_news(keyword: str, template: str, hours: int, limit: int) -> list[dict]:
    """구글 뉴스 RSS 검색 결과를 가져와 리스트로 반환"""
    url = template.format(keyword=quote(keyword))
    parsed = feedparser.parse(url)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    articles = []
    for entry in parsed.entries[: limit * 3]:  # 시간 필터링 전 여유 있게 가져옴
        pub = parse_entry_time(entry)
        if pub and pub < cutoff:
            continue
        articles.append({
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", "").strip(),
            "source": entry.get("source", {}).get("title", "Google News") if isinstance(entry.get("source"), dict) else "Google News",
            "published": pub.isoformat() if pub else "(시간 정보 없음)",
            "summary": entry.get("summary", "").strip()[:200],
            "keyword": keyword,
        })
        if len(articles) >= limit:
            break
    return articles


def fetch_static_feed(feed_cfg: dict, hours: int) -> list[dict]:
    """고정 RSS 피드(AI타임스 등)에서 최근 기사 수집"""
    url = feed_cfg["url"]
    name = feed_cfg["name"]
    parsed = feedparser.parse(url)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    articles = []
    for entry in parsed.entries[:30]:
        pub = parse_entry_time(entry)
        if pub and pub < cutoff:
            continue
        articles.append({
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", "").strip(),
            "source": name,
            "published": pub.isoformat() if pub else "(시간 정보 없음)",
            "summary": entry.get("summary", "").strip()[:200],
            "keyword": "(고정 피드)",
        })
    return articles


def _normalize_title(title: str) -> str:
    """제목 정규화 — 같은 기사를 같은 키로 만들기.
    구글 뉴스는 제목 끝에 ' - 출처명' 을 붙이고 직접 RSS 는 안 붙여서
    글자가 미세하게 달라지므로, 출처 꼬리표 제거 + 공백·기호 제거 후 비교한다.
    """
    t = title.strip()
    # 구글 뉴스가 붙이는 마지막 ' - 출처명' 제거
    t = re.sub(r"\s*-\s*[^-]+$", "", t)
    # 공백·따옴표·문장부호 전부 제거 (한글·영문·숫자만 남김)
    t = re.sub(r"[^0-9A-Za-z가-힣]", "", t)
    return t.lower()


def dedupe_by_title(articles: list[dict]) -> list[dict]:
    """정규화된 제목 기준으로 중복 제거 (출처 꼬리표·기호 차이 무시)"""
    seen = set()
    result = []
    for a in articles:
        key = _normalize_title(a["title"])
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(a)
    return result


def print_summary(articles: list[dict]) -> None:
    """수집된 기사를 카테고리별로 콘솔에 출력"""
    if not articles:
        print("\n[결과] 최근 24시간 안에 매칭된 기사가 없습니다.\n")
        return

    print(f"\n[결과] 총 {len(articles)}개 기사 수집됨\n")
    print("=" * 70)

    # 키워드별로 묶어 출력
    by_keyword: dict[str, list[dict]] = {}
    for a in articles:
        by_keyword.setdefault(a["keyword"], []).append(a)

    for keyword, items in by_keyword.items():
        print(f"\n■ 키워드: {keyword}  ({len(items)}개)")
        print("-" * 70)
        for i, a in enumerate(items, 1):
            print(f"  {i}. {a['title']}")
            print(f"     출처: {a['source']}  |  {a['published'][:16]}")
            print(f"     링크: {a['link']}")
            if a["summary"]:
                clean = a["summary"].replace("<", "").replace(">", "")[:120]
                print(f"     요약: {clean}...")
            print()
    print("=" * 70)


def save_to_json(articles: list[dict], path: Path) -> None:
    """수집 결과를 JSON 으로 저장 (다음 챕터에서 Claude 가 읽음)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_count": len(articles),
        "articles": articles,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[저장] {path}")


def main():
    config = load_config()

    settings = config.get("settings", {})
    hours = settings.get("hours_lookback", 24)
    per_kw = settings.get("max_articles_per_keyword", 5)
    do_dedupe = settings.get("dedupe_by_title", True)

    keywords = collect_all_keywords(config.get("interests", {}))
    rss_cfg = config.get("rss_sources", {})
    template = rss_cfg.get("google_news_template", "")
    static_feeds = rss_cfg.get("static_feeds", [])

    print(f"[시작] 관심사 키워드 {len(keywords)}개 + 고정 피드 {len(static_feeds)}개 수집 (최근 {hours}시간)")
    print(f"[키워드] {', '.join(keywords)}\n")

    all_articles: list[dict] = []

    # 1) 구글 뉴스 키워드 검색
    for kw in keywords:
        try:
            print(f"  [구글뉴스] {kw} 검색 중...", end=" ")
            items = fetch_google_news(kw, template, hours, per_kw)
            print(f"{len(items)}건")
            all_articles.extend(items)
        except Exception as e:
            print(f"실패 ({e})")

    # 2) 고정 피드 (AI타임스 등)
    for feed in static_feeds:
        try:
            print(f"  [고정피드] {feed['name']} 수집 중...", end=" ")
            items = fetch_static_feed(feed, hours)
            print(f"{len(items)}건")
            all_articles.extend(items)
        except Exception as e:
            print(f"실패 ({e})")

    # 3) 중복 제거
    if do_dedupe:
        before = len(all_articles)
        all_articles = dedupe_by_title(all_articles)
        print(f"\n[중복제거] {before} → {len(all_articles)}")

    # 4) 콘솔 출력
    print_summary(all_articles)

    # 5) JSON 저장 (다음 챕터 입력용)
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = BASE_DIR / "data" / f"news_raw_{today}.json"
    save_to_json(all_articles, out_path)

    print("\n[완료] 챕터 1 끝.")
    print("        다음 챕터(2)에서 Claude Haiku 가 이 결과에 관심도 점수를 매깁니다.")


if __name__ == "__main__":
    main()
