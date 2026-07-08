#!/usr/bin/env python3
"""
매월 1일 자동 실행: Claude AI + 웹 검색으로 신제품 리서치 → index.html 업데이트
필요 환경변수: ANTHROPIC_API_KEY (GitHub Secrets)
"""
import os, re, json, sys, textwrap
from datetime import date
import anthropic

# ── 날짜 ──────────────────────────────────────────────────────────
today     = date.today()
YEAR      = today.year
MONTH     = today.month
LABEL_KR  = f"{YEAR}년 {MONTH:02d}월"

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")

print(f"[시작] {LABEL_KR} 신제품 리포트 자동 업데이트")

# ── Anthropic 클라이언트 ──────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ── 브랜드 목록 ───────────────────────────────────────────────────
REGIONS = {
    "na": {
        "name": "북미 North America",
        "color": "#3B82F6",
        "brands": ["Steelcase", "Herman Miller", "Haworth", "Knoll", "Teknion",
                   "Allsteel", "Humanscale", "HON", "Kimball", "Global Furniture Group",
                   "Watson", "Davis Furniture", "OFS", "KI",
                   "Nienkämper", "Narbutas"],
        "sec_id": "na-sec",
    },
    "eu": {
        "name": "유럽 Europe",
        "color": "#10B981",
        "brands": ["Vitra", "Kinnarps", "Wilkhahn", "Bene", "Sedus",
                   "Senator Group", "Hay", "Orangebox", "Flokk", "Arper",
                   "Nowy Styl", "Framery", "Interstuhl", "Renz", "Walter Knoll",
                   "Abstracta", "Lapalma", "Muuto", "Kettal", "Gumpo", "Pedrali"],
        "sec_id": "eu-sec",
    },
    "jp": {
        "name": "일본 Japan",
        "color": "#EF4444",
        "brands": ["Okamura", "Kokuyo", "Itoki", "Uchida Yoko", "Plus Corporation",
                   "Aichi", "Karimoku", "Tendo Mokko", "Maruni", "Askul"],
        "sec_id": "jp-sec",
    },
    "kr": {
        "name": "국내 Korea",
        "color": "#C17F3E",
        "brands": ["퍼시스(Fursys)", "현대리바트", "코아스", "한샘",
                   "시디즈", "데스커", "파트라", "베스툴", "에넥스", "아모스아인스"],
        "sec_id": "kr-sec",
    },
}

BADGE_CSS = {
    "신규":   "bdg-n",
    "리뉴얼": "bdg-b",
    "수상":   "bdg-a",
    "첫진출": "bdg-w",
    "":       "",
}

# ── Claude AI 리서치 ──────────────────────────────────────────────
SYSTEM_PROMPT = (
    "당신은 글로벌 사무가구 신제품 리서처입니다. "
    "반드시 웹 검색으로 실제 확인된 신제품만 보고하세요. "
    "확인되지 않은 제품은 포함하지 마세요. "
    "JSON 배열 형식으로만 답하세요."
)

def extract_json(text: str) -> list:
    """텍스트에서 JSON 배열 추출. 코드 블록 / 앞뒤 텍스트 무시."""
    text = re.sub(r'```(?:json)?\s*', '', text)
    m = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    # 더 넓게 시도
    m2 = re.search(r'\[[\s\S]*?\]', text)
    if m2:
        try:
            return json.loads(m2.group())
        except json.JSONDecodeError:
            pass
    return []

def research_products(region_key: str, region: dict) -> list:
    brands_str = ", ".join(region["brands"])
    user_msg = textwrap.dedent(f"""
        오늘 날짜: {today.isoformat()}
        조사 대상: {region["name"]} 사무가구 브랜드
        브랜드 목록: {brands_str}

        위 브랜드들이 {LABEL_KR} 전후(최근 2개월 이내)에 발표한 신제품이나
        주목할 만한 업데이트를 웹에서 검색해서 찾아줘.
        각 브랜드당 최대 1개 제품을 선정해 아래 JSON 배열로만 답해줘:
        [
          {{
            "brand": "브랜드명",
            "product": "제품명(영문 원어 그대로)",
            "country": "국가명(한국어)",
            "date": "{YEAR}.{MONTH:02d}",
            "desc": "한국어 설명 80자 이내 — 핵심 특징·혁신점·타겟 명확히",
            "url": "실제 확인된 제품/보도자료 URL",
            "tag": "3~6자 카테고리 태그(예: 인체공학, 지속가능성, 스마트오피스)",
            "badge": "신규 또는 리뉴얼 또는 수상 또는 첫진출 또는 빈문자열"
          }}
        ]
    """).strip()

    print(f"  [{region_key.upper()}] 웹 리서치 중…")
    messages = [{"role": "user", "content": user_msg}]

    try:
        for _turn in range(6):  # 최대 6턴 (tool use 루프)
            resp = client.messages.create(
                model="claude-opus-4-8",
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=messages,
            )

            # 텍스트 블록에서 JSON 추출 시도
            for block in resp.content:
                if getattr(block, "type", None) == "text":
                    data = extract_json(block.text)
                    if data:
                        print(f"  [{region_key.upper()}] {len(data)}개 제품 수집")
                        return data

            # tool_use 인 경우 결과를 messages 에 추가하고 계속
            if resp.stop_reason == "tool_use":
                tool_results = []
                for block in resp.content:
                    if getattr(block, "type", None) == "tool_use":
                        # web_search 는 Anthropic 서버 실행 — 빈 결과로 계속
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "검색 완료",
                        })
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": tool_results})
                continue

            break  # end_turn 또는 기타

    except Exception as e:
        print(f"  [{region_key.upper()}] 오류: {e}")
    return []

# ── HTML 카드 생성 ────────────────────────────────────────────────
AV_COLORS = {
    "na": "#3B82F6", "eu": "#10B981", "jp": "#EF4444", "kr": "#C17F3E"
}

def make_card(item: dict, region_key: str) -> str:
    brand   = item.get("brand", "")
    product = item.get("product", "")
    country = item.get("country", "")
    dt      = item.get("date", f"{YEAR}.{MONTH:02d}")
    desc    = item.get("desc", "")
    url     = item.get("url", "#")
    tag     = item.get("tag", "")
    badge   = item.get("badge", "").strip()

    # 이니셜 아바타 (한글은 앞 2글자, 영문은 대문자 이니셜)
    av_text = "".join(w[0].upper() for w in brand.split()[:2]) if brand else "??"
    if any('가' <= c <= '힣' for c in brand):
        av_text = brand[:3]
    av_color = AV_COLORS.get(region_key, "#78716C")

    badge_html = ""
    if badge and badge in BADGE_CSS:
        badge_html = f'<div class="bc-badges"><span class="bdg {BADGE_CSS[badge]}">{badge}</span></div>'

    return f"""
        <div class="bc">
          <div class="bc-top">
            <div class="bc-av" style="background:{av_color}">{av_text}</div>
            <div class="bc-head">
              <div class="bc-brand">{brand}</div>
              <div class="bc-country">{country} · {dt}</div>
              {badge_html}
            </div>
          </div>
          <div class="bc-body">
            <div class="bc-prod">{product}</div>
            <div class="bc-desc">{desc}</div>
          </div>
          <div class="bc-foot">
            <span class="bc-tag">{tag}</span>
            <a class="bc-lnk" href="{url}" target="_blank">자세히 보기 ↗</a>
          </div>
        </div>"""

# ── index.html 섹션 교체 ──────────────────────────────────────────
def replace_section(html: str, sec_id: str, new_cards_html: str, region: dict) -> str:
    """<!-- ═══ ... ═══ --> ~ <!-- /sec_id --> 블록 전체를 교체"""
    n_cards = len([c for c in new_cards_html.split('class="bc"') if c]) - 1
    count_label = f"신제품 {n_cards}개 · {n_cards}개 브랜드" if n_cards > 0 else f"신제품 · {LABEL_KR} 수집"

    new_sec = (
        f'\n    <!-- ═══════════════════ {region["name"]} ═══════════════════ -->'
        f'\n    <div id="{sec_id}" class="reg-sec">'
        f'\n      <div class="reg-hd">'
        f'\n        <div class="reg-hd-bar" style="background:{region["color"]}"></div>'
        f'\n        <span class="reg-hd-name">{region["name"]}</span>'
        f'\n        <span class="reg-hd-count">{count_label}</span>'
        f'\n        <div class="reg-hd-line"></div>'
        f'\n      </div>'
        f'\n      <div class="reg-grid">'
        f'\n{new_cards_html}'
        f'\n      </div>'
        f'\n    </div>'
        f'\n    <!-- /{sec_id} -->'
    )

    # <!-- /sec_id --> 종료 마커 기반 교체 (가장 신뢰성 높음)
    pattern = rf'<!-- ═+[^>]*═+ -->\s*<div id="{sec_id}"[\s\S]*?<!-- /{sec_id} -->'
    if re.search(pattern, html):
        return re.sub(pattern, new_sec.strip(), html, count=1)

    # fallback: 종료 마커 없이 다음 <!-- 코멘트 직전까지 교체
    pattern2 = rf'(<div id="{sec_id}" class="reg-sec">[\s\S]*?</div>\s*</div>)\s*\n(\s*<!--)'
    m = re.search(pattern2, html)
    if m:
        return html[:m.start()] + new_sec + '\n' + m.group(2) + html[m.end():]

    print(f"  [{sec_id}] ⚠ 섹션을 찾지 못해 업데이트 건너뜀")
    return html

# ── 헤더 날짜 업데이트 ────────────────────────────────────────────
def update_header(html: str) -> str:
    html = re.sub(
        r'(\d{4})년 (\d{1,2})월 수집',
        f"{YEAR}년 {MONTH:02d}월 수집",
        html
    )
    html = re.sub(
        r'background:#FEF3C7[^>]*>\d{4}년 \d{1,2}월<',
        f'background:#FEF3C7;color:#D97706;padding:3px 11px;border-radius:20px;'
        f'white-space:nowrap;flex-shrink:0">{LABEL_KR}<',
        html
    )
    # topbar subtitle 날짜
    html = re.sub(
        r'\d{4}년 \d{1,2}월 수집',
        f"{LABEL_KR} 수집",
        html
    )
    return html

# ── 메인 ─────────────────────────────────────────────────────────
def main():
    with open(INDEX, encoding="utf-8") as f:
        html = f.read()

    all_products = {}
    for rk, rinfo in REGIONS.items():
        products = research_products(rk, rinfo)
        all_products[rk] = products

    # 카드 생성 및 섹션 교체
    for rk, rinfo in REGIONS.items():
        products = all_products.get(rk, [])
        if not products:
            print(f"  [{rk.upper()}] 제품 없음 — 섹션 유지")
            continue
        cards_html = "".join(make_card(p, rk) for p in products)
        html = replace_section(html, rinfo["sec_id"], cards_html, rinfo)
        print(f"  [{rk.upper()}] 섹션 업데이트 완료")

    # 헤더 날짜 업데이트
    html = update_header(html)

    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[완료] index.html 업데이트 완료 — {LABEL_KR}")

if __name__ == "__main__":
    main()
