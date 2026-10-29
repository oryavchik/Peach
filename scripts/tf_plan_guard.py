"""Read a private terraform show -json file. Never applies or prints plan values."""

import argparse
import json
from pathlib import Path


def managed_resources(module):
    return [r for r in module.get("resources", []) if r.get("mode") == "managed"] + [
        r for child in module.get("child_modules", []) for r in managed_resources(child)
    ]


def check_plan(plan, mode, expected_managed, expected_imports):
    if plan.get("errored") or "planned_values" not in plan:
        raise ValueError("A successful full Terraform JSON plan is required.")
    count = len(managed_resources(plan["planned_values"].get("root_module", {})))
    if count != expected_managed:
        raise ValueError(f"Expected {expected_managed} managed objects, found {count}; check coverage.")
    imports = 0
    for resource in plan.get("resource_changes", []):
        change = resource["change"]
        actions = change["actions"]
        if resource.get("mode") == "data" and actions in (["read"], ["no-op"]):
            continue
        if actions != ["no-op"]:
            raise ValueError(f"Rejected {resource['address']}: {'/'.join(actions)}")
        if change.get("importing"):
            imports += 1
    if mode == "import-only" and imports != expected_imports:
        raise ValueError(f"Expected {expected_imports} imports, found {imports}.")
    if mode == "no-changes":
        if imports:
            raise ValueError("Imports are not yet completed.")
        if any(c.get("actions") != ["no-op"] for c in plan.get("output_changes", {}).values()):
            raise ValueError("Outputs still change; this is not a final no-change plan.")
    return {"managed": count, "imports": imports, "cloud_mutations": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--mode", choices=["import-only", "no-changes"], required=True)
    parser.add_argument("--expected-managed", type=int, default=40)
    parser.add_argument("--expected-imports", type=int, default=40)
    args = parser.parse_args()
    try:
        result = check_plan(json.loads(args.plan.read_text()), args.mode,
                            args.expected_managed, args.expected_imports)
    except (ValueError, KeyError) as error:
        raise SystemExit(str(error)) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
