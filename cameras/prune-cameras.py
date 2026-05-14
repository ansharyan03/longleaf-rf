#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy a nerfstudio dataset to a new folder with redundant cameras removed."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input nerfstudio dataset folder")
    parser.add_argument("--output", required=True, type=Path, help="Output dataset folder")
    parser.add_argument("--min-translation", type=float, default=0.05)
    parser.add_argument("--min-rotation-deg", type=float, default=3.0)
    parser.add_argument("--forward-axis", choices=["z", "-z"], default="z")
    parser.add_argument("--image-prefix", default="frame_")
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--digits", type=int, default=5)
    parser.add_argument(
        "--copy-downscaled-dirs",
        action="store_true",
        help="Also copy matching files from images_2, images_4, images_8, etc. when present.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without copying files.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj: Dict, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n == 0:
        raise ValueError("Cannot normalize zero-length vector")
    return v / n


def camera_center(T: np.ndarray) -> np.ndarray:
    return T[:3, 3]


def view_direction(T: np.ndarray, forward_axis: str) -> np.ndarray:
    v = T[:3, 2]
    if forward_axis == "-z":
        v = -v
    return normalize(v)


def angular_distance_deg(v1: np.ndarray, v2: np.ndarray) -> float:
    dot = float(np.clip(np.dot(v1, v2), -1.0, 1.0))
    return math.degrees(math.acos(dot))


def resolve_frame_path(dataset_root: Path, file_path: str) -> Path:
    p = Path(file_path)
    if p.is_absolute():
        return p
    return (dataset_root / p).resolve()


def relative_posix_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def frame_sort_key(frame: Dict) -> Tuple:
    file_path = frame.get("file_path", "")
    p = Path(file_path)
    stem = p.stem
    digits = "".join(ch if ch.isdigit() else " " for ch in stem).split()
    last_number = int(digits[-1]) if digits else float("inf")
    return (str(p.parent), last_number, str(p.name))


def select_nonredundant_frames(
    frames: List[Dict],
    min_translation: float,
    min_rotation_deg: float,
    forward_axis: str,
) -> List[Dict]:
    kept_frames: List[Dict] = []
    kept_centers: List[np.ndarray] = []
    kept_views: List[np.ndarray] = []

    for idx, frame in enumerate(frames):
        if "transform_matrix" not in frame:
            raise KeyError(f"Frame {idx} missing transform_matrix")

        T = np.asarray(frame["transform_matrix"], dtype=float)
        if T.shape != (4, 4):
            raise ValueError(f"Frame {idx} transform_matrix has shape {T.shape}, expected (4, 4)")

        c = camera_center(T)
        v = view_direction(T, forward_axis)

        redundant = False
        for kc, kv in zip(kept_centers, kept_views):
            tdist = np.linalg.norm(c - kc)
            rdist = angular_distance_deg(v, kv)
            if tdist < min_translation and rdist < min_rotation_deg:
                redundant = True
                break

        if not redundant:
            kept_frames.append(frame)
            kept_centers.append(c)
            kept_views.append(v)

    return kept_frames


def find_related_image_dirs(input_root: Path, main_rel_path: Path) -> List[Path]:
    """
    Given a path like images/frame_00001.png, return existing sibling image dirs:
      images/
      images_2/
      images_4/
      images_8/
    ...based on the same parent directory.
    """
    rel_parent = main_rel_path.parent
    parent_name = rel_parent.name

    if not parent_name.startswith("images"):
        return [rel_parent] if (input_root / rel_parent).exists() else []

    base_parent = rel_parent.parent
    candidates: List[Path] = []

    for child in sorted((input_root / base_parent).iterdir() if (input_root / base_parent).exists() else []):
        if child.is_dir() and (child.name == "images" or child.name.startswith("images_")):
            candidates.append(base_parent / child.name)

    if not candidates and (input_root / rel_parent).exists():
        candidates.append(rel_parent)

    return candidates


def copy_related_files(
    input_root: Path,
    output_root: Path,
    src_rel_path: Path,
    new_stem: str,
    copy_downscaled_dirs: bool,
) -> str:
    """
    Copy the primary image and optionally matching images in images_2/images_4/images_8.
    Returns the new file_path to write into transforms.json for the primary image.
    """
    src_rel_path = Path(src_rel_path)
    src_name = src_rel_path.name
    src_suffix = src_rel_path.suffix

    if copy_downscaled_dirs:
        dirs_to_check = find_related_image_dirs(input_root, src_rel_path)
    else:
        dirs_to_check = [src_rel_path.parent]

    primary_new_rel: str | None = None

    for rel_dir in dirs_to_check:
        src = input_root / rel_dir / src_name
        if not src.exists():
            continue

        dst_dir = output_root / rel_dir
        dst_dir.mkdir(parents=True, exist_ok=True)

        dst_name = f"{new_stem}{src_suffix}"
        dst = dst_dir / dst_name
        shutil.copy2(src, dst)

        if rel_dir == src_rel_path.parent:
            primary_new_rel = relative_posix_path(dst, output_root)

    if primary_new_rel is None:
        raise FileNotFoundError(f"Primary referenced image not found: {input_root / src_rel_path}")

    return primary_new_rel


def main() -> None:
    args = parse_args()

    input_root = args.input.resolve()
    output_root = args.output.resolve()
    input_transforms = input_root / "transforms.json"
    output_transforms = output_root / "transforms.json"

    if not input_root.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_root}")
    if not input_transforms.exists():
        raise FileNotFoundError(f"Missing transforms.json in input folder: {input_transforms}")
    if output_root.exists() and any(output_root.iterdir()) and not args.dry_run:
        raise FileExistsError(f"Output folder already exists and is not empty: {output_root}")

    data = load_json(input_transforms)
    if "frames" not in data or not isinstance(data["frames"], list):
        raise KeyError("transforms.json must contain a top-level list field named 'frames'")

    original_frames = sorted(data["frames"], key=frame_sort_key)
    original_count = len(original_frames)

    kept_frames = select_nonredundant_frames(
        original_frames,
        min_translation=args.min_translation,
        min_rotation_deg=args.min_rotation_deg,
        forward_axis=args.forward_axis,
    )

    print(f"Input frames: {original_count}")
    print(f"Kept frames:  {len(kept_frames)}")
    print(f"Removed:      {original_count - len(kept_frames)}")

    if args.dry_run:
        print("Dry run enabled; no files copied.")
        return

    output_root.mkdir(parents=True, exist_ok=True)

    new_frames: List[Dict] = []
    for out_i, frame in enumerate(kept_frames, start=args.start_index):
        if "file_path" not in frame:
            raise KeyError("A kept frame is missing file_path")

        src_rel_path = Path(frame["file_path"])
        new_stem = f"{args.image_prefix}{out_i:0{args.digits}d}"

        new_primary_rel = copy_related_files(
            input_root=input_root,
            output_root=output_root,
            src_rel_path=src_rel_path,
            new_stem=new_stem,
            copy_downscaled_dirs=args.copy_downscaled_dirs,
        )

        new_frame = copy.deepcopy(frame)
        new_frame["file_path"] = new_primary_rel
        new_frames.append(new_frame)

    new_data = copy.deepcopy(data)
    new_data["frames"] = new_frames
    save_json(new_data, output_transforms)

    print(f"Wrote: {output_transforms}")


if __name__ == "__main__":
    main()
