from pydantic import BaseModel, Field, HttpUrl


class ScopedConfig(BaseModel):
    rsshub_url: HttpUrl = "https://rsshub.app"


class Config(BaseModel):
    elf_rss: ScopedConfig = Field(default_factory=ScopedConfig)
