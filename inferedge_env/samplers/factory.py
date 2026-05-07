from __future__ import annotations

from inferedge_env.config.target_profile import SamplerProfile
from inferedge_env.samplers.base import Sampler
from inferedge_env.samplers.jetson_tegrastats import JetsonTegrastatsSampler


def build_sampler(profile: SamplerProfile | None) -> Sampler | None:
    if profile is None:
        return None
    if profile.name == "jetson-tegrastats":
        return JetsonTegrastatsSampler(
            tegrastats_path=profile.tegrastats_path,
            interval_ms=profile.interval_ms,
            startup_wait_ms=profile.startup_wait_ms,
            required=profile.required,
            raw_log=profile.raw_log,
        )
    raise ValueError(f"Unsupported sampler: {profile.name}")
