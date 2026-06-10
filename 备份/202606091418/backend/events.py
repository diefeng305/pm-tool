# events.py
import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Set
import threading
import time
from datetime import datetime

router = APIRouter(prefix="/api/events", tags=["实时事件推送"])

# 存储所有活跃的客户端连接
class EventManager:
    def __init__(self):
        self.connections: Set[asyncio.Queue] = set()
        self._lock = threading.Lock()
    
    def add_connection(self, queue: asyncio.Queue):
        with self._lock:
            self.connections.add(queue)
    
    def remove_connection(self, queue: asyncio.Queue):
        with self._lock:
            if queue in self.connections:
                self.connections.remove(queue)
    
    async def broadcast(self, event_type: str, data: dict):
        """广播事件给所有连接的客户端"""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        message_str = f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
        
        disconnected = []
        for queue in self.connections:
            try:
                await queue.put(message_str)
            except Exception:
                disconnected.append(queue)
        
        # 清理断开的连接
        for queue in disconnected:
            self.remove_connection(queue)
    
    def get_connection_count(self):
        with self._lock:
            return len(self.connections)

# 全局事件管理器实例
event_manager = EventManager()

# 全局日志变更通知函数（供其他模块调用）
def notify_log_created(log_data: dict):
    """通知前端有新的日志创建"""
    try:
        # 创建异步任务来广播
        asyncio.create_task(event_manager.broadcast("log_created", log_data))
    except RuntimeError:
        # 如果没有运行中的事件循环，使用线程方式
        def _broadcast():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(event_manager.broadcast("log_created", log_data))
            loop.close()
        threading.Thread(target=_broadcast, daemon=True).start()


def notify_data_changed(change_type: str, target: str, target_name: str):
    """通知前端数据有变更"""
    try:
        asyncio.create_task(event_manager.broadcast("data_changed", {
            "change_type": change_type,
            "target": target,
            "target_name": target_name
        }))
    except RuntimeError:
        def _broadcast():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(event_manager.broadcast("data_changed", {
                "change_type": change_type,
                "target": target,
                "target_name": target_name
            }))
            loop.close()
        threading.Thread(target=_broadcast, daemon=True).start()


@router.get("/listen")
async def event_stream(request: Request):
    """SSE 事件流端点"""
    async def generate():
        queue = asyncio.Queue()
        event_manager.add_connection(queue)
        
        try:
            # 发送连接成功消息
            yield f"data: {json.dumps({'type': 'connected', 'message': '已连接到事件服务器'})}\n\n"
            
            while True:
                # 检查客户端是否断开
                if await request.is_disconnected():
                    break
                
                try:
                    # 等待事件，超时30秒后发送心跳
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield message
                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"
        finally:
            event_manager.remove_connection(queue)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )


@router.get("/status")
async def get_event_status():
    """获取事件连接状态"""
    return {
        "code": "SUCCESS",
        "data": {
            "connections": event_manager.get_connection_count(),
            "status": "running"
        }
    }