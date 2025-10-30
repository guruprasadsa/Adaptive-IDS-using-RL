"""
Heuristic post-processor for expanding attack types without retraining.

Given model probabilities and basic flow features, refine coarse classes
into more specific attack types when strong indicative patterns are present.
"""

from __future__ import annotations

from typing import Dict, List, Tuple


def refine_prediction(
    labels: List[str],
    probs: Dict[str, float],
    features: Dict[str, float]
) -> Tuple[str, Dict[str, float]]:
    """
    Refine a coarse prediction into more specific class names if possible.

    - Keeps original probabilities; only maps the top class name when rules match
    - Returns possibly-updated top_class and updated_probs (with same values, different keys)
    """
    if not labels or not probs:
        return "", probs

    # Identify top class
    top_class = max(probs.items(), key=lambda kv: kv[1])[0]

    # Normalize known base names
    base = top_class.replace("BENIGN", "Benign").replace("ATTACK", "Attack")

    # Feature helpers (defaults if missing)
    def f(name: str, default: float = 0.0) -> float:
        try:
            return float(features.get(name, default) or default)
        except Exception:
            return default

    flow_pkts_per_sec = f("flow_pkts_per_sec")
    flow_bytes_per_sec = f("flow_bytes_per_sec")
    fwd_pkt_rate = f("fwd_pkt_rate")
    bwd_pkt_rate = f("bwd_pkt_rate")
    fwd_iat_std = f("fwd_iat_std")
    fwd_iat_mean = f("fwd_iat_mean")
    bwd_iat_mean = f("bwd_iat_mean")
    syn_f = f("fwd_syn_flags") + f("bwd_syn_flags")
    rst_f = f("fwd_rst_flags") + f("bwd_rst_flags")
    psh_f = f("fwd_psh_flags") + f("bwd_psh_flags")
    ack_f = f("fwd_ack_flags") + f("bwd_ack_flags")

    refined = top_class

    # Heuristic splits (conservative thresholds)
    # PortScan: many SYNs with low bytes per second and high packet rate, low ACKs
    if (syn_f > 2 and ack_f < max(1.0, syn_f * 0.25) and flow_pkts_per_sec > 100 and flow_bytes_per_sec < 5e5):
        refined = "PortScan"

    # WebAttack: relatively balanced fwd/bwd packet rates with small payloads and many PSH/ACK
    elif (psh_f > 1 and ack_f > 1 and abs(fwd_pkt_rate - bwd_pkt_rate) < 100 and flow_bytes_per_sec < 3e5):
        refined = "WebAttack"

    # BruteForce: repeated attempts with frequent SYNs and RSTs, moderate rate
    elif (syn_f > 2 and rst_f > 1 and flow_pkts_per_sec > 50 and flow_pkts_per_sec < 500):
        refined = "BruteForce"

    # Slowloris/SlowHTTPTest: very low packet rates but long durations and high IAT variance
    elif (flow_pkts_per_sec < 10 and (fwd_iat_std > 1e5 or fwd_iat_mean > 1e5 or bwd_iat_mean > 1e5)):
        # Distinguish roughly by asymmetry in fwd/bwd rates
        refined = "Slowloris" if fwd_pkt_rate > bwd_pkt_rate else "Slowhttptest"

    # DDoS vs DoS variants: keep existing if present in labels
    elif base in ("DDoS", "DoS", "Hulk", "GoldenEye", "Slowloris", "Slowhttptest"):
        refined = base

    # If refined label is not in the known labels set, keep original
    if refined not in labels:
        return top_class, probs

    # Re-key probabilities to use refined class for the top score
    # Keep distribution values unchanged
    updated = dict(probs)
    if refined != top_class:
        score = updated.pop(top_class, None)
        if score is not None:
            updated[refined] = score

    return refined, updated


