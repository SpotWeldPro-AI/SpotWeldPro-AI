"""
Abstract interfaces for the temporal inference framework.

Architecture: CNN feature extractor → sliding window → GRU/LSTM sequence classifier.

IMPORTANT — no model weights are included. These are interface definitions only.
Before training or deploying any model:
  1. Collect ground truth from validated destructive testing (not assumed OK/NOK).
  2. Separate samples by weld, part, session, and production batch to prevent leakage.
  3. Benchmark GRU and LSTM baselines before considering a transformer variant.
  4. Confirm all inference is causal: is_causal must be True for real-time deployment.
  5. Characterise end-to-end latency and sustained FPS on target hardware.

The optional temporal transformer is not implemented here. Implement it only after
GRU/LSTM baseline benchmarks are published and reviewed.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Sequence


@dataclass
class FeatureVector:
    """CNN-extracted feature vector for one frame."""
    values: List[float]
    source_model: str       # model_id of the extractor that produced this
    frame_timestamp_ms: float
    frame_index: int = 0


@dataclass
class SequencePrediction:
    """
    Output from a GRU/LSTM operating on a window of FeatureVectors.
    is_causal must be True for real-time deployment.
    """
    label: str
    confidence: float               # 0.0 – 1.0; not a probability unless calibrated
    window_start_ms: float
    window_end_ms: float
    model_id: str
    is_causal: bool                 # False means future-frame leakage — never deploy in real-time
    auxiliary: dict = field(default_factory=dict)


class FeatureExtractor(ABC):
    """Abstract CNN feature extractor interface."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Human-readable identifier including architecture and version."""

    @property
    @abstractmethod
    def output_dim(self) -> int:
        """Length of the feature vector this extractor produces."""

    @abstractmethod
    def extract(self, image_bytes: bytes) -> FeatureVector:
        """
        Extract features from JPEG or PNG image bytes.
        Never invents features; raises if the image cannot be decoded.
        """

    @abstractmethod
    def is_loaded(self) -> bool:
        """True if model weights are loaded and ready."""


class SequenceClassifier(ABC):
    """Abstract GRU/LSTM sequence classifier interface."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Human-readable identifier."""

    @property
    @abstractmethod
    def window_size(self) -> int:
        """Number of consecutive FeatureVectors the model expects."""

    @property
    @abstractmethod
    def is_causal(self) -> bool:
        """
        True if the model uses only past and present frames (no future leakage).
        Only causal models may be deployed for real-time inference.
        """

    @abstractmethod
    def predict(self, window: Sequence[FeatureVector]) -> SequencePrediction:
        """
        Classify a window of feature vectors.
        Requires exactly window_size elements; raises ValueError otherwise.
        """

    @abstractmethod
    def is_loaded(self) -> bool:
        """True if weights are loaded and ready."""


class NotLoadedExtractor(FeatureExtractor):
    """
    Sentinel extractor returned when no model is loaded.
    extract() always raises, making the absent model explicit.
    """

    @property
    def model_id(self) -> str:
        return "NOT_LOADED"

    @property
    def output_dim(self) -> int:
        return 0

    def extract(self, image_bytes: bytes) -> FeatureVector:
        raise RuntimeError(
            "No CNN feature extractor is loaded. "
            "Train and register a FeatureExtractor before running temporal inference."
        )

    def is_loaded(self) -> bool:
        return False


class NotLoadedClassifier(SequenceClassifier):
    """Sentinel classifier returned when no sequence model is loaded."""

    @property
    def model_id(self) -> str:
        return "NOT_LOADED"

    @property
    def window_size(self) -> int:
        return 0

    @property
    def is_causal(self) -> bool:
        return True  # vacuously causal; never actually runs

    def predict(self, window: Sequence[FeatureVector]) -> SequencePrediction:
        raise RuntimeError(
            "No sequence classifier is loaded. "
            "Train and register a SequenceClassifier before running temporal inference."
        )

    def is_loaded(self) -> bool:
        return False
