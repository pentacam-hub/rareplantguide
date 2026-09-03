"""Validate the rendered site's visual integrity.

This is deliberately stricter than a normal broken-link check. It prevents the visual
regressions that made the site look unfinished: empty image slots, local images that
were not copied to public/, a known-problematic legacy WebP, and the same photograph
repeated across cards in one visual grid.

Stdlib only so it runs in GitHub Actions and Cloudflare without dependencies.
"""

from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"

CARD_CLASSES = {
    "editorial-visual-card",
    "editorial-action-card",
    "problem-step-card",
    "profile-index-card",
    "hub-guide-card",
    "home-path-card",
}

GRID_CLASSES = {
    "editorial-visual-grid",
    "editorial-action-grid",
    "problem-step-grid",
    "profile-index-grid",
    "hub-card-grid",
    "home-path-grid",
    "editorial-related-grid",
    "problem-related-grid",
    "profile-link-grid",
    "hub-related-grid",
}

BANNED_RENDERED_IMAGES = {
    "/images/monstera-node-vs-axillary-bud-comparison.webp",
}


class VisualAuditParser(HTMLParser):
    def __init__(self, html_path: Path):
        super().__init__(convert_charrefs=True)
        self.html_path = html_path
        self.stack: list[dict] = []
        self.errors: list[str] = []
        self.all_images: list[str] = []
        self.page_classes: set[str] = set()

    @staticmethod
    def _classes(attrs: dict[str, str | None]) -> set[str]:
        return set((attrs.get("class") or "").split())

    def handle_starttag(self, tag: str, attrs_list):
        attrs = dict(attrs_list)
        classes = self._classes(attrs)
        self.page_classes.update(classes)

        node = {"tag": tag, "cards": [], "grids": []}
        for cls in CARD_CLASSES & classes:
            node["cards"].append({"class": cls, "images": []})
        for cls in GRID_CLASSES & classes:
            node["grids"].append({"class": cls, "images": []})

        if tag == "img":
            src = (attrs.get("src") or "").strip()
            if not src:
                self.errors.append("image tag has an empty src")
                return
            self.all_images.append(src)
            for ancestor in self.stack:
                for card in ancestor["cards"]:
                    card["images"].append(src)
                for grid in ancestor["grids"]:
                    grid["images"].append(src)
            self._check_image(src)
            return

        self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs_list):
        if tag == "img":
            self.handle_starttag(tag, attrs_list)

    def handle_endtag(self, tag: str):
        idx = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                idx = i
                break
        if idx is None:
            return
        closing = self.stack[idx:]
        self.stack = self.stack[:idx]
        for node in reversed(closing):
            for card in node["cards"]:
                if not card["images"]:
                    self.errors.append(f"{card['class']} has no image")
            for grid in node["grids"]:
                images = [self._normalized_local_src(s) for s in grid["images"]]
                images = [s for s in images if s]
                duplicates = sorted(src for src, count in Counter(images).items() if count > 1)
                if duplicates:
                    self.errors.append(
                        f"{grid['class']} repeats the same image: {', '.join(duplicates)}"
                    )

    @staticmethod
    def _normalized_local_src(src: str) -> str | None:
        parsed = urlsplit(src)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
            return None
        return parsed.path

    def _check_image(self, src: str):
        path = self._normalized_local_src(src)
        if not path:
            return
        if path in BANNED_RENDERED_IMAGES:
            self.errors.append(f"banned legacy image rendered: {path}")
            return
        asset = PUBLIC / path.lstrip("/")
        if not asset.is_file():
            self.errors.append(f"local image does not exist in public/: {path}")
            return
        if asset.stat().st_size < 1024:
            self.errors.append(f"local image is suspiciously small ({asset.stat().st_size} B): {path}")

    def finish(self):
        # A standard editorial page must have a hero plus meaningful supporting
        # photography. Three distinct local images is the floor; important pages can
        # and do exceed it. This keeps legal/utility pages sensible without allowing
        # article pages to regress to a text wall with one token cover.
        normalized = [self._normalized_local_src(s) for s in self.all_images]
        unique = {s for s in normalized if s}
        if "editorial-article" in self.page_classes and len(unique) < 3:
            self.errors.append(
                f"editorial article has only {len(unique)} distinct local images; minimum is 3"
            )
        if "problem-page" in self.page_classes and len(unique) < 3:
            self.errors.append(
                f"problem page has only {len(unique)} distinct local images; minimum is 3"
            )
        if "plant-profile-page" in self.page_classes and len(unique) < 3:
            self.errors.append(
                f"plant profile has only {len(unique)} distinct local images; minimum is 3"
            )


def main() -> None:
    if not PUBLIC.exists():
        raise RuntimeError("public/ is missing; run Hugo before visual validation")

    failures: list[str] = []
    checked = 0
    for path in sorted(PUBLIC.rglob("*.html")):
        html = path.read_text(encoding="utf-8", errors="replace")
        if len(html) < 1200:
            continue
        parser = VisualAuditParser(path)
        parser.feed(html)
        parser.close()
        parser.finish()
        checked += 1
        if parser.errors:
            rel = path.relative_to(PUBLIC)
            failures.extend(f"{rel}: {error}" for error in parser.errors)

    if failures:
        sample = "\n - ".join(failures[:80])
        more = "" if len(failures) <= 80 else f"\n ... and {len(failures) - 80} more"
        raise RuntimeError(
            f"Visual integrity validation failed ({len(failures)} issues):\n - {sample}{more}"
        )

    print(f"Visual integrity PASS: {checked} rendered pages audited; no empty cards, missing assets, banned images or in-grid duplicates.")


if __name__ == "__main__":
    main()
