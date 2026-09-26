"""Canonical label order for the risk model's eight type outputs."""

from collections.abc import Iterable

LABELS = (
    "institution_impersonation",
    "money_transfer",
    "personal_information",
    "app_installation",
    "secrecy",
    "threat_pressure",
    "loan_fraud",
    "information_probing",
)
LABEL2ID = {label: index for index, label in enumerate(LABELS)}
ID2LABEL = {index: label for index, label in enumerate(LABELS)}
NUM_LABELS = len(LABELS)


def to_multi_hot(labels: Iterable[str]) -> list[int]:
    """Convert labels to the canonical eight binary targets."""

    if isinstance(labels, (str, bytes)):
        raise ValueError("labels must be an iterable of label names")
    try:
        iterator = iter(labels)
    except TypeError as error:
        raise ValueError("labels must be an iterable of label names") from error

    targets = [0] * NUM_LABELS
    for label in iterator:
        if not isinstance(label, str) or label not in LABEL2ID:
            raise ValueError(f"unknown label: {label!r}")
        targets[LABEL2ID[label]] = 1
    return targets
