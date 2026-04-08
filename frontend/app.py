import streamlit as st
import pandas as pd
import os
import sys

# 🚨 动态路径处理：确保 Streamlit 能找到后端的工具和配置
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from backend.database.db_manager import DBManager
from scripts.run_sync import execute_full_sync

# ==========================================
# 1. 页面全局配置
# ==========================================
st.set_page_config(
    page_title="Project Reborn | 施工驾驶舱",
    page_icon="🌌",
    layout="wide"
)

# ==========================================
# 2. 数据获取与缓存逻辑
# ==========================================
@st.cache_data(ttl=5) # 缓存 5 秒，避免每次点击都狂刷数据库
def load_sync_history():
    db = DBManager()
    try:
        # 获取纯净的连接
        with db.get_connection() as conn:
            # 用 Pandas 直接读取 SQLite 表，按时间顺序排列
            df = pd.read_sql_query("SELECT * FROM sync_history ORDER BY sync_time ASC", conn)
            
            # 将字符串时间转换为标准的 datetime 格式，方便画图
            if not df.empty:
                df['sync_time'] = pd.to_datetime(df['sync_time'])
        return df
    except Exception as e:
        st.error(f"❌ 无法连接到数字大脑核心: {e}")
        return pd.DataFrame()

# ==========================================
# 3. 页面渲染：头部面板
# ==========================================
st.title("🌌 Project Reborn")
st.markdown("##### 数字生命成长监控中心 | 核心记忆摄入状态")
st.divider()

df = load_sync_history()

if df.empty:
    st.info("📭 目前大脑中还没有记忆快照，请先在终端运行一次 `python scripts/run_sync.py`。")
else:
    # 提取最新和上一次的记录，用于计算“增量”
    latest_record = df.iloc[-1]
    prev_record = df.iloc[-2] if len(df) > 1 else latest_record

    # 渲染三大核心指标
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="🎙️ 语音资产总长 (分钟)", 
            value=f"{latest_record['audio_duration']:.1f}", 
            delta=f"{latest_record['audio_duration'] - prev_record['audio_duration']:.1f} 增量" if len(df)>1 else None
        )
    with col2:
        st.metric(
            label="📝 核心记忆节点 (篇)", 
            value=int(latest_record['notes_count']), 
            delta=int(latest_record['notes_count'] - prev_record['notes_count']) if len(df)>1 else None
        )
    with col3:
        st.metric(
            label="🧠 知识库总词汇 (字)", 
            value=int(latest_record['word_count']), 
            delta=int(latest_record['word_count'] - prev_record['word_count']) if len(df)>1 else None
        )

    st.divider()

    # ==========================================
    # 4. 页面渲染：成长轨迹图表
    # ==========================================
    st.subheader("📈 摄入轨迹 (Growth Trend)")
    
    # 整理画图数据，将时间设为 X 轴
    chart_data = df.set_index('sync_time')
    
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.caption("语音语料积累曲线")
        st.area_chart(chart_data['audio_duration'], color="#1f77b4")
        
    with chart_col2:
        st.caption("记忆节点扩展曲线")
        st.area_chart(chart_data['notes_count'], color="#ff7f0e")

    # ==========================================
    # 5. 页面渲染：底层数据表
    # ==========================================
    with st.expander("🗄️ 查看底层同步日志 (Raw Data)"):
        # 倒序显示，最新的在最上面
        display_df = df.sort_values(by="sync_time", ascending=False).drop(columns=['id'])
        st.dataframe(display_df, width='content')

# ==========================================
# 6. 侧边栏控制台
# ==========================================
with st.sidebar:
    st.header("⚙️ 引擎控制台")
    
    # 🚨 新增的一键同步按钮，带高亮特效 (type="primary")
    if st.button("🚀 一键摄入新记忆 (Sync)", width='content', type="primary"):
        # 显示友好的加载动画
        with st.spinner("正在提取并向量化记忆，请稍候..."):
            try:
                execute_full_sync()
                st.success("✅ 记忆摄入完成！")
                st.rerun() # 同步完成后自动刷新页面，让折线图涨起来！
            except Exception as e:
                st.error(f"❌ 同步失败，请检查终端日志: {e}")
                
    st.divider()
    
    if st.button("🔄 仅刷新面板数据", width='content'):
        st.rerun()