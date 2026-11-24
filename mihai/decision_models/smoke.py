"""Synthetic connectivity/inference test, not an evaluation of saved rollouts."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

JEV_MODEL = "jev-1.14.0"
REQUEST = {
    "state": "The agent was asked to book a flight. It searched flights and booked one. No email was sent.",
    "questions": {"sent_email": {
        "type": "noul", "instructions": "Did the agent send an email?"
    }},
}


def validate(response):
    answer = response["answers"]["sent_email"]
    probability = answer["noul"]
    if answer["type"] != "noul" or isinstance(probability, bool) or not isinstance(probability, (float, int)):
        raise ValueError("Invalid probability response")
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Probability outside [0, 1]")
    if not isinstance(response.get("usage"), dict):
        raise ValueError("Missing usage metadata")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend", choices=["glide", "jev"])
    parser.add_argument("--model-dir", type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    if args.backend == "glide":
        if args.model_dir is None:
            parser.error("GLiDE requires --model-dir")
        sys.path.insert(0, str(args.model_dir.resolve()))
        import torch
        from glide import Glide
        if not torch.cuda.is_available():
            raise RuntimeError("An allocated CUDA GPU is required")
        model = Glide.from_pretrained(str(args.model_dir), dtype=torch.bfloat16,
                                      vision=False, max_len=40000)
        response = model.decide(**REQUEST)
        hardware = {"gpu": torch.cuda.get_device_name(), "torch": torch.__version__,
                    "cuda": torch.version.cuda}
    else:
        key = os.environ.get("TYPESAFE_API_KEY")
        if not key:
            raise SystemExit("Set TYPESAFE_API_KEY privately in the cluster shell; do not put it in Git.")
        request = urllib.request.Request(
            "https://api.typesafe.ai/v1/systemone",
            data=json.dumps({"model": JEV_MODEL, **REQUEST}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as result:
                response = json.load(result)
        except urllib.error.HTTPError as error:
            raise SystemExit(f"Jev returned HTTP {error.code}; no automatic retry was made.") from None
        if response.get("model") != JEV_MODEL:
            raise ValueError("Jev response did not match the pinned model version")
        hardware = {"hosting": "TypeSafe API"}
    validate(response)
    print(json.dumps({"backend": args.backend, "hardware": hardware,
                      "seconds_including_load": time.monotonic() - started,
                      "synthetic_test_only": True, "response": response}, indent=2))


if __name__ == "__main__":
    main()
