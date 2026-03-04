import streamlit as st
import google.generativeai as genai
import pandas as pd
from gtts import gTTS
import base64
import os
import re
import random
import json
from datetime import datetime
import streamlit.components.v1 as components

# ==========================================
# 🔑 제미나이 API 키 설정
GEMINI_API_KEY = "AIzaSyDkkGaVQAz66GB94QCd9vuYQZEddfCJvl0"
genai.configure(api_key=GEMINI_API_KEY)
# ==========================================

# 💡 구글 서버 자동 탐지 시스템
def get_ai_response(prompt):
    models_to_try = ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-flash-8b', 'gemini-pro']
    last_error = None
    for model_name in models_to_try:
        try:
            target_model = genai.GenerativeModel(model_name)
            return target_model.generate_content(prompt)
        except Exception as e:
            last_error = e
            continue 
    raise Exception(f"모든 AI 모델 접근 실패. (마지막 에러: {last_error})")

VOCAB_FILE = 'my_vocab_web.csv'
WRONG_FILE = 'my_vocab_wrong_web.csv' # 🔥 오답노트 파일

def load_data(file_path):
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return pd.DataFrame(columns=['Word', 'Phonetic', 'Meaning', 'Example', 'Date', 'Status', 'Category', 'Level'])

def save_data(df, file_path):
    df.to_csv(file_path, index=False, encoding='utf-8-sig')

# ⭐️ 1. 사운드바를 없애고 보이지 않게 바로 재생되도록 수정
def speak(text):
    pure_text = text.split('[')[0].strip()
    try:
        tts = gTTS(text=pure_text, lang='en')
        tts.save("temp.mp3")
        with open("temp.mp3", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            # controls 속성을 제거하여 플레이어가 화면에 보이지 않고 즉시 재생만 됨!
            audio_tag = f'<audio autoplay><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
            st.markdown(audio_tag, unsafe_allow_html=True)
    except Exception:
        pass 

# ⭐️ 2. 정밀한 간격(1초, 2.3초)을 맞추기 위한 자바스크립트 연동 연속 듣기
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
                    setTimeout(playNext, 1000); // 같은 단어 3번 반복 사이 1초 대기
                }} else {{
                    playCount = 0;
                    currentWordIdx++;
                    setTimeout(playNext, 2300); // 다음 단어로 넘어가기 전 2.3초 대기
                }}
            }};
        }}
        playNext();
    </script>
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

# ⭐️ 3. 요청하신 순서대로 메뉴 재배치
menu = st.sidebar.selectbox("메뉴 선택", [
    "🤖 AI 단어 생성", 
    "✨ 단어 일괄 추가", 
    "📖 단어 관리", 
    "📝 실전 테스트", 
    "🔥 오답 노트 재도전", 
    "📚 영어 기초 가이드", 
    "📅 학습 기록", 
    "📊 학습 통계"
])

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
        prompt = f"""
        당신은 1타 영어 강사입니다.
        분야: {category} / 난이도: {level} / {count}개 생성.
        중복 제외: {existing_words}
        [초강력 중요 규칙]
        1. 번호나 리스트 표시 절대 금지.
        2. 영단어에 절대 ** 기호 금지.
        3. 발음 기호 폰트 깨짐 방지: 강세(ˈ, ˌ) 완전 생략, 장음(ː)은 일반 콜론(:) 사용.
        4. 품사와 뜻 통합: '품사 : 뜻' 형태.
        [형식]: 영단어;[발음기호];품사 : 뜻;실전 예문
        """
        with st.spinner("AI가 단어를 생성 중입니다..."):
            try:
                response = get_ai_response(prompt)
                lines = response.text.strip().split('\n')
                new_rows = []
                for line in lines:
                    parts = line.split(';')
                    if len(parts) >= 4:
                        eng = re.sub(r'^[\d\.\)]+\s*', '', parts[0].replace('*', '').strip())
                        new_rows.append({
                            'Word': eng, 'Phonetic': parts[1].strip(), 'Meaning': parts[2].strip(),
                            'Example': parts[3].strip(), 'Date': datetime.now().strftime("%Y-%m-%d"),
                            'Status': 'Learning', 'Category': category, 'Level': level
                        })
                if new_rows:
                    new_df = pd.DataFrame(new_rows)
                    df = pd.concat([df, new_df], ignore_index=True).drop_duplicates('Word')
                    save_data(df, VOCAB_FILE)
                    st.success(f"🎉 {len(new_rows)}개의 단어가 추가되었습니다!")
            except Exception as e:
                st.error(f"❌ 생성 오류: {e}")

# ----------------- ✨ 수동 일괄 추가 -----------------
elif menu == "✨ 단어 일괄 추가":
    st.header("✨ 단어 일괄 추가")
    words_input = st.text_area("단어를 쉼표(,)로 구분해 입력하세요.")
    if st.button("✅ 분석 및 추가"):
        if words_input:
            prompt = f"단어: {words_input}\n[형식]: 영단어;[발음기호];품사 : 뜻;실전 예문 (강세기호 생략, 번호 금지)"
            with st.spinner("분석 중..."):
                try:
                    response = get_ai_response(prompt)
                    lines = response.text.strip().split('\n')
                    new_rows = []
                    for line in lines:
                        parts = line.split(';')
                        if len(parts) >= 4:
                            eng = re.sub(r'^[\d\.\)]+\s*', '', parts[0].replace('*', '').strip())
                            new_rows.append({
                                'Word': eng, 'Phonetic': parts[1].strip(), 'Meaning': parts[2].strip(),
                                'Example': parts[3].strip(), 'Date': datetime.now().strftime("%Y-%m-%d"),
                                'Status': 'Learning', 'Category': '수동 추가', 'Level': '-'
                            })
                    if new_rows:
                        new_df = pd.DataFrame(new_rows)
                        df = pd.concat([df, new_df], ignore_index=True).drop_duplicates('Word')
                        save_data(df, VOCAB_FILE)
                        st.success("추가 완료!")
                except Exception as e:
                    st.error(f"❌ 오류: {e}")

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
            play_sequence_audio(words_to_play) # ⭐️ 3회 반복 및 대기시간 적용된 함수
            
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
                st.markdown(f"📝 **예문:** {row['Example'].replace(row['Word'], f'**:green[{row['Word']}]**')}")
                
                c1, c2, c3 = st.columns(3)
                if c1.button("🔊 듣기", key=f"btn_{idx}"):
                    speak(row['Word']) # ⭐️ 사운드바 없이 소리만 나옴
                    
                if menu == "📖 단어 관리":
                    if c2.button("✅ 학습 완료", key=f"done_{idx}"):
                        df.loc[idx, 'Status'] = 'Completed'
                        save_data(df, VOCAB_FILE)
                        st.rerun()
                else:
                    if c2.button("⏪ 다시 학습", key=f"relearn_{idx}"):
                        df.loc[idx, 'Status'] = 'Learning'
                        save_data(df, VOCAB_FILE)
                        st.rerun()
                        
                if c3.button("🗑️ 삭제", key=f"del_{idx}"):
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
            st.success("🎉 오답 노트가 비어있습니다! 모든 문제를 완벽히 마스터하셨네요!")
        else:
            st.warning("테스트할 단어가 없습니다.")
    else:
        # ⭐️ 4. 엔터키 한방에 다음문제로 넘어가는 초고속 테스트 로직
        if 'test_menu' not in st.session_state or st.session_state.test_menu != menu:
            st.session_state.test_menu = menu
            st.session_state.prev_result = None
            st.session_state.test_word = current_pool.sample(1).iloc[0]
            st.session_state.test_mode = random.choice(['E2K', 'K2E'])

        # 방금 푼 문제의 결과 및 예문 상단 표시 (입력칸은 비워져 있음)
        if st.session_state.prev_result:
            res = st.session_state.prev_result
            if res['correct']:
                st.success(f"✅ 이전 문제 정답! ({res['word']} : {res['meaning']})")
            else:
                st.error(f"❌ 이전 문제 오답... 정답: **{res['word']}** | {res['meaning']} (내 입력: {res['user_ans']})")
            st.info(f"💡 예문: {res['example']}")
            speak(res['word']) # 방금 푼 단어 발음 자동재생

        st.divider()

        # 현재 풀어야 할 새로운 문제 표시
        if 'test_word' in st.session_state:
            word_info = st.session_state.test_word

            if st.session_state.test_mode == 'E2K':
                st.subheader(f"Q: {word_info['Word']} {word_info['Phonetic']}")
                st.caption("이 단어의 뜻은?")
            else:
                st.subheader(f"Q: {word_info['Meaning']}")
                st.caption("해당하는 영어 단어는?")

            # 폼(form)을 사용하여 엔터키 입력 시 자동으로 입력칸을 비우고 제출함
            with st.form("test_form", clear_on_submit=True):
                ans = st.text_input("✍️ 정답을 입력하고 엔터(Enter)를 누르세요.")
                submitted = st.form_submit_button("제출 (엔터)")

                if submitted and ans:
                    correct = False
                    if st.session_state.test_mode == 'E2K':
                        user_stems = set(re.split(r'[,\s]+', ans))
                        correct_stems = set(re.split(r'[,\s]+', word_info['Meaning']))
                        if user_stems & correct_stems: correct = True
                    else:
                        if ans.lower() == word_info['Word'].lower(): correct = True

                    # ⭐️ 오답노트 저장 시스템
                    if correct:
                        if is_wrong_mode and word_info['Word'] in wrong_df['Word'].values:
                            wrong_df = wrong_df[wrong_df['Word'] != word_info['Word']]
                            save_data(wrong_df, WRONG_FILE)
                    else:
                        if not is_wrong_mode and word_info['Word'] not in wrong_df['Word'].values:
                            new_wrong = pd.DataFrame([word_info])
                            wrong_df = pd.concat([wrong_df, new_wrong], ignore_index=True)
                            save_data(wrong_df, WRONG_FILE)

                    # 현재 결과 저장 (다음 화면에서 상단에 띄워주기 위함)
                    st.session_state.prev_result = {
                        'correct': correct, 'word': word_info['Word'],
                        'meaning': word_info['Meaning'], 'example': word_info['Example'],
                        'user_ans': ans
                    }

                    # 즉시 새로운 문제 뽑기
                    new_pool = wrong_df if is_wrong_mode else df[df['Status'] == 'Learning']
                    if not new_pool.empty:
                        st.session_state.test_word = new_pool.sample(1).iloc[0]
                        st.session_state.test_mode = random.choice(['E2K', 'K2E'])
                    else:
                        del st.session_state.test_word
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
        st.subheader("🔄 동사 변화표 (불규칙 위주)")
        headers_v = ["패턴", "현재(V)", "과거(V-ed)", "과거분사(p.p)", "뜻"]
        data_v = [
            ["A-A-A", "put", "put", "put", "놓다"],
            ["A-A-A", "cut", "cut", "cut", "자르다"],
            ["A-A-A", "read", "read(레드)", "read(레드)", "읽다"],
            ["A-B-A", "come", "came", "come", "오다"],
            ["A-B-A", "run", "ran", "run", "달리다"],
            ["A-B-A", "become", "became", "become", "~이 되다"],
            ["A-B-B", "buy", "bought", "bought", "사다"],
            ["A-B-B", "catch", "caught", "caught", "잡다"],
            ["A-B-B", "feel", "felt", "felt", "느끼다"],
            ["A-B-B", "find", "found", "found", "찾다"],
            ["A-B-B", "have", "had", "had", "가지다"],
            ["A-B-B", "make", "made", "made", "만들다"],
            ["A-B-B", "say", "said", "said", "말하다"],
            ["A-B-B", "teach", "taught", "taught", "가르치다"],
            ["A-B-C", "be(am/is)", "was/were", "been", "이다, 있다"],
            ["A-B-C", "begin", "began", "begun", "시작하다"],
            ["A-B-C", "break", "broke", "broken", "깨다"],
            ["A-B-C", "do", "did", "done", "하다"],
            ["A-B-C", "eat", "ate", "eaten", "먹다"],
            ["A-B-C", "go", "went", "gone", "가다"],
            ["A-B-C", "know", "knew", "known", "알다"],
            ["A-B-C", "see", "saw", "seen", "보다"],
            ["A-B-C", "take", "took", "taken", "가져가다"],
            ["A-B-C", "write", "wrote", "written", "쓰다"]
        ]
        render_mobile_table(headers_v, data_v)

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
