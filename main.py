from astrbot.api.event import filter, AstrMessageEvent, EventMessageType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import os
from datetime import datetime

@register("chat_history_injector", "GraduateDust800", "聊天记录存储与提示词注入插件", "1.0.0", "https://github.com/GraduateDust800/astrbot_plugin_chat_history")
class ChatHistoryInjector(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 初始化数据存储目录
        self.data_dir = os.path.join("data", "chat_history")
        os.makedirs(self.data_dir, exist_ok=True)
        # 从配置获取历史记录数量，默认为5
        self.history_count = self.config.get("history_count", 5)
        
    # 监听所有消息事件，保存聊天记录
    @filter.event_message_type(EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        # 获取会话唯一标识
        session_id = event.unified_msg_origin
        # 构建消息数据结构
        message_data = {
            "message_id": event.message_obj.message_id,
            "sender_id": event.get_sender_id(),
            "sender_name": event.get_sender_name(),
            "timestamp": event.message_obj.timestamp,
            "content": event.message_str,
            "message_type": "group" if event.get_group_id() else "private"
        }
        
        # 保存到JSON文件
        file_path = os.path.join(self.data_dir, f"{session_id}.json")
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            else:
                history = []
            
            # 保持最新的N条记录
            history.append(message_data)
            if len(history) > self.history_count:
                history = history[-self.history_count:]
                
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
            logger.info(f"已保存消息到会话 {session_id}，当前记录数: {len(history)}")
        except Exception as e:
            logger.error(f"保存聊天记录失败: {str(e)}")
    
    # LLM请求钩子：注入历史记录
    @filter.on_llm_request()
    async def inject_history_to_llm(self, event: AstrMessageEvent, req):
        # 获取当前会话ID
        session_id = event.unified_msg_origin
        file_path = os.path.join(self.data_dir, f"{session_id}.json")
        
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
                
                # 格式化为用户要求的纯文本格式
                history_text = "这是前 {num} 条历史记录：\n".format(num=len(history))
                for i, msg in enumerate(history, 1):
                    history_text += f"{i}. {msg['sender_name']}: {msg['content']}\n"
                
                # 添加最新消息
                history_text += "这是刚刚获取到的消息：\n{message}".format(
                    message=event.message_str
                )
                
                # 注入到system_prompt
                if req.system_prompt:
                    req.system_prompt += "\n\n" + history_text
                else:
                    req.system_prompt = history_text
                    
                logger.info(f"已注入{len(history)}条历史记录到LLM请求")
        except Exception as e:
            logger.error(f"注入历史记录失败: {str(e)}")
    
    async def terminate(self):
        """插件停用前的清理工作"""
        logger.info("聊天记录存储插件已停用")