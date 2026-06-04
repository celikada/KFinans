"""CHANGELOG ayrıştırma (changelog.py) birim testleri."""

from pathlib import Path

from app.services import changelog

_SAMPLE = """# Changelog

Açıklama satırı.

---

## [0.2.0] - 2026-06-04

### Eklenenler

- Birinci özellik
- **Kalın** ikinci özellik

### Güvenlik

- Güvenlik notu

---

## [0.1.0] — 2026-05-06

### Added

- Eski sürüm özelliği
"""


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "CHANGELOG.md"
    p.write_text(_SAMPLE, encoding="utf-8")
    return p


def test_parse_existing_version(tmp_path):
    p = _write(tmp_path)
    body = changelog.parse_changelog("0.2.0", path=p)
    assert body is not None
    assert body.startswith("## [0.2.0]")
    assert "Birinci özellik" in body
    assert "Güvenlik notu" in body
    # Bir sonraki sürüm bloğu sızmamalı
    assert "0.1.0" not in body
    assert "Eski sürüm özelliği" not in body


def test_parse_em_dash_heading(tmp_path):
    """Başlık em-dash (—) ile de eşleşmeli."""
    p = _write(tmp_path)
    body = changelog.parse_changelog("0.1.0", path=p)
    assert body is not None
    assert "Eski sürüm özelliği" in body


def test_parse_with_v_prefix(tmp_path):
    p = _write(tmp_path)
    assert changelog.parse_changelog("v0.2.0", path=p) is not None


def test_parse_unknown_version_returns_none(tmp_path):
    p = _write(tmp_path)
    assert changelog.parse_changelog("9.9.9", path=p) is None


def test_latest_version_skips_unreleased(tmp_path):
    content = "# Changelog\n\n## [Unreleased]\n\n- wip\n\n## [0.2.0] - 2026-06-04\n\n- ok\n"
    p = tmp_path / "CHANGELOG.md"
    p.write_text(content, encoding="utf-8")
    assert changelog.latest_version(path=p) == "0.2.0"


def test_default_path_real_changelog():
    """Gerçek proje CHANGELOG.md'sinden 0.2.0 ayrıştırılabilmeli."""
    body = changelog.parse_changelog("0.2.0")
    assert body is not None
    assert "Sürüm bildirimleri" in body
    assert changelog.latest_version() is not None
