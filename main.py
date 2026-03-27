# pyright: reportOptionalMemberAccess=false
# pyright: reportCallIssue=false
# pyright: reportArgumentType=false

import json
import inspect
from pathlib import Path


from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult, MessageChain
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.api import AstrBotConfig

from .sqlite import AsyncSQLiteDB
from .gok_data import GOKServer


@register("astrbot_plugin_honorofkings", 
          "温雅(i12cu4)", 
          "查询王者荣耀账号的近期战绩/实时上榜战力/账号资料等功能", 
          "1.0.0",
          "https://github.com/i12cu4/astrbot_plugin_HonorOfKings.git"
)
class GokApiPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        #获取配置
        self.conf = config

        # 本地数据存储路径
        self.local_data_dir = StarTools.get_data_dir("astrbot_plugin_gok")

        # SQLite本地路径
        self.sqlite_path = Path(self.local_data_dir) /"sqlite.db"
        logger.info(f"SQLite数据文件路径：{self.sqlite_path}")

        # 读取API配置文件
        self.api_file_path = Path(__file__).parent / "api_config.json"
        with open(self.api_file_path, 'r', encoding='utf-8') as f:
            self.api_config = json.load(f)

        # 声明指令集
        self.command_map = {}

        # 指令前缀功能
        self.prefix_en = self.conf.get("prefix").get("enable")
        self.prefix_text = self.conf.get("prefix").get("text")
        if not self.prefix_text:
            self.prefix_text = "王者"
        if self.prefix_en:
            logger.info(f"已启用指令前缀功能，前缀为：{self.prefix_text}")
        else:
            logger.info(f"未启用指令前缀功能。")

        # 战绩锐评功能
        self.comment_en = self.conf.get("comment").get("enable")
        self.comment_provider = self.conf.get("comment").get("select_provider")
        if self.comment_en:
            logger.info(f"锐评功能已经启用，模型为：{self.comment_provider}")
        else:
            logger.info(f"未启用锐评功能")

        logger.info("GOK 插件初始化完成")


    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        try:
            # sqlite 实例化
            self.sql_db = AsyncSQLiteDB(self.sqlite_path)
            await self.sql_db.connect()
            await self.sql_db.execute("""
            CREATE TABLE IF NOT EXISTS users(
                gokid INTEGER,
                name TEXT                          
            )
            """)
            # 王者功能 实例化
            self.gokfun = GOKServer(self.api_config, self.conf, self.sql_db)

        except Exception as e:
            logger.error(f"功能模块初始化失败: {e}")
            raise

        # 指令集
        self.ini_command_map()

        logger.info("GOK 异步插件初始化完成")


    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        if self.gokfun:
            await self.gokfun.close()
            self.gokfun = None

        if self.sql_db:
            await self.sql_db.close()
            self.sql_db = None

        logger.info("GOK 插件已卸载/停用")


    def parse_message(self, text: str) -> list[str] | None:
        """消息解析"""
        text = text.strip()
        if not text:
            return None

        # 前缀模式
        if self.prefix_en:
            prefix = self.prefix_text
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
            else:
                # 非前缀消息，直接忽略
                return None

        return text.split()


    async def _call_with_auto_args(self, handler, event: AstrMessageEvent, args: list[str]):
        """指令执行函数"""
        sig = inspect.signature(handler)
        params = list(sig.parameters.values())

        call_args = []
        arg_index = 0

        for p in params:
            if p.name == "self":
                continue

            if p.name == "event":
                call_args.append(event)
                continue

            if arg_index < len(args):
                raw = args[arg_index]
                arg_index += 1
                try:
                    if p.annotation is int:
                        call_args.append(int(raw))
                    elif p.annotation is float:
                        call_args.append(float(raw))
                    else:
                        call_args.append(raw)
                except Exception:
                    call_args.append(p.default)
            else:
                if p.default is not inspect._empty:
                    call_args.append(p.default)
                else:
                    raise ValueError(f"缺少参数: {p.name}")

        # 只允许 coroutine
        return await handler(*call_args)
    

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        """解析所有消息"""
        if not self.command_map:
            logger.debug("插件尚未初始化完成，忽略消息")
            return
        parts = self.parse_message(event.message_str)
        if not parts:
            logger.debug("未触发指令，忽略消息")
            return

        cmd, *args = parts
        handler = self.command_map.get(cmd)
        if not handler:
            logger.debug("指令函数为空，忽略消息")
            return

        try:
            event.stop_event()
            ret = await self._call_with_auto_args(handler, event, args)
            if ret is not None:
                yield ret
        except Exception as e:
            logger.exception(f"指令执行失败: {cmd}, error={e}")
            yield event.plain_result("参数错误或执行失败")


    def ini_command_map(self):
        """初始化指令集"""
        self.command_map = {
            "功能": self.gok_helps,
            "战绩": self.gok_zhanji,
            "资料": self.gok_ziliao,
            "战力": self.gok_zhanli,
            "查看": self.gok_user_all,
            "添加": self.gok_user_add,
            "修改": self.gok_user_update,
            "删除": self.gok_user_delete,
            "查询": self.gok_user_select
        }


    async def plain_msg(self, event: AstrMessageEvent, action):
        """最终将数据整理成文本发送"""
        data= await action()
        try:
            if data["code"] == 200:
                await event.send( event.plain_result(data["data"]))
            else:
                await event.send(event.plain_result(data["msg"])) 
        except Exception as e:
            logger.error(f"功能函数执行错误: {e}")
            await event.send(event.plain_result("plain_msg失败，请稍后再试")) 


    async def T2I_image_msg(self, event: AstrMessageEvent, action):
        """最终将数据渲染成图片发送"""
        data = await action()
        try:
            if data["code"] == 200:
                if not data["temp"].strip():
                    # temp 为空 → 直接返回纯文本
                    await event.send(event.plain_result(data["data"]))
                else:
                    url = await self.html_render(data["temp"], data["data"], options={})
                    await event.send(event.image_result(url))
            else:
                await event.send(event.plain_result(data["msg"])) 
        except Exception as e:
            logger.error(f"功能函数执行错误: {e}")
            await event.send(event.plain_result("T2I_image_msg失败，请稍后再试")) 


    async def image_msg(self, event: AstrMessageEvent, action):
        """最终将数据整理成图片发送"""
        data = await action()
        try:
            if data["code"] == 200:
                await event.send(event.image_result(data["data"])) 
            else:
                await event.send(event.plain_result(data["msg"])) 

        except Exception as e:
            logger.error(f"功能函数执行错误: {e}")
            await event.send(event.plain_result("image_msg失败，请稍后再试")) 

    async def T2I_image_and_plain_msg(self, event: AstrMessageEvent, action):
        """战绩定制功能（健壮版 + 锐评提示优化）"""
        data = await action()

        # 安全获取字段（防 KeyError）
        temp = data.get("temp", "")
        msg = data.get("msg", "未知错误")
        main_data = data.get("data", "")
        comment_data = data.get("comment", {}).get("data", [])

        # 发送战绩文本
        try:
            if data.get("code") == 200:
                if temp:
                    url = await self.html_render(temp, main_data, options={})
                    await event.send(event.image_result(url))
                else:
                    await event.send(event.plain_result(main_data))
            else:
                await event.send(event.plain_result(msg))
        except Exception as e:
            logger.error(f"战绩文本发送失败: {e}", exc_info=True)
            await event.send(event.plain_result("战绩发送失败，请稍后再试"))

        # 锐评功能
        try:
            if not (data.get("code") == 200 and self.comment_en and data.get("comment", {}).get("data")):
                return

            # 获取Provider（复刻简化版逻辑）
            provider_id = self.comment_provider or await self.context.get_current_chat_provider_id(umo=event.unified_msg_origin)
            if not provider_id:
                logger.warning("[锐评] 未获取到有效LLM提供者，跳过锐评")
                return

            # 精准构建Prompt
            comment_data = data["comment"]["data"][:10]  # 保留原始10条结构
            total = len(comment_data)
            wins = [m for m in comment_data if m.get("gameresult") == 1]
            loses = [m for m in comment_data if m.get("gameresult") in (0, 2)]  # 兼容API双失败标识

            prompt = (
                f"你是一位王者荣耀数据驱动型战术教练，请基于玩家最近{total}场真实战绩（{len(wins)}胜/{len(loses)}负，倒序排列）进行≤120字专业复盘：\n\n"
                "📌 复盘框架（严格按此逻辑）：\n"
                "1️⃣ 【位置推断】\n"
                "   • 无英雄名字段！仅通过KDA特征判断：高助攻(assistcnt≥8)→辅助/坦克；高击杀(killcnt≥5)→Carry\n"
                "   • 示例：'数据体现辅助定位，参团积极' 或 'Carry位输出稳定'\n"
                "2️⃣ 【亮点肯定】\n"
                "   • 从胜场提取：'胜场3次获MVP(mvpcnt=1)，关键团贡献突出' 或 '胜场平均评分9.2+'\n"
                "3️⃣ 【败因归因】（仅负场，gameresult=0/2）\n"
                "   • 辅助倾向：'负场死亡偏高(deadcnt≥5)→调整承伤站位'\n"
                "   • Carry倾向：'负场击杀偏低(killcnt≤2)→优先发育，4分钟后发力'\n"
                "   • 通用：'负场评分普遍<7分→加强对线细节'\n"
                "4️⃣ 【行动点】\n"
                "   • 1条可执行建议 + '逆风专注带线牵制，避免强行开团'\n"
                "   • 收尾：'每局优化1个小细节，胜率自然提升！'\n\n"
                "⚠️ 严禁：\n"
                "- 编造英雄名/段位/mapName/desc等不存在字段（数据仅含：gametime,killcnt,deadcnt,assistcnt,gameresult,mvpcnt,losemvp,gradeGame）\n"
                "- 负面词汇/人身评价/跨位置要求（如'辅助刷经济'）\n"
                "- 重复胜率数字（仅位置推断环节提胜场数）\n\n"
                "💡 字段权威说明（严格按此理解）：\n"
                "gameresult: 1=胜利, 0或2=失败 | killcnt=击杀 | deadcnt=死亡 | assistcnt=助攻 | \n"
                "gradeGame=系统评分(1-16) | mvpcnt=1为胜方MVP | losemvp=1为败方MVP | gametime=对局时间(MM-dd HH:mm)\n\n"
                f"战绩数据（{total}场，倒序）：\n{comment_data}"
            )

            # LLM调用
            try:
                llm_resp = await self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=prompt,
                    timeout=30
                )
                resp_text = getattr(llm_resp, 'completion_text', '').strip()
                if not resp_text:
                    raise ValueError("LLM返回空内容")
                await event.send(event.plain_result(resp_text))
                logger.info(f"[锐评] 生成成功 | 字数:{len(resp_text)}")
            except ProviderNotFoundError as e:
                logger.error(
                    f"[锐评] Provider配置错误！系统中不存在 '{provider_id}'\n"
                    "✅ 解决方案：检查插件配置 comment_provider 值，应与AstrBot「LLM管理」中Provider名称完全一致（如'deepseek'）"
                )
                return
            except Exception as e_llm:
                logger.error(f"[锐评] LLM调用异常 | {type(e_llm).__name__}: {str(e_llm)[:150]}", exc_info=True)
                raise

        except Exception as e:
            logger.error(f"[锐评] 生成失败 | {type(e).__name__}: {str(e)[:150]}", exc_info=True)
            await event.send(event.plain_result("锐评生成失败，请稍后再试"))

    async def gok_helps(self, event: AstrMessageEvent):
        """王者功能"""
        return await self.T2I_image_msg(event, self.gokfun.helps)
    
    async def gok_zhanji(self, event: AstrMessageEvent,name: str,option:str = 0):
        """王者战绩"""
        return await self.T2I_image_and_plain_msg(event, lambda: self.gokfun.zhanji(name ,option))
    
    async def gok_ziliao(self, event: AstrMessageEvent,name: str):
        """王者资料"""
        return await self.T2I_image_msg(event, lambda: self.gokfun.ziliao(name))
    
    async def gok_zhanli(self, event: AstrMessageEvent, hero: str, type: str = ""):
        """英雄战力 名称 大区"""
        return await self.plain_msg(event, lambda: self.gokfun.zhanli(hero,type))
    
    async def gok_user_all(self, event: AstrMessageEvent):
        """角色查看"""
        return await self.T2I_image_msg(event, self.gokfun.all)
    
    async def gok_user_add(self, event: AstrMessageEvent, gokid: int, name: str):
        """角色添加 王者营地ID 名称"""
        return await self.plain_msg(event, lambda: self.gokfun.add(gokid,name))
    
    async def gok_user_update(self, event: AstrMessageEvent, gokid: int, name: str):
        """角色修改 王者营地ID 名称"""
        return await self.plain_msg(event, lambda: self.gokfun.update(gokid,name))
    
    async def gok_user_delete(self, event: AstrMessageEvent, gokid:int):
        """角色删除 王者营地ID"""
        return await self.plain_msg(event, lambda: self.gokfun.delete(gokid))
    
    async def gok_user_select(self, event: AstrMessageEvent, gokid):
        """角色查询 王者营地ID"""
        return await self.T2I_image_msg(event, lambda: self.gokfun.select(gokid))