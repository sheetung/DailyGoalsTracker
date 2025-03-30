import os
import asyncio
from datetime import datetime, timezone, timedelta
from pkg.plugin.context import *
from pkg.plugin.events import *
from pkg.platform.types import *
from .database import DatabaseManager
from .generator import Generator
from pkg.provider import entities as llm_entities
import json

@register(name="DailyGoalsTracker", 
          description="打卡系统,实现每日目标打卡，可重复打卡不同目标，并且统计持续打卡时间，月年打卡记录等", 
          version="1.11", 
          author="sheetung")
class DailyGoalsTrackerPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        self.ap = host.ap
        self.db = DatabaseManager()
        self.adminInit = False
        self.start_time = 0
        self.timeout_task = None
        
        self._generator = Generator(self.ap)
        self.cooldown = 30                  # 请求冷却时间（秒）
        self.last_request = 0               # 最后请求时间戳
        self.retry_limit = 3                # 最大重试次数

    async def handle_timeout(self, ctx):
        """处理超时的异步任务"""
        try:
            await asyncio.sleep(7)
            if self.adminInit:
                self.adminInit = False
                self.start_time = 0
                await ctx.send_message(
                    ctx.event.launcher_type,
                    str(ctx.event.launcher_id),
                    MessageChain([Plain(" 操作超时，已退出管理模式。")])
                )
        except asyncio.CancelledError:
            pass
        finally:
            self.timeout_task = None

    async def initialize(self):
        self.db.init_db()

    @handler(PersonMessageReceived)
    @handler(GroupMessageReceived)
    async def group_normal_received(self, ctx: EventContext):
        msg = str(ctx.event.message_chain)
        user_id = ctx.event.sender_id
        parts = msg.split(maxsplit=2)
        cmd = parts[0].strip()
        parts1 = parts[1].strip() if len(parts) > 1 else ""
        parts2 = parts[2].strip() if len(parts) > 2 else ""

        launcher_id = str(ctx.event.launcher_id)
        launcher_type = str(ctx.event.launcher_type)
        
        # 获取黑/白名单
        mode = self.ap.pipeline_cfg.data['access-control']['mode']
        sess_list = self.ap.pipeline_cfg.data['access-control'][mode]

        found = False
        if (launcher_type == 'group' and 'group_*' in sess_list) \
            or (launcher_type == 'person' and 'person_*' in sess_list):
            found = True
        else:
            for sess in sess_list:
                if sess == f"{launcher_type}_{launcher_id}":
                    found = True
                    break 
        
        ctn = found if mode == 'whitelist' else not found
        if not ctn:
            return

        # 处理 cmd，如果包含 / 则删除 /
        if '/' in cmd:
            cmd = cmd.replace('/', '')

        if cmd == "打卡":
            # self.db.clear_old_checkins()
            if not parts1:
                last_checkins = self.db.get_checkins(user_id)
                if not last_checkins:
                    await ctx.reply(MessageChain([At(user_id), Plain("\n请输入打卡目标且没有历史记录！\n \
                                                                    打卡命令有：\n/打卡 <目标>\n/打卡记录\n/打卡分析\n/打卡删除 <目标>\n/打卡删除 所有\n\
                                                                    /打卡管理\n/创建打卡管理员\n\
                                                                    等，具体阅读readme：https://github.com/sheetung/DailyGoalsTracker")]))
                    return
                last_checkin_id = last_checkins[-1][0]
                goals = self.db.get_goals(last_checkin_id)
            else:
                goals = [g.strip() for g in parts1.split(",") if g.strip()]

            if not goals:
                await ctx.reply(MessageChain([At(user_id), Plain(" 打卡目标不能为空！")]))
                return

            new_goals = []
            has_duplicate = False
            for goal in goals:
                if self.db.has_checked_in_today(user_id, goal):
                    has_duplicate = True
                    await ctx.reply(MessageChain([At(user_id), Plain(f" 目标【{goal}】今日已打卡！")]))
                else:
                    new_goals.append(goal)

            if not new_goals:
                return

            checkin_id = self.db.checkin(user_id, new_goals)
            if checkin_id:
                details = []
                for goal in new_goals:
                    days = self.db.get_consecutive_days(user_id, goal)
                    details.append(f"【{goal}】连续打卡 {days} 天")
                
                reply_msg = "打卡成功！\n" + "\n".join(details)
                await ctx.reply(MessageChain([At(user_id), Plain(f" {reply_msg}")]))
            else:
                await ctx.reply(MessageChain([At(user_id), Plain(" 打卡失败，请稍后重试！")]))
        
        elif cmd == "打卡删除":
            if parts1 == "所有":
                count = self.db.delete_all_checkins(user_id)
                reply = f"已删除所有打卡记录，共{count}次打卡"
            else:
                goal_to_delete = parts1
                deleted_count = self.db.delete_goals(user_id, goal_to_delete)
                if deleted_count == 0:
                    reply = f"未找到目标【{goal_to_delete}】的打卡记录"
                else:
                    reply = f"已删除目标【{goal_to_delete}】的{deleted_count}条记录"
            
            await ctx.reply(MessageChain([At(user_id), Plain(f" {reply}")]))
            return

        elif cmd == "打卡记录":
            checkins = self.db.get_checkins(user_id)
            if not checkins:
                await ctx.reply(MessageChain([At(user_id), Plain(" 暂无打卡记录！")]))
                return

            goals_data = {}
            for checkin_record in checkins:
                checkin_id = checkin_record[0]
                goals = self.db.get_goals(checkin_id)
                for goal in goals:
                    if goal not in goals_data:
                        goals_data[goal] = []
                    goals_data[goal].append(checkin_record[2])

            report = ["打卡统计："]
            goals_list = []
            for goal, times in goals_data.items():
                total = len(times)
                consecutive = self.db.get_consecutive_days(user_id, goal)
                goals_list.append((goal, total, consecutive))
            
            sorted_goals = sorted(goals_list, key=lambda x: (-x[1], -x[2]))
            
            for goal_info in sorted_goals:
                goal, total, consecutive = goal_info
                report.append(f"【{goal}】累计 {total} 天 | 连续 {consecutive} 天")

            await ctx.reply(MessageChain([At(user_id), Plain("\n".join(report))]))
            return

        elif cmd == "创建打卡管理员":
            reAdmin_status, reAdmin_id = self.db.read_admin_id(user_id)
    
            if reAdmin_status == "不存在":
                await ctx.reply(MessageChain([At(reAdmin_id), Plain(f"已创建管理员{reAdmin_id}")]))
            elif reAdmin_status == "存在":
                await ctx.reply(MessageChain([At(reAdmin_id), Plain(f"已存在管理员{reAdmin_id}")]))
                
        elif cmd == "打卡管理" and not self.adminInit:
            # reAdmin_status, reAdmin_id = self.db.read_admin_id(user_id)
            is_admin, reAdmin_id = await self._check_admin_permission(ctx, user_id, "打卡管理")
            if not is_admin and reAdmin_id:
                await ctx.reply(MessageChain([At(int(user_id)), Plain(f'需管理员权限')]))
                return
            
            if parts1 == "删除":
                self.adminInit = True
                if self.timeout_task:
                    self.timeout_task.cancel()
                self.timeout_task = asyncio.create_task(self.handle_timeout(ctx))
                await ctx.reply(MessageChain([At(user_id), Plain(f"确认清空？(确认清空)\n倒计时7S")]))         
                return
            elif parts1 == "备份":
                # 执行备份操作 默认数据路目录data目录下，默认仅保存三份
                success, result = self.db.backup_database()
                if success:
                    backup_size = os.path.getsize(result) / 1024  # 转换为KB
                    await ctx.reply(MessageChain([
                        At(user_id),
                        Plain(f"✅ 备份成功\n路径: {result}\n大小: {backup_size:.1f}KB")
                    ]))
                else:
                    await ctx.reply(MessageChain([
                        At(user_id),
                        Plain(f"❌ 备份失败\n原因: {result}")
                    ]))
            else:
                await ctx.reply(MessageChain([
                    At(int(user_id)),
                    Plain('可用命令：\n打卡管理 删除\n打卡管理 备份')
                ]))
                    
        elif cmd == "确认清空" and self.adminInit:
            self.db.clear_database()
            self.adminInit = False
            self.start_time = 0
            reply = f"已删除所有打卡记录"
            await ctx.reply(MessageChain([At(user_id), Plain(f" {reply}")]))
            return
        
        elif cmd == '打卡分析':
        #     self.ap.logger.info(f"用户 {user_id} 请求---{msg}---")  # 信息日志
            # 检查是否有打卡数据
            goal_data = self.db.get_recent_checkins(user_id)
            if not goal_data:
                await ctx.reply("您最近没有打卡记录！")
                return
            
            # 获取近30天打卡记录
            goal_data = self.db.get_recent_checkins(user_id)
            
            if not goal_data:
                # await ctx.reply(MessageChain([At(user_id), Plain(" 您最近30天没有打卡记录哦！")]))
                return
            
            # 准备分析数据
            analysis_data = {
                "user_id": user_id,
                "goals": []
            }
            
            for goal, times in goal_data.items():
                analysis_data["goals"].append({
                    "goal": goal,
                    "checkin_times": times,
                    "count": len(times)
                })
            
            # 将数据转换为JSON格式
            data_json = json.dumps(analysis_data, ensure_ascii=False, indent=2)
            # self.ap.logger.info(f"用户 {user_id} data_json---{data_json}---")  # 信息日志
            system_prompt=f"""
                你可以帮助用户分析打卡记录并提供建议。
                请根据以下规则进行分析：
                1. 首先显示"【打卡分析报告】"标题
                2. 分析不同目标的打卡时间分布规律
                3. 指出可能存在的问题（如打卡时间不稳定）
                4. 针对每个目标给出改进建议
                5. 最后用一句充满元气的话鼓励用户
                6. 使用emoji增加报告的活泼感
                7. 用户使用的是聊天工具，无法解析markdown，不要使用markdown格式输出
                
                用户数据将以JSON格式提供，包含目标名称和对应的打卡时间列表。
                
                示例回复格式：
                【打卡分析报告】
                
                📅 总体情况:
                - 您共完成了X次打卡
                - 涉及X个不同目标
                
                🔍 详细分析:
                - [目标1]: (分析内容)
                - [目标2]: (分析内容)
                
                💡 改进建议:
                - (具体建议)

                🚁 打卡寄语:
                (充满正能量的话语)
                用户的打卡数据为{data_json}
                """ 
             # 调用大模型（带重试机制）
            answer = await self._retry_chat(cmd, system_prompt)
            # 格式化输出
            # response = f"【问题】{cmd}\n【解答】{answer.strip()}"
            
            # 发送并阻止默认处理
            await ctx.reply(MessageChain([At(user_id), Plain(f" {answer}")]))
            ctx.prevent_default() 

    async def _retry_chat(self, question: str, system_prompt: str) -> str:
        """带重试机制的模型调用"""
        for attempt in range(self.retry_limit):
            try:
                return await self._generator.return_chat(
                    request=question,
                    system_prompt=system_prompt
                )
            except Exception as e:
                if attempt == self.retry_limit - 1:
                    raise
                logging.warning(f"第{attempt+1}次请求失败，1秒后重试...")
                await asyncio.sleep(1)
    
    async def _check_admin_permission(self, ctx, user_id, required_action):
        """
        统一管理员权限验证
        :param ctx: 上下文对象
        :param user_id: 当前用户ID
        :param required_action: 需要执行的操作名称（用于提示）
        :return: (is_admin, admin_id) 元组
        """
        reAdmin_status, reAdmin_id = self.db.read_admin_id(user_id)
        
        if reAdmin_status == "不存在":
            await ctx.reply(MessageChain([
                At(int(user_id)), 
                Plain(f'未创建打卡管理员\n使用命令"创建打卡管理员"进行授权')
            ]))
            return (False, None)
        
        if user_id != reAdmin_id:
            await ctx.reply(MessageChain([
                At(int(user_id)),
                Plain(f'需要管理员 [{reAdmin_id}] 权限才能{required_action}')
            ]))
            return (False, reAdmin_id)
        
        return (True, reAdmin_id)

    def __del__(self):
        pass
