import streamlit as st
import pandas as pd
import os
import sys

# 🚨 动态路径处理
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from backend.database.db_manager import DBManager
from scripts.run_sync import execute_full_sync
from backend.brain.llm_router import LLMRouter

# ==========================================
# 1. 页面全局配置
# ==========================================
st.set_page_config(
    page_title="Project Reborn | 中控台",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化 Session State 用于保存不同房间的聊天记录
if "creator_chat" not in st.session_state:
    st.session_state.creator_chat = [{"role": "assistant", "content": "你好，造物主。我是你的灵魂采访员。今天你想聊聊你在工作上的处事原则，还是对孩子的教育理念？"}]
if "sandbox_chat" not in st.session_state:
    st.session_state.sandbox_chat = [{"role": "assistant", "content": "哈喽呀！我是爸爸的数字分身，你今天在幼儿园开心吗？"}]

# ==========================================
# 2. 数据获取逻辑 (保留原汁原味)
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
# 3. 核心视图组件定义
# ==========================================
def render_dashboard():
    """视图 1：资产同步与监控大屏"""
    st.title("📊 资产同步与监控")
    st.markdown("##### 数字生命底层数据摄入状态")
    st.divider()

    df = load_sync_history()

    if df.empty:
        st.info("📭 目前大脑中还没有记忆快照，请先在终端运行一次同步或点击左侧的摄入按钮。")
    else:
        latest_record = df.iloc[-1]
        prev_record = df.iloc[-2] if len(df) > 1 else latest_record

        # 三大核心指标
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎙️ 语音资产总长 (分钟)", f"{latest_record['audio_duration']:.1f}", 
                      f"{latest_record['audio_duration'] - prev_record['audio_duration']:.1f} 增量" if len(df)>1 else None)
        with col2:
            st.metric("📝 核心记忆节点 (篇)", int(latest_record['notes_count']), 
                      int(latest_record['notes_count'] - prev_record['notes_count']) if len(df)>1 else None)
        with col3:
            st.metric("🧠 知识库总词汇 (字)", int(latest_record['word_count']), 
                      int(latest_record['word_count'] - prev_record['word_count']) if len(df)>1 else None)

        st.divider()

        # 成长轨迹图表
        st.subheader("📈 摄入轨迹 (Growth Trend)")
        chart_data = df.set_index('sync_time')
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.caption("语音语料积累曲线")
            st.area_chart(chart_data['audio_duration'], color="#1f77b4")
        with chart_col2:
            st.caption("记忆节点扩展曲线")
            st.area_chart(chart_data['notes_count'], color="#ff7f0e")

        # 底层数据表
        with st.expander("🗄️ 查看底层同步日志 (Raw Data)"):
            display_df = df.sort_values(by="sync_time", ascending=False).drop(columns=['id'])
            st.dataframe(display_df, width='content')

def render_creator_studio():
    """视图 2：灵魂采访室 (用于提炼价值观)"""
    st.title("🧠 灵魂采访室")
    st.caption("作为造物主，在这里与 AI 对话。AI 会从你的回答中提取隐性价值观，并作为‘出厂设置’落盘。")
    st.divider()

    # 初始化大模型路由器
    if "llm_router" not in st.session_state:
        try:
            st.session_state.llm_router = LLMRouter()
        except Exception as e:
            st.error(f"大脑初始化失败: {e}")
            return

    # 🚨 设定 AI 作为“采访者”的系统提示词 (System Prompt)
    system_prompt = {
        "role": "system", 
        "content": """你现在是 Project Reborn 的'灵魂采访员'。
你的任务是通过与造物主（人类用户）对话，深度挖掘他的底层逻辑、处事原则、以及对孩子未来的期盼。
你的提问要循序渐进，像一位深沉的老友。一次只问一个好问题，引导造物主多表达。"""
    }

    # 渲染聊天记录
    for msg in st.session_state.creator_chat:
        # 不在页面上显示系统提示词
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 聊天输入与处理逻辑
    if prompt := st.chat_input("输入你的想法或经历..."):
        # 1. 存入并显示用户消息
        st.session_state.creator_chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # 2. 拼接历史记录（加上 System Prompt）发送给大模型
        messages_to_send = [system_prompt] + st.session_state.creator_chat
        
        with st.chat_message("assistant"):
            with st.spinner("大脑正在思考..."):
                # 调用 llm_router 获取真实回复
                response = st.session_state.llm_router.generate_response(messages_to_send)
                st.markdown(response)
        
        # 3. 将 AI 回复存入记录
        st.session_state.creator_chat.append({"role": "assistant", "content": response})
            
    # 右侧面板：提炼控制台 (暂时保留按钮)
    with st.sidebar:
        st.markdown("### 🧬 灵魂提取器")
        st.info("当一段对话足够深入后，点击下方按钮，AI 将自动总结并生成 Markdown 记忆文件。")
        if st.button("💾 提取当前对话并落盘", type="primary", use_container_width=True):
            st.success("✅ 按钮已准备好，下一步将对接 memory_writer 组件！")

def render_avatar_sandbox():
    """视图 3：陪伴沙盒 (用于测试最终成品)"""
    st.title("👶 陪伴沙盒 (Avatar Sandbox)")
    st.caption("这是最终成品的模拟环境。你现在扮演‘孩子’或‘最终用户’，测试数字分身的语气、知识与反应。")
    st.divider()

    # 渲染聊天记录
    for msg in st.session_state.sandbox_chat:
        # 给分身换个头像
        avatar = "👶" if msg["role"] == "user" else "👨‍💻"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # 聊天输入框
    if prompt := st.chat_input("跟爸爸的分身说点什么..."):
        st.session_state.sandbox_chat.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👶"):
            st.markdown(prompt)
        
        dummy_response = f"【模拟分身回复】乖，爸爸现在正在后台升级代码呢！你刚才说的'{prompt}'爸爸记住了哦！"
        st.session_state.sandbox_chat.append({"role": "assistant", "content": dummy_response})
        with st.chat_message("assistant", avatar="👨‍💻"):
            st.markdown(dummy_response)

# ==========================================
# 4. 侧边栏与动态路由导航
# ==========================================
with st.sidebar:
    st.header("🌌 Reborn 核心枢纽")
    st.divider()
    
    # 构建侧边栏菜单
    st.markdown("### 🛠️ 创造者引擎")
    view_mode = st.radio(
        "选择功能模块:",
        options=["📊 资产同步与监控", "🧠 灵魂采访室", "💬 陪伴沙盒(测试)"],
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # 仅在“资产监控”页面显示同步按钮，保持逻辑清晰
    if view_mode == "📊 资产同步与监控":
        st.markdown("### ⚙️ 引擎控制")
        if st.button("🚀 一键摄入新记忆 (Sync)", use_container_width=True, type="primary"):
            with st.spinner("正在提取并向量化记忆..."):
                try:
                    execute_full_sync()
                    st.success("✅ 记忆摄入完成！")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 同步失败: {e}")

# ==========================================
# 5. 视图路由挂载
# ==========================================
if view_mode == "📊 资产同步与监控":
    render_dashboard()
elif view_mode == "🧠 灵魂采访室":
    render_creator_studio()
elif view_mode == "💬 陪伴沙盒(测试)":
    render_avatar_sandbox()