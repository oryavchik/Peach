"""Read an existing stack template and write a Retain-only candidate. Never deploys."""

import argparse
import json
import subprocess
from pathlib import Path


def retain_yaml(text):
    out = []
    resources = False
    for line in text.splitlines(keepends=True):
        if line.strip() == "Resources:" and not line.startswith(" "):
            resources = True
        elif resources and line.strip() and not line.startswith(" ") and not line.startswith("#"):
            resources = False
        if resources and line.startswith(("    DeletionPolicy:", "    UpdateReplacePolicy:")):
            continue
        out.append(line)
        if resources and line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
            out += ["    DeletionPolicy: Retain\n", "    UpdateReplacePolicy: Retain\n"]
    return "".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stack", choices=["peach-auth", "peach-reports", "peach-ai"])
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    response = json.loads(subprocess.check_output([
        "aws", "cloudformation", "get-template", "--stack-name", args.stack,
        "--template-stage", "Original", "--region", args.region, "--output", "json",
    ]))
    template = response["TemplateBody"]
    if isinstance(template, dict):
        for resource in template["Resources"].values():
            resource.update(DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
        candidate = json.dumps(template, indent=2) + "\n"
    else:
        try:
            document = json.loads(template)
        except ValueError:
            candidate = retain_yaml(template)
        else:
            for resource in document["Resources"].values():
                resource.update(DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
            candidate = json.dumps(document, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(candidate)
    args.output.chmod(0o600)
    print("Retain-only candidate written. No stack updated or deleted.")


if __name__ == "__main__":
    main()
