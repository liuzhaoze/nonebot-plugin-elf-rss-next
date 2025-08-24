from typing import Optional

from pydantic import AnyUrl, BaseModel, Field, HttpUrl


class ScopedConfig(BaseModel):
    debug: bool = False
    rsshub_url: HttpUrl = "https://rsshub.app"
    rsshub_fallback_urls: list[HttpUrl] = Field(default_factory=list)
    proxy: Optional[AnyUrl] = None


class Config(BaseModel):
    elf_rss: ScopedConfig = Field(default_factory=ScopedConfig)
