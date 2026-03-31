import streamlit as st
import google.generativeai as genai
import pandas as pd
from gtts import gTTS
import base64
import os
import re
import random
import json
import time
from datetime import datetime
import streamlit.components.v1 as components

# ==========================================
# 🔑 제미나이 API 키 설정 (보안 금고 연동)
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except Exception:
    st.error("🚨 스트림릿 보안 금고(Secrets)에 API 키가 등록되지 않았습니다! 앱 관리자 설정에서 키를 먼저 등록해주세요.")
    st.stop()
# ==========================================

VOCAB_FILE = 'my_vocab_web.csv'
WRONG_FILE = 'my_vocab_wrong_web.csv'
TEST_HISTORY_FILE = 'my_test_history_web.json'

# ----------------- 💡 자체 제작: 한/영 오타 자동 채점기 (외부 패키지 X) -----------------
CHO = ['r', 'R', 's', 'e', 'E', 'f', 'a', 'q', 'Q', 't', 'T', 'd', 'w', 'W', 'c', 'z', 'x', 'v', 'g']
JUNG = ['k', 'o', 'i', 'O', 'j', 'p', 'u', 'P', 'h', 'hk', 'ho', 'hl', 'y', 'n', 'nj', 'np', 'nl', 'b', 'm', 'ml', 'l']
JONG = ['', 'r', 'R', 'rt', 's', 'sw', 'sg', 'e', 'f', 'fr', 'fa', 'fq', 'ft', 'fx', 'fv', 'fg', 'a', 'q', 'qt', 't', 'T', 'd', 'w', 'c', 'z', 'x', 'v', 'g']
COMPAT_JAMO = {
    'ㄱ':'r', 'ㄲ':'R', 'ㄳ':'rt', 'ㄴ':'s', 'ㄵ':'sw', 'ㄶ':'sg', 'ㄷ':'e', 'ㄸ':'E', 'ㄹ':'f', 'ㄺ':'fr', 'ㄻ':'fa', 'ㄼ':'fq', 'ㄽ':'ft', 'ㄾ':'fx', 'ㄿ':'fv', 'ㅀ':'fg', 'ㅁ':'a', 'ㅂ':'q', 'ㅃ':'Q', 'ㅄ':'qt', 'ㅅ':'t', 'ㅆ':'T', 'ㅇ':'d', 'ㅈ':'w', 'ㅉ':'W', 'ㅊ':'c', 'ㅋ':'z', 'ㅌ':'x', 'ㅍ':'v', 'ㅎ':'g',
    'ㅏ':'k', 'ㅐ':'o', 'ㅑ':'i', 'ㅒ':'O', 'ㅓ':'j', 'ㅔ':'p', 'ㅕ':'u', 'ㅖ':'P', 'ㅗ':'h', 'ㅘ':'hk', 'ㅙ':'ho', 'ㅚ':'hl', 'ㅛ':'y', 'ㅜ':'n', 'ㅝ':'nj', 'ㅞ':'np', 'ㅟ':'nl', 'ㅠ':'b', 'ㅡ':'m', 'ㅢ':'ml', 'ㅣ':'l'
}

def get_qwerty(text):
    if not text: return ""
    res = ""
    for c in text:
        if '가' <= c <= '힣':
            offset = ord(c) - 44032
            res += CHO[offset // 588] + JUNG[(offset % 588) // 28] + JONG[offset % 28]
        elif c in COMPAT_JAMO:
            res += COMPAT_JAMO[c]
        else:
            res += c
    return res.lower().replace(" ", "")

# ----------------- 🛠️ 핵심 함수 정의 -----------------
def get_ai_response(prompt):
    try:
        available_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except Exception as e:
        raise Exception(f"API 키 연결 실패: {e}")

    if not available_models: raise Exception("사용 가능한 AI 모델이 없습니다.")

    priority_models = []
    for keyword in ['lite', '1.5-flash', 'flash', '']:
        for m in available_models:
            if keyword in m.lower() and m not in priority_models:
                priority_models.append(m)

    last_error = None
    for target_model in priority_models:
        try:
            model = genai.GenerativeModel(target_model)
            return model.generate_content(prompt)
        except Exception as e:
            last_error = str(e)
            continue
    raise Exception(f"할당량 초과. 마지막 에러: {last_error}")

def load_data(file_path):
    if os.path.exists(file_path): return pd.read_csv(file_path)
    return pd.DataFrame(columns=['Word', 'Phonetic', 'Meaning', 'Example', 'Date', 'Status', 'Category', 'Level'])

def save_data(df, file_path):
    df.to_csv(file_path, index=False, encoding='utf-8-sig')

def convert_df_to_csv(df):
    return df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

def load_test_history():
    if os.path.exists(TEST_HISTORY_FILE):
        try:
            with open(TEST_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def save_test_history(data):
    with open(TEST_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_and_add_words(response_text, df, category, level):
    lines = response_text.strip().split('\n')
    new_rows = []
    for line in lines:
        parts = line.split(';')
        if len(parts) >= 4:
            eng = re.sub(r'^[\d\.\)]+\s*', '', parts[0].replace('*', '').strip())
            phonetic = parts[1].strip()
            if phonetic:
                phonetic = phonetic.replace('[', '').replace(']', '').strip()
                phonetic = f"[ {phonetic} ]"
            else:
                phonetic = '[   ]'

            new_rows.append({
                'Word': eng, 'Phonetic': phonetic, 'Meaning': parts[2].strip(),
                'Example': parts[3].strip(), 'Date': datetime.now().strftime("%Y-%m-%d"),
                'Status': 'Learning', 'Category': category, 'Level': level
            })
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        df = pd.concat([df, new_df], ignore_index=True).drop_duplicates('Word')
    return df, len(new_rows)

def speak(text, loop=False):
    pure_text = text.split('[')[0].strip()
    try:
        tts = gTTS(text=pure_text, lang='en')
        tts.save("temp.mp3")
        with open("temp.mp3", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            unique_id = random.randint(1, 10000000)
            
            if loop:
                html_code = f"""
                <audio id="audio_{unique_id}" autoplay>
                    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                </audio>
                <script>
                    const audioEl = document.getElementById('audio_{unique_id}');
                    audioEl.onended = function() {{
                        setTimeout(() => {{
                            audioEl.play().catch(e => console.log(e));
                        }}, 2500); 
                    }};
                </script>
                """
            else:
                html_code = f'<audio autoplay><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
                
            components.html(html_code + f'<div style="display:none;">{unique_id}</div>', height=0, width=0)
    except Exception: pass 

def play_sequence_audio(words):
    audio_data_list = []
    for w in words:
        try:
            tts = gTTS(text=w.split('[')[0].strip(), lang='en')
            tts.save("temp_seq.mp3")
            with open("temp_seq.mp3", "rb") as f:
                audio_data_list.append(base64.b64encode(f.read()).decode())
        except: pass

    if not audio_data_list: return
    js_array = json.dumps(audio_data_list)
    html_code = f"""
    <audio id="seqPlayer"></audio>
    <script>
        const audioData = {js_array}; let currentWordIdx = 0; let playCount = 0; const player = document.getElementById("seqPlayer");
        function playNext() {{
            if(currentWordIdx >= audioData.length) return;
            player.src = "data:audio/mp3;base64," + audioData[currentWordIdx];
            player.play().catch(e => console.log(e));
            player.onended = function() {{
                playCount++;
                if(playCount < 3) {{ setTimeout(playNext, 1000); }} 
                else {{ playCount = 0; currentWordIdx++; setTimeout(playNext, 2300); }}
            }};
        }}
        playNext();
    </script>
    <div style="display:none;">{time.time()}</div>
    """
    components.html(html_code, height=0, width=0)

def render_mobile_table(headers, data, font_size="14px"):
    html = f'<div style="overflow-x: auto;"><table style="width: 100%; border-collapse: collapse; font-size: {font_size};">'
    html += "<tr>" + "".join([f"<th style='border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #333; color: white;'>{h}</th>" for h in headers]) + "</tr>"
    for row in data: html += "<tr>" + "".join([f"<td style='border: 1px solid #ddd; padding: 8px;'>{cell}</td>" for cell in row]) + "</tr>"
    html += "</table></div>"
    st.markdown(html, unsafe_allow_html=True)

# ----------------- 🖥️ UI 세팅 및 시스템 제어 -----------------
st.set_page_config(page_title="AI 영단어 마스터", layout="centered")
st.title("🦉 AI 영단어 마스터 Web")

components.html(
    """
    <script>
    const parentDoc = window.parent.document;
    function disableSpellcheck() {
        const elements = parentDoc.querySelectorAll('input[type="text"], textarea');
        elements.forEach(el => {
            el.setAttribute('spellcheck', 'false');
            el.setAttribute('autocomplete', 'off');
        });
    }
    disableSpellcheck();
    setInterval(disableSpellcheck, 1000); 
    </script>
    """, height=0, width=0
)

st.sidebar.title("메뉴")
menu = st.sidebar.selectbox("메뉴 선택", [
    "🤖 AI 단어 생성", "📖 단어 관리", "📝 실전 테스트", "📚 영어 기초 가이드", 
    "📅 학습 기록", "📊 학습 통계", "✨ 단어 일괄 추가", "🔥 오답 노트 재도전", "🏆 테스트 결과 기록"
])

st.sidebar.divider()
st.sidebar.markdown("### 🛠️ 시스템 관리")

if st.session_state.get('show_reset_success'):
    st.toast("✅ 캐시 및 오류가 완벽하게 초기화되었습니다!", icon="🧹")
    st.sidebar.success("✅ 초기화 완료!")
    st.session_state.show_reset_success = False

if st.sidebar.button("🧹 시스템 캐시 및 오류 초기화"):
    st.cache_data.clear()
    st.cache_resource.clear()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.show_reset_success = True
    st.rerun()

df = load_data(VOCAB_FILE)
wrong_df = load_data(WRONG_FILE)

# ⭐️ 수정됨: AI 프롬프트 4번 항목 업그레이드 (뉘앙스 추가 강제)
AI_PROMPT_RULES = """
[초강력 중요 규칙]
1. 번호나 리스트 표시 절대 금지. 줄바꿈 없이 한 단어당 한 줄로만 작성.
2. 영단어에 절대 ** 기호 금지.
3. 발음 기호: 국제음성기호(IPA) 표준을 따르고 반드시 대괄호 양옆에 공백을 한 칸씩 넣을 것! (예: [ klɑːs ])
4. 다품사 강제 & 뉘앙스 구분(⭐️): 뜻이 비슷한 유의어와 혼동되지 않도록, 뜻 앞에 괄호 ( )를 쳐서 뉘앙스나 쓰임새를 무조건 포함해서 요약해주세요.
   - 예: (내용을) 말하다 / (언어를/공식적으로) 말하다 / (정보를) 알리다
   - 같은 품사 내 뜻은 쉼표(,), 품사가 바뀌면 슬래시(/)로 구분
[형식]: 영단어;[ 발음기호 ];품사별 핵심 뜻;실전 예문 (예문은 1개만)
"""

if menu == "🤖 AI 단어 생성":
    st.header("🤖 AI 맞춤 자동 생성")
    category = st.selectbox("학습 목표", ["일반 생활 영단어", "경찰 공무원 영단어", "토익 (TOEIC) 영단어"])
    level = st.select_slider("난이도", options=["초급 (기초 필수)", "중급 (빈출 핵심)", "고급 (고득점 변별력)"])
    count = st.number_input("생성 개수", min_value=1, max_value=50, value=10)

    if st.button("🚀 단어 생성 시작"):
        existing_words = ", ".join(df['Word'].tolist())
        prompt = f"당신은 1타 영어 강사입니다.\n분야: {category} / 난이도: {level} / {count}개 생성.\n중복 제외: {existing_words}\n{AI_PROMPT_RULES}"
        with st.spinner("AI가 단어의 모든 품사와 뉘앙스를 스캔하여 요약 중입니다..."):
            try:
                response = get_ai_response(prompt)
                df, added_count = parse_and_add_words(response.text, df, category, level)
                if added_count > 0:
                    save_data(df, VOCAB_FILE)
                    st.success(f"🎉 {added_count}개의 단어가 다품사 형태로 추가되었습니다!")
            except Exception as e:
                st.error(f"❌ 생성 오류:\n{e}")

elif menu == "✨ 단어 일괄 추가":
    st.header("✨ 단어 일괄 추가")
    st.write("인터넷, 메모장, 엑셀에서 복사한 영단어 목록을 손쉽게 추가하세요.")
    
    tab1, tab2 = st.tabs(["✍️ 텍스트 복사/붙여넣기", "📁 엑셀(CSV) 파일 업로드"])
    
    with tab1:
        st.info("💡 엑셀 세로줄을 그대로 복사해서 붙여넣으셔도 자동으로 인식합니다!")
        words_input = st.text_area("영단어 목록 입력 (쉼표나 줄바꿈으로 구분)", height=150)
        if st.button("✅ 텍스트 분석 및 추가"):
            if words_input:
                clean_words = words_input.replace('\n', ',').replace('\t', ',')
                prompt = f"단어: {clean_words}\n{AI_PROMPT_RULES}"
                with st.spinner("AI가 입력하신 단어의 모든 품사를 스캔 중입니다..."):
                    try:
                        response = get_ai_response(prompt)
                        df, added_count = parse_and_add_words(response.text, df, '수동 추가', '-')
                        if added_count > 0:
                            save_data(df, VOCAB_FILE)
                            st.success(f"🎉 {added_count}개 단어의 다품사 분석 및 추가 완료!")
                    except Exception as e:
                        st.error(f"❌ 오류:\n{e}")
                        
    with tab2:
        uploaded_file = st.file_uploader("단어 목록이 담긴 엑셀(CSV) 파일을 올려주세요.", type=['csv'])
        if uploaded_file is not None:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                first_column_words = uploaded_df.iloc[:, 0].dropna().astype(str).tolist()
                words_from_csv = ", ".join(first_column_words)
                
                st.write(f"추출된 단어 ({len(first_column_words)}개):")
                st.caption(words_from_csv[:100] + "...")
                
                if st.button("✅ CSV 단어 분석 및 추가"):
                    prompt = f"단어: {words_from_csv}\n{AI_PROMPT_RULES}"
                    with st.spinner("AI가 CSV 안의 단어 품사를 스캔 중입니다..."):
                        response = get_ai_response(prompt)
                        df, added_count = parse_and_add_words(response.text, df, 'CSV 추가', '-')
                        if added_count > 0:
                            save_data(df, VOCAB_FILE)
                            st.success(f"🎉 CSV에서 {added_count}개의 단어 추가 완료!")
            except Exception as e:
                st.error("파일을 읽는 중 문제가 발생했습니다. CSV 형식을 확인해주세요.")

elif menu in ["📖 단어 관리", "📅 학습 기록"]:
    status_filter = 'Learning' if menu == "📖 단어 관리" else 'Completed'
    
    col_header, col_btn = st.columns([6, 4])
    with col_header:
        st.header(menu)
    with col_btn:
        st.write("") 
        view_df = df[df['Status'] == status_filter].sort_values('Date', ascending=False)
        if not view_df.empty:
            csv_data = convert_df_to_csv(view_df)
            st.download_button(
                label="📥 엑셀(CSV) 내보내기",
                data=csv_data,
                file_name=f"my_words_{status_filter}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
    if view_df.empty:
        st.info("해당하는 단어가 없습니다.")
    else:
        selected_indices = st.multiselect("여러 단어 동시 선택", view_df.index, format_func=lambda x: f"{view_df.loc[x, 'Word']} - {view_df.loc[x, 'Meaning']}")
        col1, col2, col3 = st.columns(3)
        if col2.button("🔊 연속 듣기") and selected_indices:
            words_to_play = [df.loc[i, 'Word'] for i in selected_indices]
            play_sequence_audio(words_to_play) 
        if menu == "📖 단어 관리":
            if col1.button("✅ 선택 완료"):
                df.loc[selected_indices, 'Status'] = 'Completed'
                save_data(df, VOCAB_FILE)
                st.rerun()
        else:
            if col1.button("⏪ 다시 학습"):
                df.loc[selected_indices, 'Status'] = 'Learning'
                save_data(df, VOCAB_FILE)
                st.rerun()

        if col3.button("🗑️ 선택 삭제"):
            df = df.drop(selected_indices)
            save_data(df, VOCAB_FILE)
            st.rerun()

        st.divider()
        for i, (idx, row) in enumerate(view_df.iterrows(), start=1):
            with st.expander(f"**{i}. {row['Word']}** {row['Phonetic']} | {row['Meaning']}"):
                st.write(f"📅 추가일: {row['Date']}")
                word_str = str(row['Word'])
                ex_str = str(row['Example'])
                highlighted_word = f"**:green[{word_str}]**"
                final_example = ex_str.replace(word_str, highlighted_word)
                st.markdown(f"📝 **예문:** {final_example}")
                
                c1, c2, c3 = st.columns(3)
                if c1.button("🔊 듣기", key=f"btn_listen_{idx}_{time.time()}"):
                    speak(row['Word']) 
                if menu == "📖 단어 관리":
                    if c2.button("✅ 학습 완료", key=f"btn_done_{idx}"):
                        df.loc[idx, 'Status'] = 'Completed'
                        save_data(df, VOCAB_FILE)
                        st.rerun()
                else:
                    if c2.button("⏪ 다시 학습", key=f"btn_relearn_{idx}"):
                        df.loc[idx, 'Status'] = 'Learning'
                        save_data(df, VOCAB_FILE)
                        st.rerun()
                if c3.button("🗑️ 삭제", key=f"btn_del_{idx}"):
                    df = df.drop(idx)
                    save_data(df, VOCAB_FILE)
                    st.rerun()

# ----------------- 📝 실전 테스트 & 🔥 오답 노트 재도전 -----------------
elif menu in ["📝 실전 테스트", "🔥 오답 노트 재도전"]:
    is_wrong_mode = (menu == "🔥 오답 노트 재도전")
    current_pool = wrong_df if is_wrong_mode else df[df['Status'] == 'Learning']
    
    col_header, col_btn = st.columns([6, 4])
    with col_header:
        st.header(menu)
    with col_btn:
        st.write("")
        if is_wrong_mode and not current_pool.empty:
            wrong_csv_data = convert_df_to_csv(current_pool)
            st.download_button(
                label="📥 오답 목록 엑셀(CSV) 추출",
                data=wrong_csv_data,
                file_name="my_wrong_words.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    if current_pool.empty:
        if is_wrong_mode: st.success("🎉 오답 노트가 비어있습니다! 완벽합니다!")
        else: st.warning("학습 중인 단어가 없습니다.")
    else:
        test_mode_option = st.radio(
            "🎯 테스트 방식 선택",
            [
                "🔀 랜덤 섞기 (뜻+단어)", 
                "🔤 영단어 맞추기 (뜻 ➔ 단어)", 
                "🇰🇷 한글 뜻 맞추기 (단어 ➔ 뜻)",
                "🎧 발음 듣고 맞추기 (단어+뜻 모두)"
            ],
            horizontal=False
        )
        st.divider()

        if 'test_menu' not in st.session_state or st.session_state.test_menu != menu:
            st.session_state.test_menu = menu
            st.session_state.prev_result = None
            st.session_state.audio_played = True 
            
            queue = current_pool['Word'].tolist()
            random.shuffle(queue)
            st.session_state.test_queue = queue
            if 'current_test_mode' in st.session_state: del st.session_state.current_test_mode
            
            st.session_state.test_total_count = len(queue)
            st.session_state.test_correct_count = 0
            st.session_state.test_incorrect_count = 0
            st.session_state.current_test_details = []
            st.session_state.test_saved = False

        if st.session_state.prev_result:
            res = st.session_state.prev_result
            if res['correct']: st.success(f"✅ 이전 문제 정답! ({res['word']} : {res['meaning']})")
            else: st.error(f"❌ 이전 문제 오답... 정답: **{res['word']}** | {res['meaning']} (내 입력: {res['user_ans']})")
            st.info(f"💡 예문: {res['example']}")
            if not st.session_state.get('audio_played') and res['mode'] != 'LISTEN':
                speak(res['word'])
                st.session_state.audio_played = True 

        st.divider()

        if not st.session_state.test_queue:
            if not st.session_state.get('test_saved'):
                test_record = {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "type": menu,
                    "total": st.session_state.test_total_count,
                    "correct": st.session_state.test_correct_count,
                    "incorrect": st.session_state.test_incorrect_count,
                    "details": st.session_state.current_test_details
                }
                history = load_test_history()
                history.insert(0, test_record)
                save_test_history(history)
                st.session_state.test_saved = True

            st.balloons()
            st.success("🎉 준비된 모든 단어의 테스트가 끝났습니다! 수고하셨습니다.")
            
            st.subheader("📊 테스트 결과 요약")
            c1, c2, c3 = st.columns(3)
            c1.metric("📝 총 문제", f"{st.session_state.test_total_count}개")
            c2.metric("✅ 정답", f"{st.session_state.test_correct_count}개")
            c3.metric("❌ 오답", f"{st.session_state.test_incorrect_count}개")
            st.divider()
            
            st.subheader("📋 전체 문제 풀이 결과")
            for i, detail in enumerate(st.session_state.current_test_details, 1):
                status_mark = "✅ (정답)" if detail['is_correct'] else "❌ (오답)"
                st.markdown(f"**문제 {i}. {status_mark}**")
                st.markdown(f"> **{detail['word']}** {detail['phonetic']} | {detail['meaning']}")
                
                disp_eng = detail['user_eng'] if detail['eng_correct'] else f"**:red[{detail['user_eng']}]**"
                disp_kor = detail['user_kor'] if detail['kor_correct'] else f"**:red[{detail['user_kor']}]**"
                st.markdown(f"**답안:** {disp_eng} | {disp_kor}")
                st.write("") 

            st.divider()
            if st.button("🔄 처음부터 다시 풀기"):
                refresh_pool = wrong_df if is_wrong_mode else df[df['Status'] == 'Learning']
                if not refresh_pool.empty:
                    queue = refresh_pool['Word'].tolist()
                    random.shuffle(queue)
                    st.session_state.test_queue = queue
                    st.session_state.prev_result = None
                    if 'current_test_mode' in st.session_state: del st.session_state.current_test_mode
                    
                    st.session_state.test_total_count = len(queue)
                    st.session_state.test_correct_count = 0
                    st.session_state.test_incorrect_count = 0
                    st.session_state.current_test_details = []
                    st.session_state.test_saved = False
                    st.rerun()
                else:
                    st.success("더 이상 풀 문제가 없습니다!")
        else:
            if test_mode_option == "🔀 랜덤 섞기 (뜻+단어)":
                if 'current_test_mode' not in st.session_state:
                    st.session_state.current_test_mode = random.choice(['E2K', 'K2E'])
                test_mode = st.session_state.current_test_mode
            elif test_mode_option == "🔤 영단어 맞추기 (뜻 ➔ 단어)":
                test_mode = 'K2E'
                st.session_state.pop('current_test_mode', None) 
            elif test_mode_option == "🇰🇷 한글 뜻 맞추기 (단어 ➔ 뜻)": 
                test_mode = 'E2K'
                st.session_state.pop('current_test_mode', None)
            else:
                test_mode = 'LISTEN'
                st.session_state.pop('current_test_mode', None)

            current_word_str = st.session_state.test_queue[0]
            word_info = current_pool[current_pool['Word'] == current_word_str].iloc[0]

            st.write(f"📝 남은 문제: {len(st.session_state.test_queue)}개")
            
            if test_mode == 'LISTEN':
                st.subheader("Q: 🎧 소리를 듣고 영단어와 뜻을 적어주세요!")
                st.info("💡 2.5초 간격으로 단어가 무한 반복 재생 중입니다.")
                speak(word_info['Word'], loop=True)
                
            elif test_mode == 'E2K':
                st.subheader(f"Q: {word_info['Word']} {word_info['Phonetic']}")
                st.caption("이 단어의 뜻은?")
                
            # ⭐️ 수정됨: 영단어 맞추기 모드에서 예문 블라인드 힌트 제공
            else:
                st.subheader(f"Q: {word_info['Meaning']}")
                st.caption("해당하는 영어 단어는?")
                try:
                    word_len = len(word_info['Word'])
                    blank_str = "_" * word_len
                    # 예문에서 정답 단어를 밑줄로 치환
                    hint_example = re.sub(rf"\b{word_info['Word']}\b", blank_str, str(word_info['Example']), flags=re.IGNORECASE)
                    st.info(f"💡 힌트(예문): {hint_example} (시작 알파벳: **{word_info['Word'][0].upper()}**)")
                except:
                    st.info(f"💡 힌트: 시작 알파벳 '**{word_info['Word'][0].upper()}**'")

            with st.form(key=f"test_form_{current_word_str}", clear_on_submit=True):
                if test_mode == 'LISTEN':
                    ans_eng = st.text_input("✍️ 영어 단어 (스펠링) 입력", key=f"eng_{current_word_str}")
                    ans_kor = st.text_input("✍️ 한글 뜻 입력", key=f"kor_{current_word_str}")
                else:
                    ans = st.text_input("✍️ 정답을 입력하고 엔터(Enter)를 누르세요.")
                    
                submitted = st.form_submit_button("제출")
                
                focus_idx = 2 if test_mode == 'LISTEN' else 1
                components.html(f"""
                <script>
                const parentDoc = window.parent.document;
                const inputs = parentDoc.querySelectorAll('div[data-testid="stForm"] input[type="text"]');
                if (inputs.length > 0) {{
                    const targetFocus = inputs[inputs.length - {focus_idx}];
                    if (targetFocus) setTimeout(() => targetFocus.focus(), 100);
                }}
                </script>
                """, height=0, width=0)

                if submitted:
                    correct = False
                    is_eng_correct = True
                    is_kor_correct = True
                    
                    u_eng = ans_eng if test_mode == 'LISTEN' else (ans if test_mode == 'K2E' else word_info['Word'])
                    u_kor = ans_kor if test_mode == 'LISTEN' else (ans if test_mode == 'E2K' else word_info['Meaning'])
                    
                    clean_meaning_full = re.sub(r'[\s\(\)\[\]\,\/]', '', word_info['Meaning'])
                    for tag in ["명사", "동사", "대명사", "형용사", "부사", "전치사", "접속사", "감탄사", ":"]:
                        clean_meaning_full = clean_meaning_full.replace(tag, "")

                    if test_mode == 'E2K':
                        ans_q = get_qwerty(ans)
                        mean_q = get_qwerty(clean_meaning_full)
                        if ans_q and ans_q in mean_q:
                            correct = True
                        else:
                            is_kor_correct = False
                        
                    elif test_mode == 'K2E':
                        ans_q = get_qwerty(ans)
                        word_q = get_qwerty(word_info['Word'])
                        if ans_q and ans_q == word_q:
                            correct = True
                        else:
                            is_eng_correct = False
                        
                    elif test_mode == 'LISTEN':
                        eng_q = get_qwerty(ans_eng)
                        word_q = get_qwerty(word_info['Word'])
                        if eng_q and eng_q == word_q:
                            is_eng_correct = True
                        else:
                            is_eng_correct = False
                            
                        kor_q = get_qwerty(ans_kor)
                        mean_q = get_qwerty(clean_meaning_full)
                        if kor_q and kor_q in mean_q:
                            is_kor_correct = True
                        else:
                            is_kor_correct = False
                            
                        if is_eng_correct and is_kor_correct: 
                            correct = True

                    if correct:
                        st.session_state.test_correct_count += 1
                        if word_info['Word'] in wrong_df['Word'].values:
                            wrong_df = wrong_df[wrong_df['Word'] != word_info['Word']]
                            save_data(wrong_df, WRONG_FILE)
                    else:
                        st.session_state.test_incorrect_count += 1
                        if word_info['Word'] not in wrong_df['Word'].values:
                            new_wrong = pd.DataFrame([word_info.to_dict()])
                            wrong_df = pd.concat([wrong_df, new_wrong], ignore_index=True)
                            save_data(wrong_df, WRONG_FILE)
                    
                    st.session_state.current_test_details.append({
                        "word": word_info['Word'],
                        "phonetic": word_info['Phonetic'],
                        "meaning": word_info['Meaning'],
                        "user_eng": u_eng if u_eng.strip() else "(빈칸)",
                        "user_kor": u_kor if u_kor.strip() else "(빈칸)",
                        "is_correct": correct,
                        "eng_correct": is_eng_correct,
                        "kor_correct": is_kor_correct,
                        "mode": test_mode
                    })

                    display_ans = f"{u_eng} | {u_kor}" if test_mode == 'LISTEN' else (ans if ans.strip() else "(빈칸)")
                    st.session_state.prev_result = {
                        'correct': correct, 'word': word_info['Word'], 'meaning': word_info['Meaning'],
                        'example': word_info['Example'], 'user_ans': display_ans, 'mode': test_mode
                    }
                    st.session_state.audio_played = False
                    st.session_state.test_queue.pop(0) 
                    if 'current_test_mode' in st.session_state:
                        del st.session_state.current_test_mode
                    st.rerun()

elif menu == "🏆 테스트 결과 기록":
    st.header("🏆 내 테스트 기록 보관함")
    st.write("과거에 진행했던 테스트 결과와 오답 노트를 한눈에 볼 수 있습니다.")
    
    history_data = load_test_history()
    
    if not history_data:
        st.info("아직 저장된 테스트 기록이 없습니다. 먼저 실전 테스트를 완료해 보세요!")
    else:
        for h_idx, record in enumerate(history_data):
            expander_title = f"🗓️ {record['date']} | {record['type']} | 총 {record['total']}문제 | 정답 {record['correct']} / 오답 {record['incorrect']}"
            with st.expander(expander_title):
                st.subheader(f"📊 점수 요약")
                c1, c2, c3 = st.columns(3)
                c1.metric("총 문제", f"{record['total']}개")
                c2.metric("정답", f"{record['correct']}개")
                c3.metric("오답", f"{record['incorrect']}개")
                
                st.divider()
                st.subheader("📋 전체 문제 상세 리뷰")
                for i, detail in enumerate(record['details'], 1):
                    status_mark = "✅ (정답)" if detail['is_correct'] else "❌ (오답)"
                    st.markdown(f"**문제 {i}. {status_mark}**")
                    st.markdown(f"> **{detail['word']}** {detail['phonetic']} | {detail['meaning']}")
                    
                    disp_eng = detail['user_eng'] if detail['eng_correct'] else f"**:red[{detail['user_eng']}]**"
                    disp_kor = detail['user_kor'] if detail['kor_correct'] else f"**:red[{detail['user_kor']}]**"
                    
                    st.markdown(f"**답안:** {disp_eng} | {disp_kor}")
                    st.write("") 

elif menu == "📊 학습 통계":
    st.header("📊 내 학습 통계")
    st.subheader(f"📚 전체 누적 단어: {len(df)}개")
    st.subheader(f"🔥 오답 노트 누적: {len(wrong_df)}개")
    if not df.empty:
        stats = df.groupby(['Category', 'Level']).size().reset_index(name='Count')
        st.dataframe(stats, hide_index=True, use_container_width=True)

# ----------------- 📚 영어 기초 가이드 -----------------
elif menu == "📚 영어 기초 가이드":
    st.header("📚 기초 영어 완벽 가이드")
    st.caption("영포자도 이해할 수 있는 원리 위주의 핵심 가이드입니다.")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗣️발음/품사", "🔄동사표", "🌱기초구문", "🌿문장/시제", "🌳심화문법"])
    
    with tab1:
        st.subheader("🗣️ 영어 발음 기호표 (IPA 표준)")
        st.write("모음(Vowels)과 자음(Consonants)을 보기 쉽게 분류했습니다.")
        headers = ["발음 기호", "소리 (한글)", "발음 기호", "소리 (한글)"]
        data = [
            ["[ iː ]", "이- (길게)", "[ ɪ ]", "이 (짧게)"],
            ["[ e ] / [ ɛ ]", "에", "[ æ ]", "애 (입크게)"],
            ["[ ɑː ]", "아- (길게)", "[ ɒ ] / [ ɔː ]", "오- (길게)"],
            ["[ ʊ ]", "우 (짧게)", "[ uː ]", "우- (길게)"],
            ["[ ʌ ]", "어 (강하게)", "[ ə ]", "어 (약하게)"],
            ["[ ɜː ] / [ əː ]", "어- (길게)", "[ eɪ ]", "에이"],
            ["[ aɪ ]", "아이", "[ ɔɪ ]", "오이"],
            ["[ aʊ ]", "아우", "[ oʊ ] / [ əʊ ]", "오우"],
            ["[ p ]", "프", "[ b ]", "브"],
            ["[ t ]", "트", "[ d ]", "드"],
            ["[ k ]", "크", "[ g ]", "그"],
            ["[ f ]", "프 (아랫입술)", "[ v ]", "브 (아랫입술)"],
            ["[ θ ]", "쓰 (번데기)", "[ ð ]", "드 (돼지꼬리)"],
            ["[ s ]", "스", "[ z ]", "즈"],
            ["[ ʃ ]", "쉬", "[ ʒ ]", "쥐 (부드럽게)"],
            ["[ h ]", "흐", "[ tʃ ]", "취"],
            ["[ dʒ ]", "쥐 / 쥬", "[ m ]", "ㅁ / 음"],
            ["[ n ]", "ㄴ / 은", "[ ŋ ]", "ㅇ / 응"],
            ["[ l ]", "ㄹ (혀끝 닿음)", "[ r ]", "ㄹ (혀 굴림)"],
            ["[ j ]", "이 / 야 (반모음)", "[ w ]", "우 / 와 (반모음)"]
        ]
        render_mobile_table(headers, data, font_size="17px")
        
        st.divider()
        st.subheader("🧩 영어의 8품사")
        st.markdown("""
        단어들을 역할과 기능에 따라 8가지로 분류한 '재료'입니다.
        1. **명사 (Noun)** : 사람, 사물, 개념의 이름. *(apple, love, desk)*
        2. **대명사 (Pronoun)** : 명사를 대신 부르는 말. *(he, she, it, 단수)*
        3. **동사 (Verb)** : 동작이나 상태 (~다). *(run, eat, is)*
        4. **형용사 (Adjective)** : 명사의 상태를 꾸며줌 (~한). *(pretty, happy)*
        5. **부사 (Adverb)** : 동사나 형용사를 꾸며줌 (~하게). *(quickly, very)*
        6. **전치사 (Preposition)** : 명사 앞에 붙어 시간/장소를 나타냄. *(in, on, at)*
        7. **접속사 (Conjunction)** : 단어나 문장을 연결하는 접착제. *(and, but, because)*
        8. **감탄사 (Interjection)** : 감정 표현. *(oh, wow)*
        """)

    with tab2:
        st.subheader("🔄 핵심 필수 동사표 (100+)")
        st.markdown("### 1. 규칙 동사 모음 (Regular Verbs)")
        headers_reg = ["규칙 패턴", "현재(V)", "과거(V-ed)", "과거분사(p.p)", "뜻"]
        data_reg = [
            ["일반 (+ed)", "want", "wanted", "wanted", "원하다"],
            ["일반 (+ed)", "play", "played", "played", "놀다"],
            ["일반 (+ed)", "help", "helped", "helped", "돕다"],
            ["일반 (+ed)", "look", "looked", "looked", "보다"],
            ["-e로 끝 (+d)", "use", "used", "used", "사용하다"],
            ["-e로 끝 (+d)", "agree", "agreed", "agreed", "동의하다"],
            ["자음+y 끝 (y->ied)", "try", "tried", "tried", "시도하다"],
            ["자음+y 끝 (y->ied)", "study", "studied", "studied", "공부하다"],
            ["단모음+자음 (자음추가)", "stop", "stopped", "stopped", "멈추다"],
            ["단모음+자음 (자음추가)", "plan", "planned", "planned", "계획하다"]
        ]
        render_mobile_table(headers_reg, data_reg)

        st.divider()
        st.markdown("### 2. 불규칙 동사 모음 (Irregular Verbs)")
        render_mobile_table(["현재(V)", "과거", "과거분사", "뜻"], [
            ["put", "put", "put", "놓다"], ["cut", "cut", "cut", "자르다"],
            ["read", "read(레드)", "read(레드)", "읽다"], ["hit", "hit", "hit", "치다"],
            ["set", "set", "set", "세팅하다"], ["let", "let", "let", "허락하다"],
            ["come", "came", "come", "오다"], ["run", "ran", "run", "달리다"],
            ["buy", "bought", "bought", "사다"], ["catch", "caught", "caught", "잡다"],
            ["have", "had", "had", "가지다"], ["make", "made", "made", "만들다"],
            ["be(am/is/are)", "was/were", "been", "이다, 있다"], ["go", "went", "gone", "가다"],
            ["take", "took", "taken", "가져가다"], ["write", "wrote", "written", "쓰다"]
        ])

    with tab3:
        st.subheader("🌱 기초 구문 (명사, 대명사, 전치사)")
        st.markdown("""
        **■ 1. 가산명사 vs 불가산명사**
        * **가산명사**: 하나면 `a/an`, 여러 개면 `-s`. (예: `an apple`)
        * **불가산명사**: 셀 수 없음. `a`나 `-s` 금지. (예: `water`)

        **■ 2. 만능 단어 'it'의 3가지 쓰임**
        * **지시대명사**: 앞서 말한 그것.
        * **비인칭주어**: 시간/날씨 자리 채움 (해석 안함).
        * **가주어**: 진짜 주어가 길어서 빈자리를 채움.

        **■ 3. 전치사 (for vs during)**
        * **for + 숫자 기간**: 시간의 양. ("for 3 hours")
        * **during + 특정 기간 명사**: 시간의 이름. ("during the class")
        """)

    with tab4:
        st.subheader("🌿 문장과 시제 (5형식과 동사)")
        st.markdown("""
        **■ 1. 문장의 5형식**
        * **1형식 (S+V)**: I run.
        * **2형식 (S+V+C)**: I am a student.
        * **3형식 (S+V+O)**: I love you.
        * **4형식 (S+V+O1+O2)**: I gave him a book.
        * **5형식 (S+V+O+C)**: I made him happy.

        **■ 2. 시제 (Tense)**
        * **현재시제**: 늘상 하는 습관/팩트.
        * **현재완료 (have+p.p)**: 과거의 일이 '현재'까지 영향을 미칠 때. 
        """)

    with tab5:
        st.subheader("🌳 심화 문법 (길고 세련된 문장 만들기)")
        st.markdown("""
        **■ 1. 준동사 (to부정사 vs 동명사)**
        * **to부정사**: 미래, 지향적 성향. 
        * **동명사**: 과거, 경험 성향. 

        **■ 2. 분사 (현재분사 vs 과거분사)**
        * **현재분사 (-ing)**: 능동/진행. 
        * **과거분사 (p.p)**: 수동/완료. 

        **■ 3. 관계대명사 (who, which, that)**
        문장을 두 번 말하기 귀찮을 때 선행사 뒤에 붙여 설명.

        **■ 4. 수동태 (be동사 + p.p)**
        주어가 행동을 당할 때 사용.
        """)
