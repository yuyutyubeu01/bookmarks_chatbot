import streamlit as st
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
import time
import random

# 페이지 설정
st.set_page_config(
    page_title="북마크 검색 봇",
    page_icon="🔖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS 스타일 적용
st.markdown("""
<style>
    /* 전체 폰트 스타일 */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Noto Sans KR', sans-serif;
    }
    
    /* 메인 컨테이너 스타일 */
    .main {
        padding: 2rem;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    /* 카드 스타일 */
    .stCard {
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        padding: 1.5rem;
        margin-bottom: 1rem;
        background: white;
    }
    
    /* 버튼 스타일 */
    .stButton>button {
        border-radius: 25px;
        padding: 0.5rem 2rem;
        background: #4b6cb7;
        color: white;
        border: none;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        background: #182848;
        transform: translateY(-2px);
    }
    
    /* 프로그레스 바 스타일 */
    .stProgress > div > div {
        background-color: #4b6cb7;
    }
    
    /* 성공 메시지 스타일 */
    .success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #c3e6cb;
    }
    
    /* 경고 메시지 스타일 */
    .warning-message {
        background-color: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #ffeeba;
    }
</style>
""", unsafe_allow_html=True)

# Gemini API 설정
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

def parse_bookmark_html(file):
    soup = BeautifulSoup(file, "html.parser")
    bookmarks = []
    for link in soup.find_all("a"):
        href = link.get("href")
        title = link.text
        if href:
            bookmarks.append({"title": title, "url": href})
    return bookmarks

def fetch_webpage_content(url, progress_bar=None):
    try:
        response = requests.get(url, timeout=5)
        if response.ok and "text/html" in response.headers.get("Content-Type", ""):
            page = BeautifulSoup(response.text, "html.parser")
            return page.get_text(separator=" ", strip=True)
    except:
        if progress_bar:
            progress_bar.error(f"⚠️ {url} 접근 실패")
        return ""
    return ""

def find_relevant_bookmarks(question, bookmarks):
    # 제목 기반 관련성 확인을 위한 프롬프트
    title_prompt = f"""
    사용자 질문: "{question}"
    
    아래는 북마크 제목 목록입니다. 질문과 관련 있는 북마크의 인덱스 번호만 숫자로 나열해주세요.
    관련 있는 북마크가 없다면 "없음"이라고만 답해주세요.
    예시 답변: "1, 3, 5" 또는 "없음"
    
    북마크 목록:
    {', '.join([f"{i}. {b['title']}" for i, b in enumerate(bookmarks, 1)])}
    """
    
    response = model.generate_content(title_prompt)
    result = response.text.strip()
    
    if result.lower() == "없음":
        return []
    
    try:
        # 인덱스 번호를 파싱하여 해당하는 북마크 반환
        indices = [int(idx.strip()) for idx in result.replace(' ', '').split(',')]
        return [bookmarks[i-1] for i in indices if 0 < i <= len(bookmarks)]
    except:
        return []

def search_question_in_bookmarks(question, bookmarks):
    # 1단계: 제목 기반 관련 북마크 찾기
    with st.container():
        st.markdown("### 🔍 검색 진행 상황")
        step1 = st.empty()
        step1.info("관련 북마크를 검색 중...")
        relevant_bookmarks = find_relevant_bookmarks(question, bookmarks)
        
        if not relevant_bookmarks:
            step1.warning("❌ 질문과 관련된 북마크를 찾을 수 없습니다.")
            return None
        
        # 북마크가 30개 이상인 경우 랜덤 샘플링
        if len(relevant_bookmarks) > 30:
            original_count = len(relevant_bookmarks)
            relevant_bookmarks = random.sample(relevant_bookmarks, 30)
            step1.success(f"✅ {original_count}개의 관련 북마크 30개를 찾았습니다.")
        else:
            step1.success(f"✅ {len(relevant_bookmarks)}개의 관련 북마크를 찾았습니다!")
    
    # 2단계: 북마크 내용 수집
    with st.container():
        st.markdown("### 📑 북마크 분석")
        progress_bar = st.progress(0)
        status_container = st.empty()
        
        combined_info = ""
        for idx, bookmark in enumerate(relevant_bookmarks):
            progress = (idx + 1) / len(relevant_bookmarks)
            progress_bar.progress(progress)
            status_container.info(f"🌐 분석 중: {bookmark['title']} ({idx + 1}/{len(relevant_bookmarks)})")
            
            content = fetch_webpage_content(bookmark['url'], status_container)
            combined_info += f"[{bookmark['title']}]({bookmark['url']}): {content[:1000]}\n"
            time.sleep(0.5)
        
        progress_bar.empty()
        status_container.empty()
    
    # 3단계: Gemini 분석
    with st.container():
        st.markdown("### 🤖 AI 분석")
        analysis_status = st.empty()
        analysis_status.info("북마크 내용을 분석하는 중...")
        
        prompt = f"""
        사용자의 질문: "{question}"

        아래는 북마크에 저장된 웹페이지 정보입니다.
        사용자의 질문과 가장 관련 있는 URL들을 설명과 함께 추천해주세요.
        {f'(전체 {len(relevant_bookmarks)}개 중 랜덤 샘플링된 결과입니다)' if len(relevant_bookmarks) == 30 else ''}

        {combined_info}
        """

        response = model.generate_content(prompt)
        analysis_status.empty()
        return response.text

# 메인 UI
st.markdown('<div class="header-container">', unsafe_allow_html=True)
st.title("🔖 북마크 검색 봇")
st.markdown("매번 저장만 해서 잔뜩 쌓여있던 북마크... 이제 원하는 정보를 가진 북마크만 쉽게 찾아보세요!")
st.markdown('</div>', unsafe_allow_html=True)

# 파일 업로드 섹션
with st.container():
    uploaded_file = st.file_uploader("📁 북마크 파일 업로드", type=["html"])

if uploaded_file:
    bookmarks = parse_bookmark_html(uploaded_file.getvalue().decode("utf-8"))
    st.markdown(f'<div class="success-message">✅ 파일이 업로드되었습니다. (총 {len(bookmarks)}개의 북마크)</div>', unsafe_allow_html=True)
    
    # 검색 섹션
    with st.container():
        question = st.text_input("💬 어떤 정보를 찾고 싶으신가요?", 
                               placeholder="예: 파이썬 웹 개발 관련 자료를 찾아줘")
        if question and bookmarks:
            with st.spinner("🔎 북마크를 검색하고 분석하는 중..."):
                answer = search_question_in_bookmarks(question, bookmarks)
                if answer:
                    st.markdown("---")
                    st.markdown('<div class="stCard">', unsafe_allow_html=True)
                    st.subheader("📎 검색 결과")
                    st.markdown(answer, unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="warning-message">Chrome 북마크 파일을 업로드해주세요.</div>', unsafe_allow_html=True)
