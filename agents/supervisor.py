"""
Supervisor编排Agent — 中央协调者
负责接收用户请求，根据意图路由到对应子Agent，汇总结果返回。
采用LangGraph StateGraph实现。
"""

from __future__ import annotations

import os
import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 禁用追踪（仅保留核心配置，无冗余）
os.environ["OTEL_SDK_DISABLED"] = "true"

# 导入核心Agent
from agents.intent_router import IntentRouterAgent
from agents.knowledge_rag import KnowledgeRAGAgent
from agents.ticket_handler import TicketHandlerAgent
from agents.compliance_checker import ComplianceCheckerAgent
# 导入记忆模块
from memory.working_memory import WorkingMemory
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory

# ─── 全局状态定义 ───
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    user_id: str
    session_id: str
    intent: str
    sub_results: dict[str, Any]
    compliance_passed: bool
    final_response: str
    current_agent: str
    retry_count: int

# ─── 系统提示词 ───
SUPERVISOR_SYSTEM_PROMPT = """你是一个智能客服系统的主管（Supervisor）。
你的职责是：
1. 分析用户意图，分发任务给对应子Agent
2. 汇总处理结果，生成最终回复
3. 确保所有回复通过合规审查

可调用子Agent：
- knowledge_rag: 知识库问答
- ticket_handler: 工单处理
- compliance_checker: 合规审查
"""

# ─── 主管核心节点 ───
class SupervisorNode:
    def __init__(self, llm: ChatOpenAI, working_memory: WorkingMemory):
        self.llm = llm
        self.working_memory = working_memory

    async def route_decision(self, state: AgentState) -> AgentState:
        """意图路由决策"""
        messages = state["messages"]
        session_id = state.get("session_id", "default")
        context = self.working_memory.get_context(session_id)

        routing_prompt = [
            SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
            SystemMessage(content=f"当前上下文: {context}"),
            *messages,
            HumanMessage(content="请分析用户意图，仅返回路由目标：knowledge_rag / ticket_handler")
        ]

        response = await self.llm.ainvoke(routing_prompt)
        intent = str(response.content).strip().lower()

        if intent not in ["knowledge_rag", "ticket_handler"]:
            intent = "knowledge_rag"

        self.working_memory.update(session_id, {"last_intent": intent})

        return {
            **state,
            "intent": intent,
            "current_agent": "supervisor",
        }

    async def synthesize_response(self, state: AgentState) -> AgentState:
        """生成最终回答"""
        compliance_passed = state.get("compliance_passed", True)
        sub_results = state.get("sub_results", {})

        if not compliance_passed:
            final_response = "抱歉，您的请求涉及敏感内容，已转交人工客服。"
        else:
            result_parts = [str(res) for res in sub_results.values() if res]
            final_response = "\n\n".join(result_parts) if result_parts else "抱歉，暂时无法处理您的请求。"

        return {
            **state,
            "final_response": final_response,
            "messages": [AIMessage(content=final_response)],
        }

# ─── 路由逻辑 ───
def route_to_agent(state: AgentState) -> str:
    intent = state.get("intent", "knowledge_rag")
    return intent

# ─── 构建流程图 ───
def create_supervisor_graph(
    llm: ChatOpenAI | None = None,
    working_memory: WorkingMemory | None = None,
    short_term_memory: ShortTermMemory | None = None,
    long_term_memory: LongTermMemory | None = None,
    enable_checkpointing: bool = True,
) -> StateGraph:

    load_dotenv()
    if llm is None:
        llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME"),  # 完全读取配置，不强制任何模型
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_BASE_URL"),
            temperature=0.7
        )
    if working_memory is None:
        working_memory = WorkingMemory()

    # 初始化Agent
    supervisor = SupervisorNode(llm, working_memory)
    knowledge_agent = KnowledgeRAGAgent(llm, long_term_memory)
    ticket_agent = TicketHandlerAgent(llm)
    compliance_agent = ComplianceCheckerAgent(llm)

    # 构建流程图
    graph = StateGraph(AgentState)
    
    # 添加节点
    graph.add_node("supervisor_route", supervisor.route_decision)
    graph.add_node("knowledge_rag", knowledge_agent.process)
    graph.add_node("ticket_handler", ticket_agent.process)
    graph.add_node("compliance_check", compliance_agent.process)
    graph.add_node("synthesize", supervisor.synthesize_response)

    # 流程编排
    graph.set_entry_point("supervisor_route")
    graph.add_conditional_edges("supervisor_route", route_to_agent)
    graph.add_edge("knowledge_rag", "compliance_check")
    graph.add_edge("ticket_handler", "compliance_check")
    graph.add_edge("compliance_check", "synthesize")
    graph.add_edge("synthesize", END)

    # 内存持久化
    checkpointer = MemorySaver() if enable_checkpointing else None
    return graph.compile(checkpointer=checkpointer)