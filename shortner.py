from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
import shortuuid
import sqlite3
from contextlib import contextmanager
from starlette.requests import Request

app = FastAPI()

DATABASE_URL = 'url_shortener.db'

async def log_requests(request: Request, call_next):
    id = request.headers.get("X-Request-ID", "Unknown")
    logger.info(f"Starting request {request.method} {request.url} ID: {id}")
    response = await call_next(request)
    logger.info(f"Request {request.method} {request.url} completed with status code {response.status_code}")
    return response
    

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def get_db_cursor(commit=False):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            if commit:
                conn.commit()
        finally:
            cursor.close()

def create_tables():
    with get_db_cursor(commit=True) as cursor:
        create_table = '''
        CREATE TABLE IF NOT EXISTS urlshortener(
            original_url VARCHAR,
            short_slug VARCHAR UNIQUE,
            short_url VARCHAR
        );
        '''
        cursor.execute(create_table)

# 데이터베이스 테이블을 앱 시작 시 생성
create_tables()

@app.get("/")
async def health_check():
    return {"message": "우리가게 정상영업합니다"}

@app.post("/", status_code=status.HTTP_201_CREATED)
async def create_short_url(url: str):
    if not url.startswith("http://") and not url.startswith("https://"):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": "Invalid URL format"})

    with get_db_cursor(commit=True) as cursor:
        cursor.execute("SELECT short_slug FROM urlshortener WHERE original_url = ?", (url,))
        existing_slug = cursor.fetchone()

        if existing_slug:
            short_slug = existing_slug[0]
            short_url = f"http://127.0.0.1:8000/{short_slug}"
            return JSONResponse(status_code=status.HTTP_200_OK, content={"original_url": url, "short_slug": short_slug, "short_url": short_url})

        short_slug = shortuuid.uuid()[:6]
        short_url = f"http://127.0.0.1:8000/{short_slug}"
        cursor.execute("INSERT INTO urlshortener (original_url, short_slug, short_url) VALUES (?, ?, ?)", (url, short_slug, short_url))

    return {"original_url": url, "short_slug": short_slug, "short_url": short_url}

@app.get("/{short_slug}", status_code=status.HTTP_308_PERMANENT_REDIRECT)
async def redirect_short_url(short_slug: str):
    with get_db_cursor() as cursor:
        cursor.execute("SELECT original_url FROM urlshortener WHERE short_slug = ?", (short_slug,))
        original_url = cursor.fetchone()

        if original_url:
            return RedirectResponse(url=original_url[0])
        else:
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "URL not found"})


