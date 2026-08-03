"""Standalone Project Reborn backup recovery tool.

This file intentionally does not import reborn_core. It needs only Python 3,
cryptography, and the encrypted backup archive.
"""

import argparse
import getpass
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import struct
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import IO

from cryptography.fernet import Fernet, InvalidToken

STREAM_MAGIC = b"RBN1"
HASH_CHUNK_SIZE = 64 * 1024


def _sha256_stream(handle: IO[bytes]) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while chunk := handle.read(HASH_CHUNK_SIZE):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _cipher(key: str) -> Fernet:
    try:
        return Fernet(key.strip().encode("ascii"))
    except (UnicodeEncodeError, ValueError):
        raise ValueError("Fernet 密钥格式无效；应为完整的 44 个 ASCII 字符。") from None


def decrypt_backup(source: Path, target_zip: Path, key: str) -> None:
    """Decrypt RBN1 chunked or legacy single-token Fernet backup."""
    cipher = _cipher(key)
    with source.open("rb") as src:
        magic = src.read(len(STREAM_MAGIC))
        if magic != STREAM_MAGIC:
            src.seek(0)
            try:
                plaintext = cipher.decrypt(src.read())
            except InvalidToken as exc:
                raise ValueError("备份解密失败：密钥错误或文件已损坏。") from exc
            target_zip.write_bytes(plaintext)
            return

        with target_zip.open("wb") as dst:
            while True:
                length_bytes = src.read(4)
                if not length_bytes:
                    break
                if len(length_bytes) != 4:
                    raise ValueError("备份损坏：分块长度头不完整。")
                length = struct.unpack(">I", length_bytes)[0]
                token = src.read(length)
                if len(token) != length:
                    raise ValueError("备份损坏：加密分块不完整。")
                try:
                    dst.write(cipher.decrypt(token))
                except InvalidToken as exc:
                    raise ValueError("备份解密失败：密钥错误或文件已损坏。") from exc


def _safe_member_path(root: Path, name: str) -> Path:
    portable = PurePosixPath(name)
    if portable.is_absolute() or ".." in portable.parts:
        raise ValueError(f"拒绝不安全的归档路径：{name}")
    destination = (root / Path(*portable.parts)).resolve()
    resolved_root = root.resolve()
    if destination != resolved_root and resolved_root not in destination.parents:
        raise ValueError(f"拒绝越界的归档路径：{name}")
    return destination


def _is_symlink(member: zipfile.ZipInfo) -> bool:
    mode = member.external_attr >> 16
    return stat.S_IFMT(mode) == stat.S_IFLNK


def verify_and_extract(zip_path: Path, output_dir: Path) -> dict[str, object]:
    """Verify manifest hashes, extract safely, and check the SQLite snapshot."""
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"输出目录必须为空：{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as archive:
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except KeyError as exc:
            raise ValueError("备份缺少 manifest.json。") from exc
        files = manifest.get("files")
        if not isinstance(files, list):
            raise ValueError("manifest.json 中的 files 字段无效。")

        expected_paths: set[str] = set()
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("manifest.json 包含无效文件记录。")
            archive_path = item.get("archive_path")
            if not isinstance(archive_path, str) or archive_path in expected_paths:
                raise ValueError("manifest.json 包含重复或无效路径。")
            expected_paths.add(archive_path)
            try:
                member = archive.getinfo(archive_path)
            except KeyError as exc:
                raise ValueError(f"备份缺少文件：{archive_path}") from exc
            if _is_symlink(member):
                raise ValueError(f"拒绝符号链接归档成员：{archive_path}")
            with archive.open(member, "r") as handle:
                digest, size = _sha256_stream(handle)
            if digest != item.get("sha256"):
                raise ValueError(f"文件哈希校验失败：{archive_path}")
            if size != item.get("size"):
                raise ValueError(f"文件大小校验失败：{archive_path}")

        for member in archive.infolist():
            destination = _safe_member_path(output_dir, member.filename)
            if _is_symlink(member):
                raise ValueError(f"拒绝符号链接归档成员：{member.filename}")
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)

    database_path = output_dir / "sqlite" / "reborn.db"
    if not database_path.is_file():
        raise ValueError("备份缺少 sqlite/reborn.db。")
    connection = sqlite3.connect(database_path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    if integrity != "ok":
        raise ValueError(f"SQLite 完整性检查失败：{integrity}")

    return {
        "backup_id": manifest.get("backup_id"),
        "file_count": len(files),
        "sqlite_integrity": integrity,
        "profile": str(output_dir / "profile" / "project_profile.toml"),
        "vault": str(output_dir / "vault"),
        "database": str(database_path),
    }


def restore_backup(archive: Path, output_dir: Path, key: str) -> dict[str, object]:
    """Decrypt and restore an archive without modifying the source."""
    archive = archive.resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"找不到备份文件：{archive}")
    with tempfile.TemporaryDirectory(prefix="reborn-offline-") as temp:
        decrypted_zip = Path(temp) / "reborn.zip"
        decrypt_backup(archive, decrypted_zip, key)
        return verify_and_extract(decrypted_zip, output_dir.resolve())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project Reborn 离线备份恢复工具")
    parser.add_argument("archive", type=Path, help=".zip.fernet 备份文件")
    parser.add_argument("output", type=Path, help="必须为空的恢复输出目录")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    key = os.environ.get("REBORN_BACKUP_KEY") or getpass.getpass("Fernet 密钥：")
    try:
        result = restore_backup(args.archive, args.output, key)
    except Exception as exc:
        print(f"恢复失败：{exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
