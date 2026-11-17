#!/usr/bin/env python3
"""Set OME-TIFF channel names and display colours without rewriting pixels."""

import argparse
import colorsys
import csv
import re
import xml.etree.ElementTree as ET

import tifffile


NAMED_COLORS = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "white": (255, 255, 255),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "pink": (255, 192, 203),
}
PALETTE = [
    NAMED_COLORS[name] for name in ("red", "green", "yellow", "cyan", "magenta")
]


def parse_color(value):
    """Return an RGB tuple, or None for an empty CSV cell."""
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized in NAMED_COLORS:
            return NAMED_COLORS[normalized]
        if re.fullmatch(r"#?[0-9a-f]{6}", normalized):
            hex_value = normalized.lstrip("#")
            return tuple(int(hex_value[i:i + 2], 16) for i in (0, 2, 4))
    raise ValueError(
        "Invalid color {!r}; accepted forms: #RRGGBB, RRGGBB, or {}".format(
            value, ", ".join(NAMED_COLORS)
        )
    )


def channel_colors(marker_names, explicit):
    """Choose colours and encode them as OME signed 32-bit RGBA integers.

    Explicit colours may be parsed RGB tuples or CSV strings. Only channels
    without an explicit colour or a DAPI/Hoechst name advance the palette.
    """
    result = []
    palette_index = 0
    for index, name in enumerate(marker_names):
        rgb = explicit[index] if explicit and index < len(explicit) else None
        if rgb is None or isinstance(rgb, str):
            rgb = parse_color(rgb)
        if rgb is None:
            if name.strip().lower().startswith(("dapi", "hoechst")):
                rgb = NAMED_COLORS["blue"]
            else:
                if palette_index < len(PALETTE):
                    rgb = PALETTE[palette_index]
                else:
                    hue = (((palette_index - len(PALETTE)) * 60 + 30) % 360) / 360.0
                    rgb = tuple(
                        int(round(component * 255))
                        for component in colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                    )
                palette_index += 1
        r, g, b = rgb
        rgba = (r << 24) | (g << 16) | (b << 8) | 255
        result.append(rgba - (1 << 32) if rgba >= (1 << 31) else rgba)
    return result


def read_markers(path):
    """Read names and optional color/colour cells, retaining removed channels.

    Keep one entry per CSV row, using a generated name for an unnamed row so
    subsequent colours cannot shift onto the wrong channel.
    """
    names, colors = [], []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("marker_name") or row.get("marker") or row.get("name")
                    or row.get("channel_name") or "Channel_{}".format(len(names)))
            parsed = [parse_color(row.get(key)) for key in ("color", "colour")]
            names.append(name)
            colors.append(next((color for color in parsed if color is not None), None))
    return names, colors


def label_channels(path, marker_names, colors, sample_name=None):
    """Update OME-XML only; metadata failures must not discard written pixels.

    On a channel-count mismatch, retain the file's names and derive default
    colours from those names, ignoring all CSV names and explicit colours.
    Return the channel count on success, or None after reporting a failure.
    """
    try:
        root = ET.fromstring(tifffile.tiffcomment(str(path)))
        namespace = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
        if namespace:
            ET.register_namespace("", namespace[1:-1])
        count = 0
        for image in root.findall(namespace + "Image"):
            if sample_name:
                image.set("Name", sample_name)
            pixels = image.find(namespace + "Pixels")
            channels = pixels.findall(namespace + "Channel") if pixels is not None else []
            if len(channels) != len(marker_names):
                print(
                    "Warning: OME-TIFF has {} channels but markers.csv has {} entries; "
                    "keeping existing names and using default colours.".format(
                        len(channels), len(marker_names)
                    )
                )
                names = [channel.get("Name", "") for channel in channels]
                selected_colors = channel_colors(names, [])
            else:
                names = marker_names
                selected_colors = channel_colors(names, colors)
                for channel, name in zip(channels, names):
                    channel.set("Name", str(name))
            for channel, color in zip(channels, selected_colors):
                channel.set("Color", str(color))
            count += len(channels)
        # OME-XML may contain µm; tifffile requires bytes for non-ASCII comments.
        tifffile.tiffcomment(
            str(path), ET.tostring(root, encoding="utf-8", xml_declaration=True)
        )
        print("Channel metadata: {} channels named and coloured".format(count))
        return count
    except Exception as error:  # The pixels have already been written.
        print("Warning: could not label channels: {}".format(error))
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="OME-TIFF to label in place.")
    parser.add_argument("--markers", required=True, help="CSV matching the image channels.")
    parser.add_argument("--sample-name", help="Optional OME Image name.")
    args = parser.parse_args()
    names, colors = read_markers(args.markers)
    return 0 if label_channels(args.image, names, colors, args.sample_name) is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
