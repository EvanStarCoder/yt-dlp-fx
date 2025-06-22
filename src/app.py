from contextlib import asynccontextmanager
from typing import AsyncGenerator

# 不再需要 httpx 和 urllib.parse
import fastapi
import logging
from aiohttp_client_cache.session import CachedSession
from aiohttp_client_cache.backends.sqlite import SQLiteBackend
from fake_useragent import UserAgent

from .utils import fetch_post_info
# `shorten_url` 也不再需要，但保留 import 不會影響

@asynccontextmanager
async def app_lifespan(app: fastapi.FastAPI) -> AsyncGenerator[None, None]:
    app.state.client = CachedSession(
        cache=SQLiteBackend(cache_name="cache.db", expire_after=3600),
    )
    try:
        yield
    finally:
        await app.state.client.close()


ua = UserAgent()
logger = logging.getLogger("uvicorn")
app = fastapi.FastAPI(lifespan=app_lifespan)


@app.get("/")
def index() -> fastapi.responses.RedirectResponse:
    return fastapi.responses.RedirectResponse("https://huannago.com")


async def embed_fixer(request: fastapi.Request, url: str) -> fastapi.responses.Response:
    if "Discordbot" not in request.headers.get("User-Agent", ""):
        return fastapi.responses.RedirectResponse(url)

    try:
        post = await fetch_post_info(app.state.client, url=url)
    except Exception:
        logger.exception(f"Error fetching post info")
        return fastapi.responses.RedirectResponse(url)

    if post.error or not post.downloads:
        logger.error(f"Failed to get post info: {post}")
        return fastapi.responses.RedirectResponse(url)
    
    # 選擇一個高畫質的下載連結
    download = next(
        (d for d in post.downloads if d.ext == "mp4" and "hd" in d.format_id.lower()), 
        post.downloads[0] # 如果沒有hd，就用第一個
    )
    
    # 【核心修改】直接使用從 yt-dlp 獲取的原始影片連結
    video_url = download.url
    logger.info(f"Direct Video URL: {video_url[:100]}...") # 只印出前100個字元
    print(f"Video URL: {video_url}")
    html = f"""
    <html>
    <head>
        <meta property="charset" content="utf-8">
        <meta property="theme-color" content="#395898">
        <meta property="og:title" content="{post.description or 'Facebook Video'}">
        <meta property="og:type" content="video">
        <meta property="og:site_name" content="Facebook Reels">
        <meta property="og:url" content="{post.source}">
        <meta property="og:video" content="{video_url}">
        <meta property="og:video:secure_url" content="{video_url}">
        <meta property="og:video:type" content="video/mp4">
        <meta property="og:video:width" content="1280">
        <meta property="og:video:height" content="720">
    </head>
    </html>
    """
    return fastapi.responses.HTMLResponse(html)

# ----- 我們不再需要 /proxy 代理端點，將其完全移除 -----

# ----- 所有路由端點保持不變，它們都呼叫 embed_fixer -----

@app.get("/share/r/{reel_id}")
async def share_reel(
    request: fastapi.Request, reel_id: str
) -> fastapi.responses.Response:
    url = f"https://www.facebook.com/share/r/{reel_id}"
    return await embed_fixer(request, url)


@app.get("/reel/{reel_id}")
async def reel(request: fastapi.Request, reel_id: str) -> fastapi.responses.Response:
    url = f"https://www.facebook.com/reel/{reel_id}"
    return await embed_fixer(request, url)


@app.get("/share/v/{video_id}")
async def share_video(
    request: fastapi.Request, video_id: str
) -> fastapi.responses.Response:
    async with app.state.client.get(
        f"https://www.facebook.com/share/v/{video_id}",
        headers={"User-Agent": ua.random},
    ) as response:
        url = str(response.url)
    logger.info(f"Final URL: {url}")
    return await embed_fixer(request, url)


@app.get("/watch")
async def watch(request: fastapi.Request) -> fastapi.responses.Response:
    params = dict(request.query_params)
    video_id = params.get("v")
    if not video_id:
        return fastapi.responses.RedirectResponse("https://www.facebook.com")
        
    url = f"https://www.facebook.com/watch/?v={video_id}"
    return await embed_fixer(request, url)