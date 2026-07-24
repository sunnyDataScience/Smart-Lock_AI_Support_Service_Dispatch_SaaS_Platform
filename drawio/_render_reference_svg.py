#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the uncompressed reference-architecture Draw.io XML as flat SVG.

This is intentionally a small renderer for the shapes used by 06_參考架構.
Draw.io remains the editable source of truth; SVG is a deterministic review
artifact generated from the same cells, geometry, labels, and edge styles.
"""

from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
from html import escape


def _style_map(style: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for part in style.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            values[key] = value
        elif part:
            values[part] = "1"
    return values


def _number(value: str | None, default: float = 0) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def _clean_label(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _visual_units(text: str) -> float:
    return sum(1.0 if ord(char) > 255 else 0.56 for char in text)


def _wrap_line(line: str, max_units: float) -> list[str]:
    if not line:
        return [""]
    wrapped: list[str] = []
    remainder = line
    while _visual_units(remainder) > max_units:
        units = 0.0
        cut = 0
        last_space = -1
        for index, char in enumerate(remainder):
            units += 1.0 if ord(char) > 255 else 0.56
            if char.isspace():
                last_space = index
            if units > max_units:
                cut = index
                break
        if cut <= 0:
            cut = 1
        if last_space >= max(1, cut // 2):
            cut = last_space
        wrapped.append(remainder[:cut].rstrip())
        remainder = remainder[cut:].lstrip()
    wrapped.append(remainder)
    return wrapped


def _wrapped_lines(text: str, width: float, font_size: float) -> list[str]:
    max_units = max(5.0, (width - 14) / max(font_size, 1))
    lines: list[str] = []
    for source_line in _clean_label(text).split("\n"):
        lines.extend(_wrap_line(source_line, max_units))
    while lines and not lines[-1]:
        lines.pop()
    return lines or [""]


def _absolute_geometry(
    cell_id: str,
    cells: dict[str, ET.Element],
    cache: dict[str, tuple[float, float, float, float]],
) -> tuple[float, float, float, float]:
    if cell_id in cache:
        return cache[cell_id]
    cell = cells[cell_id]
    geometry = cell.find("mxGeometry")
    x = _number(geometry.get("x") if geometry is not None else None)
    y = _number(geometry.get("y") if geometry is not None else None)
    width = _number(geometry.get("width") if geometry is not None else None)
    height = _number(geometry.get("height") if geometry is not None else None)
    parent = cell.get("parent")
    if parent in cells and cells[parent].get("vertex") == "1":
        parent_x, parent_y, _, _ = _absolute_geometry(parent, cells, cache)
        x += parent_x
        y += parent_y
    cache[cell_id] = (x, y, width, height)
    return cache[cell_id]


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x, y, width, height = box
    return x + width / 2, y + height / 2


def _boundary(
    box: tuple[float, float, float, float],
    toward: tuple[float, float],
) -> tuple[float, float]:
    center_x, center_y = _center(box)
    delta_x = toward[0] - center_x
    delta_y = toward[1] - center_y
    if abs(delta_x) < 0.001 and abs(delta_y) < 0.001:
        return center_x, center_y
    _, _, width, height = box
    scale_x = (width / 2) / abs(delta_x) if abs(delta_x) > 0.001 else math.inf
    scale_y = (height / 2) / abs(delta_y) if abs(delta_y) > 0.001 else math.inf
    scale = min(scale_x, scale_y)
    return center_x + delta_x * scale, center_y + delta_y * scale


def _polyline_midpoint(points: list[tuple[float, float]]) -> tuple[float, float]:
    if len(points) < 2:
        return points[0] if points else (0, 0)
    lengths = [
        math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
        for i in range(len(points) - 1)
    ]
    half = sum(lengths) / 2
    travelled = 0.0
    for index, length in enumerate(lengths):
        if travelled + length >= half and length:
            ratio = (half - travelled) / length
            x1, y1 = points[index]
            x2, y2 = points[index + 1]
            return x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio
        travelled += length
    return points[-1]


def _render_text(
    label: str,
    box: tuple[float, float, float, float],
    style: dict[str, str],
    *,
    zone_header: bool = False,
) -> str:
    x, y, width, height = box
    font_size = _number(style.get("fontSize"), 10)
    bold = style.get("fontStyle") == "1" or zone_header
    align = style.get("align", "center")
    if zone_header:
        lines = [_clean_label(label)]
        anchor = "start"
        text_x = x + 12
        text_y = y + 23
    else:
        lines = _wrapped_lines(label, width, font_size)
        anchor = "start" if align == "left" else "middle"
        text_x = x + 9 if align == "left" else x + width / 2
        line_height = font_size * 1.25
        content_height = line_height * len(lines)
        if style.get("verticalAlign") == "top":
            text_y = y + font_size + 8
        else:
            text_y = y + (height - content_height) / 2 + font_size
    fill = style.get("fontColor", "#0F172A")
    weight = "600" if bold else "400"
    line_height = font_size * 1.25
    tspans = []
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else f"{line_height:.1f}"
        tspans.append(
            f'<tspan x="{text_x:.1f}" dy="{dy}">{escape(line)}</tspan>'
        )
    return (
        f'<text x="{text_x:.1f}" y="{text_y:.1f}" text-anchor="{anchor}" '
        f'font-size="{font_size:.1f}" font-weight="{weight}" fill="{fill}">'
        + "".join(tspans)
        + "</text>"
    )


def _edge_points(
    cell: ET.Element,
    boxes: dict[str, tuple[float, float, float, float]],
    style: dict[str, str],
) -> list[tuple[float, float]]:
    geometry = cell.find("mxGeometry")
    explicit: list[tuple[float, float]] = []
    if geometry is not None:
        array = geometry.find("Array[@as='points']")
        if array is not None:
            explicit = [
                (_number(point.get("x")), _number(point.get("y")))
                for point in array.findall("mxPoint")
            ]

    source_id = cell.get("source")
    target_id = cell.get("target")
    if source_id in boxes and target_id in boxes:
        source_center = _center(boxes[source_id])
        target_center = _center(boxes[target_id])
        route = explicit[:]
        if not route and "orthogonalEdgeStyle" in style:
            mid_x = (source_center[0] + target_center[0]) / 2
            route = [(mid_x, source_center[1]), (mid_x, target_center[1])]
        first_toward = route[0] if route else target_center
        last_toward = route[-1] if route else source_center
        return [
            _boundary(boxes[source_id], first_toward),
            *route,
            _boundary(boxes[target_id], last_toward),
        ]

    if geometry is not None:
        source_point = geometry.find("mxPoint[@as='sourcePoint']")
        target_point = geometry.find("mxPoint[@as='targetPoint']")
        if source_point is not None and target_point is not None:
            return [
                (_number(source_point.get("x")), _number(source_point.get("y"))),
                *explicit,
                (_number(target_point.get("x")), _number(target_point.get("y"))),
            ]
    return []


def render_drawio_to_svg(xml_text: str, output_path: str) -> None:
    """Render the first page of an uncompressed Draw.io mxfile to SVG."""
    root = ET.fromstring(xml_text)
    model = root.find("./diagram/mxGraphModel")
    if model is None:
        raise ValueError("Draw.io XML does not contain an mxGraphModel")
    page_width = _number(model.get("pageWidth"), 1700)
    page_height = _number(model.get("pageHeight"), 1200)
    graph_root = model.find("root")
    if graph_root is None:
        raise ValueError("Draw.io mxGraphModel does not contain a root")

    cells = {cell.get("id"): cell for cell in graph_root.findall("mxCell") if cell.get("id")}
    geometry_cache: dict[str, tuple[float, float, float, float]] = {}
    boxes = {
        cell_id: _absolute_geometry(cell_id, cells, geometry_cache)
        for cell_id, cell in cells.items()
        if cell.get("vertex") == "1"
    }
    vertices = [cell for cell in cells.values() if cell.get("vertex") == "1"]
    edges = [cell for cell in cells.values() if cell.get("edge") == "1"]

    palette = {
        "#2563EB": "blue",
        "#16A34A": "green",
        "#9333EA": "purple",
        "#EA580C": "orange",
        "#64748B": "gray",
    }
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_width:.0f}" '
        f'height="{page_height:.0f}" viewBox="0 0 {page_width:.0f} {page_height:.0f}">',
        "<defs>",
        '<style>text{font-family:"Noto Sans TC","Microsoft JhengHei","PingFang TC",Arial,sans-serif}'
        ".edge-label-bg{fill:#fff;fill-opacity:.94;stroke:#E2E8F0;stroke-width:.6}</style>",
    ]
    for color, marker_name in palette.items():
        svg.append(
            f'<marker id="arrow-{marker_name}" markerWidth="8" markerHeight="8" '
            'refX="7.5" refY="4" orient="auto" markerUnits="strokeWidth">'
            f'<path d="M0,0 L8,4 L0,8 z" fill="{color}"/></marker>'
        )
    svg.extend(["</defs>", '<rect width="100%" height="100%" fill="#FFFFFF"/>'])
    edge_labels: list[str] = []

    # L1 zones first so edges and L2 components remain visible above them.
    for cell in vertices:
        style = _style_map(cell.get("style", ""))
        if "swimlane" not in style:
            continue
        box = boxes[cell.get("id")]
        x, y, width, height = box
        stroke = style.get("strokeColor", "#CBD5E1")
        fill = style.get("fillColor", "#FFFFFF")
        header_fill = style.get("swimlaneFillColor", "#F8FAFC")
        header_height = _number(style.get("startSize"), 36)
        svg.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
            f'rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>'
        )
        svg.append(
            f'<path d="M{x + 8:.1f},{y:.1f} H{x + width - 8:.1f} '
            f'Q{x + width:.1f},{y:.1f} {x + width:.1f},{y + 8:.1f} '
            f'V{y + header_height:.1f} H{x:.1f} V{y + 8:.1f} '
            f'Q{x:.1f},{y:.1f} {x + 8:.1f},{y:.1f} Z" fill="{header_fill}"/>'
        )
        svg.append(
            f'<line x1="{x:.1f}" y1="{y + header_height:.1f}" '
            f'x2="{x + width:.1f}" y2="{y + header_height:.1f}" '
            f'stroke="{stroke}" stroke-width="1"/>'
        )
        svg.append(_render_text(cell.get("value", ""), box, style, zone_header=True))

    # Data paths are drawn before L2 boxes so accidental overlaps cannot hide a component.
    for cell in edges:
        style_text = cell.get("style", "")
        style = _style_map(style_text)
        points = _edge_points(cell, boxes, style_text)
        if len(points) < 2:
            continue
        stroke = style.get("strokeColor", "#64748B")
        width = _number(style.get("strokeWidth"), 1.5)
        dash = ""
        if style.get("dashed") == "1":
            dash_pattern = style.get("dashPattern", "6 4").replace(" ", ",")
            dash = f' stroke-dasharray="{dash_pattern}"'
        marker_name = palette.get(stroke, "gray")
        marker_end = f' marker-end="url(#arrow-{marker_name})"' if style.get("endArrow", "classic") != "none" else ""
        marker_start = f' marker-start="url(#arrow-{marker_name})"' if "startArrow" in style else ""
        point_text = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        svg.append(
            f'<polyline points="{point_text}" fill="none" stroke="{stroke}" '
            f'stroke-width="{width:.1f}" stroke-linecap="round" stroke-linejoin="round"'
            f'{dash}{marker_start}{marker_end}/>'
        )
        label = _clean_label(cell.get("value", ""))
        if label:
            label_x, label_y = _polyline_midpoint(points)
            font_size = _number(style.get("fontSize"), 9)
            label_lines: list[str] = []
            for source_line in label.split("\n"):
                label_lines.extend(_wrap_line(source_line, 28))
            line_height = font_size * 1.3
            label_width = max(_visual_units(line) for line in label_lines) * font_size + 12
            label_height = len(label_lines) * line_height + 6
            edge_labels.append(
                f'<rect class="edge-label-bg" x="{label_x - label_width / 2:.1f}" '
                f'y="{label_y - label_height / 2:.1f}" width="{label_width:.1f}" '
                f'height="{label_height:.1f}" rx="3"/>'
            )
            first_y = label_y - label_height / 2 + font_size + 1
            edge_labels.append(
                f'<text x="{label_x:.1f}" y="{first_y:.1f}" '
                f'text-anchor="middle" font-size="{font_size:.1f}" '
                f'fill="{style.get("fontColor", stroke)}">'
            )
            for index, line in enumerate(label_lines):
                dy = "0" if index == 0 else f"{line_height:.1f}"
                edge_labels.append(
                    f'<tspan x="{label_x:.1f}" dy="{dy}">{escape(line)}</tspan>'
                )
            edge_labels.append("</text>")

    # All non-zone vertices, including title, notes, legend, swatches and L2 cards.
    for cell in vertices:
        style = _style_map(cell.get("style", ""))
        if "swimlane" in style:
            continue
        box = boxes[cell.get("id")]
        x, y, width, height = box
        is_text = "text" in style and style.get("strokeColor") == "none"
        if not is_text:
            fill = style.get("fillColor", "#FFFFFF")
            stroke = style.get("strokeColor", "#64748B")
            dash = ' stroke-dasharray="6,4"' if style.get("dashed") == "1" else ""
            radius = 7 if style.get("rounded") == "1" else 0
            svg.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
                f'rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.3"{dash}/>'
            )
        label = cell.get("value", "")
        if label:
            svg.append(_render_text(label, box, style))

    svg.extend(edge_labels)
    svg.append("</svg>")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as output:
        output.write("\n".join(svg))


if __name__ == "__main__":
    raise SystemExit("Use drawio/_build_drawio.py so SVG stays aligned with Draw.io.")
