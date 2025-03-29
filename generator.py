"""
Author: ElvisChenML
Github: https://github.com/ElvisChenML
"""
import json
import typing
import re
import functools
import os
from pkg.core import app
from pkg.provider import entities as llm_entities
from pkg.provider.modelmgr import errors


def handle_errors(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except errors.RequesterError as e:
            args[0].ap.logger.error(f"请求错误：{e}")
            raise
        except Exception as e:
            args[0].ap.logger.error(f"未处理的异常：{e}")
            raise
    return wrapper


class Generator:
    def __init__(self, ap: app.Application):
        self.ap = ap
        self._jail_break_dict = {}
        self._jail_break_type = ""
        self._speakers = []

    def _get_chat_prompts(self, 
                        user_prompt: str | typing.List[llm_entities.Message],
                        system_prompt: str = None
                        ) -> typing.List[llm_entities.Message]:
        """构建对话提示词链"""
        messages = []
        
        # 破甲提示词处理
        if self._jail_break_type in ["before", "all"] and "before" in self._jail_break_dict:
            messages.append(llm_entities.Message(
                role="system",
                content=self._jail_break_dict["before"]
            ))
        
        # 系统提示词
        if system_prompt:
            messages.append(llm_entities.Message(
                role="system", 
                content=system_prompt
            ))
        
        # 后置破甲提示词
        if self._jail_break_type in ["after", "all"] and "after" in self._jail_break_dict:
            messages.append(llm_entities.Message(
                role="system",
                content=self._jail_break_dict["after"]
            ))
        
        # 结尾附加内容
        if self._jail_break_type in ["end", "all"] and "end" in self._jail_break_dict:
            end_content = self._jail_break_dict["end"]
            if isinstance(user_prompt, list):
                user_prompt[-1].content += end_content
            else:
                user_prompt += end_content
        
        # 添加用户输入
        if isinstance(user_prompt, list):
            messages.extend(user_prompt)
        else:
            messages.append(llm_entities.Message(
                role="user", 
                content=user_prompt
            ))
        
        return messages

    @handle_errors
    async def return_chat(self, 
                        request: str | typing.List[llm_entities.Message],
                        system_prompt: str = None
                        ) -> str:
        """核心对话接口"""
        model_info = await self.ap.model_mgr.get_model_by_name(
            self.ap.provider_cfg.data["model"]
        )
        
        # 构建消息链
        messages = self._get_chat_prompts(request, system_prompt)
        
        # 记录请求日志
        self.ap.logger.debug("发送请求：\n%s", 
                            "\n".join(m.readable_str() for m in messages))
        
        # 调用模型
        response = await model_info.requester.call(
            None, 
            model=model_info, 
            messages=messages
        )
        
        # 清洗响应内容
        cleaned_response = self._clean_response(response.content)
        # self.ap.logger.debug("模型原始回复：%s", response.content)
        # self.ap.logger.info("清洗后回复：%s", cleaned_response)
        
        return cleaned_response

    def _clean_response(self, response: str) -> str:
        """响应清洗管道"""
        # 移除发言人前缀
        if self._speakers:
            pattern = rf"^({'|'.join(re.escape(s) for s in self._speakers)})[:：]\s*"
            response = re.sub(pattern, "", response)
        
        # 移除特殊标签
        response = self._remove_think_content(response)
        
        # 移除引号
        response = re.sub(r'[\"“‘\'「”’」]', '', response)
        
        # 移除调试标记
        response = response.replace("<结束无效提示>", "")
        
        # 移除时间戳
        return re.sub(r"\[\d{2}年\d{2}月\d{2}日[上午下午]?\d{2}时\d{2}分\]", "", response)

    def _remove_think_content(self, text: str) -> str:
        """移除思考标签"""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return re.sub(r'\n\s*\n', '\n', text.strip())

    def set_jail_break(self, 
                     jail_break_type: str, 
                     user_name: str,
                     config_dir: str = "data/plugins/Waifu/config/"):
        """配置破甲提示词"""
        self._jail_break_type = jail_break_type
        self._jail_break_dict = {}
        
        load_types = ["before", "after", "end"] if jail_break_type == "all" else [jail_break_type]
        
        for t in load_types:
            file_path = os.path.join(config_dir, f"jail_break_{t}.txt")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    self._jail_break_dict[t] = f.read().replace("{{user}}", user_name)

    def set_speakers(self, speakers: list):
        """设置发言人过滤列表"""
        self._speakers = [s.strip() for s in speakers if s.strip()]

    @property
    def active_jailbreak(self) -> str:
        """当前生效的破甲类型"""
        return self._jail_break_type