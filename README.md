<div align="center">
<a href="https://nonebot.dev/store/plugins">
  <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="350" alt="logo">
</a>

# nonebot-plugin-elf-rss-next

✨ *RSS 订阅推送插件* ✨

<a href="./LICENSE">
  <img src="https://img.shields.io/github/license/liuzhaoze/nonebot-plugin-elf-rss-next" alt="license">
</a>
</div>

> [!NOTE]
> 本项目是 [ELF_RSS](https://github.com/Quan666/ELF_RSS) 的重构版本，遵循 [NoneBot2](https://github.com/nonebot/nonebot2) 插件开发的最佳实践，简化安装流程。
>
> 项目处于重构完成初期，可能存在 bug ，欢迎提交 PR 或 Issue 。

## 📖 功能介绍

- 通过命令增加、删除、查询、修改 RSS 订阅
- 翻译 RSS 订阅内容
- 个性化订阅设置
  - 更新频率
  - 仅发送标题/图片
  - 自动下载图片至本地
  - 推送过滤黑名单/白名单
- 图片压缩
- 根据标题、链接、图片自动去重发送过的消息
- 河蟹推送中的关键词

## 💿 安装方法

- 使用 nb-cli 安装  
  在 nonebot2 项目的根目录下打开命令行, 输入以下指令：

  ```bash
  nb plugin install nonebot-plugin-elf-rss-next
  ```

- 其他安装方式参见 [文档](https://nonebot.dev/docs/tutorial/create-plugin#%E5%8A%A0%E8%BD%BD%E6%8F%92%E4%BB%B6)

## ⚙️ 配置说明

在 `.env` 文件中添加：

```env
# nonebot_plugin_elf_rss_next
# 目前并没有什么用
ELF_RSS__DEBUG=false
# RSSHub 订阅地址
ELF_RSS__RSSHUB_URL="https://rsshub.app"
# 备用 RSSHub 订阅地址（示例：["https://rsshub.app", "https://rsshub.app"]）
ELF_RSS__RSSHUB_FALLBACK_URLS=[]
# 代理地址
# ELF_RSS__PROXY="http://127.0.0.1:7890"
# 屏蔽词（示例：["互动抽奖", "XX抽奖平台"]）
ELF_RSS__BLACK_WORDS=[]
# 去重数据库记录期限
ELF_RSS__CACHE_EXPIRE=14
# 是否显示转发的内容（主要是微博），默认打开。如果关闭还有转发的信息的话，可以自行添加进屏蔽词（但是这整条消息就会没）
ELF_RSS__BLOCKQUOTE=true
# DeepL 翻译 API（可选，不填默认使用谷歌翻译）
ELF_RSS__DEEPL_API_KEY=""
# 百度翻译 API（可选，不填默认使用百度翻译）
# 前往 https://api.fanyi.baidu.com/ 获取
ELF_RSS__BAIDU_ID=""
ELF_RSS__BAIDU_API_KEY=""
# 配合 deepl_translator 使用的语言检测接口
# 前往 https://detectlanguage.com/ 注册获取
ELF_RSS__SINGLE_DETECTION_API_KEY=""
# 非 GIF 图片压缩后的最大分辨率（单位：px）
ELF_RSS__IMAGE_COMPRESS_SIZE=2048
# 不进行 GIF 图片压缩的最大大小（单位：KB）
ELF_RSS__GIF_COMPRESS_SIZE=6144
# RSS 更新推送消息的最大长度（防止消息太长刷屏，以及消息过长发送失败的情况）
ELF_RSS__MAX_LENGTH=500
# RSS 文章缓存数量
ELF_RSS__RSS_ENTRIES_FILE_LIMIT=200
```

## 📜 使用说明

### 帮助

命令：`elf help`

示例：`elf help`

功能：获取帮助信息

### 添加订阅

命令：`elf add 订阅名 订阅地址`

示例：`elf add bgm-daily /bangumi.tv/calendar/today`

功能：添加RSS订阅

说明：订阅地址可以填写完整的 URL 或 RSSHub 路由

### 取消订阅

命令：`elf del 订阅名 [订阅名 ...]`

示例：`elf del bgm-daily twitter`

功能：取消RSS订阅（支持批量操作）

### 所有订阅

命令：`elf ls`

示例：`elf ls`

功能：当前QQ号/群号下的所有订阅

### 订阅详情

命令：`elf info 订阅名`

示例：`elf info bgm-daily`

功能：获取指定订阅的详细信息

### 修改订阅

命令：`elf edit 订阅名 属性=值 [属性=值 ...]`

示例：`elf edit bgm-daily`

功能：修改指定订阅的属性

说明：可修改的属性和取值范围如下表所示

|属性|取值|说明|
|:-:|:-:|:-|
|name|无空格字符串|修改订阅的名称|
|url|无空格字符串|修改订阅的地址<br>RSSHub 订阅源可以直接填写路由，其他订阅源需要完整的 URL 地址|
|qq|英文逗号分割的 QQ 号 / -1|修改订阅的推送用户；英文逗号开头表示追加；-1 清空所有推送用户<br>取消订阅请使用 del 命令|
|qun|英文逗号分割的群号 / -1|修改订阅的推送群；英文逗号开头表示追加；-1 清空所有推送群<br>取消订阅请使用 del 命令|
|proxy|1 / 0|是否使用代理|
|freq|正整数 / 下划线分割的 crontab 字符串|正整数表示每 x 分钟检查一次更新<br>crontab 字符串格式见表格下方说明|
|trans|1 / 0|是否翻译更新内容|
|ot|1 / 0|是否仅推送标题|
|op|1 / 0|是否仅推送图片|
|dp|1 / 0|是否将图片下载到本地|
|cookie|无空格字符串|需要身份验证的订阅源可能会需要 Cookie|
|wkey|无空格字符串 / -1|设置只有包含白名单关键词的更新才会推送（支持正则）；-1 表示清空白名单关键词|
|bkey|无空格字符串 / -1|设置包含黑名单关键词的更新不会推送（支持正则）；-1 表示清空黑名单关键词|
|mode|+title / +link / +image / +or<br>-title / -link / -image / -or|设置去重模式，默认不对推送的消息进行去重<br>按照推送的标题（title）、链接（link）、图片（image）进行去重<br>如果没有 or ，则设置的判断逻辑都满足才去重；否则满足其一就进行去重|
|image|非负整数|设置最大推送图片数量，0 表示不限制|
|hexie|+/-关键词|添加/删除推送中需要和谐的关键词（支持正则）|
|merge|1 / 0|是否发送合并转发消息|
|stop|1 / 0|是否停止更新|

freq 中的 crontab 字符串定义与 [Linux crontab 命令](https://www.runoob.com/linux/linux-comm-crontab.html) 相同，但是需要将空格替换为下划线，即：

```text
f1_f2_f3_f4_f5
```

## 🤝 贡献代码

### TODO

- [ ] 为特定路由添加[定制化解析](https://github.com/Quan666/ELF_RSS/tree/2.0/src/plugins/ELF_RSS2/parsing/routes)
- [ ] 优化[正文解析逻辑](https://github.com/liuzhaoze/nonebot-plugin-elf-rss-next/blob/main/nonebot_plugin_elf_rss_next/rss_parser/html_document_processor.py)

### 开发环境

1. 在 VSCode 中安装[插件](https://github.com/liuzhaoze/nonebot-plugin-elf-rss-next/blob/main/.vscode/extensions.json)，该项目使用 isort 和 Black Formatter 进行代码格式化
2. 使用 uv 安装项目依赖

   ```bash
   uv sync
   ```
