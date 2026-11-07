r"""Train and export a Wi-Pose CSI-to-skeleton regression model.

Examples (from the repository root):
    .venv\Scripts\python.exe train.py --train-dir Wi-Pose\Train
    .venv\Scripts\python.exe train.py --predict Wi-Pose\Test\bend_009-frame001.mat

The exported TorchScript model accepts raw CSI shaped [batch, 3, 3, 30, 5]
and returns the 54 values stored in SkeletonPoints shaped [batch, 54].
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from pathlib import Path
from typing import Iterable

import h5py
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


CSI_SHAPE = (3, 3, 30, 5)
TARGET_SIZE = 54
SEQUENCE_PATTERN = re.compile(r"^(?P<sequence>.+)-frame\d+\.mat$")


def _mat_files(directory: Path) -> list[Path]:
    files = sorted(directory.glob("*.mat"))
    if not files:
        raise FileNotFoundError(f"No .mat files found in {directory}")
    return files


def _sequence_name(path: Path) -> str:
    match = SEQUENCE_PATTERN.match(path.name)
    if match is None:
        raise ValueError(f"Expected '<sequence>-frameNNN.mat', got {path.name}")
    return match.group("sequence")


def _read_mat(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with h5py.File(path, "r") as handle:
        if "CSI" not in handle or "SkeletonPoints" not in handle:
            raise KeyError(f"{path} must contain CSI and SkeletonPoints datasets")
        csi = np.asarray(handle["CSI"], dtype=np.float32)
        target = np.asarray(handle["SkeletonPoints"], dtype=np.float32).reshape(-1)
    if csi.shape != CSI_SHAPE:
        raise ValueError(f"{path} has CSI shape {csi.shape}; expected {CSI_SHAPE}")
    if target.size != TARGET_SIZE:
        raise ValueError(
            f"{path} has {target.size} SkeletonPoints; expected {TARGET_SIZE}"
        )
    if not np.isfinite(csi).all() or not np.isfinite(target).all():
        raise ValueError(f"{path} contains NaN or infinite values")
    return csi, target


class MatDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(
        self,
        files: Iterable[Path],
        input_mean: np.ndarray,
        input_std: np.ndarray,
        target_mean: np.ndarray,
        target_std: np.ndarray,
    ) -> None:
        self.files = list(files)
        self.input_mean = input_mean.astype(np.float32)
        self.input_std = input_std.astype(np.float32)
        self.target_mean = target_mean.astype(np.float32)
        self.target_std = target_std.astype(np.float32)

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        csi, target = _read_mat(self.files[index])
        csi = (csi - self.input_mean) / self.input_std
        target = (target - self.target_mean) / self.target_std
        return torch.from_numpy(csi), torch.from_numpy(target)


class PoseMLP(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Flatten(),
            nn.Linear(math.prod(CSI_SHAPE), 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, TARGET_SIZE),
        )

    def forward(self, csi: torch.Tensor) -> torch.Tensor:
        return self.network(csi)


class ExportedPoseModel(nn.Module):
    def __init__(
        self,
        model: PoseMLP,
        input_mean: np.ndarray,
        input_std: np.ndarray,
        target_mean: np.ndarray,
        target_std: np.ndarray,
    ) -> None:
        super().__init__()
        self.model = model
        self.register_buffer("input_mean", torch.from_numpy(input_mean.astype(np.float32)))
        self.register_buffer("input_std", torch.from_numpy(input_std.astype(np.float32)))
        self.register_buffer("target_mean", torch.from_numpy(target_mean.astype(np.float32)))
        self.register_buffer("target_std", torch.from_numpy(target_std.astype(np.float32)))

    def forward(self, csi: torch.Tensor) -> torch.Tensor:
        normalized = (csi - self.input_mean) / self.input_std
        return self.model(normalized) * self.target_std + self.target_mean


def _split_by_sequence(
    files: list[Path], validation_fraction: float, seed: int
) -> tuple[list[Path], list[Path]]:
    sequences: dict[str, list[Path]] = {}
    for path in files:
        sequences.setdefault(_sequence_name(path), []).append(path)
    names = sorted(sequences)
    random.Random(seed).shuffle(names)
    validation_count = max(1, round(len(names) * validation_fraction))
    validation_names = set(names[:validation_count])
    train = [path for path in files if _sequence_name(path) not in validation_names]
    validation = [path for path in files if _sequence_name(path) in validation_names]
    return train, validation


def _statistics(files: list[Path], sample_size: int, seed: int) -> tuple[np.ndarray, ...]:
    rng = random.Random(seed)
    selected = files if len(files) <= sample_size else rng.sample(files, sample_size)
    inputs: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    for path in selected:
        csi, target = _read_mat(path)
        inputs.append(csi)
        targets.append(target)
    input_values = np.stack(inputs).reshape(-1)
    target_values = np.stack(targets)
    input_mean = np.asarray(input_values.mean(), dtype=np.float32)
    input_std = np.asarray(max(input_values.std(), 1e-6), dtype=np.float32)
    target_mean = target_values.mean(axis=0).astype(np.float32)
    target_std = np.maximum(target_values.std(axis=0), 1e-6).astype(np.float32)
    return input_mean, input_std, target_mean, target_std


def _evaluate(
    model: nn.Module, loader: DataLoader[tuple[torch.Tensor, torch.Tensor]], device: torch.device
) -> tuple[float, float]:
    model.eval()
    loss_sum = 0.0
    count = 0
    with torch.inference_mode():
        for inputs, targets in loader:
            predictions = model(inputs.to(device))
            loss_sum += nn.functional.mse_loss(predictions, targets.to(device), reduction="sum").item()
            count += targets.numel()
    mse = loss_sum / count
    return mse, math.sqrt(mse)


def train(args: argparse.Namespace) -> None:
    train_files = _mat_files(args.train_dir)
    train_files, validation_files = _split_by_sequence(
        train_files, args.validation_fraction, args.seed
    )
    if args.limit is not None:
        train_files = train_files[: args.limit]
        validation_files = validation_files[: max(1, args.limit // 5)]
    input_mean, input_std, target_mean, target_std = _statistics(
        train_files, args.statistics_samples, args.seed
    )
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model = PoseMLP().to(device)
    train_loader = DataLoader(
        MatDataset(train_files, input_mean, input_std, target_mean, target_std),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
    )
    validation_loader = DataLoader(
        MatDataset(validation_files, input_mean, input_std, target_mean, target_std),
        batch_size=args.batch_size,
        num_workers=args.workers,
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    patience_left = args.patience
    for epoch in range(1, args.epochs + 1):
        model.train()
        for inputs, targets in train_loader:
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.mse_loss(model(inputs.to(device)), targets.to(device))
            loss.backward()
            optimizer.step()
        validation_loss, validation_rmse = _evaluate(model, validation_loader, device)
        print(f"epoch={epoch:03d} validation_mse={validation_loss:.6f} validation_rmse={validation_rmse:.6f}")
        if validation_loss < best_loss:
            best_loss = validation_loss
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            patience_left = args.patience
        else:
            patience_left -= 1
            if patience_left == 0:
                break
    if best_state is None:
        raise RuntimeError("Training did not produce a validation checkpoint")
    model.load_state_dict(best_state)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    exported = ExportedPoseModel(model.cpu().eval(), input_mean, input_std, target_mean, target_std)
    scripted = torch.jit.script(exported)
    model_path = args.output_dir / "wi_pose_model.pt"
    scripted.save(str(model_path))
    metadata = {
        "input_name": "CSI",
        "input_shape": list(CSI_SHAPE),
        "output_name": "SkeletonPoints",
        "output_shape": [TARGET_SIZE],
        "model_file": model_path.name,
        "train_files": len(train_files),
        "validation_files": len(validation_files),
        "device": str(device),
        "seed": args.seed,
    }
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"exported={model_path}")


def predict(model_dir: Path, mat_file: Path) -> None:
    csi, _ = _read_mat(mat_file)
    model = torch.jit.load(str(model_dir / "wi_pose_model.pt"), map_location="cpu").eval()
    with torch.inference_mode():
        prediction = model(torch.from_numpy(csi).unsqueeze(0)).numpy()[0]
    print(json.dumps({"file": str(mat_file), "skeleton_points": prediction.tolist()}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-dir", type=Path, default=Path("Wi-Pose/Train"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/wi-pose"))
    parser.add_argument("--predict", type=Path, help="Predict one MAT file using an exported model")
    parser.add_argument("--model-dir", type=Path, default=Path("artifacts/wi-pose"))
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--validation-fraction", type=float, default=0.1)
    parser.add_argument("--statistics-samples", type=int, default=4096)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--limit", type=int, help="Limit files for a quick smoke test")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    if args.predict is not None:
        predict(args.model_dir, args.predict)
    else:
        train(args)


if __name__ == "__main__":
    main()

# python train.py --train-dir Wi-Pose\Train --output-dir artifacts\wi-pose --epochs 30 --batch-size 256 --workers 0