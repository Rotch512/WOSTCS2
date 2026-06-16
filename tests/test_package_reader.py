from pathlib import Path
import zipfile

from cs2demo_analyse.package_reader import detect_package_kind, extract_single_demo
from cs2demo_analyse.pipeline import map_name_from_demo_filename


def test_extract_single_demo_from_zip(tmp_path: Path):
    package = tmp_path / "demo.zip"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("some_demo.dem", b"PBDEMS2 demo")

    assert detect_package_kind(package) == "zip"
    out = extract_single_demo(package, tmp_path / "out")

    assert out.name == "some_demo.dem"
    assert out.read_bytes() == b"PBDEMS2 demo"


def test_map_name_from_demo_filename():
    assert map_name_from_demo_filename(Path("g151-n-20260616223210794030793_de_nuke.dem")) == "nuke"
    assert map_name_from_demo_filename(Path("9206098562963747980_0.dem")) is None
