from enum import Enum
from typing import TypedDict


class PriceShockAssetGroup(Enum):
    IGNORE_STABLES = "ignore stables"
    JLP_ONLY = "jlp only"


class PriceShockParams(TypedDict):
    oracle_distortion: float
    asset_group: PriceShockAssetGroup
    n_scenarios: int
