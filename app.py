# -*- coding: utf-8 -*-
import streamlit as st
import time
import math
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 페이지 설정 (넓은 화면 사용)
st.set_page_config(page_title="웹 점수판 실시간 추적기", page_icon="📊", layout="wide")

# 커스텀 CSS로 전반적인 디자인을 평범하고 깔끔한 웹사이트처럼 다듬기
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; height: 40px; }
    .result-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-left: 5px solid #4f46e5;
        padding: 15px 20px;
        margin-bottom: 10px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        font-size: 18px;
        font-weight: 600;
        color: #1f2937;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .diff-badge {
        background-color: #eef2ff;
        color: #4f46e5;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 15px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

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

# 메인 UI 제목
st.title("📊 웹 점수판 실시간 추적 대시보드")
st.markdown("---")

# 상단 깔끔한 설정 영역 (접고 펼치기 가능)
with st.expander("⚙️ 설정 및 필터 옵션 (클릭해서 열기/닫기)", expanded=True):
    col_1, col_2, col_3 = st.columns(3)
    
    with col_1:
        url = st.text_input("점수판 링크 URL", value="https://scoredev.flabs.kr/5snb08fSl5-WwQ")
        calc_mode_str = st.radio("계산 기준 컬럼", ["💧 기여도 (6번째 열)", "⭐ 점수 (5번째 열)"])
        calc_mode = "contrib" if "기여도" in calc_mode_str else "score"
        
    with col_2:
        diff_limit = st.number_input("점수 차이 기준 (점 이하)", value=50, step=5)
        max_display = st.number_input("최대 표시 개수 (0은 제한 없음)", value=0, step=1)
        interval = st.number_input("자동 갱신 주기 (초)", value=5, min_value=1, step=1)
        
    with col_3:
        st.write("### 예외 처리 및 표시 설정")
        exclude_ceo = st.checkbox("👑 '대표 / 사장' 항목 제외", value=True)
        show_scores = st.checkbox("🏷️ 멤버 이름 옆 점수 표시", value=True)

    st.markdown("")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        start_btn = st.button("▶ 추적 시작", type="primary")
    with c2:
        stop_btn = st.button("⏹ 추적 중지")

if start_btn:
    st.session_state.is_running = True
    if st.session_state.driver is None:
        try:
            st.session_state.driver = get_driver()
            st.session_state.driver.get(url)
        except Exception as e:
            st.error(f"브라우저 실행 오류: {e}")
            st.session_state.is_running = False

if stop_btn:
    st.session_state.is_running = False
    if st.session_state.driver:
        try:
            st.session_state.driver.quit()
        except:
            pass
        st.session_state.driver = None

st.markdown("### 📌 실시간 모니터링 결과")
status_area = st.empty()
result_area = st.empty()

@st.fragment(run_every=interval)
def live_tracker():
    if st.session_state.is_running and st.session_state.driver:
        try:
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

                status_area.success(f"🟢 감시 중 (총 수집: {total_count}명 | 기준 {diff_limit}점 이하: {matched_count}건 감지됨 | 마지막 갱신: {now_str})")

                output_items = diff_results[:max_display] if max_display > 0 else diff_results

                cards_html = ""
                if output_items:
                    for item in output_items:
                        if show_scores:
                            p1_str = f"{item['p1']['name']} <span style='color: #6b7280; font-size: 15px;'>({item['p1']['score']:,.1f})</span>"
                            p2_str = f"{item['p2']['name']} <span style='color: #6b7280; font-size: 15px;'>({item['p2']['score']:,.1f})</span>"
                        else:
                            p1_str = f"{item['p1']['name']}"
                            p2_str = f"{item['p2']['name']}"
                            
                        cards_html += f"""
                        <div class="result-card">
                            <div>👤 {p1_str} &nbsp; ➔ &nbsp; 👤 {p2_str}</div>
                            <div class="diff-badge">⚡ {item['diff']}점 차이</div>
                        </div>
                        """
                else:
                    cards_html = """
                    <div style="padding: 20px; background-color: #ffffff; border-radius: 8px; text-align: center; color: #6b7280; border: 1px solid #e0e0e0;">
                        현재 설정된 조건에 맞는 점수 차이 구간이 없습니다.
                    </div>
                    """

                result_area.markdown(cards_html, unsafe_allow_html=True)
        except Exception as e:
            status_area.warning(f"⚠️ 데이터 갱신 중... ({e})")
    else:
        status_area.info("🔵 대기 중입니다. 상단 설정 메뉴에서 **[▶ 추적 시작]** 버튼을 눌러주세요.")

live_tracker()
