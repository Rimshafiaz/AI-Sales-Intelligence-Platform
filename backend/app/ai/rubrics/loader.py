from pathlib import Path


RUBRICS_DIRECTORY = Path(__file__).parent


def load_rubric(filename: str) -> str:
    rubric_path = RUBRICS_DIRECTORY / filename
    if not rubric_path.is_file():
        raise FileNotFoundError(f"Rubric not found: {rubric_path}")

    rubric = rubric_path.read_text(encoding="utf-8").strip()
    if not rubric:
        raise ValueError(f"Rubric cannot be blank: {filename}")

    return rubric
