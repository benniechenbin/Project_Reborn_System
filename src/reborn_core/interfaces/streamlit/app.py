import difflib
import json
from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st
from audio_recorder_streamlit import audio_recorder

from reborn_core.application import InterviewMode
from reborn_core.container import Container
from reborn_core.lifecycle import RebornApp, build_app
from reborn_core.observability import logger
from reborn_core.runtime import TaskStatus

from .runtime import (
    CachedRebornApp,
    is_cached_app_valid,
    register_cached_app,
    streamlit_cache_token,
)


@st.cache_resource(validate=is_cached_app_valid)
def get_reborn_app() -> CachedRebornApp[RebornApp]:
    """Build and cache the lifecycle-managed application for Streamlit."""
    app = build_app().start(show_startup_banner=False)
    return register_cached_app(CachedRebornApp(app=app, token=streamlit_cache_token()))


def submit_task(
    container: Container,
    state_key: str,
    kind: str,
    operation: Callable[..., Any],
    *args: Any,
) -> None:
    st.session_state[state_key] = container.task_runner.submit(kind, operation, *args)


@st.fragment(run_every="1s")
def render_running_task(container: Container, state_key: str, label: str) -> None:
    """Poll a background task and refresh the page after completion."""
    task_id = st.session_state.get(state_key)
    if not task_id:
        return
    task = container.task_runner.get_task(task_id)
    if task is None:
        st.warning(f"{label}任务记录不存在")
        return
    if task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
        st.rerun()
    st.info(f"{label}正在后台执行，任务 ID：`{task_id}`")
    st.caption("任务完成后页面会自动更新。")


def task_result(container: Container, state_key: str, label: str) -> Any | None:
    task_id = st.session_state.get(state_key)
    if not task_id:
        return None
    task = container.task_runner.get_task(task_id)
    if task is None:
        st.warning(f"{label}任务记录不存在")
        return None
    if task.status in {TaskStatus.QUEUED, TaskStatus.RUNNING}:
        render_running_task(container, state_key, label)
        return None
    if task.status is TaskStatus.FAILED:
        st.error(f"{label}失败：{task.error}")
        return None
    try:
        return container.task_runner.result(task_id)
    except LookupError:
        return json.loads(task.result_json) if task.result_json else None


@st.cache_data(ttl=5)
def load_sync_history(_container: Container) -> pd.DataFrame:
    try:
        return pd.DataFrame(entry.as_dict() for entry in _container.sync_service.list_history())
    except Exception:
        logger.exception("Could not load sync history")
        return pd.DataFrame()


def render_dashboard(container: Container) -> None:
    st.title("资产同步与监控")
    active = container.retrieval_generations.active_generation_id()
    st.caption(f"当前检索代次：`{active or '尚未建立'}`")
    if st.button("提交全量同步", type="primary"):
        submit_task(container, "sync_task", "memory_sync", container.run_sync)
        st.rerun()
    result = task_result(container, "sync_task", "记忆同步")
    if result is not None:
        st.success("新检索代次已构建并原子切换")
        st.json(result.as_dict() if hasattr(result, "as_dict") else result)

    history = load_sync_history(container)
    if history.empty:
        st.info("还没有同步记录。")
        return
    latest = history.iloc[-1]
    previous = history.iloc[-2] if len(history) > 1 else latest
    cols = st.columns(3)
    cols[0].metric(
        "音频总时长（分钟）",
        f"{latest['audio_duration']:.1f}",
        f"{latest['audio_duration'] - previous['audio_duration']:.1f}"
        if len(history) > 1
        else None,
    )
    cols[1].metric(
        "记忆笔记",
        int(latest["notes_count"]),
        int(latest["notes_count"] - previous["notes_count"]) if len(history) > 1 else None,
    )
    cols[2].metric(
        "知识库字符数",
        int(latest["word_count"]),
        int(latest["word_count"] - previous["word_count"]) if len(history) > 1 else None,
    )

    with st.expander("数据积累趋势与同步明细"):
        chart_data = history.copy()
        chart_data["sync_time"] = pd.to_datetime(
            chart_data["sync_time"],
            format="mixed",
            errors="coerce",
            utc=True,
        )
        chart_data = chart_data.dropna(subset=["sync_time"]).set_index("sync_time")
        if chart_data.empty:
            st.info("同步历史时间格式无法解析，暂不显示趋势图。")
        else:
            audio_chart, notes_chart = st.columns(2)
            with audio_chart:
                st.caption("语音资产积累趋势")
                st.area_chart(chart_data["audio_duration"], color="#1f77b4")
            with notes_chart:
                st.caption("记忆节点积累趋势")
                st.area_chart(chart_data["notes_count"], color="#ff7f0e")
        st.dataframe(history, width="stretch")


def render_creator(container: Container) -> None:
    st.title("灵魂采访室")
    mode_label = st.radio("采访目标", ["价值观", "人生故事"], horizontal=True)
    mode = InterviewMode.CORE_VALUES if mode_label == "价值观" else InterviewMode.LIFE_STORY
    system_prompt_id = (
        "creator_interview" if mode is InterviewMode.CORE_VALUES else "story_interview"
    )

    for message in st.session_state.creator_chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("分享你的想法或故事细节"):
        st.session_state.creator_chat.append({"role": "user", "content": prompt})
        try:
            system_prompt = container.render_builder_prompt_message(system_prompt_id)
        except ValueError as exc:
            st.error(str(exc))
            return
        messages = [
            {
                "role": "system",
                "content": (
                    f"{system_prompt['content']}\n\n"
                    f"Approved identity context:\n{container.memory_writer.read_master_identity()}"
                ),
            },
            *st.session_state.creator_chat,
        ]
        submit_task(
            container, "creator_chat_task", "creator_chat", container.generate_chat, messages
        )
        st.rerun()

    chat_response = task_result(container, "creator_chat_task", "采访回复")
    chat_task = st.session_state.get("creator_chat_task")
    if chat_response and st.session_state.get("consumed_chat_task") != chat_task:
        st.session_state.creator_chat.append({"role": "assistant", "content": chat_response})
        st.session_state.consumed_chat_task = chat_task
        st.rerun()

    title = st.text_input("记忆标题")
    if st.button("提交提炼并生成待审身份快照", type="primary"):
        if len(st.session_state.creator_chat) < 3:
            st.warning("内容还太少，再多聊几句。")
        else:
            submit_task(
                container,
                "interview_task",
                "interview_extraction",
                container.run_interview,
                list(st.session_state.creator_chat),
                mode,
                title or None,
            )
            st.rerun()
    result = task_result(container, "interview_task", "记忆提炼")
    if result is not None:
        snapshot_id = getattr(result, "identity_snapshot_id", None) or result.get(
            "identity_snapshot_id"
        )
        st.success(f"记忆已保存，身份快照 `{snapshot_id}` 等待人工确认。")


def render_identity_review(container: Container) -> None:
    st.title("身份快照审批")
    pending = container.identity_governance_service.list_pending()
    if not pending:
        st.info("目前没有待审批的身份快照。")
        return
    for snapshot in pending:
        with st.expander(f"{snapshot.created_at} · {snapshot.snapshot_id}"):
            st.caption(
                f"模型：{snapshot.model.provider}/{snapshot.model.model_name} · "
                f"提示词：{snapshot.prompt.prompt_id}@{snapshot.prompt.version}"
            )
            st.write("来源：", ", ".join(snapshot.source_ids))
            if snapshot.parent_snapshot_id:
                parent = container.identity_governance_service.get_snapshot(
                    snapshot.parent_snapshot_id
                )
                if parent:
                    diff = "".join(
                        difflib.unified_diff(
                            parent.content.splitlines(keepends=True),
                            snapshot.content.splitlines(keepends=True),
                            fromfile=parent.snapshot_id,
                            tofile=snapshot.snapshot_id,
                        )
                    )
                    st.code(diff or "内容无变化", language="diff")
            st.markdown(snapshot.content)
            note = st.text_input("审核备注", key=f"note_{snapshot.snapshot_id}")
            approve, reject = st.columns(2)
            if approve.button("批准并设为当前身份", key=f"approve_{snapshot.snapshot_id}"):
                container.identity_governance_service.approve(snapshot.snapshot_id, note or None)
                st.rerun()
            if reject.button("拒绝", key=f"reject_{snapshot.snapshot_id}"):
                container.identity_governance_service.reject(snapshot.snapshot_id, note or None)
                st.rerun()


def render_voice(container: Container) -> None:
    st.title("语音速记")
    audio_bytes = audio_recorder(
        text="点击录音 / 点击停止",
        sample_rate=16000,
        key="voice_recorder",
    )
    if audio_bytes and audio_bytes != st.session_state.get("voice_audio_bytes"):
        st.session_state.voice_audio_bytes = audio_bytes
        st.session_state.pop("voice_task", None)

    voice_audio_bytes = st.session_state.get("voice_audio_bytes")
    if voice_audio_bytes:
        st.audio(voice_audio_bytes, format="audio/wav")
        st.caption(f"已缓存录音：{len(voice_audio_bytes):,} bytes")

    if st.button(
        "提交后台转写与提炼",
        type="primary",
        disabled=not bool(voice_audio_bytes),
    ):
        try:
            submit_task(
                container,
                "voice_task",
                "voice_capture",
                container.process_voice_capture,
                voice_audio_bytes,
            )
        except Exception as exc:
            st.error(f"提交语音任务失败：{exc}")
        else:
            st.session_state.pop("voice_audio_bytes", None)
            st.rerun()
    result = task_result(container, "voice_task", "语音处理")
    if result is not None:
        transcript = result.get("transcript", "") if isinstance(result, dict) else ""
        st.success("语音已转写，身份变化仍需人工审批。")
        st.write(transcript)


def render_sandbox(container: Container) -> None:
    st.title("数字陪伴测试")
    st.caption("系统会明确说明这是数字分身，并只使用已批准身份与可追溯记忆。")
    for message in st.session_state.sandbox_chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if prompt := st.chat_input("开始对话"):
        st.session_state.sandbox_chat.append({"role": "user", "content": prompt})
        submit_task(
            container,
            "avatar_task",
            "avatar_response",
            container.generate_avatar_response,
            prompt,
            list(st.session_state.sandbox_chat[:-1]),
        )
        st.rerun()
    result = task_result(container, "avatar_task", "陪伴回复")
    task_id = st.session_state.get("avatar_task")
    if result and st.session_state.get("consumed_avatar_task") != task_id:
        response = result[0] if isinstance(result, (tuple, list)) else str(result)
        st.session_state.sandbox_chat.append({"role": "assistant", "content": response})
        st.session_state.consumed_avatar_task = task_id
        st.rerun()


def render_governance(container: Container, app: RebornApp) -> None:
    st.title("安全、备份与数字遗产治理")
    legacy = container.legacy_activation_policy.evaluate()
    st.write(
        {
            "access_policy": app.settings.access_policy_backend,
            "legacy_mode": legacy.mode.value,
            "legacy_active": legacy.active,
            "legacy_reason": legacy.reason,
            "backup_encryption_required": app.settings.backup_require_encryption,
        }
    )
    if st.button("提交加密备份"):
        submit_task(container, "backup_task", "encrypted_backup", container.run_backup)
        st.rerun()
    backup_result = task_result(container, "backup_task", "加密备份")
    if backup_result:
        st.success(f"备份已创建：{backup_result}")

    backup_path = st.text_input("备份文件路径", placeholder=str(app.settings.resolved_backup_dir))
    if st.button("提交恢复演练") and backup_path:
        submit_task(
            container,
            "drill_task",
            "recovery_drill",
            container.run_recovery_drill,
            backup_path,
        )
        st.rerun()
    drill_result = task_result(container, "drill_task", "恢复演练")
    if drill_result:
        st.success("恢复演练通过")
        st.json(drill_result)


def _initialize_session_state() -> None:
    if "creator_chat" not in st.session_state:
        st.session_state.creator_chat = [
            {"role": "assistant", "content": "你好。今天想记录一段故事，还是聊聊你的价值观？"}
        ]
    if "sandbox_chat" not in st.session_state:
        st.session_state.sandbox_chat = [
            {"role": "assistant", "content": "你好，我是依据爸爸留下的资料构建的数字陪伴者。"}
        ]


def main() -> None:
    """Render the Streamlit interface through the authoritative lifecycle entrypoint."""
    st.set_page_config(page_title="Project Reborn", layout="wide", initial_sidebar_state="expanded")
    cached_app = get_reborn_app()
    app = cached_app.app
    container = app.container
    _initialize_session_state()

    with st.sidebar:
        st.header("Project Reborn")
        page = st.radio(
            "功能",
            ["资产同步", "灵魂采访", "身份审批", "语音速记", "陪伴测试", "治理"],
        )
        st.caption(f"生命周期：{'运行中' if app.started else '未启动'}")
        st.caption(f"待审身份：{len(container.identity_governance_service.list_pending())}")

    renderers: dict[str, Callable[[], None]] = {
        "资产同步": lambda: render_dashboard(container),
        "灵魂采访": lambda: render_creator(container),
        "身份审批": lambda: render_identity_review(container),
        "语音速记": lambda: render_voice(container),
        "陪伴测试": lambda: render_sandbox(container),
        "治理": lambda: render_governance(container, app),
    }
    renderers[page]()


if __name__ == "__main__":
    main()
