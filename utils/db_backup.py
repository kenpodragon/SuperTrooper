"""
Database backup and restore utility for SuperTroopers.

Usage:
    python db_backup.py dump [--output DIR] [--tag TAG]
    python db_backup.py restore <file>
    python db_backup.py list [--dir DIR]

Requires pg_dump and pg_restore on PATH (comes with PostgreSQL installation).
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_DUMP_DIR = os.environ.get(
    "ST_DUMP_DIR",
    str(Path(__file__).resolve().parent.parent.parent / "local_code" / "db_dumps"),
)


def get_db_env():
    """Read DB connection from environment or backend/.env file."""
    env = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": os.environ.get("DB_PORT", "5555"),
        "name": os.environ.get("DB_NAME", "supertroopers"),
        "user": os.environ.get("DB_USER", "supertroopers"),
        "password": os.environ.get("DB_PASSWORD", ""),
    }

    # Try reading from backend/.env if password not set
    if not env["password"]:
        env_file = Path(__file__).resolve().parent.parent / "backend" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if key == "DB_HOST":
                    env["host"] = val
                elif key == "DB_PORT":
                    env["port"] = val
                elif key == "DB_NAME":
                    env["name"] = val
                elif key == "DB_USER":
                    env["user"] = val
                elif key == "DB_PASSWORD":
                    env["password"] = val

    return env


def dump(output_dir: str, tag: str = "") -> str:
    """Create a pg_dump of the database.

    Returns the path to the dump file.
    """
    db = get_db_env()
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag_part = f"_{tag}" if tag else ""
    filename = f"supertroopers_{timestamp}{tag_part}.dump"
    filepath = os.path.join(output_dir, filename)

    cmd = [
        "pg_dump",
        "-h", db["host"],
        "-p", db["port"],
        "-U", db["user"],
        "-d", db["name"],
        "-Fc",  # custom format (compressed, supports pg_restore)
        "-f", filepath,
    ]

    env = os.environ.copy()
    env["PGPASSWORD"] = db["password"]

    print(f"Dumping {db['name']} to {filepath}...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: pg_dump failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"Done. {size_mb:.1f} MB written to {filepath}")
    return filepath


def restore(filepath: str) -> None:
    """Restore a pg_dump file into the database.

    WARNING: This drops and recreates all tables.
    """
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    db = get_db_env()
    env = os.environ.copy()
    env["PGPASSWORD"] = db["password"]

    print(f"Restoring {filepath} into {db['name']}...")
    print("WARNING: This will overwrite existing data. Ctrl+C to cancel (3 seconds)...")

    import time
    time.sleep(3)

    cmd = [
        "pg_restore",
        "-h", db["host"],
        "-p", db["port"],
        "-U", db["user"],
        "-d", db["name"],
        "--clean",        # drop objects before recreating
        "--if-exists",    # don't error on missing objects during clean
        "--no-owner",     # don't set ownership
        filepath,
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    # pg_restore returns non-zero for warnings too, so check stderr
    if result.returncode != 0 and "ERROR" in result.stderr:
        print(f"Errors during restore:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    if result.stderr:
        print(f"Warnings:\n{result.stderr}")

    print("Restore complete.")


def list_dumps(dump_dir: str) -> None:
    """List available dump files."""
    dump_path = Path(dump_dir)
    if not dump_path.exists():
        print(f"No dump directory found at {dump_dir}")
        return

    dumps = sorted(dump_path.glob("supertroopers_*.dump"), reverse=True)
    if not dumps:
        print("No dump files found.")
        return

    print(f"{'File':<55} {'Size':>10} {'Date':>20}")
    print("-" * 87)
    for f in dumps:
        size_mb = f.stat().st_size / (1024 * 1024)
        mod_time = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{f.name:<55} {size_mb:>8.1f} MB {mod_time:>20}")


def build_parser(prog=None):
    parser = argparse.ArgumentParser(
        prog=prog,
        description="SuperTroopers database backup and restore utility",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    dump_p = sub.add_parser("dump", help="Create a database dump")
    dump_p.add_argument("--output", default=DEFAULT_DUMP_DIR, help="Output directory")
    dump_p.add_argument("--tag", default="", help="Optional tag for the dump filename")

    restore_p = sub.add_parser("restore", help="Restore from a dump file")
    restore_p.add_argument("file", help="Path to the dump file")

    list_p = sub.add_parser("list", help="List available dump files")
    list_p.add_argument("--dir", default=DEFAULT_DUMP_DIR, help="Dump directory to list")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "dump":
        dump(args.output, args.tag)
    elif args.command == "restore":
        restore(args.file)
    elif args.command == "list":
        list_dumps(args.dir)


if __name__ == "__main__":
    main()
