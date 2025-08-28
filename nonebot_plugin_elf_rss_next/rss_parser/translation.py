import hashlib
import random
import re
from typing import Optional

import aiohttp
import emoji
from deep_translator import DeeplTranslator, GoogleTranslator, single_detection
from nonebot import logger

from ..globals import plugin_config


async def _deepl_translate(text: str, proxies: Optional[dict[str, str]]) -> str:
    try:
        lang = None
        if key := plugin_config.single_detection_api_key:
            lang = single_detection(text, api_key=key)
        translator = DeeplTranslator(
            api_key=plugin_config.deepl_api_key,
            source=lang,
            target="zh",
            use_free_api=True,
            proxies=proxies,
        )
        return str(translator.translate(re.escape(text)))
    except Exception as e:
        msg = "Deepl翻译失败: " + str(e)
        logger.warning(msg)
        raise Exception(msg) from e


async def _baidu_translate(text: str, appid: str, key: str) -> str:
    url = "https://api.fanyi.baidu.com/api/trans/vip/translate"
    salt = str(random.randint(32768, 65536))
    sign = hashlib.md5((appid + text + salt + key).encode()).hexdigest()
    params = {
        "q": text,
        "from": "auto",
        "to": "zh",
        "appid": appid,
        "salt": salt,
        "sign": sign,
    }
    async with aiohttp.ClientSession() as session:
        resp = await session.get(url, params=params, timeout=aiohttp.ClientTimeout(10))
        data = await resp.json()
        try:
            return "\n".join(i["dst"] for i in data["trans_result"])
        except Exception as e:
            error_msg = f"百度翻译失败: {data['error_msg']}"
            logger.warning(error_msg)
            raise Exception(error_msg) from e


async def _google_translate(text: str, proxies: Optional[dict[str, str]]) -> str:
    try:
        translator = GoogleTranslator(source="auto", target="zh-CN", proxies=proxies)
        return str(translator.translate(re.escape(text)))
    except Exception as e:
        error_msg = "Google翻译失败: " + str(e)
        logger.warning(error_msg)
        raise Exception(error_msg) from e


async def translate(content: str, use_proxy: bool) -> str:
    proxies = (
        {"http": plugin_config.proxy, "https": plugin_config.proxy}
        if use_proxy and plugin_config.proxy
        else None
    )
    text = emoji.demojize(content)
    text = re.sub(r":[A-Za-z_]*:", " ", text)
    try:
        # 优先级 DeepL > Baidu > Google
        # 异常时使用 Google 重试
        google_translate_flag = False
        try:
            if plugin_config.deepl_api_key:
                text = await _deepl_translate(text, proxies)
            elif plugin_config.baidu_id and plugin_config.baidu_api_key:
                text = await _baidu_translate(
                    content, plugin_config.baidu_id, plugin_config.baidu_api_key
                )
            else:
                google_translate_flag = True
        except Exception:
            google_translate_flag = True
        if google_translate_flag:
            text = await _google_translate(text, proxies)
    except Exception as e:
        logger.error(e)
        text = str(e)

    text = text.replace("\\", "")
    return text
