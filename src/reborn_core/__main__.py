import argparse
import json
import sys
from pathlib import Path

from cryptography.fernet import Fernet

from reborn_core.application import IdentitySnapshotStatus
from reborn_core.core.exceptions import RebornError
from reborn_core.lifecycle import lifespan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reborn")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("sync")
    sub.add_parser("backup")
    verify = sub.add_parser("verify-backup")
    verify.add_argument("path", type=Path)
    drill = sub.add_parser("recovery-drill")
    drill.add_argument("path", type=Path)
    sub.add_parser("identity-list")
    approve = sub.add_parser("identity-approve")
    approve.add_argument("snapshot_id")
    approve.add_argument("--note")
    reject = sub.add_parser("identity-reject")
    reject.add_argument("snapshot_id")
    reject.add_argument("--note")
    sub.add_parser("legacy-status")
    sub.add_parser("generate-encryption-key")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate-encryption-key":
        print(Fernet.generate_key().decode("ascii"))
        return 0

    try:
        with lifespan(show_startup_banner=False) as app:
            container = app.container
            if args.command == "check":
                print("Project Reborn lifecycle check passed")
            elif args.command == "sync":
                task_id = container.task_runner.submit("memory_sync", container.run_sync)
                print(container.task_runner.result(task_id).as_dict())
            elif args.command == "backup":
                task_id = container.task_runner.submit("encrypted_backup", container.run_backup)
                print(container.task_runner.result(task_id))
            elif args.command == "verify-backup":
                print(
                    json.dumps(
                        container.backup_service.verify_backup(args.path), ensure_ascii=False
                    )
                )
            elif args.command == "recovery-drill":
                print(
                    json.dumps(
                        container.backup_service.run_recovery_drill(args.path), ensure_ascii=False
                    )
                )
            elif args.command == "identity-list":
                snapshots = container.identity_snapshot_repository.list_identity_snapshots(
                    IdentitySnapshotStatus.PENDING_REVIEW
                )
                for snapshot in snapshots:
                    print(snapshot.snapshot_id, snapshot.created_at, ",".join(snapshot.source_ids))
            elif args.command == "identity-approve":
                print(container.identity_governance_service.approve(args.snapshot_id, args.note))
            elif args.command == "identity-reject":
                print(container.identity_governance_service.reject(args.snapshot_id, args.note))
            elif args.command == "legacy-status":
                print(container.legacy_activation_policy.evaluate())
    except RebornError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
