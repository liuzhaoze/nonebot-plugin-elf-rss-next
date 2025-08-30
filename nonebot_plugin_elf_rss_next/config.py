from typing import Optional

from pydantic import AnyUrl, BaseModel, Field, HttpUrl


class ScopedConfig(BaseModel):
    debug: bool = False
    rsshub_url: HttpUrl = "https://rsshub.app"
    rsshub_fallback_urls: list[HttpUrl] = Field(default_factory=list)
    proxy: Optional[AnyUrl] = None
    black_words: Optional[list[str]] = None
    cache_expire: int = 14
    blockquote: bool = True
    deepl_api_key: Optional[str] = None
    baidu_id: Optional[str] = None
    baidu_api_key: Optional[str] = None
    single_detection_api_key: Optional[str] = None
    image_compress_size: int = 2 * 1024
    gif_compress_size: int = 6 * 1024
    max_length: int = 500
    rss_entries_file_limit: int = 200


class Config(BaseModel):
    elf_rss: ScopedConfig = Field(default_factory=ScopedConfig)
