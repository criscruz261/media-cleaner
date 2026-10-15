from types import SimpleNamespace
from app.retention.recommend import recommendation
from app.core.filesystem import protection


def file(name, protected=None):
    return SimpleNamespace(id=name, name=name, protected_reason=protected)


def test_original_filename_and_manual_ambiguity():
    assert recommendation([file("IMG_0971 copy.MOV"), file("IMG_0971.MOV")])[0] == "IMG_0971.MOV"
    assert recommendation([file("IMG_0971 (1).MOV"), file("IMG_0971.MOV")])[0] == "IMG_0971.MOV"
    assert recommendation([file("a.png"), file("b.png")])[0] is None
    assert recommendation([file("RAW.dng", "RAW original"), file("copy.dng")])[0] == "RAW.dng"


def test_raw_and_possible_live_photo_companions(workspace):
    (workspace / "IMG_1234.HEIC").write_bytes(b"photo")
    (workspace / "IMG_1234.MOV").write_bytes(b"video")
    assert "companion" in protection(workspace / "IMG_1234.HEIC", [])
    assert "companion" in protection(workspace / "IMG_1234.MOV", [])
    assert "RAW" in protection(workspace / "original.dng", [])
