# frontend/app.py
import streamlit as st
import pandas as pd
import os
import sys

# 🚨 动态路径处理：确保 Streamlit 能在重构后的结构中找到所有模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from backend.memory.relational.db_manager import DBManager
from scripts.run_sync import execute_full_sync
from backend.brain.llm_router import LLMRouter
from backend.brain.prompts import CREATOR_INTERVIEW_PROMPT, AVATAR_SANDBOX_PROMPT, MEMORY_EXTRACTION_PROMPT
from backend.memory.memory_writer import MemoryWriter

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
if "creator_chat" not in st.session_state:
    st.session_state.creator_chat = [{"role": "assistant", "content": "你好，造物主。我是你的灵魂采访员。今天你想聊聊你在工作上的处事原则，还是对孩子的教育理念？"}]
if "sandbox_chat" not in st.session_state:
    st.session_state.sandbox_chat = [{"role": "assistant", "content": "哈喽呀！我是爸爸的数字分身，你今天在幼儿园开心吗？"}]

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
    """视图 2：灵魂采访室 (提炼价值观并落盘)"""
    st.title("🧠 灵魂采访室")
    st.caption("在此通过深度对话提炼你的底层逻辑，并将其转化为分身的‘物理记忆’。")
    st.divider()

    # 初始化大脑和记忆写入器
    if "llm_router" not in st.session_state:
        st.session_state.llm_router = LLMRouter()
    if "memory_writer" not in st.session_state:
        st.session_state.memory_writer = MemoryWriter()

    # 渲染聊天记录
    for msg in st.session_state.creator_chat:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 聊天输入
    if prompt := st.chat_input("分享一个让你印象深刻的处事经历..."):
        st.session_state.creator_chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # 拼接上下文发送给大模型
        messages = [CREATOR_INTERVIEW_PROMPT] + st.session_state.creator_chat
        with st.chat_message("assistant"):
            with st.spinner("正在倾听并思考..."):
                response = st.session_state.llm_router.generate_response(messages)
                st.markdown(response)
        st.session_state.creator_chat.append({"role": "assistant", "content": response})
            
    # 侧边栏辅助功能：提炼并保存记忆
    with st.sidebar:
        st.markdown("### 🧬 灵魂提取控制台")
        memory_title = st.text_input("给这段记忆起个标题", placeholder="例如：关于诚实的价值观")
        
        if st.button("💾 提取对话精华并存入硬盘", type="primary", use_container_width=True):
            if len(st.session_state.creator_chat) < 3:
                st.warning("⚠️ 对话内容太少，建议多聊几句再提炼。")
            else:
                with st.spinner("AI 正在深度复盘并生成总结..."):
                    # 1. 将对话历史转化为字符串
                    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.creator_chat if m['role'] != 'system'])
                    
                    # 2. 调用专门的“提炼 Prompt”
                    extract_msgs = [
                        MEMORY_EXTRACTION_PROMPT, 
                        {"role": "user", "content": f"请提炼以下对话的精华内容：\n{history_str}"}
                    ]
                    insight = st.session_state.llm_router.generate_response(extract_msgs)
                    
                    # 3. 调用 MemoryWriter 落盘
                    final_title = memory_title if memory_title else f"碎片_{pd.Timestamp.now().strftime('%m%d_%H%M')}"
                    success = st.session_state.memory_writer.save_core_value(topic=final_title, content=insight)
                    
                    if success:
                        st.success(f"✅ 记忆已成功落盘！\n文件位置：data/memories/core_values/")
                        st.info(f"提炼结果：\n{insight[:150]}...")
                    else:
                        st.error("❌ 记忆落盘失败，请检查 backend/logs 记录。")

def render_avatar_sandbox():
    """视图 3：陪伴沙盒 (测试分身语气)"""
    st.title("👶 陪伴沙盒 (Alpha)")
    st.caption("模拟孩子与分身的交互。后续将接入 RAG 记忆检索，使回复更真实。")
    st.divider()

    if "llm_router" not in st.session_state:
        st.session_state.llm_router = LLMRouter()

    for msg in st.session_state.sandbox_chat:
        avatar = "👶" if msg["role"] == "user" else "👨‍💻"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    if prompt := st.chat_input("跟爸爸的分身聊天..."):
        st.session_state.sandbox_chat.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👶"):
            st.markdown(prompt)
        
        # 暂时使用基础提示词，未来在此注入 RAG 检索结果
        messages = [AVATAR_SANDBOX_PROMPT] + st.session_state.sandbox_chat
        with st.chat_message("assistant", avatar="👨‍💻"):
            with st.spinner("爸爸正在回忆..."):
                response = st.session_state.llm_router.generate_response(messages)
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