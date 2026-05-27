# daily-news-agent

> 매일 아침 관심사 기반 뉴스를 자동 수집·요약·이메일 발송하는 AI 에이전트.

---

## 진행 상황

- [x] **챕터 1** — RSS 뉴스 수집 (`fetch_news.py`)
- [ ] **챕터 2** — Claude Haiku 관심도 필터링
- [ ] **챕터 3** — Claude Sonnet 요약 + 인사이트
- [ ] **챕터 4** — Gmail SMTP 이메일 발송
- [ ] **챕터 5** — Windows 작업 스케줄러 자동 실행
- [ ] **챕터 6** — 피드백 학습 루프

---

## 챕터 1 실행 방법

### 1. 의존성 설치 (최초 1회)

```bash
pip install -r requirements.txt
```

### 2. 실행

```bash
python fetch_news.py
```

### 3. 결과 확인

- 콘솔에 키워드별 수집 결과가 출력됩니다.
- `data/news_raw_YYYY-MM-DD.json` 파일이 생성됩니다 (다음 챕터 입력용).

---

## 관심사 키워드 수정

`config.json` 의 `interests` 항목을 자유롭게 편집하세요.

```json
"interests": {
  "AI_플랫폼": ["ChatGPT", "Claude", "Gemini"],
  "마케팅_콘텐츠": ["숏폼 마케팅", "바이럴 마케팅"]
}
```

키워드를 추가/삭제/변경 후 다시 `python fetch_news.py` 실행하면 즉시 반영됩니다.
