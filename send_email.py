"""
챕터 4 — Gmail SMTP 이메일 발송

챕터 2 가 필터링한 8점 이상 기사를 HTML 메일로 자기 자신에게 발송합니다.
요약 없이 [점수 + 이유 + 제목 + 출처 + 링크] 형식으로 압축.

준비물:
  1) Gmail 2단계 인증 활성화 (https://myaccount.google.com/security)
  2) Gmail 앱 비밀번호 발급 (https://myaccount.google.com/apppasswords)
  3) .env 파일에 GMAIL_ADDRESS, GMAIL_APP_PASSWORD 추가

사용:
  python send_email.py
"""

import json
import os
import smtplib
import sys
import io
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Windows 콘솔 한글 깨짐 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
except ImportError:
    print("[준비] pip install python-dotenv")
    sys.exit(1)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def load_env() -> tuple[str, str]:
    """Gmail 주소 + 앱 비밀번호 로드"""
    load_dotenv(BASE_DIR / ".env", override=True)
    addr = (os.getenv("GMAIL_ADDRESS") or "").strip()
    pw = (os.getenv("GMAIL_APP_PASSWORD") or "").strip().replace(" ", "")  # 공백 제거 (구글이 16자리를 4자리씩 띄어 표시함)
    if not addr or not pw:
        print("[오류] .env 에 GMAIL_ADDRESS / GMAIL_APP_PASSWORD 가 없습니다.")
        print("       Gmail 앱 비밀번호 발급:")
        print("       https://myaccount.google.com/apppasswords")
        sys.exit(1)
    return addr, pw


def find_latest_filtered_json() -> Path:
    files = sorted(DATA_DIR.glob("news_filtered_*.json"), reverse=True)
    if not files:
        print("[오류] data/news_filtered_*.json 이 없습니다.")
        print("       먼저 'python filter_news.py' (챕터 2) 실행이 필요합니다.")
        sys.exit(1)
    return files[0]


def build_html(articles: list[dict], today_label: str) -> str:
    """깔끔한 인스타 카드 느낌의 HTML 이메일 본문 생성"""
    # 점수별 색상 (9~10: 초록, 8: 파랑, 6~7: 회색)
    def score_color(s: int) -> str:
        if s >= 9:
            return "#10b981"  # emerald
        if s >= 8:
            return "#3b82f6"  # blue
        return "#6b7280"      # gray

    cards = []
    for i, a in enumerate(articles, 1):
        color = score_color(a.get("score", 0))
        title = a.get("title", "").replace("<", "&lt;").replace(">", "&gt;")
        reason = a.get("reason", "").replace("<", "&lt;").replace(">", "&gt;")
        source = a.get("source", "")
        link = a.get("link", "#")
        score = a.get("score", 0)

        cards.append(f"""
        <tr>
          <td style="padding: 16px 0; border-bottom: 1px solid #e5e7eb;">
            <div style="margin-bottom: 8px;">
              <span style="display: inline-block; padding: 2px 10px; border-radius: 12px;
                     background-color: {color}; color: white; font-size: 12px; font-weight: 700;">
                {score}점
              </span>
              <span style="color: #9ca3af; font-size: 13px; margin-left: 8px;">{source}</span>
            </div>
            <a href="{link}" style="color: #111827; text-decoration: none; font-size: 16px; font-weight: 600; line-height: 1.4;">
              {i}. {title}
            </a>
            <div style="color: #4b5563; font-size: 14px; margin-top: 6px; line-height: 1.5;">
              💡 {reason}
            </div>
            <div style="margin-top: 8px;">
              <a href="{link}" style="color: #3b82f6; text-decoration: none; font-size: 13px;">
                기사 읽기 →
              </a>
            </div>
          </td>
        </tr>
        """)

    cards_html = "".join(cards)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>아침 브리핑 — {today_label}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, 'Segoe UI', 'Malgun Gothic', sans-serif;">
  <table align="center" cellpadding="0" cellspacing="0" border="0" style="max-width: 640px; width: 100%; margin: 0 auto; background-color: white;">

    <!-- 헤더 -->
    <tr>
      <td style="padding: 32px 28px 20px 28px; border-bottom: 2px solid #111827;">
        <div style="color: #6b7280; font-size: 13px; margin-bottom: 4px;">{today_label}</div>
        <div style="color: #111827; font-size: 26px; font-weight: 800;">☀ 아침 브리핑</div>
        <div style="color: #6b7280; font-size: 14px; margin-top: 8px;">
          오늘 너의 관심사에 매칭된 기사 <b style="color: #111827;">{len(articles)}개</b>
        </div>
      </td>
    </tr>

    <!-- 기사 리스트 -->
    <tr>
      <td style="padding: 8px 28px 24px 28px;">
        <table cellpadding="0" cellspacing="0" border="0" width="100%">
          {cards_html}
        </table>
      </td>
    </tr>

    <!-- 푸터 -->
    <tr>
      <td style="padding: 20px 28px 32px 28px; background-color: #f9fafb; border-top: 1px solid #e5e7eb;">
        <div style="color: #9ca3af; font-size: 12px; line-height: 1.6;">
          이 메일은 <code style="background:#e5e7eb; padding:1px 6px; border-radius:4px;">daily-news-agent</code> 가
          자동 발송했습니다.<br>
          관심사·임계값 조정은 <code style="background:#e5e7eb; padding:1px 6px; border-radius:4px;">config.json</code> 편집.
        </div>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_plain_text(articles: list[dict], today_label: str) -> str:
    """HTML 미지원 클라이언트용 평문 폴백"""
    lines = [f"☀ 아침 브리핑 — {today_label}", f"매칭 기사 {len(articles)}개", "=" * 50, ""]
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. [{a.get('score', 0)}점] {a.get('title', '')}")
        lines.append(f"   💡 {a.get('reason', '')}")
        lines.append(f"   📰 {a.get('source', '')}")
        lines.append(f"   🔗 {a.get('link', '')}")
        lines.append("")
    return "\n".join(lines)


def send_via_gmail(to_addr: str, app_pw: str, subject: str, html: str, plain: str) -> None:
    """Gmail SMTP (SSL 465 포트) 로 발송"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = to_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    print(f"[Gmail] {to_addr} → {to_addr} 발송 중...")
    # local_hostname 명시 — 한글 컴퓨터 이름이 EHLO에 들어가 ASCII 인코딩 에러 나는 것 방지
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, local_hostname="localhost") as smtp:
        smtp.login(to_addr, app_pw)
        smtp.send_message(msg)
    print("[Gmail] 발송 완료 ✅")


def main():
    addr, pw = load_env()

    # 1) 필터링된 기사 로드
    filtered_path = find_latest_filtered_json()
    with open(filtered_path, encoding="utf-8") as f:
        payload = json.load(f)
    articles = payload["articles"]

    if not articles:
        print("[알림] 오늘은 임계값 통과 기사가 없어 메일을 발송하지 않습니다.")
        return

    print(f"[입력] {filtered_path.name}  |  기사 {len(articles)}개")

    # 2) 본문 생성
    today_label = datetime.now().strftime("%Y년 %m월 %d일 (%a)")
    subject = f"☀ {datetime.now().strftime('%m월 %d일')} 아침 브리핑 ({len(articles)}개)"
    html = build_html(articles, today_label)
    plain = build_plain_text(articles, today_label)

    # 3) 발송
    send_via_gmail(addr, pw, subject, html, plain)

    print(f"\n[완료] 챕터 4 끝. 받은편지함 확인하세요 ({addr})")
    print("        다음 챕터(5)에서 Windows 작업 스케줄러로 매일 자동 실행을 설정합니다.")


if __name__ == "__main__":
    main()
