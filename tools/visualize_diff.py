#!/usr/bin/env python3
"""Generate SVG visualizations of zoom/pan changes between snapshot clips.

No external dependencies — pure Python, outputs SVG strings.
"""

import json
import os


def load_snapshot(path):
    with open(path) as f:
        return json.load(f)


def get_video_clips(snap, timeline_name):
    for tl in snap["timelines"]:
        if tl["name"] == timeline_name:
            return [c for c in tl["clips"] if c.get("track_type") == "video"]
    return []


def compute_viewport(zoom_x, zoom_y, pan, tilt, fw=1920, fh=1080):
    """Visible viewport rect in source-pixel coords."""
    vw = fw / zoom_x
    vh = fh / zoom_y
    cx = fw / 2 + pan
    cy = fh / 2 + tilt
    return cx - vw / 2, cy - vh / 2, vw, vh


def clip_svg(clip_name, before, after, fw=1920, fh=1080):
    """Return an SVG string for one clip's before/after viewport comparison."""
    # Scale everything into a 400x250 viewBox with some padding
    pad = 20
    vb_w, vb_h = 400, 260
    scale = min((vb_w - 2 * pad) / fw, (vb_h - 50 - 2 * pad) / fh)
    ox = (vb_w - fw * scale) / 2
    oy = 40 + (vb_h - 40 - fh * scale) / 2

    def tx(x):
        return ox + x * scale

    def ty(y):
        return oy + y * scale

    def tw(w):
        return w * scale

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb_w} {vb_h}"'
                 f' width="{vb_w}" height="{vb_h}" style="background:#111119;border-radius:8px">')

    # Title
    lines.append(f'  <text x="{vb_w/2}" y="24" text-anchor="middle"'
                 f' fill="#e0e0e0" font-family="sans-serif" font-size="13" font-weight="bold">'
                 f'{clip_name}</text>')

    # Source frame
    lines.append(f'  <rect x="{tx(0):.1f}" y="{ty(0):.1f}"'
                 f' width="{tw(fw):.1f}" height="{tw(fh):.1f}"'
                 f' fill="#1a1a2e" stroke="#444" stroke-width="1"/>')
    lines.append(f'  <text x="{tx(fw/2):.1f}" y="{ty(fh/2)+4:.1f}" text-anchor="middle"'
                 f' fill="#333" font-family="sans-serif" font-size="9">{fw}x{fh}</text>')

    # Before viewport
    bx, by, bw, bh = compute_viewport(
        before.get("ZoomX", 1), before.get("ZoomY", 1),
        before.get("Pan", 0), before.get("Tilt", 0), fw, fh)
    lines.append(f'  <rect x="{tx(bx):.1f}" y="{ty(by):.1f}"'
                 f' width="{tw(bw):.1f}" height="{tw(bh):.1f}"'
                 f' fill="rgba(79,195,247,0.08)" stroke="#4fc3f7" stroke-width="2"'
                 f' stroke-dasharray="6 3"/>')

    # After viewport
    ax, ay, aw, ah = compute_viewport(
        after.get("ZoomX", 1), after.get("ZoomY", 1),
        after.get("Pan", 0), after.get("Tilt", 0), fw, fh)
    lines.append(f'  <rect x="{tx(ax):.1f}" y="{ty(ay):.1f}"'
                 f' width="{tw(aw):.1f}" height="{tw(ah):.1f}"'
                 f' fill="rgba(255,112,67,0.10)" stroke="#ff7043" stroke-width="2"/>')

    # Center crosshairs
    bcx, bcy = tx(bx + bw / 2), ty(by + bh / 2)
    acx, acy = tx(ax + aw / 2), ty(ay + ah / 2)
    cs = 6  # crosshair size
    lines.append(f'  <line x1="{bcx-cs}" y1="{bcy}" x2="{bcx+cs}" y2="{bcy}" stroke="#4fc3f7" stroke-width="1.5"/>')
    lines.append(f'  <line x1="{bcx}" y1="{bcy-cs}" x2="{bcx}" y2="{bcy+cs}" stroke="#4fc3f7" stroke-width="1.5"/>')
    lines.append(f'  <line x1="{acx-cs}" y1="{acy}" x2="{acx+cs}" y2="{acy}" stroke="#ff7043" stroke-width="1.5"/>')
    lines.append(f'  <line x1="{acx}" y1="{acy-cs}" x2="{acx}" y2="{acy+cs}" stroke="#ff7043" stroke-width="1.5"/>')

    # Arrow from before center to after center
    if abs(acx - bcx) > 1 or abs(acy - bcy) > 1:
        lines.append(f'  <defs><marker id="ah" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">'
                     f'<path d="M0,0 L8,3 L0,6" fill="#ffee58"/></marker></defs>')
        lines.append(f'  <line x1="{bcx:.1f}" y1="{bcy:.1f}" x2="{acx:.1f}" y2="{acy:.1f}"'
                     f' stroke="#ffee58" stroke-width="1.5" marker-end="url(#ah)"/>')

    # Change annotations
    annotations = []
    zxb, zxa = before.get("ZoomX", 1), after.get("ZoomX", 1)
    zyb, zya = before.get("ZoomY", 1), after.get("ZoomY", 1)
    pb, pa = before.get("Pan", 0), after.get("Pan", 0)
    tb, ta = before.get("Tilt", 0), after.get("Tilt", 0)
    if zxb != zxa or zyb != zya:
        annotations.append(f"Zoom: {zxb}x → {zxa}x")
    if pb != pa:
        annotations.append(f"Pan: {pb} → {pa}")
    if tb != ta:
        annotations.append(f"Tilt: {tb} → {ta}")

    for i, text in enumerate(annotations):
        lines.append(f'  <text x="{vb_w - 8}" y="{vb_h - 8 - (len(annotations)-1-i)*14:.0f}"'
                     f' text-anchor="end" fill="#aaa" font-family="sans-serif" font-size="10"'
                     f' font-style="italic">{text}</text>')

    # Legend
    ly = vb_h - 8 - len(annotations) * 14 - 10
    lines.append(f'  <rect x="8" y="{ly}" width="10" height="3" fill="#4fc3f7"/>')
    lines.append(f'  <text x="22" y="{ly+3}" fill="#4fc3f7" font-family="sans-serif" font-size="9">Before</text>')
    lines.append(f'  <rect x="8" y="{ly+10}" width="10" height="3" fill="#ff7043"/>')
    lines.append(f'  <text x="22" y="{ly+13}" fill="#ff7043" font-family="sans-serif" font-size="9">After</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def diff_svg(snap1, snap2, timeline_name):
    """Return a combined SVG for all clips with zoom/pan changes."""
    clips_before = {c["name"]: c for c in get_video_clips(snap1, timeline_name)}
    clips_after = {c["name"]: c for c in get_video_clips(snap2, timeline_name)}

    changed = []
    for name in clips_before:
        if name not in clips_after:
            continue
        b, a = clips_before[name], clips_after[name]
        for prop in ["ZoomX", "ZoomY", "Pan", "Tilt"]:
            if b.get(prop) != a.get(prop):
                changed.append(name)
                break

    if not changed:
        return "<p>No zoom/pan changes found.</p>"

    card_w, card_h = 400, 260
    gap = 16
    total_w = len(changed) * card_w + (len(changed) - 1) * gap + 40
    total_h = card_h + 70

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}"'
                 f' width="{total_w}" height="{total_h}" style="background:#0d0d1a;border-radius:10px">')

    # Title
    title = f"Zoom &amp; Pan Changes: {snap1['snapshot_name']} vs {snap2['snapshot_name']}"
    parts.append(f'  <text x="{total_w/2}" y="28" text-anchor="middle"'
                 f' fill="#e0e0e0" font-family="sans-serif" font-size="15" font-weight="bold">{title}</text>')

    for i, name in enumerate(changed):
        x_off = 20 + i * (card_w + gap)
        svg_inner = clip_svg(name, clips_before[name], clips_after[name])
        parts.append(f'  <g transform="translate({x_off}, 44)">')
        # Strip the outer <svg> wrapper and embed the content
        for line in svg_inner.split("\n"):
            if line.strip().startswith("<svg") or line.strip().startswith("</svg"):
                continue
            parts.append(f"    {line}")
        # Background card
        parts.insert(-len(svg_inner.split("\n")) + 2,
                     f'    <rect width="{card_w}" height="{card_h}" rx="8"'
                     f' fill="#111119" stroke="#282838" stroke-width="1"/>')
        parts.append("  </g>")

    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    snap_dir = os.path.expanduser("~/.resolve-snapshots/SampleProject")
    snap1 = load_snapshot(os.path.join(snap_dir, "BeforeEdit_20260319.json"))
    snap2 = load_snapshot(os.path.join(snap_dir, "AfterEdit_20260320.json"))
    print(diff_svg(snap1, snap2, "Main Edit"))
