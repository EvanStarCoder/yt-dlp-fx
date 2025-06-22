import asyncio
from yt_dlp import YoutubeDL
from aiohttp_client_cache.session import CachedSession

# 引入我們剛剛定義的資料結構
from .schema import PostInfo, DownloadInfo

def _extract_info_sync(url: str) -> dict:
    """
    這是一個同步函式，專門用來執行 yt-dlp 的核心抓取邏輯。
    我們把它獨立出來，以便透過 asyncio.to_thread 呼叫。
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    }
    with YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


async def fetch_post_info(client: CachedSession, *, url: str) -> PostInfo:
    """
    這是取代舊版的全新函式。
    它會非同步地執行 yt-dlp，並將結果打包成 PostInfo 物件。
    """
    try:
        # 在背景執行緒中執行同步的 _extract_info_sync 函式
        info = await asyncio.to_thread(_extract_info_sync, url)

        downloads = []
        if 'formats' in info:
            for f in info['formats']:
                # 我們只想要有影像和聲音的影片，並且有 URL
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('url'):
                    downloads.append(DownloadInfo(
                        url=f['url'],
                        ext=f.get('ext', 'mp4'),
                        format_id=f.get('format_id'),
                        width=f.get('width'),      # <-- 新增這一行
                        height=f.get('height')     # <-- 新增這一行
                    ))
        
        # 將 yt-dlp 的結果對應到我們的 PostInfo 物件
        return PostInfo(
            id=info.get('id'), # <-- 新增這一行，從 yt-dlp 的結果中獲取 id
            title=info.get('title'),
            description=info.get('description') or info.get('title'),
            source=info.get('webpage_url', url),
            thumbnail=info.get('thumbnail'),
            downloads=downloads,
            error=None
        )
    except Exception as e:
        print(f"Error fetching with yt-dlp: {e}")
        # 如果抓取失敗，回傳一個包含錯誤訊息的物件
        # app.py 會根據 error 是否為 None 來判斷是否成功
        return PostInfo(source=url, error=str(e))