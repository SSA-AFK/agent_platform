from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import json
from fastapi import APIRouter, Request, Depends
from starlette.responses import StreamingResponse

from backed.agent.sup_agent import main_agent
from backed.agent.checkpointer import global_memory_saver, init_checkpointer, close_checkpointer
from backed.crud.chat_session import get_session_by_id, get_user_sessions, create_chat_session, delete_chat_session, \
    update_session_title
from backed.crud.db_config import ASYNC_DATABASE_URL, get_db

from backed.models.users import User
from backed.schema.chat import ChatRequest
from backed.utils.auth import get_current_user
from backed.utils.response import success_response

chat_router = APIRouter(prefix="/api/chat", tags=["chat"])

@chat_router.get("/sessions")
async def list_sessions(user: User = Depends(get_current_user),db: AsyncSession = Depends(get_db)):
    sessions = await get_user_sessions(db, user.id)
    return success_response(
        message="获取会话列表成功",
        data=[
            {
                "session_id": s.session_id,
                "title": s.title,
                "updated_at": s.updated_at
            }
            for s in sessions
        ]
    )
@chat_router.post("/sessions")
async def create_session(user: User = Depends(get_current_user),db: AsyncSession = Depends(get_db)):
    session = await create_chat_session(db, user.id)
    return success_response(
        message="创建会话成功",
        data={
            "session_id": session.session_id,
            "title": session.title,
            "updated_at": session.updated_at
        }
    )
@chat_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: User = Depends(get_current_user),db: AsyncSession = Depends(get_db)):
    await delete_chat_session(db, session_id, user.id)
    return success_response(message="删除会话成功")


@chat_router.get("/history/{session_id}")
async def get_chat_history(
        session_id: str,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """获取指定会话的聊天历史记录（支持图片 + 地图 + 文本）"""
    # 验证会话属于该用户
    await get_session_by_id(db, session_id, user.id)

    if not global_memory_saver:
        return success_response(data=[])

    config = {"configurable": {"thread_id": session_id}}
    checkpoint = await global_memory_saver.aget_tuple(config)

    if not checkpoint or not checkpoint.checkpoint:
        return success_response(data=[])

    messages = checkpoint.checkpoint.get("channel_values", {}).get("messages", [])

    history = []
    for msg in messages:
        # 只保留 human 和 ai 消息，过滤掉工具调用等中间消息
        if msg.type not in ["human", "ai"]:
            continue
            
        role = "user" if msg.type == "human" else "assistant"
        
        # 兼容：字符串、列表、消息块等所有 LangChain 内容格式
        content = msg.content
        
        if isinstance(content, list):
            content_parts = []
            for part in content:
                if isinstance(part, str):
                    content_parts.append(part)
                elif isinstance(part, dict):
                    # 图片类型
                    if part.get("type") == "image_url":
                        img_url = part.get("image_url", {}).get("url", "")
                        content_parts.append(f"\n![图片]({img_url})\n")
            content = "\n".join(content_parts)

        if isinstance(content, str) and content.strip():
            history.append({
                "role": role,
                "content": content  # 现在会包含：文本 + 图片标记![图片](url) + 地图JSON代码块
            })

    return success_response(data=history)

@chat_router.post("/stream")
async def chat_stream(
        req: ChatRequest,
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    流式对话接口
    """
    session_id = req.session_id
    # 验证会话权限 + 自动更新标题
    session = await get_session_by_id(db, session_id, user.id)
    if session.title == "新对话":
        await update_session_title(db, session_id, user.id, req.query[:15])

    config = {"configurable": {"thread_id": session_id}}

    async def event_generator():
        accumulated_content = ""  # 收集完整回复用于保存
        try:
            # 发送 session_id 给前端
            yield f"event: session_id\ndata: {session_id}\n\n"

            # 流式推理
            async for event in main_agent.astream_events(
                    {"messages": [{"role": "user", "content": req.query}]},
                    config=config,
                    version="v2"
            ):
                # 前端断开连接 → 停止生成
                if await request.is_disconnected():
                    break

                kind = event["event"]

                # 模型输出(只推送主代理最终结果)
                if kind == "on_chat_model_stream":
                    metadata = event.get("metadata", {})
                    node_name = metadata.get("langgraph_node", "")
                
                    print(f"DEBUG: node_name={node_name}, kind={kind}")
                
                    content = event["data"]["chunk"].content
                    print(f"DEBUG: content type={type(content)}, value={repr(content)[:100]}")
                                    
                    # 严格过滤空内容,避免发送无意义的空块
                    if content and isinstance(content, str) and content.strip():
                        accumulated_content += content  # 累积内容
                        msg = {"type": "message_chunk", "content": content}
                        yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                        print(f"DEBUG: yielding message_chunk: {content[:50]}")

                # 工具开始
                elif kind == "on_tool_start":
                    name = event.get("name")
                    if name == "task":
                        input_data = event.get("data", {}).get("input", {})
                        subagent = input_data.get("subagent_type", "未知智能体")
                        msg = {"type": "agent_call", "content": f"正在呼叫子智能体: {subagent}..."}
                    else:
                        msg = {"type": "tool_call", "content": f"正在使用工具: {name}..."}
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"

                # 工具结束
                elif kind == "on_tool_end":
                    name = event.get("name")
                    tool_output = event["data"].get("output", "")

                    # Unsplash 图片处理
                    if name == "get_unsplash_image" and "URL:" in tool_output:
                        img_url = tool_output.split("URL: ")[1].split("\n")[0]
                        img_msg = json.dumps({
                            'type': 'message_chunk',
                            'content': f'\n![图片]({img_url})\n'
                        }, ensure_ascii=False)
                        yield f"data: {img_msg}\n\n"
                        
                        # 将图片数据也保存到消息内容中（作为 Markdown 图片格式），以便历史记录可以读取
                        accumulated_content += f'\n![图片]({img_url})\n'

                    # Maps 处理
                    elif name.startswith("maps_"):
                        try:
                            map_data = json.loads(tool_output)
                            map_payload = json.dumps({
                                'type': 'map_data',
                                'tool': name,
                                'data': map_data
                            }, ensure_ascii=False)
                            yield f"data: {map_payload}\n\n"
                            
                            # 将地图数据保存到消息内容中（作为 JSON 代码块），以便历史记录可以读取
                            map_json_block = f'\n```json\n{json.dumps({"type": "MAP_DATA", "tool": name, "data": map_data}, ensure_ascii=False)}\n```\n'
                            accumulated_content += map_json_block
                        except Exception:
                            pass  # 解析失败就跳过

                    # 通用工具结束提示
                    tool_msg = json.dumps({
                        'type': 'tool_result',
                        'content': f'工具 {name} 执行完毕'
                    }, ensure_ascii=False)
                    yield f"data: {tool_msg}\n\n"

        except Exception as e:
            # 错误推送
            error_msg = json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"

        finally:
            # 确保一定发送结束标记
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )




