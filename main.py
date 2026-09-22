from pathlib import Path
import argparse
import json
import logging
import yaml

from corrector.docx_reader import extract_sentences
from corrector.pipeline import CorrectionPipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--test",
        type=int,
        default=0,
        metavar="N",
        help="Обработать только первые N чанков"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    if not args.input.exists():
        raise SystemExit(f"File not found: {args.input}")

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    sentences = extract_sentences(args.input)

    work_dir = Path(".book_corrector") / args.input.stem
    work_dir.mkdir(parents=True, exist_ok=True)

    (work_dir / "sentences.json").write_text(
        json.dumps([s.model_dump() for s in sentences], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    pipeline = CorrectionPipeline(
        input_path=args.input,
        sentences=sentences,
        work_dir=work_dir,
        config=config,
        resume=args.resume or config["processing"].get("resume", True),
        test_chunks=args.test,
    )
    pipeline.run()


if __name__ == "__main__":
    main()
