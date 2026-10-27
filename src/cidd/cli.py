import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cidd",
        description="Contract Isolated Driven Development",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="CIDD 0.1.0",
    )

    parser.parse_args()


if __name__ == "__main__":
    main()