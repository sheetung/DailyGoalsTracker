import os
import asyncio
import json
from pkg.plugin.context import *
from pkg.plugin.events import *
from pkg.platform.types import *
from typing import Dict, Callable, Optional
from pkg.plugin.context import APIHost, BasePlugin, register
from .dbedit import DatabaseManager
from .generator import Generator
from collections import defaultdict
from datetime import datetime, timedelta, timezone

china_tz = timezone(timedelta(hours=8))

class CommandHandler:
    """命令处理基类"""
    def __init__(self, plugin: 'DailyGoalsTrackerPlugin'):
        self.plugin = plugin
        self.db = plugin.db
        self.ap = plugin.ap
    async def handle(self, ctx: EventContext, user_id: str, args: list):
        raise NotImplementedError
class CheckInHandler(CommandHandler):
    """打卡命令处理（支持无参数自动使用上次目标）"""
    async def handle(self, ctx: EventContext, user_id: str, args: list):
        if not args:
            await self._handle_no_args(ctx, user_id)
        else:
            await self._handle_with_args(ctx, user_id, args)
    async def _handle_no_args(self, ctx: EventContext, user_id: str):
        """处理无参数打卡（增强版）"""
        last_goals = self._get_last_goals(user_id)
        
        if not last_goals:
            await self._show_help(ctx, user_id)
            await ctx.reply([
                At(user_id),
                Plain("\n❌ 没有历史打卡记录，请指定目标！")
            ])
            return
        
        # 获取所有目标的打卡状态
        goal_status = []
        valid_goals = []
        for goal in last_goals:
            if self.db.has_checked_in_today(user_id, goal):
                days = self.db.get_consecutive_days(user_id, goal) - 1  # 今日之前连续天数
                goal_status.append(f"【{goal}】今日已打卡（连续 {days} 天）")
            else:
                valid_goals.append(goal)
        
        if valid_goals:
            # 执行有效目标打卡
            checkin_id = self.db.checkin(user_id, valid_goals)
            details = self._build_checkin_details(user_id, valid_goals)
            
            reply = (
                f"⏰ 自动使用上次目标\n"
                f"{details}"
            )
        else:
            # 所有目标已打卡时显示完整信息
            current_status = "\n".join(goal_status)
            reply = (
                f"🎉 今日打卡完成！\n"
                f"{current_status}"
            )
        
        await ctx.reply([At(user_id), Plain(reply)])

    def _get_last_goals(self, user_id: str) -> list:
        """获取用户最后一次打卡目标"""
        last_checkin = self.db.get_checkins(user_id)
        if not last_checkin:
            return []
        
        last_checkin_id = last_checkin[0][0]
        return self.db.get_goals(last_checkin_id)
    async def _handle_with_args(self, ctx: EventContext, user_id: str, args: list):
        """处理带参数打卡"""
        goals = [g.strip() for g in args[0].split(",") if g.strip()]
        
        if not goals:
            await ctx.reply([At(user_id), Plain("❌ 目标不能为空！")])
            return
        
        new_goals, duplicates = self._filter_duplicates(user_id, goals)
        
        if duplicates:
            await ctx.reply([
                At(user_id),
                Plain(f"⚠️ 已过滤重复目标：{', '.join(duplicates)}")
            ])
        
        if not new_goals:
            return
        
        checkin_id = self.db.checkin(user_id, new_goals)
        details = self._build_checkin_details(user_id, new_goals)
        await ctx.reply([At(user_id), Plain(f"✅ 打卡成功！\n{details}")])

    def _filter_duplicates(self, user_id: str, goals: list) -> tuple:
        new_goals = []
        duplicates = []
        for goal in goals:
            if self.db.has_checked_in_today(user_id, goal):
                duplicates.append(goal)
            else:
                new_goals.append(goal)
        return new_goals, duplicates
    def _build_checkin_details(self, user_id: str, goals: list) -> str:
        details = []
        for goal in goals:
            days = self.db.get_consecutive_days(user_id, goal)
            details.append(f"【{goal}】连续打卡 {days} 天")
        return "\n".join(details)
    async def _show_help(self, ctx: EventContext, user_id: str):
        help_msg = (
            "打卡命令格式：\n"
            "/打卡 <目标1>,<目标2>\n"
            "示例：/打卡 健身,阅读"
        )
        await ctx.reply([At(user_id), Plain(help_msg)])

class DeleteHandler(CommandHandler):
    """删除打卡记录处理"""
    async def handle(self, ctx: EventContext, user_id: str, args: list):
        if not args:
            return await self._show_help(ctx, user_id)
        
        target = args[0]
        if target == "所有":
            # 管理员权限验证
            is_admin, admin_id = await self.plugin._check_admin_permission(
                ctx, user_id, "删除所有记录"
            )
            if not is_admin:
                return
            
            count = self.db.delete_all_checkins(user_id)
            reply = f"已删除所有打卡记录，共{count}次打卡"
        else:
            deleted_count = self.db.delete_goals(user_id, target)
            if deleted_count == 0:
                reply = f"未找到目标【{target}】的打卡记录"
            else:
                reply = f"已删除目标【{target}】的{deleted_count}条记录"
        
        await ctx.reply([At(user_id), Plain(reply)])
    async def _show_help(self, ctx: EventContext, user_id: str):
        help_msg = (
            "删除命令格式：\n"
            "/打卡删除 <目标名称>\n"
            "/打卡删除 所有\n"
            "（删除所有需要管理员权限）"
        )
        await ctx.reply([At(user_id), Plain(help_msg)])
class RecordHandler(CommandHandler):
    """打卡记录查询处理"""
    async def handle(self, ctx: EventContext, user_id: str, args: list):
        checkins = self.db.get_checkins(user_id)
        if not checkins:
            return await ctx.reply([At(user_id), Plain(" 暂无打卡记录！")])
        
        # 按目标分类统计
        goals_stats = self._analyze_goals(checkins, user_id)
        report = self._format_report(goals_stats)
        
        await ctx.reply([At(user_id), Plain(report)])
    def _analyze_goals(self, checkins: list, user_id: str) -> list:
        goals_data = {}
        for checkin in checkins:
            goals = self.db.get_goals(checkin[0])
            for goal in goals:
                if goal not in goals_data:
                    goals_data[goal] = {
                        'total': 0,
                        'last_date': None,
                        'dates': []
                    }
                goals_data[goal]['total'] += 1
                goals_data[goal]['dates'].append(checkin[2])
                goals_data[goal]['last_date'] = max(
                    goals_data[goal]['last_date'] or checkin[2],
                    checkin[2]
                )
        
        # 计算连续天数
        stats = []
        for goal, data in goals_data.items():
            consecutive = self.db.get_consecutive_days(user_id, goal)
            stats.append((
                goal,
                data['total'],
                consecutive,
                data['last_date']
            ))
        return sorted(stats, key=lambda x: (-x[1], -x[2]))
    def _format_report(self, stats: list) -> str:
        report = ["📊 打卡记录报告", "----------------"]
        for goal, total, consecutive, last_date in stats:
            report.append(
                f"🏷️ 目标：{goal}\n"
                f"✅ 累计天数：{total}天\n"
                f"📆 最后打卡：{last_date[:16]}\n"
                f"⏳ 当前连续：{consecutive}天"
            )
        return "\n".join(report)
class AnalysisHandler(CommandHandler):
    """数据分析处理（纯JSON存储版）"""
    def __init__(self, plugin):
        super().__init__(plugin)
        self.current_directory = os.path.dirname(os.path.abspath(__file__))
        self.storage_file = os.path.join(self.current_directory, "analysis_usage.json")  # 使用记录文件
        self.lock = asyncio.Lock()  # 异步文件操作锁

    async def handle(self, ctx: EventContext, user_id: str, args: list):
        # 检查缓存并处理
        cached_report = await self._get_cached_report(user_id)
        if cached_report:
            time_str = datetime.fromisoformat(cached_report["time"]).strftime("%H:%M")
            return await ctx.reply([
                At(user_id),
                Plain(f"📊 分析报告（{time_str}生成）：\n{cached_report['content']}")
            ])
        # 生成新报告流程
        analysis_data = self._prepare_analysis_data(user_id)
        if not analysis_data:
            return await ctx.reply([At(user_id), Plain("⏳ 暂无近期打卡数据可供分析")])
        try:
            # 生成提示词
            prompt = self._build_prompt(analysis_data)
            
            # 调用大模型
            await ctx.reply([At(user_id), Plain("分析报告正在生成中...")])
            analysis = await self.plugin._retry_chat(
                question="生成打卡分析报告",
                system_prompt=prompt
            )
            
            # 保存并发送结果
            await self._save_report(user_id, analysis)
            await ctx.reply([At(user_id), Plain(f"✅ 最新分析报告：\n{analysis}")])
        except Exception as e:
            await ctx.reply([At(user_id), Plain("⚠️ 报告生成失败，请稍后重试")])
            self.plugin.ap.logger.error(f"分析失败: {str(e)}")

    async def _get_cached_report(self, user_id: str) -> Optional[dict]:
        """获取缓存报告"""
        async with self.lock:
            if not os.path.exists(self.storage_file):
                return None
            try:
                with open(self.storage_file, 'r') as f:
                    reports = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return None
            user_report = reports.get(user_id)
            if not user_report:
                return None
            # 检查时间有效性
            report_time = datetime.fromisoformat(user_report["time"])
            current_time = datetime.now(china_tz)
            if (current_time - report_time) < timedelta(hours=24):
                return user_report
            return None
    async def _save_report(self, user_id: str, content: str):
        """保存报告到文件"""
        async with self.lock:
            # 读取现有数据
            if os.path.exists(self.storage_file):
                try:
                    with open(self.storage_file, 'r') as f:
                        reports = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    reports = {}
            else:
                reports = {}
            # 更新记录
            reports[user_id] = {
                "time": datetime.now(china_tz).isoformat(),
                "content": content
            }
            # 写入文件
            with open(self.storage_file, 'w') as f:
                json.dump(reports, f, indent=2, ensure_ascii=False)
            
    def _prepare_analysis_data(self, user_id: str) -> dict:
        goal_data = self.db.get_recent_checkins(user_id)
        if not goal_data:
            return None
        
        # 准备解析数据
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
        return data_json
        
    def _build_prompt(self, data: dict) -> str:
        return f"""
            请根据以下打卡数据生成分析报告：
            {data}
            
            报告要求：
            1. 使用中文口语化表达
            2. 包含总体情况、目标分析、改进建议三个部分
            3. 每个目标指出最佳打卡时间段和波动情况
            4. 使用emoji增加可读性
            5. 最后给出鼓励语句
            6. 禁止使用Markdown格式
            """
class SupplementHandler(CommandHandler):
    """补打卡处理"""
    async def handle(self, ctx: EventContext, user_id: str, args: list):
        try:
            target_user, goal, date_str = self._parse_args(user_id, args)
            
            # 权限验证（当操作其他用户时）
            if target_user != user_id:
                is_admin, _ = await self.plugin._check_admin_permission(
                    ctx, user_id, "为他人补打卡"
                )
                if not is_admin:
                    return
            
            # 执行补打卡
            checkin_id = self.db.supplement_checkin(
                user_id=target_user,
                goal=goal,
                checkin_date=date_str
            )
            
            reply = (
                f"✅ 补打卡成功！\n"
                f"用户：{target_user}\n"
                f"目标：{goal}\n"
                f"时间：{date_str}\n"
                f"当前连续天数：{self.db.get_consecutive_days(target_user, goal)}"
            )
            await ctx.reply([At(user_id), Plain(reply)])
        except ValueError as e:
            await ctx.reply([At(user_id), Plain(f"❌ 参数错误：{str(e)}")])
        except Exception as e:
            await ctx.reply([At(user_id), Plain(" 补打卡失败，请检查格式")])
    def _parse_args(self, sender_id: str, args: list) -> tuple:
        """解析参数返回 (目标用户, 目标, 日期时间)"""
        if len(args) < 2:
            raise ValueError("参数不足")
        
        # 判断第一个参数是否是用户ID
        if args[0].isdigit() and len(args[0]) >= 8:
            target_user = args[0]
            goal = args[1]
            date_str = " ".join(args[2:]) if len(args) > 2 else args[2]
        else:
            target_user = sender_id
            goal = args[0]
            date_str = " ".join(args[1:])
        
        # 验证日期格式
        try:
            datetime.strptime(date_str[:10], "%Y-%m-%d")
        except ValueError:
            raise ValueError("日期格式应为YYYY-MM-DD")
        
        return target_user, goal, date_str
class AdminCommandHandler(CommandHandler):
    """管理员命令处理（优化版）"""
    def __init__(self, plugin):
        super().__init__(plugin)

    async def handle(self, ctx: EventContext, user_id: str, args: list):
        if not args:
            return await self._show_help(ctx, user_id)
        
        action = args[0]
        if action == "创建":
            await self._handle_create_admin(ctx, user_id)
        elif action == "备份":
            await self._handle_backup(ctx, user_id)
        else:
            await self._show_help(ctx, user_id)

    async def _handle_create_admin(self, ctx: EventContext, user_id: str):
        """创建管理员"""
        is_admin, _ = await self.plugin._check_admin_permission(ctx, user_id, "创建管理员")
        if not is_admin:
            return
        status, admin_id = self.db.read_admin_id(user_id)
        if status == "存在":
            reply = f"⚠️ 管理员已存在：{admin_id}"
        else:
            reply = f"✅ 管理员身份已授予：{user_id}"
        await ctx.reply([At(user_id), Plain(reply)])

    async def _handle_backup(self, ctx: EventContext, user_id: str):
        """处理数据备份"""
        is_admin, _ = await self.plugin._check_admin_permission(ctx, user_id, "数据备份")
        if not is_admin:
            return
        
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

    async def _show_help(self, ctx: EventContext, user_id: str):
        help_msg = (
            "🛠️ 管理命令指南\n"
            "----------------\n"
            "1. 创建管理员：/打卡管理 创建\n"
            "2. 数据备份：/打卡管理 备份\n"
            "----------------\n"
            "⚠️ 所有操作需管理员权限"
        )
        await ctx.reply([At(user_id), Plain(help_msg)])

class HelpCommandHandler(CommandHandler):
    def __init__(self, plugin):
        super().__init__(plugin)

    async def handle(self, ctx: EventContext, user_id: str, args: list):
        help_msg = (
                "📝 打卡系统使用指南\n"
                "-----------------\n"
                "1. 日常打卡：/打卡 <目标>\n"
                "2. 记录查询：/打卡记录\n"
                "3. 数据分析：/打卡分析\n"
                "4. 记录删除：/打卡删除 <目标|所有>\n"
                "5. 补打卡：/打卡补 [用户] <目标> <日期>\n"
                "6. 管理功能：/打卡管理\n"
                "7. 打卡帮助: /打卡帮助"
            )
        await ctx.reply([At(user_id), Plain(help_msg)])

class CheckInManager:
    """打卡系统核心管理类"""
    def __init__(self, plugin: 'DailyGoalsTrackerPlugin'):
        self.plugin = plugin
        self.command_handlers: Dict[str, CommandHandler] = {
            '打卡': CheckInHandler(plugin),
            '打卡删除': DeleteHandler(plugin),
            '打卡记录': RecordHandler(plugin),
            '打卡分析': AnalysisHandler(plugin),
            '打卡补': SupplementHandler(plugin),
            '打卡管理': AdminCommandHandler(plugin),
            '打卡帮助': HelpCommandHandler(plugin)
        }
    
    async def process_command(self, ctx: EventContext, cmd: str, user_id: str, args: list):
        handler = self.command_handlers.get(cmd)
        if handler:
            await handler.handle(ctx, user_id, args)
        else:
            return

@register(name="DailyGoalsTracker", 
         description="打卡系统，支持目标管理、AI分析等功能",
         version="2.14", 
         author="sheetung")
class DailyGoalsTrackerPlugin(BasePlugin):
    def __init__(self, host: APIHost):
        self.ap = host.ap
        self.db = DatabaseManager()
        self.manager = CheckInManager(self)
        # self.admin_mode = AdminModeManager(self)
        self._generator = Generator(self.ap)
        
        # 初始化配置
        self.cooldown = 30
        self.retry_limit = 3
        self._last_request = 0

    async def initialize(self):
        self.db.init_db()

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
        
        if user_id != str(reAdmin_id):
            self.ap.logger.info(f"user_id:{user_id} reAdmin_id:{reAdmin_id}")  # 信息日志
            await ctx.reply(MessageChain([
                At(int(user_id)),
                Plain(f'需要管理员 [{reAdmin_id}] 权限才能{required_action}')
            ]))
            return (False, reAdmin_id)
        
        return (True, reAdmin_id)
    
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
    
    @handler(PersonMessageReceived)
    @handler(GroupMessageReceived)
    async def handle_message(self, ctx: EventContext):
        if not self._should_process(ctx):
            return
        
        msg = str(ctx.event.message_chain).strip()
        cmd, *args = msg.lstrip('/').split(maxsplit=1)
        args = args[0].split() if args else []
        self.ap.logger.info(f"cmd: {cmd} args:{args}")  # 信息日志
        await self.manager.process_command(
            ctx,
            cmd=cmd,
            user_id=str(ctx.event.sender_id),
            args=args
        )
    def _should_process(self, ctx: EventContext) -> bool:
        """判断是否处理该消息"""
        # 处理黑/白名单
        launcher_id = str(ctx.event.launcher_id)
        launcher_type = str(ctx.event.launcher_type)

        mode = ctx.event.query.pipeline_config['trigger']['access-control']['mode']
        sess_list = ctx.event.query.pipeline_config['trigger']['access-control'][mode]

        found = False
        if (launcher_type== 'group' and 'group_*' in sess_list) \
            or (launcher_type == 'person' and 'person_*' in sess_list):
            found = True
        else:
            for sess in sess_list:
                if sess == f"{launcher_type}_{launcher_id}":
                    found = True
                    break 
        ctn = False
        if mode == 'whitelist':
            ctn = found
        else:
            ctn = not found
        if not ctn:
            self.ap.logger.info(f'根据访问控制，插件[DailyGoalsTracker]忽略消息\n')
            return False
        # 处理非打卡消息
        cmd_daka = str(ctx.event.message_chain).strip().lstrip('/').startswith("打卡")
        # self.ap.logger.info(f"if:{cmd_daka}")  # 信息日志
        if not cmd_daka:
            return False
        return True
    
# class AdminModeManager:
#     """管理员模式管理"""
#     def __init__(self, plugin: 'DailyGoalsTrackerPlugin'):
#         self.plugin = plugin
#         self.active = False
#         self.timeout_task: Optional[asyncio.Task] = None
#     async def enter_admin_mode(self, ctx: EventContext, user_id: str):
#         """进入管理模式"""
#         if self.active:
#             await ctx.reply([At(user_id), Plain(" 已处于管理模式")])
#             return
        
#         self.active = True
#         await ctx.reply([At(user_id), Plain(" 进入管理模式，7秒无操作自动退出")])
#         self._start_timeout(ctx)
#     async def handle_admin_command(self, ctx: EventContext, user_id: str, action: str):
#         """处理管理命令"""
#         if action == "删除":
#             self.db.clear_database()
#             await ctx.reply([At(user_id), Plain(" 已清空所有数据")])
#         elif action == "备份":
#             success, path = self.db.backup_database()
#             if success:
#                 await ctx.reply([At(user_id), Plain(f" 备份成功：{path}")])
#             else:
#                 await ctx.reply([At(user_id), Plain(f" 备份失败：{path}")])
#         self.exit_admin_mode()
#     def exit_admin_mode(self):
#         """退出管理模式"""
#         self.active = False
#         if self.timeout_task:
#             self.timeout_task.cancel()
#         self.timeout_task = None
#     def _start_timeout(self, ctx: EventContext):
#         """启动超时计时"""
#         async def timeout_task():
#             await asyncio.sleep(7)
#             self.exit_admin_mode()
#             await ctx.reply([At(ctx.event.sender_id), Plain(" 管理模式已超时退出")])
        
#         self.timeout_task = asyncio.create_task(timeout_task())
    