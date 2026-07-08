#!/usr/bin/env python3
"""
매월 1일 자동 실행:
  1. 전월 index.html → reports/YYYY-MM.html 아카이브 저장
  2. archive.html 월 카드 업데이트 (mc-future/pending → mc-done)
  3. archive.html 사이드바에 월 링크 추가
"""
import re, sys, os
from datetime import date, timedelta

# ── 날짜 계산 ─────────────────────────────────────────────
def last_month(today=None):
    if today is None:
        today = date.today()
    first = today.replace(day=1)
    last  = first - timedelta(days=1)
    return last.year, last.month

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC    = os.path.join(ROOT, "index.html")
ARCH   = os.path.join(ROOT, "archive.html")
REPDIR = os.path.join(ROOT, "reports")

# CLI: python monthly_archive.py 2026 6  (수동 지정)
if len(sys.argv) == 3:
    year, month = int(sys.argv[1]), int(sys.argv[2])
else:
    year, month = last_month()

yearmonth  = f"{year}-{month:02d}"
label_kr   = f"{year}년 {month:02d}월"
month_ko   = f"{month}월"
dest       = os.path.join(REPDIR, f"{yearmonth}.html")

# 이미 존재하면 건너뜀
if os.path.exists(dest):
    print(f"[SKIP] {dest} 이미 존재 — 아카이브 건너뜀")
else:
    os.makedirs(REPDIR, exist_ok=True)

    with open(SRC, encoding="utf-8") as f:
        html = f.read()

    # ── 아카이브 배너 CSS 삽입 ────────────────────────────
    BANNER_CSS = """
/* Archive banner */
.arch-bar{background:#FEF3C7;border-bottom:2px solid #FCD34D;padding:8px 22px;
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;font-size:13px}
.arch-bar b{color:#D97706;font-weight:700}
.arch-bar a{color:#D97706;font-weight:700;text-decoration:none}
.arch-bar a:hover{text-decoration:underline}
"""
    html = html.replace("</style>", BANNER_CSS + "</style>", 1)

    # ── 타이틀 변경 ───────────────────────────────────────
    html = re.sub(
        r"<title>.*?</title>",
        f"<title>퍼시스 · {label_kr} 신제품 리포트 (아카이브)</title>",
        html, count=1
    )

    # ── 아카이브 배너 HTML 삽입 (topbar 아래, cnt 위) ──────
    BANNER_HTML = (
        f'\n  <div class="arch-bar">'
        f'<b>📦 {label_kr} 아카이브 — 읽기 전용</b>'
        f'<a href="../archive.html">← 월별 아카이브</a>'
        f'</div>'
    )
    html = html.replace(
        '<div class="cnt" id="view-dash">',
        BANNER_HTML + '\n  <div class="cnt" id="view-dash">',
        1
    )

    # ── 상대 경로 수정 ────────────────────────────────────
    html = html.replace('href="archive.html"', 'href="../archive.html"')

    # ── 파일 저장 ─────────────────────────────────────────
    with open(dest, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] {dest} 생성 완료")

# ── archive.html 업데이트 ─────────────────────────────────
with open(ARCH, encoding="utf-8") as f:
    arch = f.read()

# 이미 mc-done으로 되어 있으면 건너뜀
done_marker = f'data-m="{yearmonth}"'
if f'class="mc mc-done" {done_marker}' in arch or f'{done_marker}" class="mc mc-done"' in arch:
    print(f"[SKIP] archive.html 에 {label_kr} 이미 완료 상태")
    sys.exit(0)

# ── 해당 월 카드를 mc-done 으로 교체 ──────────────────────
# 패턴: <div class="mc mc-..." data-m="YYYY-MM"> ... </div>
card_pattern = re.compile(
    rf'<(?:div|a)[^>]*class="mc[^"]*"[^>]*data-m="{re.escape(yearmonth)}"[^>]*>[\s\S]*?</(?:div|a)>',
    re.MULTILINE
)

NEW_CARD = (
    f'<a class="mc mc-done" data-m="{yearmonth}" '
    f'href="reports/{yearmonth}.html" style="text-decoration:none;">\n'
    f'    <div class="mc-month">{month_ko}</div>\n'
    f'    <div class="mc-label">{date(year, month, 1).strftime("%B")} {year}</div>\n'
    f'    <div class="mc-meta">\n'
    f'      <span>🌍 4개 지역</span>\n'
    f'      <span>📦 신제품 수집</span>\n'
    f'      <span>🏢 글로벌 브랜드</span>\n'
    f'    </div>\n'
    f'    <div class="mc-status mc-status-done">리포트 보기 →</div>\n'
    f'  </a>'
)

if card_pattern.search(arch):
    arch = card_pattern.sub(NEW_CARD, arch, count=1)
    print(f"[OK] archive.html 월 카드 업데이트: {label_kr}")
else:
    print(f"[WARN] archive.html 에서 {yearmonth} 카드를 찾지 못했습니다")

# ── 사이드바 월 링크 추가 ────────────────────────────────
# 기존 가장 최근 완료 링크 찾아서 앞에 삽입
NEW_SIDEBAR_LINK = (
    f'\n    <a class="sbl sbl-sub" href="reports/{yearmonth}.html" '
    f'style="text-decoration:none;color:var(--a);font-weight:600;">'
    f'<span class="sbl-ic">●</span>{label_kr}'
    f'<span class="sbl-cnt" style="background:var(--ab);color:var(--a);">완료</span></a>'
)

# 이미 사이드바에 있으면 건너뜀
if f'"reports/{yearmonth}.html"' not in arch:
    # '신제품 아카이브' 버튼 바로 다음에 삽입
    arch = arch.replace(
        '<button class="sbl on"><span class="sbl-ic">◈</span>신제품 아카이브</button>',
        '<button class="sbl on"><span class="sbl-ic">◈</span>신제품 아카이브</button>'
        + NEW_SIDEBAR_LINK,
        1
    )
    print(f"[OK] archive.html 사이드바 링크 추가: {label_kr}")
else:
    print(f"[SKIP] 사이드바에 {label_kr} 링크 이미 존재")

with open(ARCH, "w", encoding="utf-8") as f:
    f.write(arch)
print(f"[OK] archive.html 저장 완료")
