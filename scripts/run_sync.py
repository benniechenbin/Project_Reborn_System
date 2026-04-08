import os
import sys
from datetime import datetime

# 将项目根目录动态加入 Python 环境变量
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from config.settings import settings
from backend.obsidian.injector import ObsidianInjector

def fetch_latest_metrics():
    """模拟从数据库抓取数据，供注入器使用"""
    # 待您后续完成 sqlite 模块后，这里将替换为真正的 DB 查询逻辑
    return {
        'audio_duration': 35,
        'notes_count': 18,
        'word_count': 15600,
        'sync_time': datetime.now().strftime('%Y-%m-%d %H:%M')
    }

if __name__ == "__main__":
    print("🚀 启动数据同步任务...")
    
    vault_path = settings.active_obsidian_path
    
    # 修正冗余判断和报错文案
    if not vault_path:
        print("❌ 错误：未读取到当前操作系统的 Obsidian 路径。")
        print("💡 请检查 .env 文件中是否正确配置了 OBSIDIAN_VAULT_PATH_MAC 或 OBSIDIAN_VAULT_PATH_WIN。")
        sys.exit(1)
        
    print(f"✅ 成功加载系统配置。数据库: {settings.db_path}")
    print(f"✅ 锁定知识库路径: {vault_path}")
    
    # 1. 抓取数据
    metrics = fetch_latest_metrics()
    
    if metrics:
        # 2. 实例化注入器并执行更新
        injector = ObsidianInjector(vault_path=vault_path)
        # 注意：这里的路径是相对 vault_path 的
        injector.update_metrics('01_Project_Plan.md', metrics)
    else:
        print("⚠️ 同步中止：未能获取到有效数据。")