from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
MILESTONES_DIR = SCRIPT_DIR
INDEX_FILE = MILESTONES_DIR / "index.json"
README_FILE = MILESTONES_DIR / "README.md"
EXCLUDED_NAMES = {"__pycache__", ".git", ".idea", ".vscode", "milestones"}
DEFAULT_MATCH_LIMIT = 3


@dataclass
class Milestone:
    milestone_id: str
    timestamp: str
    description: str
    snapshot_dir: Path
    files: list[str]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "milestone"


def ensure_storage() -> None:
    MILESTONES_DIR.mkdir(exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text("[]\n", encoding="utf-8")
    if not README_FILE.exists():
        README_FILE.write_text(
            (
                "# Project Milestones\n\n"
                "Use `python milestones/milestone_manager.py create --description \"...\"` to save a snapshot.\n\n"
                "Use `python milestones/milestone_manager.py list` to see available milestones.\n\n"
                "Use `python milestones/milestone_manager.py restore --id <milestone_id>` to restore a snapshot.\n"
            ),
            encoding="utf-8",
        )


def iter_project_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_NAMES for part in relative.parts):
            continue
        if path.suffix != ".py":
            continue
        files.append(path)
    files.sort(key=lambda item: item.relative_to(ROOT).as_posix())
    return files


def load_index() -> list[dict]:
    ensure_storage()
    data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def save_index(items: list[dict]) -> None:
    INDEX_FILE.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")


def build_milestone(description: str) -> Milestone:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    folder_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    milestone_id = f"{folder_time}_{slugify(description)}"
    snapshot_dir = MILESTONES_DIR / milestone_id / "project"
    files = [path.relative_to(ROOT).as_posix() for path in iter_project_files()]
    return Milestone(
        milestone_id=milestone_id,
        timestamp=timestamp,
        description=description,
        snapshot_dir=snapshot_dir,
        files=files,
    )


def create_milestone(description: str) -> Milestone:
    ensure_storage()
    milestone = build_milestone(description)
    milestone.snapshot_dir.mkdir(parents=True, exist_ok=False)

    for relative_name in milestone.files:
        source = ROOT / relative_name
        destination = milestone.snapshot_dir / relative_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    metadata = {
        "id": milestone.milestone_id,
        "timestamp": milestone.timestamp,
        "description": milestone.description,
        "files": milestone.files,
    }
    metadata_path = milestone.snapshot_dir.parent / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    index = load_index()
    index.append(
        {
            "id": milestone.milestone_id,
            "timestamp": milestone.timestamp,
            "description": milestone.description,
            "path": milestone.snapshot_dir.parent.relative_to(ROOT).as_posix(),
        }
    )
    save_index(index)
    return milestone


def get_milestone_path(milestone_id: str) -> Path:
    milestone_path = MILESTONES_DIR / milestone_id
    metadata_path = milestone_path / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Milestone '{milestone_id}' was not found.")
    return milestone_path


def _print_milestone_matches(matches: list[dict]) -> None:
    print("Matching milestones:")
    for index, item in enumerate(matches, start=1):
        print(f"  {index}. {item['id']} | {item['timestamp']} | {item['description']}")


def _prompt_milestone_selection(matches: list[dict]) -> str:
    while True:
        choice = input("Select a milestone number (or press Enter to cancel): ").strip()
        if not choice:
            raise KeyboardInterrupt("Restore cancelled.")
        if choice.isdigit():
            selected_index = int(choice)
            if 1 <= selected_index <= len(matches):
                return matches[selected_index - 1]["id"]
        print(f"Please enter a number between 1 and {len(matches)}, or press Enter to cancel.")


def _latest_milestones(items: list[dict], limit: int = 5) -> list[dict]:
    return sorted(items, key=lambda item: item["timestamp"], reverse=True)[:limit]


def resolve_milestone_id(milestone_id: str) -> str:
    items = list_milestones()
    if not items:
        raise FileNotFoundError("No milestones found.")

    exact_ids = {item["id"] for item in items}
    if milestone_id in exact_ids:
        return milestone_id

    normalized_query = milestone_id.strip().lower()
    contains_matches = [
        item for item in items
        if normalized_query in item["id"].lower() or normalized_query in item["description"].lower()
    ]
    if contains_matches:
        _print_milestone_matches(contains_matches)
        return _prompt_milestone_selection(contains_matches)

    close_ids = difflib.get_close_matches(
        milestone_id,
        [item["id"] for item in items],
        n=DEFAULT_MATCH_LIMIT,
        cutoff=0.35,
    )
    fuzzy_matches = [item for item in items if item["id"] in close_ids]
    if fuzzy_matches:
        _print_milestone_matches(fuzzy_matches)
        return _prompt_milestone_selection(fuzzy_matches)

    print(f"Milestone '{milestone_id}' was not found exactly.")
    latest_matches = _latest_milestones(items, limit=DEFAULT_MATCH_LIMIT)
    _print_milestone_matches(latest_matches)
    return _prompt_milestone_selection(latest_matches)


def restore_milestone(milestone_id: str) -> dict:
    milestone_path = get_milestone_path(resolve_milestone_id(milestone_id))
    metadata = json.loads((milestone_path / "metadata.json").read_text(encoding="utf-8"))
    snapshot_dir = milestone_path / "project"

    for relative_name in metadata["files"]:
        if not relative_name.endswith(".py"):
            continue
        source = snapshot_dir / relative_name
        destination = ROOT / relative_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    return metadata


def list_milestones() -> list[dict]:
    return load_index()


def build_parser() -> tuple[argparse.ArgumentParser, dict[str, argparse.ArgumentParser]]:
    parser = argparse.ArgumentParser(
        description="Save and restore project milestones.",
        epilog=(
            "Examples:\n"
            "  python milestones/milestone_manager.py create -d \"initial parser\"\n"
            "  python milestones/milestone_manager.py list\n"
            "  python milestones/milestone_manager.py restore -i 20260325_123456_initial-parser"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")
    parser.set_defaults(_all_help=False)

    create_parser = subparsers.add_parser("create", help="Create a new project milestone.")
    create_parser.add_argument(
        "-d",
        "--description",
        required=True,
        help="Short description of what changed in this milestone.",
    )

    list_parser = subparsers.add_parser("list", help="List available milestones.")

    restore_parser = subparsers.add_parser("restore", help="Restore project files from a milestone.")
    restore_parser.add_argument(
        "-i",
        "--id",
        required=True,
        help="Milestone id returned by the create/list command. Supports partial and fuzzy matching."
    )
    subparsers.required = True
    subparsers_map = {
        "create": create_parser,
        "list": list_parser,
        "restore": restore_parser,
    }
    return parser, subparsers_map


def print_full_help(parser: argparse.ArgumentParser, subparsers_map: dict[str, argparse.ArgumentParser]) -> None:
    print(parser.format_help().rstrip())
    print("\nSubcommand Details:\n")
    for name in ("create", "list", "restore"):
        print(subparsers_map[name].format_help().rstrip())
        if name != "restore":
            print()


def main() -> None:
    parser, subparsers_map = build_parser()

    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        print_full_help(parser, subparsers_map)
        return

    args = parser.parse_args()

    if args.command == "create":
        milestone = create_milestone(args.description)
        print(f"Created milestone: {milestone.milestone_id}")
        print(f"Saved {len(milestone.files)} files.")
        return

    if args.command == "list":
        items = list_milestones()
        if not items:
            print("No milestones found.")
            return
        for item in items:
            print(f"{item['id']} | {item['timestamp']} | {item['description']}")
        return

    if args.command == "restore":
        try:
            metadata = restore_milestone(args.id)
        except KeyboardInterrupt:
            print("Restore cancelled.")
            return
        print(f"Restored milestone: {metadata['id']}")
        print(f"Restored {len(metadata['files'])} files.")


if __name__ == "__main__":
    main()
