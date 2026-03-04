import streamlit as st
import google.generativeai as genai
import pandas as pd
from gtts import gTTS
import base64
import os
import re
from datetime import datetime

# ==========================================
# 🔑 제미나이 API 키 설정
GEMINI_API_KEY = "AIzaSyAmZ1aHJ0d9TJoabKY7Mn5zAhZiAH3UlSo"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash') 
# ==========================================

# 파일 경로 설정
VOCAB_FILE = 'my_vocab_web.csv'

# 데이터 로드/저장 함수
def load_data():
    if os.path.exists(VOCAB_FILE):
        return pd.read_csv(VOCAB_FILE)
    return pd.DataFrame(columns=['Word', 'Phonetic', 'Meaning', 'Example', 'Date', 'Status', 'Category', 'Level'])

def save_data(df):
    df.to_csv(VOCAB_FILE, index=False, encoding='utf-8-sig')

# TTS 음성 생성 함수 (HTML 오디오 태그 활용)
def speak(text):
    pure_text = text.split('[')[0].strip()
    tts = gTTS(text=pure_text, lang='en')
    tts.save("temp.mp3")
    with open("temp.mp3", "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        md = f"""
            <audio autoplay="true">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)

# 메인 UI 설정
st.set_page_config(page_title="AI 영단어 마스터", layout="centered")
st.title("🦉 AI 영단어 마스터 Web")

# 사이드바 메뉴 (모바일에서는 왼쪽 상단 화살표 누르면 나옴)
menu = st.sidebar.selectbox("메뉴 선택", ["🤖 AI 단어 생성", "✨ 단어 일괄 추가", "📖 단어 관리", "📅 학습 기록", "📝 실전 테스트", "📊 학습 통계"])

df = load_data()

# ----------------- 🤖 AI 단어 생성 -----------------
if menu == "🤖 AI 단어 생성":
    st.header("🤖 AI 맞춤 자동 생성")
    category = st.selectbox("학습 목표", ["일반 생활 영단어", "경찰 공무원 영단어", "토익 (TOEIC) 영단어"])
    level = st.select_slider("난이도", options=["초급 (기초 필수)", "중급 (빈출 핵심)", "고급 (고득점 변별력)"])
    count = st.number_input("생성 개수", min_value=1, max_value=50, value=10)

    if st.button("🚀 단어 생성 시작"):
        existing_words = ", ".join(df['Word'].tolist())
        prompt = f"""
        분야: {category} / 난이도: {level} / {count}개 생성.
        중복 제외: {existing_words}
        규칙: 강세 기호 생략, 장음은 : 사용.
        형식: 영단어;[발음기호];품사 : 뜻;실전 예문
        """
        
        with st.spinner("AI가 단어를 고르고 있습니다..."):
            response = model.generate_content(prompt)
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
            
            new_df = pd.DataFrame(new_rows)
            df = pd.concat([df, new_df], ignore_index=True).drop_duplicates('Word')
            save_data(df)
            st.success(f"{len(new_rows)}개의 단어가 추가되었습니다!")

# ----------------- 📖 단어 관리 (학습 중) -----------------
elif menu == "📖 단어 관리":
    st.header("📖 학습 중인 단어")
    view_df = df[df['Status'] == 'Learning'].sort_values('Date', ascending=False)
    
    if view_df.empty:
        st.info("학습 중인 단어가 없습니다.")
    else:
        # 체크박스 선택 시스템 (Streamlit 전용)
        selected_indices = st.multiselect("학습 완료/삭제할 단어 선택", view_df.index, format_func=lambda x: f"{view_df.loc[x, 'Word']} - {view_df.loc[x, 'Meaning']}")
        
        col1, col2, col3 = st.columns(3)
        if col1.button("✅ 학습 완료"):
            df.loc[selected_indices, 'Status'] = 'Completed'
            save_data(df)
            st.rerun()
        
        if col2.button("🔊 발음 듣기") and selected_indices:
            speak(df.loc[selected_indices[0], 'Word']) # 첫 번째 단어 재생

        if col3.button("🗑️ 삭제"):
            df = df.drop(selected_indices)
            save_data(df)
            st.rerun()

        st.divider()
        for idx, row in view_df.iterrows():
            with st.expander(f"**{row['Word']}** {row['Phonetic']} | {row['Meaning']}"):
                st.write(f"📅 추가일: {row['Date']}")
                st.markdown(f"📝 **예문:** {row['Example'].replace(row['Word'], f'**:green[{row['Word']}]**')}")
                if st.button(f"🔊 듣기", key=f"btn_{row['Word']}"):
                    speak(row['Word'])

# ----------------- 📝 실전 테스트 -----------------
elif menu == "📝 실전 테스트":
    st.header("📝 실전 랜덤 테스트")
    test_pool = df[df['Status'] == 'Learning']
    
    if test_pool.empty:
        st.warning("테스트할 단어가 없습니다.")
    else:
        if 'test_word' not in st.session_state:
            st.session_state.test_word = test_pool.sample(1).iloc[0]
            st.session_state.test_mode = random.choice(['E2K', 'K2E'])

        word_info = st.session_state.test_word
        
        if st.session_state.test_mode == 'E2K':
            st.subheader(f"Q: {word_info['Word']}")
            st.write(word_info['Phonetic'])
        else:
            st.subheader(f"Q: {word_info['Meaning']}")

        ans = st.text_input("정답 입력")
        
        if st.button("제출"):
            correct = False
            if st.session_state.test_mode == 'E2K':
                if ans in word_info['Meaning']: correct = True
            else:
                if ans.lower() == word_info['Word'].lower(): correct = True
            
            if correct:
                st.success("✅ 정답입니다!")
                speak(word_info['Word'])
            else:
                st.error(f"❌ 틀렸습니다. 정답: {word_info['Word']} | {word_info['Meaning']}")
            
            st.info(f"💡 예문: {word_info['Example']}")
            if st.button("다음 문제"):
                del st.session_state.test_word
                st.rerun()

# ----------------- 기타 메뉴는 기존 로직을 Streamlit 방식으로 구현 가능 -----------------
else:
    st.write("나머지 메뉴(학습 기록, 통계 등)도 동일한 방식으로 구현됩니다.")