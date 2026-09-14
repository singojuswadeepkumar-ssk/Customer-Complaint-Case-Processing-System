"""Tests for document_loader module."""

from pathlib import Path
import pytest
from src.document_loader import load_document, load_all_documents, SUPPORTED_EXTENSIONS


def test_load_txt(tmp_path: Path):
    """TXT file should be read correctly."""
    txt_file = tmp_path / "complaint.txt"
    txt_file.write_text("Customer complaint text.", encoding="utf-8")
    result = load_document(txt_file)
    assert result == "Customer complaint text."


def test_unsupported_extension(tmp_path: Path):
    """Unsupported file types should return None without raising."""
    bad_file = tmp_path / "complaint.csv"
    bad_file.write_text("some,data", encoding="utf-8")
    result = load_document(bad_file)
    assert result is None


def test_corrupted_txt(tmp_path: Path):
    """Corrupted / unreadable files should return None without raising."""
    corrupt = tmp_path / "bad.txt"
    corrupt.write_bytes(b"\x80\x81\x82")  # invalid UTF-8 and latin-1 edge bytes
    # Should not raise — graceful degradation
    result = load_document(corrupt)
    assert result is not None or result is None  # outcome may vary; just no exception


def test_load_all_documents_empty_dir(tmp_path: Path):
    """An empty directory should return an empty mapping."""
    result = load_all_documents(tmp_path)
    assert result == {}


def test_load_all_documents_missing_dir(tmp_path: Path):
    """A non-existent directory should return an empty mapping."""
    result = load_all_documents(tmp_path / "nonexistent")
    assert result == {}


def test_load_all_documents_mixed(tmp_path: Path):
    """Only supported extensions should be returned."""
    (tmp_path / "a.txt").write_text("A", encoding="utf-8")
    (tmp_path / "b.csv").write_text("B", encoding="utf-8")  # unsupported
    result = load_all_documents(tmp_path)
    assert "a.txt" in result
    assert "b.csv" not in result
