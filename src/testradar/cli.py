from __future__ import annotations

import argparse
import json
from pathlib import Path

from testradar.audit import calculate_miss_rate, load_node_set
from testradar.config import load_config
from testradar.report import selection_report
from testradar.select import index_repository, select_targets


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    config = load_config(
        repo_root,
        base_ref=args.base_ref,
        graph_path=args.graph_path,
        git_dir=args.git_dir,
        git_work_tree=args.git_work_tree,
    )
    return args.handler(args, config)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="testradar")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-ref", default=None)
    parser.add_argument("--graph-path", default=None)
    parser.add_argument("--git-dir", default=None)
    parser.add_argument("--git-work-tree", default=None)

    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Build or update the static graph")
    index_parser.set_defaults(handler=_handle_index)

    refresh_parser = subparsers.add_parser("refresh", help="Alias for index in static-only mode")
    refresh_parser.set_defaults(handler=_handle_index)

    classify_parser = subparsers.add_parser("classify", help="Classify changed files")
    classify_parser.add_argument("--json", action="store_true", dest="as_json")
    classify_parser.set_defaults(handler=_handle_classify)

    select_parser = subparsers.add_parser("select", help="Emit affected pytest targets")
    select_parser.add_argument("--json", action="store_true", dest="as_json")
    select_parser.add_argument("--report", default=None)
    select_parser.add_argument("--targets-file", default=None)
    select_parser.set_defaults(handler=_handle_select)

    audit_parser = subparsers.add_parser("audit", help="Calculate miss rate from selected and failed sets")
    audit_parser.add_argument("--selected", required=True)
    audit_parser.add_argument("--failed", required=True)
    audit_parser.set_defaults(handler=_handle_audit)

    return parser


def _handle_index(args, config) -> int:
    snapshot, mode = index_repository(config)
    print(json.dumps({"graph_mode": mode, "python_files": len(snapshot.files)}))
    return 0


def _handle_classify(args, config) -> int:
    from testradar.classify import classify_changes
    from testradar.gitdiff import changed_files, resolve_base_commit

    base_commit = resolve_base_commit(
        config.repo_root,
        config.base_ref,
        git_dir=config.git_dir,
        git_work_tree=config.git_work_tree,
    )
    changes = changed_files(
        config.repo_root,
        base_commit,
        git_dir=config.git_dir,
        git_work_tree=config.git_work_tree,
    )
    rows = [
        {
            "path": change.path,
            "status": change.status,
            "old_path": change.old_path,
            "scope": decision.scope.value,
            "reason": decision.reason,
            "anchor": decision.anchor,
        }
        for change, decision in zip(changes, classify_changes(config, changes))
    ]
    if args.as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        for row in rows:
            print(f"{row['path']}\t{row['scope']}\t{row['reason']}")
    return 0


def _handle_select(args, config) -> int:
    result = select_targets(config)
    report = selection_report(result)
    if args.report:
        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = config.repo_root / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    rendered_targets = "\n".join(result.target_strings())
    if args.targets_file:
        targets_path = Path(args.targets_file)
        if not targets_path.is_absolute():
            targets_path = config.repo_root / targets_path
        targets_path.parent.mkdir(parents=True, exist_ok=True)
        targets_path.write_text(f"{rendered_targets}\n" if rendered_targets else "", encoding="utf-8")

    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        if rendered_targets:
            print(rendered_targets)
    return 0


def _handle_audit(args, _config) -> int:
    selected = load_node_set(Path(args.selected))
    failed = load_node_set(Path(args.failed))
    result = calculate_miss_rate(selected, failed)
    print(
        json.dumps(
            {
                "selected": sorted(result.selected),
                "failed": sorted(result.failed),
                "missed": sorted(result.missed),
                "miss_rate": result.miss_rate,
            },
            indent=2,
            sort_keys=True,
        ),
    )
    return 0
