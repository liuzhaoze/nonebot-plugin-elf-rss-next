import re
from io import BytesIO
from typing import Any, Optional

import aiohttp
import imagehash
from nonebot import logger
from PIL import Image, UnidentifiedImageError
from tenacity import RetryError, retry, stop_after_attempt, stop_after_delay
from yarl import URL

from ..globals import plugin_config


async def fuck_pixiv_cat(url: str) -> str:
    img_id = re.sub("https://pixiv.cat/", "", url)
    img_id = img_id[:-4]
    info_list = img_id.split("-")
    async with aiohttp.ClientSession() as session:
        try:
            resp = await session.get(
                f"https://api.obfs.dev/api/pixiv/illust?id={info_list[0]}"
            )
            resp_json = await resp.json()
            if len(info_list) >= 2:
                return str(
                    resp_json["illust"]["meta_pages"][int(info_list[1]) - 1][
                        "image_urls"
                    ]["original"]
                )
            else:
                return str(
                    resp_json["illust"]["meta_single_page"]["original_image_url"]
                )
        except Exception as e:
            logger.error(f"处理 pixiv.cat 链接[{url}]时出现问题: {e}")
            return url


@retry(stop=(stop_after_attempt(5) | stop_after_delay(30)))
async def download_image(url: str, use_proxy: bool) -> Optional[bytes]:
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        referer = f"{URL(url).scheme}://{URL(url).host}/"
        headers = {"referer": referer}
        resp = await session.get(
            url, headers=headers, proxy=(plugin_config.proxy if use_proxy else None)
        )
        content = await resp.read()

        # 如果图片无法获取到，直接返回
        if len(content) == 0:
            if "pixiv.cat" in url:
                url = await fuck_pixiv_cat(url)
                return await download_image(url, use_proxy)
            logger.error(
                f"图片[{url}]下载失败 Content-Type: {resp.headers['Content-Type']} status: {resp.status}"
            )
            return None

        # 如果图片格式为 SVG ，先转换为 PNG
        if resp.headers["Content-Type"].startswith("image/svg+xml"):
            next_url = str(
                URL("https://images.weserv.nl/").with_query(f"url={url}&output=png")
            )
            return await download_image(next_url, use_proxy)

        return content


async def get_image_hash(url: str, use_proxy: bool) -> Optional[str]:
    try:
        content = await download_image(url, use_proxy)
        if not content:
            return None
    except RetryError:
        logger.error(f"图片[{url}]下载失败，已到达最大重试次数，请检查代理设置")
        return None

    try:
        image = Image.open(BytesIO(content))
    except UnidentifiedImageError:
        return None

    # GIF 图片的 image_hash 实际上是第一帧的值，为了避免误伤直接跳过
    if image.format == "GIF":
        return None

    return str(imagehash.dhash(image))
