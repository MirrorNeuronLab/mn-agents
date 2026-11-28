"""Export the versioned MirrorNeuron agent catalog using only the standard library."""

import argparse
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def catalog_files(root):
    index = json.loads((root / "index.json").read_bytes())
    if index["schema_version"] != "mn-agents.index.v2":
        raise ValueError("Unsupported agent catalog")
    files = {}
    entries = []
    for entry in index["agents"]:
        ident, version = entry["agent_id"], str(entry["version"])
        if not re.fullmatch(r"[a-z][a-z0-9_.-]*", ident) or not version.isdecimal():
            raise ValueError(f"Invalid agent identity {ident}@{version}")
        folder = root / entry["resource_path"]
        folder.resolve(strict=True).relative_to(root)
        descriptor = json.loads(folder.read_bytes())
        if (
            descriptor["agent_id"],
            str(descriptor["version"]),
            descriptor["package_kind"],
        ) != (ident, version, entry["package_kind"]):
            raise ValueError(f"Agent resource identity mismatch for {ident}@{version}")
        prefix = f"agents/{ident}/{version}/"
        path = prefix + "agent.json"
        if path in files:
            raise ValueError(f"Duplicate reference {ident}@{version}")
        for filename in (
            "agent.json",
            descriptor.get("input_spec", "input.spec.json"),
            descriptor.get("output_spec", "output.spec.json"),
        ):
            if Path(filename).name != filename or not filename.endswith(".json"):
                raise ValueError(f"Invalid resource path in {ident}@{version}")
            resource = folder.parent / filename
            resource.resolve(strict=True).relative_to(folder.parent.resolve())
            files[prefix + filename] = resource.read_bytes()
        entries.append(
            {
                **entry,
                "resource_path": path,
                "sha256": hashlib.sha256(files[path]).hexdigest(),
            }
        )
    files["index.json"] = (
        json.dumps({**index, "agents": entries}, indent=2) + "\n"
    ).encode()
    return files


def export(destination, root=ROOT):
    destination = Path(destination).absolute()
    files = catalog_files(root.resolve())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as staging:
        if destination.suffix == ".zip":
            archive = Path(staging, "catalog.zip")
            with ZipFile(archive, "w") as packed:
                for name, data in sorted(files.items()):
                    info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                    info.external_attr = 0o100644 << 16
                    packed.writestr(info, data, compress_type=ZIP_DEFLATED)
            archive.replace(destination)
        else:
            folder = Path(staging, "catalog")
            for name, data in files.items():
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            folder.rename(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "destination", type=Path, help="A new directory or a .zip archive"
    )
    export(parser.parse_args().destination)
