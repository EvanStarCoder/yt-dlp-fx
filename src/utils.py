import asyncio
from yt_dlp import YoutubeDL
from aiohttp_client_cache.session import CachedSession
import requests
from PIL import Image
import io

# 引入我們剛剛定義的資料結構
from .schema import PostInfo, DownloadInfo, ImageRequest

# 盲文點陣的映射表 (與 JS 版本相同)
BRAILLE_MAP = [
    [0x01, 0x08],
    [0x02, 0x10],
    [0x04, 0x20],
    [0x40, 0x80],
]

def _extract_info_sync(url: str) -> dict:
    """
    這是一個同步函式，專門用來執行 yt-dlp 的核心抓取邏輯。
    我們把它獨立出來，以便透過 asyncio.to_thread 呼叫。
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'cookiefile': './facebook_cookies.txt',
    }
    with YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


async def fetch_post_info(url: str) -> PostInfo:
    """
    全新升級版函式。
    它能非同步地執行 yt-dlp，並處理影片、多圖片貼文。
    """
    try:
        info = await asyncio.to_thread(_extract_info_sync, url)

        downloads = []
        media_type = 'video' # 預設媒體類型

        # 【修改】判斷是否存在 'entries'，如果存在，代表是多圖片/影片貼文
        if 'entries' in info and info.get('entries'):
            media_type = 'gallery' # 將類型標記為畫廊
            for entry in info['entries']:
                # 確保 entry 是一個字典並且有 url
                if isinstance(entry, dict) and entry.get('url'):
                     downloads.append(DownloadInfo(
                        url=entry['url'],
                        ext=entry.get('ext', 'jpg'),
                        format_id=entry.get('format_id'),
                        width=entry.get('width'),
                        height=entry.get('height')
                    ))
        # 如果不是多圖片貼文，則沿用舊的影片格式抓取邏輯
        elif 'formats' in info:
            for f in info['formats']:
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('url'):
                    downloads.append(DownloadInfo(
                        url=f['url'],
                        ext=f.get('ext', 'mp4'),
                        format_id=f.get('format_id'),
                        width=f.get('width'),
                        height=f.get('height')
                    ))

        return PostInfo(
            id=info.get('id'),
            title=info.get('title'),
            # 【修改】讓 description 也能處理沒有 description 但有 title 的情況
            description=info.get('description') or info.get('title') or "No description found.",
            source=info.get('webpage_url', url),
            thumbnail=info.get('thumbnail'),
            downloads=downloads,
            # 您可以選擇性地加入 media_type，讓您的 API 消費者知道這是什麼類型的貼文
            # media_type=media_type, 
            error=None
        )
    except Exception as e:
        print(f"Error fetching with yt-dlp: {e}")
        return PostInfo(source=url, error=str(e))
    
async def dot_art(request: dict) -> dict:
    #try:
    # 1. 從 URL 下載圖片
    response = requests.get(request['image_url'], timeout=10)
    response.raise_for_status()  # 如果下載失敗會拋出錯誤

    # 2. 使用 Pillow 讀取圖片資料
    image = Image.open(io.BytesIO(response.content))

    # 3. 圖片預處理
    TARGET_WIDTH = 50
    # 計算縮放後的高度
    width, height = image.size
    new_height = int(TARGET_WIDTH * 2 * height / width)
    # 確保高度是 4 的倍數
    new_height = new_height - (new_height % 4)
    
    # 縮小尺寸、轉為灰階、並使用抖色增強效果
    processed_image = image.resize((TARGET_WIDTH * 2, new_height)).convert('L').point(lambda x: 0 if x < 128 else 255, '1')


    # 4. 核心轉換邏輯
    result = ""
    for y in range(0, processed_image.height, 4):
        for x in range(0, processed_image.width, 2):
            char_code = 0x2800
            for i in range(4): # y-offset
                for j in range(2): # x-offset
                    # Pillow 中，0 代表黑色，255 代表白色
                    pixel_value = processed_image.getpixel((x + j, y + i))
                    if pixel_value != 0: # == 如果是黑色 (!= 白色)
                        char_code += BRAILLE_MAP[i][j]
            result += chr(char_code)
        result += "\n"
    
    return {"dot_art": result}

    #except Exception as e:
    #    print(f"Error processing image: {e}")
    #    return {"error": "Failed to process image."}
