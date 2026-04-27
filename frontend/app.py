import streamlit as st
import pandas as pd
import os
import sys

# 🚨 动态路径处理：确保 Streamlit 能在重构后的结构中找到所有模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from backend.core.bootstrap import init_system
init_system()

from backend.memory.relational.db_manager import DBManager
from backend.brain.llm_router import LLMRouter
from backend.brain.rag_engine import RAGEngine
from backend.memory.memory_writer import MemoryWriter
from scripts.run_sync import execute_full_sync
from backend.services.interview_service import InterviewService

from backend.brain.prompts import (
    CREATOR_INTERVIEW_PROMPT, 
    MEMORY_EXTRACTION_PROMPT,
    STORY_INTERVIEW_PROMPT,   
    STORY_EXTRACTION_PROMPT,
    IDENTITY_CONSOLIDATION_PROMPT
)
# ==========================================
# 1. 页面全局配置
# ==========================================
st.set_page_config(
    page_title="Project Reborn | 中控台",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化 Session State，用于持久化聊天记录
# A. 初始化底层基础设施
if "llm_router" not in st.session_state:
    st.session_state.llm_router = LLMRouter()
    
if "memory_writer" not in st.session_state:       
    st.session_state.memory_writer = MemoryWriter()

# B. 初始化聊天记录状态
if "creator_chat" not in st.session_state:
    st.session_state.creator_chat = [{"role": "assistant", "content": "你好，造物主。我是你的灵魂采访员。今天你想聊聊你在工作上的处事原则，还是对孩子的教育理念？"}]
    
if "sandbox_chat" not in st.session_state:
    st.session_state.sandbox_chat = [{"role": "assistant", "content": "哈喽呀！我是爸爸的数字分身，你今天在幼儿园开心吗？"}]

# C. 初始化业务服务层 (现在安全了，因为底层设施已经准备好了)
if "interview_service" not in st.session_state:
    st.session_state.interview_service = InterviewService(
        st.session_state.llm_router, 
        st.session_state.memory_writer
    )

# ==========================================
# 2. 数据获取逻辑
# ==========================================
@st.cache_data(ttl=5)
def load_sync_history():
    db = DBManager()
    try:
        with db.get_connection() as conn:
            df = pd.read_sql_query("SELECT * FROM sync_history ORDER BY sync_time ASC", conn)
            if not df.empty:
                df['sync_time'] = pd.to_datetime(df['sync_time'])
        return df
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 3. 核心视图组件
# ==========================================

def render_dashboard():
    """视图 1：资产同步与监控大屏"""
    st.title("📊 资产同步与监控")
    st.markdown("##### 数字生命底层数据摄入状态")
    st.divider()

    df = load_sync_history()

    if df.empty:
        st.info("📭 目前大脑中还没有记忆快照，请点击左侧的摄入按钮。")
    else:
        latest_record = df.iloc[-1]
        prev_record = df.iloc[-2] if len(df) > 1 else latest_record

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎙️ 语音资产总长 (分)", f"{latest_record['audio_duration']:.1f}", 
                      f"{latest_record['audio_duration'] - prev_record['audio_duration']:.1f}" if len(df)>1 else None)
        with col2:
            st.metric("📝 核心记忆节点 (篇)", int(latest_record['notes_count']), 
                      int(latest_record['notes_count'] - prev_record['notes_count']) if len(df)>1 else None)
        with col3:
            st.metric("🧠 知识库总词汇 (字)", int(latest_record['word_count']), 
                      int(latest_record['word_count'] - prev_record['word_count']) if len(df)>1 else None)

        st.divider()
        st.subheader("📈 摄入轨迹 (Growth Trend)")
        chart_data = df.set_index('sync_time')
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.caption("语音语料积累曲线")
            st.area_chart(chart_data['audio_duration'], color="#1f77b4")
        with chart_col2:
            st.caption("记忆节点扩展曲线")
            st.area_chart(chart_data['notes_count'], color="#ff7f0e")

def render_creator_studio():
    """视图 2：灵魂采访室 (双模式切换)"""
    # 1. 在侧边栏增加模式选择器
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🎯 当前采访目标")
        interview_mode = st.radio(
            "你想聊什么内容？",
            ["💡 提炼价值观 (ROM)", "📖 记录往事 (RAM)"],
            help="模式切换后，AI 会调整提问风格。提炼时会根据模式存入不同文件夹。"
        )
        
        # 模式切换提醒：如果切换模式，建议重置聊天
        if st.button("🆕 开启新话题", help="清空当前对话记录"):
            st.session_state.creator_chat = [{"role": "assistant", "content": "好的，我已经准备好了。我们开始吧！"}]
            st.rerun()
    # 2. 动态确定当前使用的 System Prompt
    current_system_prompt = (
        CREATOR_INTERVIEW_PROMPT if interview_mode == "💡 提炼价值观 (ROM)" 
        else STORY_INTERVIEW_PROMPT
    )

    st.title("🧠 灵魂采访室")
    st.caption(f"当前模式：{interview_mode}")
    st.divider()

    # 3. 渲染聊天记录 (保持原有逻辑)
    for msg in st.session_state.creator_chat:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 4. 聊天输入处理
    if prompt := st.chat_input("分享你的想法或故事细节..."):
        st.session_state.creator_chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        master_identity = st.session_state.memory_writer.read_master_identity()

        dynamic_system_prompt = {
            "role": "system",
            "content": f"{current_system_prompt['content']}\n\n【已知全局背景信息（请务必牢记）】：\n{master_identity}"
        }
        # 拼接上下文，使用当前模式的 System Prompt
        messages = [dynamic_system_prompt] + [m for m in st.session_state.creator_chat if m["role"] != "system"]
        with st.chat_message("assistant"):
            with st.spinner("正在倾听..."):
                response = st.session_state.llm_router.generate_response(messages)
                st.markdown(response)
        st.session_state.creator_chat.append({"role": "assistant", "content": response})

    # 5. 侧边栏：提炼与保存控制台
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🧬 记忆提炼")
        memory_title = st.text_input("记忆标题", placeholder="例如：丽水的水牛")
        
        if st.button("💾 提取并同步至 Obsidian", type="primary", use_container_width=True):
            if len(st.session_state.creator_chat) < 3:
                st.warning("⚠️ 内容太少，再多聊几句吧。")
            else:
                with st.spinner("AI 正在深度提炼并同步进化身份核..."):
                    # 🚀 调用封装好的业务逻辑
                    success, result = st.session_state.interview_service.process_and_save_interview(
                        chat_history=st.session_state.creator_chat,
                        interview_mode=interview_mode,
                        custom_title=memory_title
                    )
                    
                    if success:
                        st.success("✅ 记忆已存入 Obsidian，且身份核已同步进化！")
                        st.toast("🧬 身份核已完成一次增量演进", icon="✅")
                        with st.expander("查看本次提炼的笔记"):
                            st.markdown(result)
                    else:
                        # 在这里接住底层抛出的异常，进行“安抚用户”
                        st.error(f"❌ 同步失败：{result}")
                        st.info("建议检查网络连接或后端日志。")
                        
                # 👈 注意这里的缩进！它应该紧接着上面的保存逻辑，但仍然在 else 分支内
                with st.spinner("AI 正在提炼记忆并更新身份核..."):
                    old_identity = st.session_state.memory_writer.read_master_identity()
                    consolidation_msgs = [
                        IDENTITY_CONSOLIDATION_PROMPT,
                        {"role": "user", "content": f"旧身份核：\n{old_identity}\n\n新记忆碎片：\n{insight}"}
                    ]
                    # 调用 LLM 进行合并
                    updated_identity = st.session_state.llm_router.generate_response(consolidation_msgs)
                    
                    # 覆盖写入
                    if st.session_state.memory_writer.save_master_identity(updated_identity):
                        st.toast("✅ 身份核(Master Identity)已同步进化！", icon="🧬")
def render_avatar_sandbox():
    """视图 3：陪伴沙盒 (测试分身语气)"""
    st.title("👶 陪伴沙盒 (Alpha)")
    st.caption("模拟孩子与分身的交互。后续将接入 RAG 记忆检索，使回复更真实。")
    st.divider()

    if "rag_engine" not in st.session_state:
        with st.spinner("正在加载层级记忆模型 (ROM/RAM)..."):
            st.session_state.rag_engine = RAGEngine()

    for msg in st.session_state.sandbox_chat:
        avatar = "👶" if msg["role"] == "user" else "👨‍💻"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    if prompt := st.chat_input("跟爸爸的分身聊天..."):
        st.session_state.sandbox_chat.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👶"):
            st.markdown(prompt)
        
        # 暂时使用基础提示词，未来在此注入 RAG 检索结果
        with st.chat_message("assistant", avatar="👨‍💻"):
            with st.spinner("爸爸正在回忆..."):               
                response = st.session_state.rag_engine.generate_avatar_response(
                    prompt, 
                    st.session_state.sandbox_chat[:-1] 
                )
                st.markdown(response)
        st.session_state.sandbox_chat.append({"role": "assistant", "content": response})

# ==========================================
# 4. 侧边栏路由与全局控制
# ==========================================
with st.sidebar:
    st.header("🌌 Reborn 核心枢纽")
    st.divider()
    view_mode = st.radio("功能模块:", options=["📊 资产同步与监控", "🧠 灵魂采访室", "💬 陪伴沙盒(测试)"])
    st.divider()
    
    if view_mode == "📊 资产同步与监控":
        if st.button("🚀 一键同步记忆 (Sync)", use_container_width=True, type="primary"):
            with st.spinner("正在解析 Obsidian 并更新向量库..."):
                execute_full_sync()
                st.success("同步成功！")
                st.rerun()

# 根据路由渲染页面
if view_mode == "📊 资产同步与监控": render_dashboard()
elif view_mode == "🧠 灵魂采访室": render_creator_studio()
elif view_mode == "💬 陪伴沙盒(测试)": render_avatar_sandbox()