"""Channel display metadata tests; no registration containers are required."""

import csv
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import tifffile


SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "label_channels.py"
sys.path.insert(0, str(SCRIPT.parent))
from label_channels import channel_colors, label_channels, parse_color, read_markers


@pytest.mark.parametrize("value, expected", [
    (None, None),
    ("", None),
    (" \t ", None),
    ("#12AbEF", (18, 171, 239)),
    ("12abef", (18, 171, 239)),
    ("  #FFFFFF \t", (255, 255, 255)),
    ("000000", (0, 0, 0)),
    (" RED ", (255, 0, 0)),
    ("Green", (0, 255, 0)),
    ("bLuE", (0, 0, 255)),
    ("yellow", (255, 255, 0)),
    ("cyan", (0, 255, 255)),
    ("magenta", (255, 0, 255)),
    ("white", (255, 255, 255)),
    ("gray", (128, 128, 128)),
    ("grey", (128, 128, 128)),
    ("orange", (255, 165, 0)),
    ("purple", (128, 0, 128)),
    ("pink", (255, 192, 203)),
])
def test_parse_color(value, expected):
    assert parse_color(value) == expected


@pytest.mark.parametrize("value", [
    "blu", "#FFF", "#12345678", "12345G", "0xff0000", "##123456", "rgb(1,2,3)", 123,
])
def test_parse_color_rejects_bad_values(value):
    with pytest.raises(ValueError) as exc:
        parse_color(value)
    assert str(value) in str(exc.value)


def unpack_color(value):
    return tuple((value >> shift) & 255 for shift in (24, 16, 8))


def test_default_colors_reserve_blue_for_nuclear_stains():
    names = ["CD3", "DAPI1", "CD20", "hoechst", "Ki67", "CD4", "CD8", "PanCK"]
    colors = channel_colors(names, [None] * len(names))
    assert colors[:7] == [-16776961, 65535, 16711935, 65535, -65281, 16777215, -16711681]
    assert unpack_color(colors[7]) == (255, 128, 0)  # First hue after the fixed palette.
    palette = channel_colors(["marker"] * 20, [])
    assert (0, 0, 255) not in [unpack_color(value) for value in palette]
    assert [unpack_color(value) for value in palette[5:11]] == [
        (255, 128, 0), (128, 255, 0), (0, 255, 128),
        (0, 128, 255), (128, 0, 255), (255, 0, 128),
    ]
    assert all(-(2 ** 31) <= value < 2 ** 31 and value & 255 == 255 for value in palette)


def test_explicit_colors_override_defaults_without_advancing_palette():
    colors = channel_colors(
        ["DAPI1", "CD3", "HoEcHsT33342", "CD20", "CD4", "DAPI2"],
        [parse_color("white"), None, "orange", "#123456", None, None],
    )
    assert [unpack_color(value) for value in colors] == [
        (255, 255, 255), (255, 0, 0), (255, 165, 0),
        (18, 52, 86), (0, 255, 0), (0, 0, 255),
    ]
    assert colors[0] == -1


@pytest.mark.parametrize("name_column", ["marker_name", "marker", "name", "channel_name"])
@pytest.mark.parametrize("color_column", ["color", "colour"])
def test_read_markers_keeps_removed_rows(tmp_path, name_column, color_column):
    markers = tmp_path / "markers.csv"
    markers.write_text(
        "{},remove,{}\nDAPI1,TRUE,blue\nCD3,FALSE,\n".format(name_column, color_column),
        encoding="utf-8",
    )
    assert read_markers(markers) == (["DAPI1", "CD3"], [(0, 0, 255), None])


def test_read_markers_without_colors_preserves_row_alignment(tmp_path):
    markers = tmp_path / "markers.csv"
    markers.write_text("marker_name\nDAPI1\n\"\"\nCD3\n", encoding="utf-8")
    assert read_markers(markers) == (["DAPI1", "Channel_1", "CD3"], [None, None, None])


def write_image(path):
    data = np.arange(3 * 8 * 9, dtype=np.uint16).reshape(3, 8, 9)
    tifffile.imwrite(
        path, data, ome=True, photometric="minisblack",
        metadata={
            "axes": "CYX",
            "Channel": {"Name": ["DAPI original", "old 2", "old 3"]},
            "PhysicalSizeX": 0.5,
            "PhysicalSizeXUnit": "µm",
        },
    )
    return data


def image_metadata(path):
    root = ET.fromstring(tifffile.tiffcomment(path))
    ns = {"ome": "http://www.openmicroscopy.org/Schemas/OME/2016-06"}
    image = root.find("ome:Image", ns)
    pixels = image.find("ome:Pixels", ns)
    return image, pixels, pixels.findall("ome:Channel", ns)


@pytest.mark.parametrize("color_column", ["color", "colour"])
def test_cli_round_trip(tmp_path, color_column):
    image_path = tmp_path / "sample.ome.tif"
    data = write_image(image_path)
    with tifffile.TiffFile(image_path) as image:
        pixel_locations = [(page.dataoffsets, page.databytecounts) for page in image.pages]
    markers = tmp_path / "markers.csv"
    names = ["DAPI1", "CD3, µ marker", "CD20"]
    with markers.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["marker_name", color_column])
        writer.writerows(zip(names, ["", " #12AbEF ", ""]))

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--image", str(image_path),
         "--markers", str(markers), "--sample-name", "Sample µ"],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "Channel metadata: 3 channels named and coloured"
    assert result.stderr == ""
    image, pixels, channels = image_metadata(image_path)
    assert image.get("Name") == "Sample µ"
    assert pixels.get("PhysicalSizeXUnit") == "µm"
    assert [channel.get("Name") for channel in channels] == names
    assert [int(channel.get("Color")) for channel in channels] == [
        65535, 313257983, -16776961,
    ]
    with tifffile.TiffFile(image_path) as image:
        assert [(page.dataoffsets, page.databytecounts) for page in image.pages] == pixel_locations
        np.testing.assert_array_equal(image.asarray(), data)


@pytest.mark.parametrize("count", [2, 4])
def test_channel_count_mismatch_preserves_names_and_uses_defaults(tmp_path, capsys, count):
    image_path = tmp_path / "sample.ome.tif"
    data = write_image(image_path)
    assert label_channels(image_path, ["wrong"] * count, ["white"] * count) == 3
    assert "Warning:" in capsys.readouterr().out
    _, _, channels = image_metadata(image_path)
    assert [channel.get("Name") for channel in channels] == ["DAPI original", "old 2", "old 3"]
    assert [int(channel.get("Color")) for channel in channels] == [65535, -16776961, 16711935]
    np.testing.assert_array_equal(tifffile.imread(image_path), data)


def test_metadata_failure_warns_without_raising(tmp_path, capsys):
    invalid = tmp_path / "not-a-tiff"
    invalid.write_bytes(b"preserve this file")
    assert label_channels(invalid, ["DAPI1"], [None]) is None
    assert "Warning: could not label channels:" in capsys.readouterr().out
    assert invalid.read_bytes() == b"preserve this file"
