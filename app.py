import streamlit as st
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
import time

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
    st.write("🔍 제목 기반으로 관련 북마크 검색 중...")
    relevant_bookmarks = find_relevant_bookmarks(question, bookmarks)
    
    if not relevant_bookmarks:
        st.warning("❌ 질문과 관련된 북마크를 찾을 수 없습니다.")
        return None
    
    # 2단계: 관련 북마크 목록 표시
    st.success(f"✅ {len(relevant_bookmarks)}개의 관련 북마크를 찾았습니다!")
    
    # 3단계: 각 북마크의 내용 수집
    st.write("📑 북마크 내용을 수집하는 중...")
    progress_bar = st.progress(0)
    status_container = st.empty()
    
    combined_info = ""
    for idx, bookmark in enumerate(relevant_bookmarks):
        progress = (idx + 1) / len(relevant_bookmarks)
        progress_bar.progress(progress)
        status_container.write(f"🌐 처리 중: {bookmark['title']}")
        
        content = fetch_webpage_content(bookmark['url'], status_container)
        combined_info += f"[{bookmark['title']}]({bookmark['url']}): {content[:1000]}\n"
        time.sleep(0.5)  # UI 업데이트를 볼 수 있도록 약간의 지연 추가
    
    progress_bar.empty()
    status_container.empty()
    
    # 4단계: Gemini를 통한 최종 분석
    st.write("🤖 Gemini가 북마크 내용을 분석하는 중...")
    
    prompt = f"""
    사용자의 질문: "{question}"

    아래는 북마크에 저장된 웹페이지 정보입니다.
    사용자의 질문과 가장 관련 있는 URL들을 설명과 함께 추천해주세요.

    {combined_info}
    """

    response = model.generate_content(prompt)
    return response.text

st.set_page_config(page_title="북마크 기반 검색 챗봇", layout="wide")

st.title("🔖 북마크 검색 챗봇")
st.markdown("Chrome에서 내보낸 북마크 HTML 파일을 업로드하고, 원하는 정보를 가진 URL을 찾아보세요.")
st.markdown("---")

uploaded_file = st.file_uploader("📁 북마크 HTML 파일 업로드", type=["html"])

if uploaded_file:
    bookmarks = parse_bookmark_html(uploaded_file.getvalue().decode("utf-8"))
    st.success(f"✅ 파일이 업로드되었습니다. (총 {len(bookmarks)}개의 북마크)")
    
    question = st.text_input("💬 어떤 정보를 찾고 싶으신가요?")
    if question and bookmarks:
        with st.spinner("🔎 북마크를 검색하고 분석하는 중..."):
            answer = search_question_in_bookmarks(question, bookmarks)
            if answer:
                st.markdown("---")
                st.subheader("📎 검색 결과")
                st.markdown(answer, unsafe_allow_html=True)
else:
    st.warning("Chrome 북마크 HTML 파일을 업로드해주세요.")
