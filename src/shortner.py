'''
biggest contribution : Chat gpt 4 the goat of ai
'''

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
import shortuuid
import sqlite3
from contextlib import contextmanager

app = FastAPI() #fastapi 인스턴스 정의

DATABASE_URL = 'url_shortener.db' #데이터베이스 경로 지정(/root/url_shortener.db)

class UrlData(BaseModel): #문자열 검증을 위해 사용된 pydantic
    url: str

# 데이터베이스 연결을 관리하기 위해 contextmanager를 정의함
@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)  # SQLite 데이터베이스 연결
    try:
        yield conn
    finally:
        conn.close()

#위 contextmanager를 위한 커서
@contextmanager
def get_db_cursor(commit=False):
    with get_db_connection() as conn: # 데이터베이스 연결 생성
        cursor = conn.cursor()
        try:
            yield cursor
            if commit:
                conn.commit()
        finally:
            cursor.close()

#original url, short slug, short url 세개의 콜론이 있는 데이터베이스를 생성
def create_tables():
    with get_db_cursor(commit=True) as cursor:
        create_table = '''
        CREATE TABLE IF NOT EXISTS urlshortener(
            original_url VARCHAR,
            short_slug VARCHAR UNIQUE,
            short_url VARCHAR
        );
        '''
        cursor.execute(create_table) #커서가 만들어줌

create_tables()#위 함수 실행

#healthcheck를 통과하기 위해 우리 코드가 정상 영업중임을 알림
@app.get("/")
async def health_check():
    return {"message": "우리 코드 정상영업합니다"}

# 새로운 단축 URL 생성을 위한 POST 요청 처리
@app.post("/", status_code=status.HTTP_201_CREATED)
async def create_short_url(url_data: UrlData):
    url = url_data.url #요청에서 url 입력받기
    if not url.startswith("http://") and not url.startswith("https://"): #url 형식이 이상하면 400 badrequest 반환
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": "Invalid URL format"})

    with get_db_cursor(commit=True) as cursor:
        cursor.execute("SELECT short_slug FROM urlshortener WHERE original_url = ?", (url,))
        existing_slug = cursor.fetchone()

        # 기존에 단축된 URL이 있는지 데이터베이스에서 확인

        if existing_slug: 
            short_slug = existing_slug[0]
            short_url = f"http://127.0.0.1:8000/{short_slug}" # 이미 존재하는 단축 URL 정보 반환
            return JSONResponse(status_code=status.HTTP_200_OK, content={"original_url": url, "short_slug": short_slug, "short_url": short_url}) #200과 데이터를 리턴

        short_slug = shortuuid.uuid()[:6] # 새로운 단축 URL 생성 및 데이터베이스 삽입
        short_url = f"http://127.0.0.1:8000/{short_slug}"
        cursor.execute("INSERT INTO urlshortener (original_url, short_slug, short_url) VALUES (?, ?, ?)", (url, short_slug, short_url))

    # 생성된 단축 URL 정보 반환
    return {"original_url": url, "short_slug": short_slug, "short_url": short_url}

#단축된 url을 원본으로 리디렉션 하는 요청을 처리해줌
@app.get("/{short_slug}", status_code=status.HTTP_308_PERMANENT_REDIRECT)
async def redirect_short_url(short_slug: str):
    with get_db_cursor() as cursor:
        cursor.execute("SELECT original_url FROM urlshortener WHERE short_slug = ?", (short_slug,))
        original_url = cursor.fetchone()
        # 단축 슬러그를 기준으로 원본 URL 검색

        if original_url:
            return RedirectResponse(url=original_url[0]) #있는거면 원본 리디렉션
        else:
            # 없으면 오류반환
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "URL not found"})



