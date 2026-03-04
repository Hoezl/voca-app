import streamlit as st
import google.generativeai as genai
import pandas as pd
from gtts import gTTS
import base64
import os
import re
import random
from datetime import datetime

# ==========================================
# 🔑 제미나이 API 키 설정
GEMINI_API_KEY = "AIzaSyDkkGaVQAz66GB94QCd9vuYQZEddfCJvl0"
genai.configure(api_key=GEMINI_API_KEY)
# ==========================================

# 💡 [최종 해결책] 구글 서버에 직접 접속 가능한 모델을 물어보고 자동 선택하는 시스템!
def get_ai_response(prompt):
    try:
        # 1. 내 API 키로 쓸 수 있는 모든 모델 목록을 구글에서 가져옵니다.
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        if not available_models:
            raise Exception("이 API 키로 텍스트를 생성할 수 있는 권한이 없습니다.")

        # 2. 가져온 목록 중 가장 가볍고 무료 할당량이 많은 '1.5-flash' 계열을 1순위로 찾습니다.
        target_model_name = None
        for name in available_models:
            if '1.5-flash' in name:
                target_model_name = name
                break
        
        # 만약 flash 모델이 없다면, 구글이 허락한 첫 번째 모델을 무조건 씁니다.
        if not target_model_name:
            target_model_name = available_models[0]

        # 3. 알아낸 정확한 이름으로 단어 생성을 지시합니다.
        target_model = genai.GenerativeModel(target_model_name)
        return target_model.generate_content(prompt)

    except Exception as e:
        raise Exception(f"AI 자동 탐지 및 생성 실패: {str(e)}")

VOCAB_FILE = 'my_vocab_web.csv'

def load_data():
    if os.path.exists(VOCAB_FILE):
        return pd.read_csv(VOCAB_FILE)
    return pd.DataFrame(columns=['Word', 'Phonetic', 'Meaning', 'Example', 'Date', 'Status', 'Category', 'Level'])

def save_data(df):
    df.to_csv(VOCAB_FILE, index=False, encoding='utf-8-sig')

def speak(text):
    pure_text = text.split('[')[0].strip()
    try:
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
    except Exception:
        pass 

st.set_page_config(page_title="AI 영단어 마스터", layout="centered")
st.title("🦉 AI 영단어 마스터 Web")

menu = st.sidebar.selectbox("메뉴 선택", ["🤖 AI 단어 생성", "✨ 단어 일괄 추가", "📖 단어 관리", "📅 학습 기록", "📝 실전 테스트", "📊 학습 통계", "📚 영어 기초 가이드"])

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
        당신은 1타 영어 강사입니다.
        분야: {category} / 난이도: {level} / {count}개 생성.
        중복 제외: {existing_words}
        [초강력 중요 규칙]
        1. 번호나 리스트 표시 절대 금지.
        2. 영단어에 절대 ** 기호 금지.
        3. 발음 기호 폰트 깨짐 방지: 특수 강세 기호(ˈ, ˌ)는 완전히 생략하고, 장음 기호(ː) 대신 일반 콜론(:)을 사용.
        4. 품사와 뜻 통합: '품사 : 뜻' 형태.
        [형식]: 영단어;[발음기호];품사 : 뜻;실전 출제 스타일 예문
        """
        
        with st.spinner("AI가 최적의 서버를 스캔하여 단어를 생성 중입니다..."):
            try:
                # 무적 탐지 함수 호출
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
                    save_data(df)
                    st.success(f"🎉 {len(new_rows)}개의 단어가 성공적으로 추가되었습니다!")
            except Exception as e:
                st.error(f"❌ 생성 중 오류가 발생했습니다.\n{e}")

# ----------------- ✨ 수동 일괄 추가 -----------------
elif menu == "✨ 단어 일괄 추가":
    st.header("✨ 단어 일괄 추가")
    words_input = st.text_area("추가할 단어들을 쉼표(,)로 구분해 입력하세요.")
    if st.button("✅ 분석 및 추가"):
        if words_input:
            prompt = f"단어: {words_input}\n[형식]: 영단어;[발음기호];품사 : 뜻;실전 예문 (강세기호 생략, 번호 금지)"
            with st.spinner("분석 중..."):
                try:
                    # 무적 탐지 함수 호출
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
                        save_data(df)
                        st.success("추가 완료!")
                except Exception as e:
                    st.error(f"❌ 분석 중 오류가 발생했습니다.\n{e}")

# ----------------- 📖 단어 관리 / 학습 기록 -----------------
elif menu in ["📖 단어 관리", "📅 학습 기록"]:
    status_filter = 'Learning' if menu == "📖 단어 관리" else 'Completed'
    st.header(menu)
    view_df = df[df['Status'] == status_filter].sort_values('Date', ascending=False)
    
    if view_df.empty:
        st.info("해당하는 단어가 없습니다.")
    else:
        selected_indices = st.multiselect("체크박스 (단어 선택)", view_df.index, format_func=lambda x: f"{view_df.loc[x, 'Word']} - {view_df.loc[x, 'Meaning']}")
        
        col1, col2, col3 = st.columns(3)
        if menu == "📖 단어 관리":
            if col1.button("✅ 학습 완료"):
                df.loc[selected_indices, 'Status'] = 'Completed'
                save_data(df)
                st.rerun()
        else:
            if col1.button("⏪ 다시 학습"):
                df.loc[selected_indices, 'Status'] = 'Learning'
                save_data(df)
                st.rerun()
                
        if col2.button("🔊 선택 발음 듣기") and selected_indices:
            speak(df.loc[selected_indices[0], 'Word']) 

        if col3.button("🗑️ 삭제"):
            df = df.drop(selected_indices)
            save_data(df)
            st.rerun()

        st.divider()
        for idx, row in view_df.iterrows():
            with st.expander(f"**{row['Word']}** {row['Phonetic']} | {row['Meaning']}"):
                st.write(f"📅 추가일: {row['Date']}")
                st.markdown(f"📝 **예문:** {row['Example'].replace(row['Word'], f'**:green[{row['Word']}]**')}")
                if st.button("🔊 듣기", key=f"btn_{row['Word']}_{idx}"):
                    speak(row['Word'])

# ----------------- 📝 실전 테스트 -----------------
elif menu == "📝 실전 테스트":
    st.header("📝 실전 랜덤 테스트")
    test_pool = df[df['Status'] == 'Learning']
    
    if test_pool.empty:
        st.warning("테스트할 단어가 없습니다. 단어를 먼저 추가해주세요.")
    else:
        if 'test_word' not in st.session_state:
            st.session_state.test_word = test_pool.sample(1).iloc[0]
            st.session_state.test_mode = random.choice(['E2K', 'K2E'])

        word_info = st.session_state.test_word
        
        if st.session_state.test_mode == 'E2K':
            st.subheader(f"Q: {word_info['Word']} {word_info['Phonetic']}")
            st.caption("이 단어의 뜻은?")
        else:
            st.subheader(f"Q: {word_info['Meaning']}")
            st.caption("해당하는 영어 단어는?")

        ans = st.text_input("정답 입력 (제출은 엔터)")
        
        if ans: 
            correct = False
            if st.session_state.test_mode == 'E2K':
                user_stems = set(re.split(r'[,\s]+', ans))
                correct_stems = set(re.split(r'[,\s]+', word_info['Meaning']))
                if user_stems & correct_stems: correct = True
            else:
                if ans.lower() == word_info['Word'].lower(): correct = True
            
            if correct:
                st.success("✅ 완벽합니다!")
            else:
                st.error(f"❌ 아쉽네요. 정답: **{word_info['Word']}** | {word_info['Meaning']}")
            
            st.info(f"💡 예문: {word_info['Example']}")
            speak(word_info['Word'])
            
            if st.button("다음 문제"):
                del st.session_state.test_word
                st.rerun()

# ----------------- 📊 학습 통계 -----------------
elif menu == "📊 학습 통계":
    st.header("📊 내 학습 통계")
    st.subheader(f"📚 전체 누적 단어: {len(df)}개")
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
        st.markdown('<div style="overflow-x: auto;">', unsafe_allow_html=True)
        st.markdown("""
        | 번호 | 발음기호 | 소리 | 번호 | 발음기호 | 소리 | 번호 | 발음기호 | 소리 |
        |---|---|---|---|---|---|---|---|---|
        | 1 | `[a]` | 아 | 18 | `[ou]` | 오우 | 35 | `[ʒ]` | 쥐 |
        | 2 | `[e]` | 에 | 19 | `[iə]` | 이어 | 36 | `[tʃ]` | 취 |
        | 3 | `[æ]` | 애 | 20 | `[eə]` | 에어 | 37 | `[dʒ]` | 쥬(쥐) |
        | 4 | `[i]` | 이 | 21 | `[uə]` | 우어 | 38 | `[h]` | 흐 |
        | 5 | `[ɔ]` | 오 | 22 | `[p]` | 프 | 39 | `[r]` | ㄹ (굴림) |
        | 6 | `[u]` | 우 | 23 | `[b]` | 브 | 40 | `[m]` | ㅁ |
        | 7 | `[ə]` | 어 | 24 | `[t]` | 트 | 41 | `[n]` | ㄴ |
        | 8 | `[ʌ]` | 어(강함) | 25 | `[d]` | 드 | 42 | `[ŋ]` | 응 |
        | 9 | `[a:]` | 아: | 26 | `[k]` | 크 | 43 | `[l]` | ㄹ (닿음) |
        | 10 | `[i:]` | 이: | 27 | `[g]` | 그 | 44 | `[j]` | 이 (반모음) |
        | 11 | `[ɔ:]` | 오: | 28 | `[f]` | 프 | 45 | `[w]` | 우 (반모음) |
        | 12 | `[u:]` | 우: | 29 | `[v]` | 브 | 46 | `[wa]` | 와 |
        | 13 | `[ə:]` | 어: | 30 | `[θ]` | 쓰 (번데기)| 47 | `[wɔ]` | 워 |
        | 14 | `[ai]` | 아이 | 31 | `[ð]` | 드 (돼지꼬리)| 48 | `[ju]` | 유 |
        | 15 | `[ei]` | 에이 | 32 | `[s]` | 스 | 49 | `[dʒa]` | 쟈 |
        | 16 | `[au]` | 아우 | 33 | `[z]` | 즈 | 50 | `[tʃa]` | 챠 |
        | 17 | `[ɔi]` | 오이 | 34 | `[ʃ]` | 쉬 | - | - | - |
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
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
        st.markdown('<div style="overflow-x: auto;">', unsafe_allow_html=True)
        st.markdown("""
        영어의 일반동사는 과거형과 완료/수동태에 쓰이는 과거분사(p.p) 형태로 변신합니다. 대부분은 `-ed`만 붙이면 되지만, 아래 불규칙 동사는 외워야 합니다.

        **① A - A - A 형 (모두 똑같음)**
        | 현재(V) | 과거(V-ed) | 과거분사(p.p) | 뜻 |
        |---|---|---|---|
        | put | put | put | 놓다 |
        | cut | cut | cut | 자르다 |
        | read | read(레드) | read(레드) | 읽다 |

        **② A - B - A 형 (현재와 p.p가 같음)**
        | 현재(V) | 과거(V-ed) | 과거분사(p.p) | 뜻 |
        |---|---|---|---|
        | come | came | come | 오다 |
        | run | ran | run | 달리다 |
        | become | became | become | ~이 되다 |

        **③ A - B - B 형 (과거와 p.p가 같음 - 가장 흔함)**
        | 현재(V) | 과거(V-ed) | 과거분사(p.p) | 뜻 |
        |---|---|---|---|
        | buy | bought | bought | 사다 |
        | catch | caught | caught | 잡다 |
        | feel | felt | felt | 느끼다 |
        | find | found | found | 찾다 |
        | have | had | had | 가지다 |
        | make | made | made | 만들다 |
        | say | said | said | 말하다 |
        | teach | taught | taught | 가르치다 |

        **④ A - B - C 형 (3개가 모두 다름)**
        | 현재(V) | 과거(V-ed) | 과거분사(p.p) | 뜻 |
        |---|---|---|---|
        | be | was/were | been | ~이다, 있다 |
        | begin | began | begun | 시작하다 |
        | break | broke | broken | 깨다 |
        | do | did | done | 하다 |
        | eat | ate | eaten | 먹다 |
        | go | went | gone | 가다 |
        | know | knew | known | 알다 |
        | see | saw | seen | 보다 |
        | take | took | taken | 가져가다 |
        | write | wrote | written | 쓰다 |
        """)
        st.markdown('</div>', unsafe_allow_html=True)

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
