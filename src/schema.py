from pydantic import BaseModel
from typing import List, Optional

# 這個 class 對應 yt-dlp 回傳的眾多格式中的一種
class DownloadInfo(BaseModel):
    url: str
    ext: str
    format_id: Optional[str] = None
    width: Optional[int] = None      # <-- 新增這一行
    height: Optional[int] = None     # <-- 新增這一行
    # 您也可以根據需求加入 filesize, resolution 等欄位

# 這是 fetch_post_info 最終回傳的物件格式
# app.py 會直接使用這個物件
class PostInfo(BaseModel):
    id: Optional[str] = None  # <-- 新增這一行
    title: Optional[str] = None
    description: Optional[str] = None
    source: str
    thumbnail: Optional[str] = None
    downloads: List[DownloadInfo] = []
    error: Optional[str] = None

class ImageRequest(BaseModel):
    image_url: str