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
# 🔑 제미나이 API 키 설정
GEMINI_API_KEY = ""
genai.configure(api_key=GEMINI_API_KEY)
# ==========================================

def get_ai_response(prompt):
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_name = m.name.replace('models/', '')
                available_models.append(model_name)
    except Exception as e:
        raise Exception(f"API 키 연결 실패: {e}")

    if not available_models:
        raise Exception("사용 가능한 AI 모델이 없습니다. API 키를 다시 확인해주세요.")

    priority_models = []
    for m in available_models:
        if 'lite' in m.lower() and m not in priority_models:
            priority_models.append(m)
    for m in available_models:
        if '1.5-flash' in m.lower() and m not in priority_models:
            priority_models.append(m)
    for m in available_models:
        if 'flash' in m.lower() and m not in priority_models:
            priority_models.append(m)
    for m in available_models:
        if m not in priority_models:
            priority_models.append(m)

    last_error = None
    for target_model in priority_models:
        try:
            model = genai.GenerativeModel(target_model)
            return model.generate_content(prompt)
        except Exception as e:
            last_error = str(e)
            continue

    raise Exception(f"사용 가능한 모든 AI 서버의 일일 할당량이 초과되었습니다.\n마지막 에러: {last_error}")

VOCAB_FILE = 'my_vocab_web.csv'
WRONG_FILE = 'my_vocab_wrong_web.csv'

def load_data(file_path):
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return pd.DataFrame(columns=['Word', 'Phonetic', 'Meaning', 'Example', 'Date', 'Status', 'Category', 'Level'])

def save_data(df, file_path):
    df.to_csv(file_path, index=False, encoding='utf-8-sig')

def speak(text):
    pure_text = text.split('[')[0].strip()
    try:
        tts = gTTS(text=pure_text, lang='en')
        tts.save("temp.mp3")
        with open("temp.mp3", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            unique_id = random.randint(1, 10000000)
            html_code = f"""
                <audio autoplay>
                    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                </audio>
                <div style="display:none;">{unique_id}</div>
            """
            components.html(html_code, height=0, width=0)
    except Exception:
        pass 

def play_sequence_audio(words):
    audio_data_list = []
    for w in words:
        pure_w = w.split('[')[0].strip()
        try:
            tts = gTTS(text=pure_w, lang='en')
            tts.save("temp_seq.mp3")
            with open("temp_seq.mp3", "rb") as f:
                audio_data_list.append(base64.b64encode(f.read()).decode())
        except:
            pass

    if not audio_data_list: return

    js_array = json.dumps(audio_data_list)
    html_code = f"""
    <audio id="seqPlayer"></audio>
    <script>
        const audioData = {js_array};
        let currentWordIdx = 0;
        let playCount = 0;
        const player = document.getElementById("seqPlayer");

        function playNext() {{
            if(currentWordIdx >= audioData.length) return;
            player.src = "data:audio/mp3;base64," + audioData[currentWordIdx];
            player.play().catch(e => console.log(e));
            player.onended = function() {{
                playCount++;
                if(playCount < 3) {{
                    setTimeout(playNext, 1000); 
                }} else {{
                    playCount = 0;
                    currentWordIdx++;
                    setTimeout(playNext, 2300); 
                }}
            }};
        }}
        playNext();
    </script>
    <div style="display:none;">{time.time()}</div>
    """
    components.html(html_code, height=0, width=0)

def render_mobile_table(headers, data):
    html = '<div style="overflow-x: auto;"><table style="width: 100%; border-collapse: collapse; font-size: 14px;">'
    html += "<tr>" + "".join([f"<th style='border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #333; color: white;'>{h}</th>" for h in headers]) + "</tr>"
    for row in data:
        html += "<tr>" + "".join([f"<td style='border: 1px solid #ddd; padding: 8px;'>{cell}</td>" for cell in row]) + "</tr>"
    html += "</table></div>"
    st.markdown(html, unsafe_allow_html=True)

st.set_page_config(page_title="AI 영단어 마스터", layout="centered")
st.title("🦉 AI 영단어 마스터 Web")

st.sidebar.title("메뉴")
menu = st.sidebar.selectbox("메뉴 선택", [
    "🤖 AI 단어 생성", 
    "📖 단어 관리", 
    "📝 실전 테스트", 
    "📚 영어 기초 가이드", 
    "📅 학습 기록", 
    "📊 학습 통계",
    "✨ 단어 일괄 추가",
    "🔥 오답 노트 재도전"
])

st.sidebar.divider()
st.sidebar.markdown("### 🛠️ 시스템 관리")
if st.sidebar.button("🧹 시스템 캐시 및 오류 초기화"):
    st.cache_data.clear()
    st.cache_resource.clear()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    st.sidebar.success("✅ 캐시 삭제 완료! 앱을 재시작합니다.")
    time.sleep(1)
    st.rerun()

df = load_data(VOCAB_FILE)
wrong_df = load_data(WRONG_FILE)

# ----------------- 🤖 AI 단어 생성 -----------------
if menu == "🤖 AI 단어 생성":
    st.header("🤖 AI 맞춤 자동 생성")
    category = st.selectbox("학습 목표", ["일반 생활 영단어", "경찰 공무원 영단어", "토익 (TOEIC) 영단어"])
    level = st.select_slider("난이도", options=["초급 (기초 필수)", "중급 (빈출 핵심)", "고급 (고득점 변별력)"])
    count = st.number_input("생성 개수", min_value=1, max_value=50, value=10)

    if st.button("🚀 단어 생성 시작"):
        existing_words = ", ".join(df['Word'].tolist())
        # ⭐️ 프롬프트 핵심 수정: "모든 품사를 찾되, 뜻만 짧게 써라!" 명시
        prompt = f"""
        당신은 1타 영어 강사입니다.
        분야: {category} / 난이도: {level} / {count}개 생성.
        중복 제외: {existing_words}
        [초강력 중요 규칙]
        1. 번호나 리스트 표시 절대 금지. 줄바꿈 없이 한 단어당 한 줄로만 작성하세요.
        2. 영단어에 절대 ** 기호 금지.
        3. 발음 기호 규칙: 반드시 대괄호 `[]`로 양옆을 감쌀 것! (예: [klɑ:s])
        4. 다품사 강제 출력 및 뜻 요약 (가장 중요⭐️): 하나의 품사만 적는 것을 엄격히 금지합니다! 단어가 문장에서 쓰일 수 있는 **모든 주요 품사(명사, 동사, 형용사, 부사 등)를 무조건 끝까지 다 찾아내서 적으세요.** 단, 뜻은 각 품사별로 가장 핵심적인 1~2개만 간결하게 적습니다.
           - 같은 품사 내의 뜻은 쉼표(,)로 구분
           - 품사가 바뀌면 슬래시(/)로 구분
           - (예시 1 - water) 명사 : 물 / 동사 : 물을 주다
           - (예시 2 - downstairs) 명사 : 아래층 / 부사 : 아래층으로 / 형용사 : 아래층의
        [형식]: 영단어;[발음기호];품사별 핵심 뜻;실전 예문 (예문은 1개만)
        """
        with st.spinner("AI가 단어의 모든 품사를 스캔하여 요약 중입니다..."):
            try:
                response = get_ai_response(prompt)
                lines = response.text.strip().split('\n')
                new_rows = []
                for line in lines:
                    parts = line.split(';')
                    if len(parts) >= 4:
                        eng = re.sub(r'^[\d\.\)]+\s*', '', parts[0].replace('*', '').strip())
                        
                        phonetic = parts[1].strip()
                        if phonetic:
                            if not phonetic.startswith('['): phonetic = '[' + phonetic
                            if not phonetic.endswith(']'): phonetic = phonetic + ']'
                        else:
                            phonetic = '[]'

                        new_rows.append({
                            'Word': eng, 'Phonetic': phonetic, 'Meaning': parts[2].strip(),
                            'Example': parts[3].strip(), 'Date': datetime.now().strftime("%Y-%m-%d"),
                            'Status': 'Learning', 'Category': category, 'Level': level
                        })
                if new_rows:
                    new_df = pd.DataFrame(new_rows)
                    df = pd.concat([df, new_df], ignore_index=True).drop_duplicates('Word')
                    save_data(df, VOCAB_FILE)
                    st.success(f"🎉 {len(new_rows)}개의 단어가 다품사 형태(요약본)로 추가되었습니다!")
            except Exception as e:
                st.error(f"❌ 생성 오류:\n{e}")

# ----------------- ✨ 수동 일괄 추가 -----------------
elif menu == "✨ 단어 일괄 추가":
    st.header("✨ 단어 일괄 추가")
    words_input = st.text_area("단어를 쉼표(,)로 구분해 입력하세요.")
    if st.button("✅ 분석 및 추가"):
        if words_input:
            prompt = f"""
            단어: {words_input}
            [초강력 중요 규칙]
            1. 번호나 리스트 표시 절대 금지. 줄바꿈 없이 한 단어당 한 줄로만 작성하세요.
            2. 영단어에 절대 ** 기호 금지.
            3. 발음 기호 규칙: 반드시 대괄호 `[]`로 양옆을 감쌀 것!
            4. 다품사 강제 출력 및 뜻 요약 (가장 중요⭐️): 하나의 품사만 적는 것을 엄격히 금지합니다! 단어가 문장에서 쓰일 수 있는 **모든 주요 품사(명사, 동사, 형용사, 부사 등)를 무조건 끝까지 다 찾아내서 적으세요.** 단, 뜻은 각 품사별로 가장 핵심적인 1~2개만 간결하게 적습니다.
               - 같은 품사 내의 뜻은 쉼표(,)로 구분
               - 품사가 바뀌면 슬래시(/)로 구분
               - (예시 1 - water) 명사 : 물 / 동사 : 물을 주다
               - (예시 2 - downstairs) 명사 : 아래층 / 부사 : 아래층으로 / 형용사 : 아래층의
            [형식]: 영단어;[발음기호];품사별 핵심 뜻;실전 예문
            """
            with st.spinner("AI가 입력하신 단어의 모든 품사를 스캔 중입니다..."):
                try:
                    response = get_ai_response(prompt)
                    lines = response.text.strip().split('\n')
                    new_rows = []
                    for line in lines:
                        parts = line.split(';')
                        if len(parts) >= 4:
                            eng = re.sub(r'^[\d\.\)]+\s*', '', parts[0].replace('*', '').strip())
                            
                            phonetic = parts[1].strip()
                            if phonetic:
                                if not phonetic.startswith('['): phonetic = '[' + phonetic
                                if not phonetic.endswith(']'): phonetic = phonetic + ']'
                            else:
                                phonetic = '[]'

                            new_rows.append({
                                'Word': eng, 'Phonetic': phonetic, 'Meaning': parts[2].strip(),
                                'Example': parts[3].strip(), 'Date': datetime.now().strftime("%Y-%m-%d"),
                                'Status': 'Learning', 'Category': '수동 추가', 'Level': '-'
                            })
                    if new_rows:
                        new_df = pd.DataFrame(new_rows)
                        df = pd.concat([df, new_df], ignore_index=True).drop_duplicates('Word')
                        save_data(df, VOCAB_FILE)
                        st.success("다품사 분석 및 추가 완료!")
                except Exception as e:
                    st.error(f"❌ 오류:\n{e}")

# ----------------- 📖 단어 관리 / 학습 기록 -----------------
elif menu in ["📖 단어 관리", "📅 학습 기록"]:
    status_filter = 'Learning' if menu == "📖 단어 관리" else 'Completed'
    st.header(menu)
    view_df = df[df['Status'] == status_filter].sort_values('Date', ascending=False)
    
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
        
        for idx, row in view_df.iterrows():
            with st.expander(f"**{row['Word']}** {row['Phonetic']} | {row['Meaning']}"):
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
    st.header(menu)
    is_wrong_mode = (menu == "🔥 오답 노트 재도전")
    current_pool = wrong_df if is_wrong_mode else df[df['Status'] == 'Learning']
    
    if current_pool.empty:
        if is_wrong_mode:
            st.success("🎉 오답 노트가 비어있습니다! 완벽합니다!")
        else:
            st.warning("학습 중인 단어가 없습니다.")
    else:
        if 'test_menu' not in st.session_state or st.session_state.test_menu != menu:
            st.session_state.test_menu = menu
            st.session_state.prev_result = None
            st.session_state.audio_played = True 
            
            queue = current_pool['Word'].tolist()
            random.shuffle(queue)
            st.session_state.test_queue = queue
            
            if 'current_test_mode' in st.session_state:
                del st.session_state.current_test_mode

        if st.session_state.prev_result:
            res = st.session_state.prev_result
            if res['correct']:
                st.success(f"✅ 이전 문제 정답! ({res['word']} : {res['meaning']})")
            else:
                st.error(f"❌ 이전 문제 오답... 정답: **{res['word']}** | {res['meaning']} (내 입력: {res['user_ans']})")
            st.info(f"💡 예문: {res['example']}")
            
            if not st.session_state.get('audio_played'):
                speak(res['word'])
                st.session_state.audio_played = True 

        st.divider()

        if not st.session_state.test_queue:
            st.success("🎉 준비된 모든 단어의 테스트가 끝났습니다! 정말 고생하셨습니다.")
            if st.button("🔄 처음부터 다시 풀기"):
                refresh_pool = wrong_df if is_wrong_mode else df[df['Status'] == 'Learning']
                if not refresh_pool.empty:
                    queue = refresh_pool['Word'].tolist()
                    random.shuffle(queue)
                    st.session_state.test_queue = queue
                    st.session_state.prev_result = None
                    if 'current_test_mode' in st.session_state:
                        del st.session_state.current_test_mode
                    st.rerun()
                else:
                    st.success("더 이상 풀 문제가 없습니다!")
        else:
            if 'current_test_mode' not in st.session_state:
                st.session_state.current_test_mode = random.choice(['E2K', 'K2E'])
            test_mode = st.session_state.current_test_mode

            current_word_str = st.session_state.test_queue[0]
            word_info = current_pool[current_pool['Word'] == current_word_str].iloc[0]

            st.write(f"📝 남은 문제: {len(st.session_state.test_queue)}개")
            if test_mode == 'E2K':
                st.subheader(f"Q: {word_info['Word']} {word_info['Phonetic']}")
                st.caption("이 단어의 뜻은?")
            else:
                st.subheader(f"Q: {word_info['Meaning']}")
                st.caption("해당하는 영어 단어는?")

            with st.form(key=f"test_form_{current_word_str}", clear_on_submit=True):
                ans = st.text_input("✍️ 정답을 입력하고 엔터(Enter)를 누르세요.")
                submitted = st.form_submit_button("제출")
                
                components.html(
                    """
                    <script>
                        const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                        if (inputs.length > 0) { inputs[inputs.length - 1].focus(); }
                    </script>
                    """, height=0, width=0
                )

                if submitted and ans:
                    correct = False
                    
                    if test_mode == 'E2K':
                        clean_ans = re.sub(r'[\s\(\)\[\]\,\/]', '', ans)
                        clean_meaning = re.sub(r'[\s\(\)\[\]\,\/]', '', word_info['Meaning'])
                        pos_tags = ["명사", "동사", "대명사", "형용사", "부사", "전치사", "접속사", "감탄사", ":"]
                        for tag in pos_tags:
                            clean_meaning = clean_meaning.replace(tag, "")
                        
                        if clean_ans and clean_ans in clean_meaning:
                            correct = True
                    else:
                        clean_ans = re.sub(r'[^a-zA-Z]', '', ans).lower()
                        clean_word = re.sub(r'[^a-zA-Z]', '', word_info['Word']).lower()
                        if clean_ans == clean_word:
                            correct = True

                    if correct:
                        if word_info['Word'] in wrong_df['Word'].values:
                            wrong_df = wrong_df[wrong_df['Word'] != word_info['Word']]
                            save_data(wrong_df, WRONG_FILE)
                    else:
                        if word_info['Word'] not in wrong_df['Word'].values:
                            new_wrong = pd.DataFrame([word_info.to_dict()])
                            wrong_df = pd.concat([wrong_df, new_wrong], ignore_index=True)
                            save_data(wrong_df, WRONG_FILE)

                    st.session_state.prev_result = {
                        'correct': correct, 'word': word_info['Word'],
                        'meaning': word_info['Meaning'], 'example': word_info['Example'],
                        'user_ans': ans
                    }
                    st.session_state.audio_played = False
                    st.session_state.test_queue.pop(0) 
                    del st.session_state.current_test_mode
                    st.rerun()

# ----------------- 📊 학습 통계 -----------------
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
        st.subheader("🗣️ 영어 발음 기호표 (IPA)")
        headers = ["번호", "발음기호", "소리", "번호", "발음기호", "소리", "번호", "발음기호", "소리"]
        data = [
            ["1", "[a]", "아", "18", "[ou]", "오우", "35", "[ʒ]", "쥐"],
            ["2", "[e]", "에", "19", "[iə]", "이어", "36", "[tʃ]", "취"],
            ["3", "[æ]", "애", "20", "[eə]", "에어", "37", "[dʒ]", "쥬(쥐)"],
            ["4", "[i]", "이", "21", "[uə]", "우어", "38", "[h]", "흐"],
            ["5", "[ɔ]", "오", "22", "[p]", "프", "39", "[r]", "ㄹ (굴림)"],
            ["6", "[u]", "우", "23", "[b]", "브", "40", "[m]", "ㅁ"],
            ["7", "[ə]", "어", "24", "[t]", "트", "41", "[n]", "ㄴ"],
            ["8", "[ʌ]", "어(강)", "25", "[d]", "드", "42", "[ŋ]", "응"],
            ["9", "[a:]", "아:", "26", "[k]", "크", "43", "[l]", "ㄹ (닿음)"],
            ["10", "[i:]", "이:", "27", "[g]", "그", "44", "[j]", "이(반모음)"],
            ["11", "[ɔ:]", "오:", "28", "[f]", "프", "45", "[w]", "우(반모음)"],
            ["12", "[u:]", "우:", "29", "[v]", "브", "46", "[wa]", "와"],
            ["13", "[ə:]", "어:", "30", "[θ]", "쓰(번데기)", "47", "[wɔ]", "워"],
            ["14", "[ai]", "아이", "31", "[ð]", "드(꼬리)", "48", "[ju]", "유"],
            ["15", "[ei]", "에이", "32", "[s]", "스", "49", "[dʒa]", "쟈"],
            ["16", "[au]", "아우", "33", "[z]", "즈", "50", "[tʃa]", "챠"],
            ["17", "[ɔi]", "오이", "34", "[ʃ]", "쉬", "-", "-", "-"]
        ]
        render_mobile_table(headers, data)
        
        st.divider()
        st.subheader("🧩 영어의 8품사")
        st.markdown("""
        단어들을 역할과 기능에 따라 8가지로 분류한 '재료'입니다.
        1. **명사 (Noun)** : 사람, 사물, 개념의 이름. *(apple, love, desk)*
        2. **대명사 (Pronoun)** : 명사를 대신 부르는 말. *(he, she, it, they)*
        3. **동사 (Verb)** : 동작이나 상태 (~다). *(run, eat, is)*
        4. **형용사 (Adjective)** : 명사의 상태를 꾸며줌 (~한). *(pretty, happy)*
        5. **부사 (Adverb)** : 동사나 형용사를 꾸며줌 (~하게). *(quickly, very)*
        6. **전치사 (Preposition)** : 명사 앞에 붙어 시간/장소를 나타냄. *(in, on, at)*
        7. **접속사 (Conjunction)** : 단어나 문장을 연결하는 접착제. *(and, but, because)*
        8. **감탄사 (Interjection)** : 감정 표현. *(oh, wow)*
        """)

    with tab2:
        st.subheader("🔄 핵심 필수 동사표 (100+ 총망라)")
        
        st.markdown("### 1. 규칙 동사 모음 (Regular Verbs)")
        headers_reg = ["규칙 패턴", "현재(V)", "과거(V-ed)", "과거분사(p.p)", "뜻"]
        data_reg = [
            ["일반 (+ed)", "want", "wanted", "wanted", "원하다"],
            ["일반 (+ed)", "play", "played", "played", "놀다"],
            ["일반 (+ed)", "help", "helped", "helped", "돕다"],
            ["일반 (+ed)", "look", "looked", "looked", "보다"],
            ["일반 (+ed)", "call", "called", "called", "부르다"],
            ["일반 (+ed)", "ask", "asked", "asked", "묻다"],
            ["일반 (+ed)", "work", "worked", "worked", "일하다"],
            ["일반 (+ed)", "need", "needed", "needed", "필요하다"],
            ["일반 (+ed)", "seem", "seemed", "seemed", "보이다"],
            ["-e로 끝 (+d)", "use", "used", "used", "사용하다"],
            ["-e로 끝 (+d)", "agree", "agreed", "agreed", "동의하다"],
            ["-e로 끝 (+d)", "smile", "smiled", "smiled", "웃다"],
            ["-e로 끝 (+d)", "decide", "decided", "decided", "결정하다"],
            ["-e로 끝 (+d)", "hope", "hoped", "hoped", "희망하다"],
            ["자음+y 끝 (y->ied)", "try", "tried", "tried", "시도하다"],
            ["자음+y 끝 (y->ied)", "study", "studied", "studied", "공부하다"],
            ["자음+y 끝 (y->ied)", "cry", "cried", "cried", "울다"],
            ["자음+y 끝 (y->ied)", "worry", "worried", "worried", "걱정하다"],
            ["단모음+자음 (자음추가)", "stop", "stopped", "stopped", "멈추다"],
            ["단모음+자음 (자음추가)", "plan", "planned", "planned", "계획하다"],
            ["단모음+자음 (자음추가)", "drop", "dropped", "dropped", "떨어뜨리다"]
        ]
        render_mobile_table(headers_reg, data_reg)

        st.divider()

        st.markdown("### 2. 불규칙 동사 모음 (Irregular Verbs)")
        
        st.markdown("#### ① A-A-A 형 (형태가 모두 같음)")
        headers_aaa = ["현재(V)", "과거(V-ed)", "과거분사(p.p)", "뜻"]
        data_aaa = [
            ["put", "put", "put", "놓다"],
            ["cut", "cut", "cut", "자르다"],
            ["read", "read(레드)", "read(레드)", "읽다"],
            ["hit", "hit", "hit", "치다"],
            ["set", "set", "set", "세팅하다"],
            ["let", "let", "let", "허락하다"],
            ["cost", "cost", "cost", "비용이 들다"],
            ["shut", "shut", "shut", "닫다"],
            ["hurt", "hurt", "hurt", "다치다"],
            ["quit", "quit", "quit", "그만두다"]
        ]
        render_mobile_table(headers_aaa, data_aaa)

        st.markdown("#### ② A-B-A 형 (현재와 과거분사가 같음)")
        headers_aba = ["현재(V)", "과거(V-ed)", "과거분사(p.p)", "뜻"]
        data_aba = [
            ["come", "came", "come", "오다"],
            ["run", "ran", "run", "달리다"],
            ["become", "became", "become", "~이 되다"],
            ["overcome", "overcame", "overcome", "극복하다"]
        ]
        render_mobile_table(headers_aba, data_aba)

        st.markdown("#### ③ A-B-B 형 (과거와 과거분사가 같음)")
        headers_abb = ["현재(V)", "과거(V-ed)", "과거분사(p.p)", "뜻"]
        data_abb = [
            ["buy", "bought", "bought", "사다"],
            ["catch", "caught", "caught", "잡다"],
            ["feel", "felt", "felt", "느끼다"],
            ["find", "found", "found", "찾다"],
            ["have", "had", "had", "가지다"],
            ["make", "made", "made", "만들다"],
            ["say", "said", "said", "말하다"],
            ["teach", "taught", "taught", "가르치다"],
            ["keep", "kept", "kept", "유지하다"],
            ["sleep", "slept", "slept", "자다"],
            ["leave", "left", "left", "떠나다"],
            ["meet", "met", "met", "만나다"],
            ["bring", "brought", "brought", "가져오다"],
            ["think", "thought", "thought", "생각하다"],
            ["fight", "fought", "fought", "싸우다"],
            ["build", "built", "built", "짓다"],
            ["spend", "spent", "spent", "소비하다"],
            ["lose", "lost", "lost", "잃다"],
            ["win", "won", "won", "이기다"],
            ["sell", "sold", "sold", "팔다"],
            ["tell", "told", "told", "말하다"],
            ["hear", "heard", "heard", "듣다"],
            ["hold", "held", "held", "잡다"],
            ["stand", "stood", "stood", "서다"],
            ["understand", "understood", "understood", "이해하다"]
        ]
        render_mobile_table(headers_abb, data_abb)

        st.markdown("#### ④ A-B-C 형 (3개가 모두 다름)")
        headers_abc = ["현재(V)", "과거(V-ed)", "과거분사(p.p)", "뜻"]
        data_abc = [
            ["be(am/is/are)", "was/were", "been", "이다, 있다"],
            ["begin", "began", "begun", "시작하다"],
            ["break", "broke", "broken", "깨다"],
            ["do", "did", "done", "하다"],
            ["eat", "ate", "eaten", "먹다"],
            ["go", "went", "gone", "가다"],
            ["know", "knew", "known", "알다"],
            ["see", "saw", "seen", "보다"],
            ["take", "took", "taken", "가져가다"],
            ["write", "wrote", "written", "쓰다"],
            ["drive", "drove", "driven", "운전하다"],
            ["ride", "rode", "ridden", "타다"],
            ["speak", "spoke", "spoken", "말하다"],
            ["steal", "stole", "stolen", "훔치다"],
            ["choose", "chose", "chosen", "선택하다"],
            ["wake", "woke", "woken", "깨다"],
            ["wear", "wore", "worn", "입다"],
            ["fly", "flew", "flown", "날다"],
            ["grow", "grew", "grown", "자라다"],
            ["throw", "threw", "thrown", "던지다"],
            ["draw", "drew", "drawn", "그리다"],
            ["show", "showed", "shown", "보여주다"],
            ["fall", "fell", "fallen", "떨어지다"],
            ["hide", "hid", "hidden", "숨다"],
            ["bite", "bit", "bitten", "물다"]
        ]
        render_mobile_table(headers_abc, data_abc)

    with tab3:
        st.subheader("🌱 기초 구문 (명사, 대명사, 전치사)")
        st.markdown("""
        **■ 1. 가산명사 vs 불가산명사**
        * **가산명사 (셀 수 있음)**: 하나면 앞에 `a/an`, 여러 개면 뒤에 `-s`를 붙입니다. (예: `an apple`, `apples`)
        * **불가산명사 (셀 수 없음)**: 액체나 덩어리, 안보이는 개념. `a`나 `-s`를 붙일 수 없습니다. (예: `water`, `information`, `money`)

        **■ 2. 만능 단어 'it'의 3가지 쓰임**
        * **지시대명사**: 앞서 말한 그것. "Where is my book? **It** is on the desk."
        * **비인칭주어**: 시간/날씨/거리에서 자리만 채움 (해석 안함). "**It** is raining."
        * **가주어**: 진짜 주어가 길어서 뒤로 빼고 빈자리를 채움. "**It** is hard to master English."

        **■ 3. 명령문과 감탄문**
        * **명령문**: 주어를 빼고 '동사원형'으로 시작. "**Close** the door!" (부정: **Don't** run!)
        * **감탄문**: 어순을 바꿈. 
            * 명사가 있을 때: `What a(an) 형 명 주 동!` ➔ "What a beautiful flower it is!"
            * 명사가 없을 때: `How 형/부 주 동!` ➔ "How beautiful it is!"

        **■ 4. 전치사 (for vs during)**
        * **for + 숫자 기간**: 시간의 '양'을 나타냄. "I slept **for 3 hours**."
        * **during + 특정 기간 명사**: 시간의 '이름'을 나타냄. "I slept **during the class**."
        """)

    with tab4:
        st.subheader("🌿 문장과 시제 (5형식과 동사)")
        st.markdown("""
        **■ 1. 문장의 5형식 (자리가 뜻을 결정한다!)**
        * **1형식 (S+V)**: I run.
        * **2형식 (S+V+C)**: I am a student.
        * **3형식 (S+V+O)**: I love you.
        * **4형식 (S+V+O1+O2)**: I gave him a book.
        * **5형식 (S+V+O+C)**: I made him happy.

        **■ 2. 시제 (Tense) 완벽 이해**
        * **현재시제**: 지금이 아니라 '늘상 하는 습관/팩트'. "I go to school."
        * **진행형(be+ing)**: 지금 생생하게 하는 중. "I am eating."
        * **현재완료 (have+p.p)**: 과거의 일이 '현재'까지 영향을 미칠 때. 
            * *현재완료*: I **have lost** my key. (과거에 잃어버려서 ➔ 지금 내 손에 없다!)

        **■ 3. 조동사 (추측/의무/used to)**
        * **추측**: must (99% 확신), may (50%), cannot (~일 리 없다)
        * **의무**: must / have to (강제), should (부드러운 조언)
        * **used to**: 과거엔 했지만 '지금은 절대 안 해!'라는 뉘앙스. "I used to smoke."
        """)

    with tab5:
        st.subheader("🌳 심화 문법 (길고 세련된 문장 만들기)")
        st.markdown("""
        **■ 1. 준동사 (to부정사 vs 동명사)**
        * **to부정사 (to+동사원형)**: 미래, 지향적 성향. (want, hope 뒤에 옴) "I want to study."
        * **동명사 (동사원형+ing)**: 과거, 경험 성향. (finish, enjoy 뒤에 옴) "I finished reading."

        **■ 2. 분사 (현재분사 vs 과거분사)**
        동사를 형용사로 변신시킴.
        * **현재분사 (-ing)**: 능동/진행. "a sleeping baby" (자고 있는 아기)
        * **과거분사 (p.p)**: 수동/완료. "a broken window" (누군가에 깨진 창문)

        **■ 3. 관계대명사 (who, which, that)**
        문장을 두 번 말하기 귀찮을 때, 선행사(명사) 뒤에 접착제를 붙여 문장으로 길게 설명.
        * "I saw the man **who** was running."

        **■ 4. 수동태 (be동사 + p.p)**
        주어가 행동을 '당할 때', 또는 행위자보다 당한 대상이 중요할 때 사용.
        * "My car **was stolen**."

        **■ 5. 간접의문문**
        의문문이 다른 문장 속으로 쏙 들어갈 때. 진짜 질문이 아니므로 어순이 평서문으로 바뀜.
        * 간접: I don't know **who he is**. (의문사+주어+동사)
        """)
