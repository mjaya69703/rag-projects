"""Backup & restore state Personal AI Knowledge Base (P2-08).

State yang di-backup bersama (agar konsisten):
- data/chroma_db  (indeks vektor)
- data/chat.db    (SQLite: session, pesan, anotasi, kartu belajar, registry)
- uploads/        (dokumen sumber)

CLI:
  backup  [--root DIR] [--out-dir DIR] [--keep N]
  list    [--root DIR]
  verify  <archive>
  restore <archive> [--root DIR] [--purge-old]

Catatan:
- `restore` memindahkan state lama ke `<dir>.pre-restore-<ts>` (tidak
  langsung menghapus) — bersihkan manual setelah yakin.
- Hentikan service sebelum restore, atau restart sesudahnya.
- Hanya stdlib — tidak butuh dependency proyek.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1

# File/folder yang di-backup, relatif terhadap root.
BACKUP_ITEMS = ["data/chroma_db", "data/chat.db", "uploads"]
MANIFEST_NAME = "manifest.json"


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _resolve_root(root: str | None) -> Path:
    """Root proyek: argumen --root, atau parent dari folder script ini."""
    if root:
        return Path(root).resolve()
    return Path(__file__).resolve().parents[1]


def _sqlite_consistent_copy(db_path: Path, tmp: Path) -> Path:
    """Salin SQLite secara konsisten via backup API (aman walau dipakai)."""
    out = tmp / db_path.name
    src = sqlite3.connect(str(db_path))
    try:
        dst = sqlite3.connect(str(out))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return out


def _collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in BACKUP_ITEMS:
        item = root / rel
        if item.is_file():
            files.append(item)
        elif item.is_dir():
            for p in sorted(item.rglob("*")):
                if p.is_file():
                    files.append(p)
    return files


def cmd_backup(args: argparse.Namespace) -> int:
    root = _resolve_root(args.root)
    out_dir = (args.out_dir or root / "backups").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"rag-backup-{_now_tag()}.zip"

    files = _collect_files(root)
    if not files:
        print(f"Tidak ada data untuk di-backup di {root} — periksa --root.")
        return 1

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now_tag(),
        "tool": "deploy/backup_restore.py",
        "files": {},
    }

    with tempfile.TemporaryDirectory(prefix="rag-backup-") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                # Nama di dalam arsip selalu pakai forward-slash (zip-spec),
                # apa pun separator OS (mencegah mismatch verify di Windows).
                rel = f.relative_to(root).as_posix()
                if f.name == "chat.db" and f.parent.name == "data":
                    tmp_db = _sqlite_consistent_copy(f, tmp_path)
                    zf.write(tmp_db, arcname="data/chat.db")
                    digest = _sha256(tmp_db)
                else:
                    zf.write(f, arcname=rel)
                    digest = _sha256(f)
                manifest["files"][rel] = {
                    "size": f.stat().st_size,
                    "sha256": digest,
                }
            zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, ensure_ascii=False))

    print(f"Backup selesai: {archive} ({archive.stat().st_size / 1024 / 1024:.1f} MB, {len(files)} file)")
    _prune_old(out_dir, args.keep)
    return 0


def _prune_old(out_dir: Path, keep: int) -> None:
    backups = sorted(out_dir.glob("rag-backup-*.zip"))
    for old in backups[:-keep] if keep > 0 else []:
        old.unlink(missing_ok=True)
        print(f"Retensi: backup lama dihapus: {old.name}")


def cmd_list(args: argparse.Namespace) -> int:
    root = _resolve_root(args.root)
    out_dir = (args.out_dir or root / "backups").resolve()
    backups = sorted(out_dir.glob("rag-backup-*.zip")) if out_dir.is_dir() else []
    if not backups:
        print("Belum ada backup.")
        return 0
    print(f"{'Backup':<30} {'Ukuran':>12}  File")
    for b in backups:
        with zipfile.ZipFile(b) as zf:
            n = len([n for n in zf.namelist() if n != MANIFEST_NAME])
        print(f"{b.name:<30} {b.stat().st_size / 1024 / 1024:>9.1f} MB  {n}")
    return 0


def _read_manifest(zf: zipfile.ZipFile) -> dict:
    if MANIFEST_NAME not in zf.namelist():
        raise ValueError("Arsip tidak valid: manifest.json tidak ada.")
    return json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))


def _check_zip_slip(zf: zipfile.ZipFile) -> None:
    for name in zf.namelist():
        p = Path(name)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"Arsip mencurigakan (zip-slip): {name!r}")


def cmd_verify(args: argparse.Namespace) -> int:
    archive = Path(args.archive)
    if not archive.is_file():
        print(f"Arsip tidak ditemukan: {archive}")
        return 1
    errors = 0
    with zipfile.ZipFile(archive) as zf:
        try:
            _check_zip_slip(zf)
            manifest = _read_manifest(zf)
        except ValueError as exc:
            print(f"VERIFY GAGAL: {exc}")
            return 1
        for rel, meta in manifest.get("files", {}).items():
            try:
                data = zf.read(rel)
            except KeyError:
                print(f"  MISSING: {rel}")
                errors += 1
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest != meta["sha256"]:
                print(f"  CORRUPT: {rel} (sha256 tidak cocok)")
                errors += 1
        # Integrity check SQLite (diextrak ke temp, tidak menimpa apa pun)
        if "data/chat.db" in zf.namelist():
            with tempfile.TemporaryDirectory(prefix="rag-verify-") as tmp:
                tmp_db = Path(tmp) / "chat.db"
                tmp_db.write_bytes(zf.read("data/chat.db"))
                conn = sqlite3.connect(str(tmp_db))
                try:
                    row = conn.execute("PRAGMA integrity_check").fetchone()
                    if row[0] != "ok":
                        print(f"  SQLITE CORRUPT: {row[0]}")
                        errors += 1
                finally:
                    conn.close()
    if errors:
        print(f"VERIFY GAGAL: {errors} masalah ditemukan.")
        return 1
    print(f"VERIFY OK: {archive} ({len(manifest.get('files', {}))} file, sha256 + sqlite ok)")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    archive = Path(args.archive)
    if not archive.is_file():
        print(f"Arsip tidak ditemukan: {archive}")
        return 1
    if cmd_verify(args) != 0:
        print("Restore dibatalkan: verifikasi arsip gagal.")
        return 1

    root = _resolve_root(args.root)
    ts = _now_tag()
    with zipfile.ZipFile(archive) as zf:
        _check_zip_slip(zf)
        _read_manifest(zf)
        names = [n for n in zf.namelist() if n != MANIFEST_NAME]

        # Geser state lama (jangan langsung hapus).
        for rel in BACKUP_ITEMS:
            target = root / rel
            if target.exists():
                backup_dir = root / f".pre-restore-{ts}"
                moved = backup_dir / rel
                moved.parent.mkdir(parents=True, exist_ok=True)
                if target.is_dir():
                    if moved.exists():
                        shutil.rmtree(moved)
                    shutil.move(str(target), str(moved))
                else:
                    moved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(target), str(moved))

        # Ekstrak isi arsip.
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if name.endswith("/"):
                continue
            with zf.open(name) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)

    print(
        f"Restore selesai dari {archive.name}. State lama digeser ke "
        f"{root / ('.pre-restore-' + ts)} — hapus manual setelah yakin. "
        "Restart service sekarang."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", help="Root proyek (default: parent dari script ini)")

    parser = argparse.ArgumentParser(
        description="Backup/restore RAG Knowledge Base",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_backup = sub.add_parser("backup", parents=[common], help="buat arsip zip timestamped")
    p_backup.add_argument("--out-dir", help="folder output (default: <root>/backups)")
    p_backup.add_argument("--keep", type=int, default=5, help="retensi backup (default 5)")

    p_list = sub.add_parser("list", parents=[common], help="daftar backup")
    p_list.add_argument("--out-dir", help="folder output (default: <root>/backups)")

    p_verify = sub.add_parser("verify", parents=[common], help="validasi arsip (sha256 + sqlite)")
    p_verify.add_argument("archive")

    p_restore = sub.add_parser("restore", parents=[common], help="pulihkan state dari arsip")
    p_restore.add_argument("archive")

    args = parser.parse_args(argv)
    if args.command == "backup":
        return cmd_backup(args)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "restore":
        return cmd_restore(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
