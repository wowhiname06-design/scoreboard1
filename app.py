# -*- coding: utf-8 -*-
import streamlit as st
import time
import math
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

st.set_page_config(page_title="점수판 실시간 추적기", page_icon="📊", layout="wide")

if 'last_valid_parsed_list' not in st.session_state:
    st.session_state.last_valid_parsed_list = []
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'driver' not in st.session_state:
    st.session_state.driver = None

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1200,2000")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

def parse_all_with_scroll(driver, calc_mode, exclude_ceo):
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.3)
    except:
        pass

    try:
        raw_rows_data = driver.execute_script("""
            let rows = document.querySelectorAll('tr, div[class*="row"], div[class*="item"], div[class*="list"]');
            let results = [];
            rows.forEach(r => {
                let text = r.innerText.trim();
                if (text) { results.push(text); }
            });
            return results;
        """)
    except Exception:
        raw_rows_data = []

    people = []
    job_titles = ["대표", "사장", "부장", "차장", "과장", "팀장", "비서", "대리", "주임", "사원", "청소부", "이사", "부팀장", "썹청소부", "썯청소부", "인턴", "회장", "매니저", "사원1", "사원2", "청소부1", "청소부2", "청소부3"]

    for line in raw_rows_data:
        try:
            full_line = line.replace('\n', ' ').strip()
            if not full_line: continue
            if any(kw in full_line for kw in ["스트리머", "기여도", "웹후원", "계좌후원", "점수", "순위", "직급", "NOTICE", "공지"]): continue
            if "조퇴" in full_line: continue
            if exclude_ceo and ("대표" in full_line or "사장" in full_line or "류도현" in full_line): continue

            tokens = [t for t in full_line.split() if t]
            if len(tokens) < 2: continue

            name = ""
            for tk_val in tokens:
                clean_tk = tk_val.strip()
                if clean_tk.isdigit(): continue
                if clean_tk in job_titles or any(jt in clean_tk for jt in job_titles): continue
                if re.search(r'[\d.,()]', clean_tk): continue
                if len(clean_tk) > 12 or len(clean_tk) < 1: continue
                name = clean_tk
                break

            nums = []
            for tk_val in tokens:
                clean_t = re.sub(r'\(.*?\)', '', tk_val).replace(',', '').strip()
                try:
                    val = float(clean_t)
                    nums.append(val)
                except ValueError:
                    pass

            if not nums or not name: continue
            target_value = nums[-1] if calc_mode == "contrib" else (nums[-2] if len(nums) >= 2 else nums[0])

            if name and name not in ["직급", "스트리머", "웹후원", "계좌후원", "점수", "기여도", "대표", "사장"]:
                people.append({'name': name, 'score': target_value})
        except Exception:
            continue

    unique_people = []
    seen = set()
    for p in people:
      if p['name'] not in seen:
          seen.add(p['name'])
          unique_people.append(p)

    return unique_people

st.title("📊 웹 점수판 실시간 추적기")

with st.sidebar:
    st.header("⚙️ 설정 메뉴")
    url = st.text_input("점수판 링크 URL", value="https://scoredev.flabs.kr/5snb08fSl5-WwQ")
    calc_mode_str = st.radio("계산 기준 컬럼", ["💧 기여도 (6번째 열)", "⭐ 점수 (5번째 열)"])
    calc_mode = "contrib" if "기여도" in calc_mode_str else "score"
    diff_limit = st.number_input("점수 차이 기준 (점 이하)", value=50, step=5)
    max_display = st.number_input("최대 표시 개수 (0은 제한 없음)", value=0, step=1)
    interval = st.number_input("자동 갱신 주기 (초)", value=5, min_value=1, step=1)
    exclude_ceo = st.checkbox("👑 '대표 / 사장' 항목 제외", value=True)
    show_scores = st.checkbox("🏷️ 멤버 이름 옆 점수 표시", value=True)
    font_size = st.slider("🔤 글씨 크기 조절", min_value=12, max_value=36, value=20)
    is_bold = st.checkbox("🔤 글씨 굵게 (Bold)", value=True)

    col1, col2 = st.columns(2)
    with col1: start_btn = st.button("▶ 추적 시작", use_container_width=True)
    with col2: stop_btn = st.button("⏹ 추적 중지", use_container_width=True)

if start_btn:
    st.session_state.is_running = True
    if st.session_state.driver is None:
        st.session_state.driver = get_driver()
        st.session_state.driver.get(url)

if stop_btn:
    st.session_state.is_running = False
    if st.session_state.driver:
        st.session_state.driver.quit()
        st.session_state.driver = None

status_area = st.empty()
result_area = st.empty()

if st.session_state.is_running and st.session_state.driver:
    parsed_list = parse_all_with_scroll(st.session_state.driver, calc_mode, exclude_ceo)

    if not parsed_list or len(parsed_list) < 12:
        if st.session_state.last_valid_parsed_list:
            parsed_list = st.session_state.last_valid_parsed_list
    else:
        st.session_state.last_valid_parsed_list = parsed_list

    if parsed_list:
        parsed_list.sort(key=lambda x: x['score'], reverse=True)
        diff_results = []
        for i in range(len(parsed_list) - 1):
            p1 = parsed_list[i]
            p2 = parsed_list[i + 1]
            diff_exact = p1['score'] - p2['score']
            if diff_exact.is_integer():
                diff = int(diff_exact) + 1
            else:
                diff = math.ceil(diff_exact)

            if diff <= diff_limit:
                diff_results.append({'p1': p1, 'p2': p2, 'diff': diff})

        matched_count = len(diff_results)
        total_count = len(parsed_list)
        now_str = datetime.now().strftime("%H:%M:%S")

        output_items = diff_results[:max_display] if max_display > 0 else diff_results
        displayed_count = len(output_items)

        status_area.success(f"🟢 감시 중 (총 {total_count}명 수집 | {diff_limit}점 이하 {matched_count}건 중 {displayed_count}개 표시 | {now_str})")

        lines = []
        for item in output_items:
            if show_scores:
                p1_str = f"{item['p1']['name']}({item['p1']['score']:,.1f})"
                p2_str = f"{item['p2']['name']}({item['p2']['score']:,.1f})"
            else:
                p1_str = f"{item['p1']['name']}"
                p2_str = f"{item['p2']['name']}"
            lines.append(f"• {p1_str} - {p2_str} ➔ {item['diff']}점 차이")

        if not diff_results:
            lines.append("• 현재 설정된 조건에 맞는 점수 차이 구간이 없습니다.")

        font_weight = "bold" if is_bold else "normal"
        custom_css = f"""
        <div style="font-size: {font_size}px; font-weight: {font_weight}; line-height: 1.6; background-color: #1e1e1e; color: #ffffff; padding: 15px; border-radius: 10px;">
            {"<br>".join(lines)}
        </div>
        """
        result_area.markdown(custom_css, unsafe_allow_html=True)

    time.sleep(interval)
    st.rerun()

else:
    status_area.info("🔵 대기 중... 사이드바 메뉴에서 '▶ 추적 시작' 버튼을 누르세요.")