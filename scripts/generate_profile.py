from pathlib import Path
import argparse
from generate_ascii import generate_ascii_svg
from generate_stats import generate_all_stats

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def main():
    parser = argparse.ArgumentParser(description="Generate the GalacticBear GitHub profile assets.")
    parser.add_argument("--skip-portrait", action="store_true", help="Skip local portrait generation.")
    parser.add_argument("--skip-stats", action="store_true", help="Skip GitHub statistics generation.")
    args = parser.parse_args()

    ASSETS.mkdir(parents=True, exist_ok=True)

    if not args.skip_portrait:
        source = ASSETS / "source.jpg"
        if not source.exists():
            raise SystemExit("Put your photo at assets/source.jpg")
        print("Generating ASCII portrait...")
        generate_ascii_svg(source, ASSETS / "profile.svg")
        print("ASCII portrait generated: assets/profile.svg")

    if not args.skip_stats:
        print("Generating GitHub statistics...")
        generate_all_stats(ASSETS)
        print("GitHub statistics generated.")


if __name__ == "__main__":
    main()
