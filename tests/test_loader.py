from pathlib import Path

import pytest

import app.resume.loader as loader


# ============================================================
# HELPERS
# ============================================================

class FakePage:
    """
    Minimal fake PDF page used for testing extraction logic.
    """

    def __init__(self, text=""):
        self.text = text

    def get_text(self, mode):
        return self.text


# ============================================================
# NORMAL TEXT EXTRACTION
# ============================================================

def test_extract_text_from_page_uses_pdf_text():

    page = FakePage(
        "GARNEPUDI NAVEEN SAI\nElectrical Engineer"
    )

    result = loader.extract_text_from_page(page)

    assert result == (
        "GARNEPUDI NAVEEN SAI\nElectrical Engineer"
    )


# ============================================================
# EMPTY PAGE
# ============================================================

def test_extract_text_from_page_handles_empty_text(monkeypatch):

    class FakePixmap:
        samples = bytes([0, 0, 0])
        height = 1
        width = 1
        n = 3

    class FakeOCR:

        def __call__(self, image):
            return [], None

    class FakePage:

        def get_text(self, mode):
            return ""

        def get_pixmap(self, matrix, alpha=False):
            return FakePixmap()

    monkeypatch.setattr(
        loader,
        "get_ocr_engine",
        lambda: FakeOCR(),
    )

    result = loader.extract_text_from_page(
        FakePage()
    )

    assert result == ""


# ============================================================
# OCR EXTRACTION
# ============================================================

def test_extract_text_from_page_uses_ocr(monkeypatch):

    class FakePixmap:

        samples = bytes([
            255, 255, 255,
            255, 255, 255,
            255, 255, 255,
        ])

        height = 1
        width = 3
        n = 3

    class FakeOCR:

        def __call__(self, image):

            return [
                [
                    [[0, 0], [1, 0], [1, 1], [0, 1]],
                    "GARNEPUDI NAVEEN SAI",
                    0.99,
                ],
                [
                    [[0, 0], [1, 0], [1, 1], [0, 1]],
                    "Electrical Engineering",
                    0.98,
                ],
            ], None

    class FakePage:

        def get_text(self, mode):
            return ""

        def get_pixmap(self, matrix, alpha=False):
            return FakePixmap()

    monkeypatch.setattr(
        loader,
        "get_ocr_engine",
        lambda: FakeOCR(),
    )

    result = loader.extract_text_from_page(
        FakePage()
    )

    assert "GARNEPUDI NAVEEN SAI" in result
    assert "Electrical Engineering" in result


# ============================================================
# OCR RESULT WITH EMPTY TEXT
# ============================================================

def test_ocr_ignores_empty_recognized_text(monkeypatch):

    class FakePixmap:

        samples = bytes([
            255, 255, 255,
            255, 255, 255,
            255, 255, 255,
        ])

        height = 1
        width = 3
        n = 3

    class FakeOCR:

        def __call__(self, image):

            return [
                [
                    [[0, 0], [1, 0], [1, 1], [0, 1]],
                    "",
                    0.99,
                ],
                [
                    [[0, 0], [1, 0], [1, 1], [0, 1]],
                    "Python",
                    0.98,
                ],
            ], None

    class FakePage:

        def get_text(self, mode):
            return ""

        def get_pixmap(self, matrix, alpha=False):
            return FakePixmap()

    monkeypatch.setattr(
        loader,
        "get_ocr_engine",
        lambda: FakeOCR(),
    )

    result = loader.extract_text_from_page(
        FakePage()
    )

    assert result == "Python"


# ============================================================
# FILE NOT FOUND
# ============================================================

def test_load_resume_missing_file():

    with pytest.raises(FileNotFoundError):

        loader.load_resume(
            "does_not_exist.pdf"
        )


# ============================================================
# NON-PDF FILE
# ============================================================

def test_load_resume_rejects_non_pdf(tmp_path):

    file_path = tmp_path / "resume.txt"

    file_path.write_text(
        "Test resume",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):

        loader.load_resume(
            str(file_path)
        )


# ============================================================
# LAZY OCR ENGINE
# ============================================================

def test_ocr_engine_is_lazy(monkeypatch):

    calls = []

    class FakeRapidOCR:

        def __init__(self):
            calls.append("created")

    monkeypatch.setattr(
        loader,
        "RapidOCR",
        FakeRapidOCR,
    )

    monkeypatch.setattr(
        loader,
        "ocr_engine",
        None,
    )

    engine = loader.get_ocr_engine()

    assert engine is not None
    assert calls == ["created"]

    # Second call should reuse the same engine.

    second_engine = loader.get_ocr_engine()

    assert second_engine is engine
    assert calls == ["created"]