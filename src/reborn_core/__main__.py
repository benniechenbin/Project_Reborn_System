import sys
from reborn_core.core.bootstrap import init_system

def main():
    print("🌌 Project Reborn Core CLI")
    if len(sys.argv) < 2:
        print("Usage: python -m reborn_core [api|sync]")
        return

    command = sys.argv[1]
    if command == "sync":
        from reborn_core.scripts.run_sync import execute_full_sync
        execute_full_sync()
    elif command == "api":
        print("🚀 API mode not yet implemented in __main__.py")
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    init_system()
    main()
