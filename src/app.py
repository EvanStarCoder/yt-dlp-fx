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
    
    video_width = download.width or 1280
    video_height = download.height or 720

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
        <meta property="og:video:width" content="{video_width}">
        <meta property="og:video:height" content="{video_height}">
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

# --- 【在這裡貼上新的程式碼】 ---
@app.get("/share/p/{post_id}")
async def share_post(request: fastapi.Request, post_id: str) -> fastapi.responses.Response:
    """
    處理像 facebook.com/share/p/xxx 這種格式的一般貼文連結。
    """
    # 注意：Facebook 的分享連結通常最後會帶一個斜線
    url = f"https://www.facebook.com/share/p/{post_id}/"
    logger.info(f"Handling /share/p/ link: {url}")
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

# --- 【在這裡貼上新的程式碼】 ---
@app.get("/videos/{video_id}")
async def videos(request: fastapi.Request, video_id: str) -> fastapi.responses.Response:
    """
    處理像 facebook.com/xxx/videos/xxx 這種格式的連結。
    我們其實只需要影片 ID 就夠了。
    """
    url = f"https://www.facebook.com/videos/{video_id}"
    logger.info(f"Handling /videos/ link: {url}")
    return await embed_fixer(request, url)

# 如果您想要完全匹配 facebook.com/{user_name}/videos/{video_id} 格式，也可以用下面這個更精確的版本
@app.get("/{user_name}/videos/{video_id}")
async def user_videos(
    request: fastapi.Request, user_name: str, video_id: str
) -> fastapi.responses.Response:
    """
    處理 facebook.com/{user_name}/videos/{video_id} 格式的連結。
    """
    url = f"https://www.facebook.com/{user_name}/videos/{video_id}"
    logger.info(f"Handling /{user_name}/videos/ link: {url}")
    return await embed_fixer(request, url)