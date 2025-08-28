import base64
import random
import re
from io import BytesIO
from typing import Optional, Union

import aiohttp
import imagehash
from nonebot import logger, require
from PIL import Image, UnidentifiedImageError
from pyquery import PyQuery as pq
from tenacity import RetryError, retry, stop_after_attempt, stop_after_delay
from yarl import URL

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

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


@retry(stop=(stop_after_attempt(5) | stop_after_delay(30)))
async def resize_gif(url: str, resize_ratio: int = 2) -> Optional[bytes]:
    """通过 ezgif 压缩 GIF"""
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            "https://s3.ezgif.com/resize", data={"new-image-url": url}
        )
        d = pq(await resp.text())
        next_url = d("form").attr("action")
        _file = d("form > input[type=hidden]:nth-child(1)").attr("value")
        token = d("form > input[type=hidden]:nth-child(2)").attr("value")
        old_width = d("form > input[type=hidden]:nth-child(3)").attr("value")
        old_height = d("form > input[type=hidden]:nth-child(4)").attr("value")
        data = {
            "file": _file,
            "token": token,
            "old_width": old_width,
            "old_height": old_height,
            "width": str(int(old_width) // resize_ratio),
            "method": "gifsicle",
            "ar": "force",
        }
        resp = await session.post(next_url, params="ajax=true", data=data)
        d = pq(await resp.text())
        output_img_url = "https:" + d("img:nth-child(1)").attr("src")
        return await download_image(output_img_url)


async def compress_image(url: URL, content: bytes):
    try:
        image = Image.open(BytesIO(content))
    except UnidentifiedImageError:
        logger.error(f"无法识别图像文件")
        return None

    if image.format != "GIF":
        if image.format == "WEBP":
            with BytesIO() as output:
                image.save(output, "PNG")
                image = Image.open(output)
        # 降低图片分辨率
        image.thumbnail(
            (plugin_config.image_compress_size, plugin_config.image_compress_size)
        )
        width, height = image.size
        logger.debug(f"调整图片大小至: {width} * {height}")
        # 改变角落像素防河蟹
        points = [(0, 0), (0, height - 1), (width - 1, 0), (width - 1, height - 1)]
        for x, y in points:
            image.putpixel((x, y), random.randint(0, 255))
        return image
    else:
        if len(content) > plugin_config.gif_compress_size * 1024:
            try:
                return await resize_gif(url)
            except RetryError:
                logger.error(f"GIF压缩失败，将发送原图")
        return content


def save_image(dir: str, name: str, content: bytes):
    file_dir = store.get_plugin_data_dir() / dir
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / name
    file_path.write_bytes(content)
    logger.debug(f"图片已保存至: {file_path}")


def get_image_base64(content: Union[Image.Image, bytes, None]) -> str:
    if not content:
        return ""
    if isinstance(content, Image.Image):
        with BytesIO() as output:
            content.save(output, format=content.format)
            content = output.getvalue()
    if isinstance(content, bytes):
        return str(base64.b64encode(content).decode())
    return ""


async def get_image_cqcode(
    url: URL, use_proxy: bool, save: bool, dir: str, content: Optional[bytes] = None
) -> str:
    """获取图片的 CQ 码并保存"""
    missing_image_msg = f"图片走丢啦！链接：{url}"
    if not content:
        content = await download_image(url, use_proxy)
    if not content:
        return missing_image_msg

    if save:
        try:
            save_image(dir, url.name, content)
        except Exception as e:
            logger.warning(f"保存图片至本地时出现错误: {e}")

    compressed_content = await compress_image(url, content)
    if not compressed_content:
        return missing_image_msg

    image_base64 = get_image_base64(compressed_content)
    if not image_base64:
        return missing_image_msg
    return f"[CQ:image,file=base64://{image_base64}]"
