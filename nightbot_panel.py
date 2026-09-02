import html
import json
import re
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st


COMMANDS_FILE = Path(__file__).with_name("commands.json")
GITHUB_REPO = "wowhiname06-design/scoreboard1"


def _secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _normalise_command(value):
    value = value.strip().split()[0] if value.strip() else ""
    if value and not value.startswith("!"):
        value = "!" + value
    return value.lower()


def _load_commands():
    if "nightbot_commands" not in st.session_state:
        try:
            st.session_state.nightbot_commands = json.loads(
                COMMANDS_FILE.read_text(encoding="utf-8")
            )
        except Exception:
            st.session_state.nightbot_commands = {}
    return st.session_state.nightbot_commands


def _save_to_github(commands):
    token = _secret("GITHUB_TOKEN")
    if not token:
        return False, "GITHUB_TOKEN이 없어 현재 실행 중에만 저장됩니다."

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    api = f"https://api.github.com/repos/{GITHUB_REPO}/contents/commands.json"
    current = requests.get(api, headers=headers, timeout=10)
    sha = current.json().get("sha") if current.ok else None
    import base64

    payload = {
        "message": "사이트 명령어 내용 저장",
        "content": base64.b64encode(
            json.dumps(commands, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("ascii"),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    result = requests.put(api, headers=headers, json=payload, timeout=15)
    if not result.ok:
        return False, f"저장 실패: {result.status_code}"
    return True, "저장되었습니다."


def _video_id(value):
    value = value.strip()
    patterns = [r"youtu\.be/([\w-]{11})", r"[?&]v=([\w-]{11})", r"/live/([\w-]{11})"]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    return value if re.fullmatch(r"[\w-]{11}", value) else ""


def _get_live_chat_id(api_key, video_id):
    response = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "liveStreamingDetails", "id": video_id, "key": api_key},
        timeout=10,
    )
    response.raise_for_status()
    items = response.json().get("items", [])
    if not items:
        raise ValueError("유튜브 영상을 찾을 수 없습니다.")
    chat_id = items[0].get("liveStreamingDetails", {}).get("activeLiveChatId")
    if not chat_id:
        raise ValueError("현재 진행 중인 라이브 채팅이 없습니다.")
    return chat_id


def _poll_chat(api_key, live_chat_id):
    params = {
        "part": "snippet,authorDetails",
        "liveChatId": live_chat_id,
        "key": api_key,
        "maxResults": 200,
    }
    if st.session_state.get("yt_page_token"):
        params["pageToken"] = st.session_state.yt_page_token
    response = requests.get(
        "https://www.googleapis.com/youtube/v3/liveChat/messages",
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    st.session_state.yt_page_token = data.get("nextPageToken")
    return data.get("items", [])


def _command_editor():
    commands = _load_commands()
    with st.expander("📝 명령어와 표시 내용 관리", expanded=False):
        admin_key = _secret("ADMIN_KEY")
        entered_key = st.text_input("관리자 키", type="password", key="nightbot_admin_key")
        allowed = bool(admin_key and entered_key == admin_key)
        if not admin_key:
            st.warning("사이트 비밀 설정에 ADMIN_KEY를 먼저 등록해주세요.")
        elif entered_key and not allowed:
            st.error("관리자 키가 맞지 않습니다.")

        with st.form("command_form", clear_on_submit=True):
            command = st.text_input("명령어", placeholder="!공지")
            content = st.text_area("사이트에 표시할 내용", placeholder="지금부터 공지를 시작합니다.")
            submitted = st.form_submit_button("명령어 저장", type="primary", disabled=not allowed)
        if submitted:
            command = _normalise_command(command)
            if not command or not content.strip():
                st.error("명령어와 내용을 모두 입력해주세요.")
            else:
                commands[command] = content.strip()
                ok, message = _save_to_github(commands)
                (st.success if ok else st.warning)(message)

        if commands:
            for command, content in list(commands.items()):
                left, middle, right = st.columns([1, 5, 1])
                left.code(command)
                middle.write(content)
                if right.button("삭제", key=f"delete_{command}", disabled=not allowed):
                    del commands[command]
                    ok, message = _save_to_github(commands)
                    (st.success if ok else st.warning)(message)
                    st.rerun()
        else:
            st.info("저장된 명령어가 없습니다.")


def render_nightbot_panel():
    st.markdown("---")
    st.header("📺 유튜브 Nightbot 명령어 실시간 표시")
    st.caption("유튜브 채팅에 등록된 명령어가 입력되면 아래 화면에 저장된 내용이 표시됩니다.")
    _command_editor()

    default_api_key = _secret("YOUTUBE_API_KEY")
    col1, col2 = st.columns([3, 1])
    with col1:
        live_url = st.text_input("유튜브 라이브 주소", placeholder="https://www.youtube.com/watch?v=...")
        api_key = default_api_key or st.text_input("YouTube API 키", type="password")
    with col2:
        st.write("")
        st.write("")
        start = st.button("▶ 채팅 감시 시작", type="primary", use_container_width=True)
        stop = st.button("⏹ 채팅 감시 중지", use_container_width=True)

    if start:
        video_id = _video_id(live_url)
        if not api_key:
            st.error("YouTube API 키를 입력해주세요.")
        elif not video_id:
            st.error("올바른 유튜브 라이브 주소를 입력해주세요.")
        else:
            try:
                st.session_state.yt_live_chat_id = _get_live_chat_id(api_key, video_id)
                st.session_state.yt_api_key = api_key
                st.session_state.yt_page_token = None
                st.session_state.yt_skip_first_batch = True
                st.session_state.yt_watching = True
                st.success("라이브 채팅 감시를 시작했습니다.")
            except Exception as exc:
                st.error(str(exc))
    if stop:
        st.session_state.yt_watching = False

    status = st.empty()
    output = st.empty()

    @st.fragment(run_every=5)
    def watch_chat():
        if not st.session_state.get("yt_watching"):
            status.info("라이브 주소를 넣고 채팅 감시 시작을 눌러주세요.")
            return
        try:
            messages = _poll_chat(
                st.session_state.yt_api_key,
                st.session_state.yt_live_chat_id,
            )
            commands = _load_commands()
            if st.session_state.pop("yt_skip_first_batch", False):
                messages = []
            for item in messages:
                text = item.get("snippet", {}).get("displayMessage", "").strip()
                command = _normalise_command(text)
                if command in commands:
                    st.session_state.yt_last_match = {
                        "command": command,
                        "content": commands[command],
                        "author": item.get("authorDetails", {}).get("displayName", "시청자"),
                        "time": datetime.now().strftime("%H:%M:%S"),
                    }
            status.success(f"🟢 채팅 감시 중 · 마지막 확인 {datetime.now().strftime('%H:%M:%S')}")
            match = st.session_state.get("yt_last_match")
            if match:
                safe_command = html.escape(match["command"])
                safe_author = html.escape(match["author"])
                safe_time = html.escape(match["time"])
                safe_content = html.escape(match["content"]).replace("\n", "<br>")
                output.markdown(
                    f"""<div style="padding:28px;border-radius:16px;background:#111827;color:white;"
                    ><div style="color:#a5b4fc;font-weight:700">{safe_command} · {safe_author} · {safe_time}</div>
                    <div style="font-size:30px;font-weight:800;margin-top:10px">{safe_content}</div></div>""",
                    unsafe_allow_html=True,
                )
        except Exception as exc:
            status.warning(f"채팅 확인 중 오류: {exc}")

    watch_chat()
