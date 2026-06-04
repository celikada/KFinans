"""CHANGELOG.md ayrıştırma (Keep a Changelog formatı).

Sürüm bildirimi (release notes) maili içeriğini doğrudan proje kökündeki
CHANGELOG.md'den üretir. Saf fonksiyonlar — dosya yolu opsiyonel parametre
(test'te geçici dosya verilebilir).

Biçim:
    ## [x.y.z] - YYYY-MM-DD        (veya em-dash "—" ile)
    ...gövde...
    ## [sonraki]                   (bir sonraki "## " başlığında biter)

`[Unreleased]` gibi versiyon-olmayan başlıklar `latest_version()` tarafından
atlanır (yalnızca x.y.z benzeri semver başlıkları aday sayılır).
"""

import re
from pathlib import Path

# backend/app/services/changelog.py -> parents[2] = backend/ (CHANGELOG.md burada;
# backend Docker image build context'i backend/ olduğundan production'da da erişilir).
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "CHANGELOG.md"

# "## [0.2.0] - 2026-06-04" veya "## [0.2.0] — ..." veya "## [Unreleased]".
# Versiyon, köşeli parantez içindeki ilk token. Tarih/ayraç opsiyonel.
_HEADING_RE = re.compile(r"^##\s*\[([^\]]+)\]")
# Semver benzeri: 1, 1.2, 1.2.3 (+ ön/son ekler rc gibi). "Unreleased" eşleşmez.
_SEMVER_RE = re.compile(r"^\d+(?:\.\d+){0,2}")


def _read(path: Path | None) -> str:
    target = path or _DEFAULT_PATH
    return target.read_text(encoding="utf-8")


def _heading_version(line: str) -> str | None:
    """Bir satır '## [versiyon]' başlığı ise versiyon token'ını döndürür."""
    m = _HEADING_RE.match(line.strip())
    return m.group(1).strip() if m else None


def parse_changelog(version: str, *, path: Path | None = None) -> str | None:
    """Verilen sürümün markdown gövdesini (başlık dahil) döndürür.

    `version` köşeli parantez içindeki token ile eşleştirilir (örn. "0.2.0").
    Bulunamazsa None döner. Gövde, başlık satırından bir sonraki '## ' başlığına
    (veya dosya sonuna / '---' ayraçına) kadar olan bölümdür.
    """
    target_norm = version.strip().lstrip("vV")
    lines = _read(path).splitlines()

    start: int | None = None
    for idx, line in enumerate(lines):
        ver = _heading_version(line)
        if ver is not None and ver.lstrip("vV") == target_norm:
            start = idx
            break

    if start is None:
        return None

    body: list[str] = [lines[start]]
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        # Yatay ayraç sürüm bloklarını ayırır — gövdeye dahil etme.
        if line.strip() == "---":
            break
        body.append(line)

    # Sondaki boş satırları kırp.
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body).strip() or None


def latest_version(*, path: Path | None = None) -> str | None:
    """CHANGELOG'taki ilk semver başlığını (en üstteki yayınlanmış sürüm) döndürür.

    '[Unreleased]' gibi versiyon-olmayan başlıklar atlanır. Dosya tepeden okunduğu
    için en yeni sürüm önce gelir.
    """
    for line in _read(path).splitlines():
        ver = _heading_version(line)
        if ver is None:
            continue
        if _SEMVER_RE.match(ver.lstrip("vV")):
            return ver.strip()
    return None
