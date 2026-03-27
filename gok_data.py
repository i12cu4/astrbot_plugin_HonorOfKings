# pyright: reportArgumentType=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportIndexIssue=false
# pyright: reportOptionalMemberAccess=false
# pyright: reportCallIssue=false

from datetime import datetime
from typing import Dict, Any, Optional, List, Union
import base64

from astrbot.api import logger
from astrbot.api import AstrBotConfig

from .request import APIClient
from .sqlite import AsyncSQLiteDB
from .fun_basic import load_template,extract_fields

HERO_ID_MAP = {
    "105": "廉颇", "106": "小乔", "107": "赵云", "108": "墨子", "109": "妲己",
    "110": "嬴政", "111": "孙尚香", "112": "鲁班七号", "113": "庄周", "114": "刘禅",
    "115": "高渐离", "116": "阿轲", "117": "钟无艳", "118": "孙膑", "119": "扁鹊",
    "120": "白起", "121": "芈月", "123": "吕布", "124": "周瑜",
    "125": "元歌", "126": "夏侯惇", "127": "甄姬", "128": "曹操", "129": "典韦",
    "130": "宫本武藏", "131": "李白", "132": "马可波罗", "133": "狄仁杰", "134": "达摩",
    "135": "项羽", "136": "武则天", "137": "司马懿", "139": "老夫子",
    "140": "关羽", "141": "貂蝉", "142": "安琪拉", "144": "程咬金",
    "146": "露娜", "148": "姜子牙", "149": "刘邦",
    "150": "韩信", "151": "孙权", "152": "王昭君", "153": "兰陵王", "154": "花木兰",
    "155": "艾琳", "156": "张良", "157": "不知火舞", "159": "朵莉亚",
    "162": "娜可露露", "163": "橘右京",
    "166": "亚瑟", "167": "孙悟空", "168": "牛魔", "169": "后羿",
    "170": "刘备", "171": "张飞", "172": "蚩姹", "173": "李元芳", "174": "虞姬",
    "175": "钟馗", "176": "杨玉环", "177": "苍", "178": "杨戬", "179": "女娲",
    "180": "哪吒", "182": "干将莫邪", "183": "雅典娜", "184": "蔡文姬",
    "186": "太乙真人", "187": "东皇太一", "188": "大禹", "189": "鬼谷子",
    "190": "诸葛亮", "191": "大乔", "192": "黄忠", "193": "铠", "194": "苏烈",
    "195": "百里玄策", "196": "百里守约", "197": "弈星", "198": "梦奇", "199": "公孙离",
    "312": "沈梦溪",
    "501": "明世隐", "502": "裴擒虎", "503": "狂铁", "504": "米莱狄",
    "505": "瑶", "506": "云中君", "507": "李信", "508": "伽罗", "509": "盾山",
    "510": "孙策", "511": "猪八戒", "513": "上官婉儿", "514": "亚连",
    "515": "嫦娥", "517": "大司命", "518": "马超", "519": "敖隐",
    "521": "海月", "522": "曜", "523": "西施", "524": "蒙犽",
    "525": "鲁班大师", "527": "蒙恬", "528": "澜", "529": "盘古",
    "531": "镜", "533": "阿古朵", "534": "桑启",
    "536": "夏洛特", "537": "司空震", "538": "云缨",
    "540": "金蝉", "542": "暃", "544": "赵怀真",
    "545": "莱西奥", "548": "戈娅",
    "550": "空空儿",
    "558": "影",
    "563": "海诺", "564": "姬小满",
    "577": "少司缘",
    "581": "元流之子(坦克)", "582": "元流之子(法师)", "584": "元流之子(射手)",
    "585": "元流之子(辅助)"
}

class GOKServer:
    def __init__(self, api_config, config:AstrBotConfig, sqlite:AsyncSQLiteDB ):
        self._api = APIClient()
        # 引用API配置文件
        self._api_config = api_config
        # 引用插件配置文件
        self._config = config
        # 引用数据库类
        self._sql_db = sqlite

        # 获取配置中的 Token
        self.ytapi_token = self._config.get("ytapi_token", "")
        if  self.ytapi_token == "":
            logger.warning("获取应天API令牌配置失败，部分功能无法正常使用")
        else:
            logger.debug(f"获取应天API令牌成功。{self.ytapi_token}")

        self.nyapi_token = self._config.get("nyapi_token", "")
        if  self.nyapi_token == "":
            logger.warning("获取柠柚API令牌配置失败，部分功能无法正常使用")
        else:
            logger.debug(f"获取柠柚API令牌成功。{self.nyapi_token}")


    async def close(self):
        """释放底层 APIClient 资源"""
        if self._api:
            await self._api.close()
            self._api = None


    def _init_return_data(self) -> Dict[str, Any]:
        """初始化标准的返回数据结构"""
        return {
            "code": 0,
            "msg": "功能函数未执行",
            "data": {}
        }
    

    async def _base_request(
            self, 
            config_key: str, 
            method: str, 
            params: Optional[Dict[str, Any]] = None, 
            out_key: Optional[str] = "data"
        ) -> Optional[Any]:
            """
            基础请求封装，处理配置获取和API调用。
            
            :param config_key: 配置字典中对应 API 的键名。
            :param method: HTTP方法 ('GET' 或 'POST')。
            :param params: 请求参数或 Body 数据。
            :param out_key: 响应数据中需要提取的字段。
            :return: 成功时返回提取后的数据，失败时返回 None。
            """
            try:
                api_config = self._api_config.get(config_key)
                if not api_config:
                    logger.error(f"配置文件中未找到 key: {config_key}")
                    return None
                
                # 复制 params，避免修改原始配置模板
                request_params = api_config.get("params", {}).copy()
                if params:
                    request_params.update(params)

                url = api_config.get("url", "")
                if not url:
                    logger.error(f"API配置缺少 URL: {config_key}")
                    return None
                    
                if method.upper() == 'POST':
                    data = await self._api.post(url, data=request_params, out_key=out_key)
                else: # 默认为 GET
                    data = await self._api.get(url, params=request_params, out_key=out_key)
                
                if not data:
                    logger.warning(f"获取接口信息失败或返回空数据: {config_key}")
                
                return data
                
            except Exception as e:
                logger.error(f"基础请求调用出错 ({config_key}): {e}")
                return None


    async def helps(self) -> Dict[str, Any]:
        return_data = self._init_return_data()
        help_text = (
            "功能          → 功能总览\n"
            "战绩 [标识]   → 对局战绩(需应天API令牌)\n"
            "资料 [标识]   → 角色资料(需应天API令牌)\n"
            "战力 英雄 大区(aqq/awx/iqq/iwx,默认不填输出四区)(需柠柚API令牌)\n"
            "查看\n"
            "添加 营地ID 名称\n"
            "修改 营地ID 名称\n"
            "删除 营地ID\n"
            "查询 [标识]\n"
            "[标识] = 自定义角色名 或 营地ID"
        )
        return_data["data"] = help_text
        return_data["code"] = 200
        return_data["msg"] = ""
        return_data["temp"] = ""
        return return_data


    async def add(self,gokid: int, name: str) -> Dict[str, Any]:
        """角色添加 王者营地ID 角色"""
        return_data = self._init_return_data()
        
        # 添加数据
        try:
            await self._sql_db.insert(
                "users",
                {
                    "gokid": gokid,
                    "name": name,
                }
            )

        except FileNotFoundError as e:
            logger.error(f"添加失败: {e}")
            return_data["msg"] = "添加失败"
            return return_data

        return_data["data"] = (
            "添加成功\n"
            f"王者营地ID：{gokid}\n"
            f"名称：{name}\n"
        )  

        return_data["code"] = 200
        return_data["temp"] = ""
        return return_data
    

    async def all(self) -> Dict[str, Any]:
        """角色查看"""
        return_data = self._init_return_data()
        
        try:
            data = await self._sql_db.select_all("users")
        except Exception as e:
            logger.error(f"查看失败: {e}")
            return_data["msg"] = "数据库查询失败"
            return return_data

        if not data:
            return_data["data"] = "📭 未绑定任何角色"
            return_data["code"] = 200
            return_data["msg"] = ""
            return return_data
        
        lines = []
        for item in data:
            gokid = str(item.get("gokid", "")).ljust(12)
            name = item.get("name", "").strip()
            lines.append(f"🆔 {gokid}👤 {name}")
        
        return_data["data"] = "\n".join(lines)
        return_data["code"] = 200
        return_data["msg"] = ""
        return_data["temp"] = ""
        return return_data
    

    async def select(self, name) -> Dict[str, Any]:
        """角色查询"""
        return_data = self._init_return_data()
        
        # 判断输入是否为整数
        try:
            int(name)
            if int(name) >= 100000000:
                like = "gokid LIKE ?"
            else:
                raise Exception("id数据异常")
        except (ValueError, TypeError, Exception):
            like = "name LIKE ?"

        # 模糊拼接
        like_name = f"%{name}%"

        # 查询数据
        try:
            data = await self._sql_db.select_all(
                "users",
                like,
                (like_name,)
            )
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return_data["msg"] = "数据库查询失败"
            return_data["temp"] = ""
            return return_data

        if not data:
            return_data["data"] = "📭 未查询到角色数据"
            return_data["code"] = 200
            return_data["msg"] = ""
            return_data["temp"] = ""
            return return_data
        
        lines = []
        for item in data:
            gokid = str(item.get("gokid", "")).ljust(12)
            name = item.get("name", "").strip()
            lines.append(f"🆔 {gokid}👤 {name}")
        
        return_data["data"] = "\n".join(lines)
        return_data["code"] = 200
        return_data["msg"] = ""
        return_data["temp"] = ""
        return return_data
    

    async def update(self, gokid:int, name: str) -> Dict[str, Any]:
        """角色修改 王者营地ID 角色"""
        return_data = self._init_return_data()
        
        data = await self._sql_db.select_one(
                "users",
                "gokid=?",
                (gokid,)
            )

        if not data:
            return_data["msg"] = "没有当前ID"
            return return_data
        

        # 修改数据
        try:
            await self._sql_db.update(
                "users",
                {
                    "name": name,
                },
                "gokid=?",
                (gokid,)
            )

        except FileNotFoundError as e:
            logger.error(f"避雷修改失败: {e}")
            return_data["msg"] = "避雷修改失败"
            return return_data

        return_data["data"] = (
            "修改成功\n"
            f"王者营地ID：{gokid}\n"
            f"名称：{name}\n"
        )  

        return_data["code"] = 200
        return_data["temp"] = ""
        return return_data
    

    async def delete(self, gokid:int) -> Dict[str, Any]:
        """角色删除 王者营地ID"""
        return_data = self._init_return_data()
        
        data = await self._sql_db.select_one(
                "users",
                "gokid=?",
                (gokid,)
            )

        if not data:
            return_data["msg"] = "没有当前ID"
            return return_data

        # 删除
        try:
            await self._sql_db.delete(
                "users",
                "gokid=?",
                (gokid,)
            )

        except FileNotFoundError as e:
            logger.error(f"删除失败: {e}")
            return_data["msg"] = "删除失败"
            return return_data

        return_data["data"] = f"删除成功。王者营地ID：{gokid}"
        return_data["code"] = 200
        return_data["temp"] = ""
        return return_data


    async def get_gokid(self,name: str):
        # 判断输入是否为整数
        try:
            # 直接返回输入
            int(name)
            if int(name) >=10000000:
                gokid = name
                return gokid
            else:
                raise Exception("输入不是ID")
        except (ValueError, TypeError, Exception):
            # 查询数据
            try:
                data = await self._sql_db.select_one(
                    "users",
                    "name=?",
                    (name,)
                )

                if not data:
                    gokid = None
                    return gokid
                
                gokid = data['gokid']
                return gokid
            except FileNotFoundError as e:
                logger.error(f"查询失败: {e}")
                gokid = None
                return gokid


    async def zhanji(self, name: str, option: str):
        """战绩查询"""
        return_data = self._init_return_data()
        return_data["temp"] = ""
        return_data["comment"] = {"data": []}
        return_data["data"] = ""

        if self.ytapi_token == "":
            return_data["msg"] = "❌ 未配置应天API令牌，战绩功能不可用"
            return return_data
        
        gokid = await self.get_gokid(name)
        if not gokid:
            return_data["msg"] = "❌ 未查询到该用户，请确认输入正确的角色或营地ID"
            return return_data
        
        params = {"id": gokid, "option": option, "key": self.ytapi_token}
        
        # 确保包含必要字段
        fields = [
            "gametime", "killcnt", "deadcnt", "assistcnt", "gameresult", "mvpcnt", "losemvp",
            "oldMasterMatchScore", "newMasterMatchScore", "usedTime", "roleJobName", "stars", "desc",
            "gradeGame", "godLikeCnt", "firstBlood", "hero1TripleKillCnt", "hero1UltraKillCnt", "hero1RampageCnt",
            "branchEvaluate", "heroId", "mapName"
        ]
        comment = ["gametime", "killcnt", "deadcnt", "assistcnt", "gameresult", "mvpcnt", "losemvp", "gradeGame"]

        data = await self._base_request("gok_zhanji", "GET", params=params)       
        if not data or not data.get('list'):
            return_data["msg"] = "❌ 获取战绩数据失败或无对局记录"
            return return_data  

        try:
            return_data["comment"]["data"] = extract_fields(data['list'], comment)[:10]
            result = extract_fields(data['list'], fields)[:25]
            for m in result:
                minutes = m["usedTime"] // 60
                seconds = m["usedTime"] % 60
                m["time_str"] = f"{minutes}:{seconds:02d}"
            
            result_lines = []
            for game in result:
                # 比赛类型判断
                map_name = str(game.get('mapName', '')).strip()
                battle_type_str = "[未知模式]"
                rank_info = ""
                
                if "排位赛" in map_name:
                    battle_type_str = f"[{map_name}]"
                    role_job = game.get('roleJobName', '')
                    stars = game.get('stars', 0)
                    rank_info = f"{role_job}{stars}星" if role_job else "未知段位"
                elif "巅峰赛" in map_name:
                    battle_type_str = "[巅峰赛]"
                    old_score = game.get('oldMasterMatchScore', 0)
                    new_score = game.get('newMasterMatchScore', 0)
                    rank_info = f"{old_score}→{new_score}" if (old_score or new_score) else "巅峰赛"
                else:
                    battle_type_str = "[娱乐赛]"
                    # 娱乐赛不显示段位
                
                # 胜负判断
                result_flag = "胜利" if game.get('gameresult') == 1 else "失败"
                
                # 高亮逻辑
                highlight = ""
                branch_eval = game.get('branchEvaluate', '')
                if branch_eval is not None:
                    eval_str = str(branch_eval).strip()
                    eval_map = {
                        "1": "MVP", "2": "最佳队友", "3": "Carry", "4": "MVP",
                        "MVP": "MVP", "最佳队友": "最佳队友", "Carry": "Carry", "carry": "Carry"
                    }
                    if eval_str in eval_map:
                        highlight = f"[{eval_map[eval_str]}]"
                    elif eval_str and not eval_str.isdigit() and 1 <= len(eval_str) <= 8:
                        clean = ''.join(c for c in eval_str if c.isalnum() or c in ' 最佳队友CarryMVP')
                        if clean.strip():
                            highlight = f"[{clean.strip()}]"
                
                if not highlight:
                    if game.get('mvpcnt', 0) > 0:
                        highlight = "[MVP]"
                    elif game.get('losemvp', 0) > 0:
                        highlight = "[败方MVP]"
                
                achievement = ""
                if game.get('hero1RampageCnt', 0) > 0: achievement = "[五杀]"
                elif game.get('hero1UltraKillCnt', 0) > 0: achievement = "[四杀]"
                elif game.get('hero1TripleKillCnt', 0) > 0: achievement = "[三杀]"
                elif game.get('godLikeCnt', 0) > 0: achievement = "[超神]"
                elif game.get('firstBlood', 0) > 0: achievement = "[一血]"
                
                # 英雄与评分
                hero_id = game.get('heroId', '未知')
                hero_str = HERO_ID_MAP.get(str(hero_id), f"未知{hero_id}")
                grade_str = f"评分:{game['gradeGame']}" if game.get('gradeGame') else ""
                desc_str = game.get('desc', '').strip()
                
                parts = [
                    game['gametime'],  # 03-21 20:08
                    f"时长:{game['time_str']}",  # 时长
                    battle_type_str,  # [巅峰赛/排位赛等]
                    hero_str,  # 英雄名字
                    f"{game['killcnt']}-{game['deadcnt']}-{game['assistcnt']}",  # KDA
                    result_flag,  # 胜利/失败
                    grade_str,  # 评分
                    rank_info,  # 巅峰分
                    f"{highlight}{achievement}".strip(),  # [MVP][三杀]等
                    desc_str  # 伯仲局/带飞局/暴走局等
                ]
                
                # 过滤空字段
                filtered_parts = [p for p in parts if p and p.strip()]
                result_lines.append(" ".join(filtered_parts))
            
            return_data["data"] = "\n".join(result_lines)
            return_data["code"] = 200
            
        except Exception as e:
            logger.error(f"处理数据时出错: {e}", exc_info=True)
            return_data["msg"] = "❌ 处理战绩数据时出错"
            return_data["code"] = 500

        return return_data


    async def ziliao(self, name: str):
        return_data = self._init_return_data()
        return_data["temp"] = ""
        return_data["comment"] = {"data": []}
        return_data["data"] = ""
        
        if not self.ytapi_token.strip():
            return_data["msg"] = "❌ 未配置应天API令牌"
            return return_data
        
        gokid = await self.get_gokid(name)
        if not gokid:
            return_data["msg"] = "❌ 未查询到该用户"
            return return_data

        params = {"id": gokid, "key": self.ytapi_token}
        api_resp = await self._base_request("gok_ziliao", "GET", params=params, out_key="")
        
        if not isinstance(api_resp, dict) or api_resp.get("code") != 200:
            return_data["msg"] = f"❌ {api_resp.get('msg', '查询失败')}" if isinstance(api_resp, dict) else "❌ API返回异常"
            return return_data
        
        raw_data = api_resp.get("data", {})
        if not isinstance(raw_data, dict):
            return_data["msg"] = "⚠️ 资料数据格式异常"
            return return_data
        
        role_card = raw_data.get("roleCard", {})
        if not role_card:
            return_data["msg"] = "ℹ️ 未获取到角色资料数据"
            return return_data
        
        # 安全格式化数字
        def fmt_num(val):
            if val is None or (isinstance(val, str) and not val.strip()):
                return ""
            try:
                clean = ''.join(c for c in str(val) if c.isdigit())
                return f"{int(clean):,}" if clean else ""
            except:
                return ""
        
        lines = []
        
        # ID
        role_name = (role_card.get("roleName") or "").strip() or "玩家朋友"
        server_name = (role_card.get("serverName") or "").strip() or "未知区服"
        
        # 在线状态
        online_status = ""
        game_online = role_card.get("gameOnline")
        if game_online == 1:
            online_status = "在线"
        elif game_online == 0:
            online_status = "离线"
        
        id_parts = [f"「{role_name}」", server_name]
        if online_status:
            id_parts.append(online_status)
        lines.append(" ".join(id_parts))
        
        # 段位
        role_job = (role_card.get("roleJobName") or "").strip()
        star_num = (role_card.get("starNum") or "").strip()
        if role_job or star_num:
            seg_parts = []
            if role_job:
                seg_parts.append(role_job)
            if star_num:
                seg_parts.append(f"★{star_num}星")
            lines.append(" ".join(seg_parts))
        
        # 战斗统计分区
        stats = []
        
        # 战斗力（需千分位）
        fp_val = fmt_num(role_card.get("fightPowerItem", {}).get("value1"))
        if fp_val:
            stats.append(f"战斗力：{fp_val}")
        
        # 总对局数（需千分位 + "场"）
        tb_val = fmt_num(role_card.get("totalBattleCountItem", {}).get("value1"))
        if tb_val:
            stats.append(f"总对局数：{tb_val}场")
        
        # MVP次数（需千分位 + "次"）
        mvp_val = fmt_num(role_card.get("mvpNumItem", {}).get("value1"))
        if mvp_val:
            stats.append(f"MVP次数：{mvp_val}次")
        
        # 胜率（保留原始格式，如"50.37%"）
        win_val = (role_card.get("winRateItem", {}).get("value1") or "").strip()
        if win_val:
            stats.append(f"胜率：{win_val}")
        
        # 两两分组输出（严格按原顺序，缺失即跳过）
        for i in range(0, len(stats), 2):
            lines.append(" ".join(stats[i:i+2]))
        
        # 英雄皮肤分区
        hero_item = role_card.get("heroNumItem", {})
        skin_item = role_card.get("skinNumItem", {})
        
        hero_val1 = (hero_item.get("value1") or "").strip()
        hero_val2 = (hero_item.get("value2") or "").strip()
        skin_val1 = (skin_item.get("value1") or "").strip()
        skin_val2 = (skin_item.get("value2") or "").strip()
        
        parts = []
        # 英雄部分：仅当已拥有数量（value1）有效时显示
        if hero_val1:
            parts.append(f"英雄 {hero_val1}/{hero_val2 if hero_val2 else '-'}")
        # 皮肤部分：仅当已拥有数量（value1）有效时显示
        if skin_val1:
            parts.append(f"皮肤 {skin_val1}/{skin_val2 if skin_val2 else '-'}")
        
        # 仅当至少有一个部分有效时添加该行
        if parts:
            lines.append(" ".join(parts))
        
        # 输出
        if len(lines) >= 2:  # 至少有ID行+段位行
            return_data["data"] = "\n".join(lines)
            return_data["code"] = 200
        else:
            return_data["msg"] = "ℹ️ 未提取到有效资料字段"
        
        return return_data


    async def zhanli(self, hero: str, type: str):
        return_data = self._init_return_data()
        
        if not self.nyapi_token:
            return_data["msg"] = "❌ 未配置柠柚API令牌，战力查询不可用"
            return return_data

        type_clean = type.strip() if type else ""
        
        # 关键逻辑：仅当 type 是 "aqq" 且非用户显式指定其他有效大区时，触发四大区查询
        if not type_clean or type_clean.lower() in ["aqq", "all"]:
            query_types = ["aqq", "awx", "iqq", "iwx"]
        else:
            query_types = [type_clean]
            
        type_order = {"aqq": 0, "awx": 1, "iqq": 2, "iwx": 3}
        results = []

        # 严格串行查询（兼容原API逻辑）
        for t in query_types:
            params = {"hero": hero, "type": t, "apikey": self.nyapi_token}
            try:
                data = await self._base_request("gok_zhanli", "GET", params=params)
                if not data or not isinstance(data, dict) or 'info' not in data:
                    results.append({"type": t, "success": False, "error": "数据格式异常"})
                    continue
                
                info = data['info']
                results.append({
                    "type": t,
                    "success": True,
                    "province": str(info.get('province', '未知')),
                    "provincePower": str(info.get('provincePower', '0')),
                    "city": str(info.get('city', '未知')),
                    "cityPower": str(info.get('cityPower', '0')),
                    "area": str(info.get('area', '未知')),
                    "areaPower": str(info.get('areaPower', '0'))
                })
            except Exception as e:
                results.append({"type": t, "success": False, "error": str(e)})

        # 全失败处理
        if not any(r["success"] for r in results):
            errs = "\n".join([f"{r['type']}: {r['error']}" for r in results])
            return_data["msg"] = f"❌ 查询失败：\n{errs}"
            return return_data

        # 构建统一输出（严格按 aqq→awx→iqq→iwx 排序），并简化类型标记
        lines = [f"{hero}最低战力"]
        for res in sorted(results, key=lambda x: type_order.get(x["type"].lower(), 999)):
            if res["success"]:
                type_short = res["type"][:2]  # 取类型首字母简化显示
                lines.append(
                    f"{type_short}{res['province']}{res['provincePower']}"
                    f"{res['city']}{res['cityPower']}"
                    f"{res['area']}{res['areaPower']}"
                )
            else:
                lines.append(f"{res['type']} | ❌ {res['error']}")
        
        # 添加数据更新时间
        from datetime import datetime
        update_time = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        lines.append(f"数据更新时间：{update_time}")

        return_data["data"] = "\n".join(lines)
        return_data["code"] = 200
        return return_data