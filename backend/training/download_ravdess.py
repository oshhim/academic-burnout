"""Download the original public speech corpus, verify it, extract WAV only."""
import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

URL = "https://zenodo.org/records/1188976/files/Audio_Speech_Actors_01-24.zip?download=1"
MD5 = "bc696df654c87fed845eb13823edef8a"
CITATION = "Livingstone SR, Russo FA (2018). RAVDESS. PLoS ONE 13(5): e0196391. https://doi.org/10.1371/journal.pone.0196391"


def main():
    parser = argparse.ArgumentParser(description="Download RAVDESS original speech only (~209 MB); noncommercial research/education.")
    parser.add_argument("--output", type=Path, default=Path("data/public/ravdess"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / "Audio_Speech_Actors_01-24.zip"
    if not archive.exists():
        partial = archive.with_suffix(".zip.partial")
        try:
            request = urllib.request.Request(URL, headers={"User-Agent": "EMPath-academic-baseline/0.2"})
            with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as out:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 260 * 1024 * 1024:
                        raise RuntimeError("Unexpected archive size")
                    out.write(chunk)
                    if total // (20 * 1024 * 1024) != (total - len(chunk)) // (20 * 1024 * 1024):
                        print(f"Downloaded {total // (1024 * 1024)} MiB", flush=True)
            partial.replace(archive)
        finally:
            partial.unlink(missing_ok=True)
    digest = hashlib.md5(usedforsecurity=False)
    with archive.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != MD5:
        raise RuntimeError("Archive does not match the publisher's MD5. Remove it and download the original speech archive again.")
    count = 0
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            path = Path(item.filename)
            if path.suffix.lower() != ".wav" or path.name.startswith(".") or "__MACOSX" in path.parts:
                continue
            # Flatten by actor/name rather than trusting arbitrary archive paths.
            actor = path.stem.split("-")[-1]
            if not actor.isdigit() or not 1 <= int(actor) <= 24 or item.file_size > 4 * 1024 * 1024:
                raise RuntimeError("Unexpected WAV entry in official archive")
            destination = args.output / f"Actor_{actor}" / path.name
            destination.parent.mkdir(exist_ok=True)
            with z.open(item) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    if count != 1440:
        raise RuntimeError(f"Expected 1440 speech recordings, found {count}")
    (args.output / "PROVENANCE.json").write_text(json.dumps({"dataset": "RAVDESS audio speech", "url": URL, "archive_md5": MD5, "wav_count": count, "actors": 24, "license": "CC-BY-NC-SA-4.0", "citation": CITATION}, indent=2), encoding="utf-8")
    print(f"Verified and extracted {count} public speech recordings to {args.output}")


if __name__ == "__main__":
    main()
