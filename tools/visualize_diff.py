#!/usr/bin/env python3
"""Visualize zoom and pan changes between two snapshot clips."""

import json
import os
import sys

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
except ImportError:
    print("pip install matplotlib")
    sys.exit(1)


def load_snapshot(path):
    with open(path) as f:
        return json.load(f)


def get_video_clips(snap, timeline_name):
    for tl in snap["timelines"]:
        if tl["name"] == timeline_name:
            return [c for c in tl["clips"] if c.get("track_type") == "video"]
    return []


def compute_viewport(zoom_x, zoom_y, pan, tilt, frame_w=1920, frame_h=1080):
    """Return (x, y, w, h) of the visible viewport in source-pixel coords."""
    vw = frame_w / zoom_x
    vh = frame_h / zoom_y
    cx = frame_w / 2 + pan
    cy = frame_h / 2 + tilt
    return cx - vw / 2, cy - vh / 2, vw, vh


def draw_clip_comparison(ax, clip_name, before, after, frame_w=1920, frame_h=1080):
    """Draw a single clip's before/after viewport on one axes."""
    ax.set_xlim(-100, frame_w + 100)
    ax.set_ylim(frame_h + 100, -100)  # y-down like video
    ax.set_aspect("equal")
    ax.set_title(clip_name, fontsize=11, fontweight="bold", pad=10)

    # Full source frame
    frame = patches.Rectangle(
        (0, 0), frame_w, frame_h,
        linewidth=1.5, edgecolor="#555", facecolor="#1a1a2e", linestyle="-"
    )
    ax.add_patch(frame)
    ax.text(frame_w / 2, frame_h / 2, f"{frame_w}x{frame_h}",
            ha="center", va="center", color="#444", fontsize=9)

    # Before viewport
    bx, by, bw, bh = compute_viewport(
        before.get("ZoomX", 1), before.get("ZoomY", 1),
        before.get("Pan", 0), before.get("Tilt", 0),
        frame_w, frame_h
    )
    before_rect = patches.Rectangle(
        (bx, by), bw, bh,
        linewidth=2.5, edgecolor="#4fc3f7", facecolor="#4fc3f722",
        linestyle="--", label="Before"
    )
    ax.add_patch(before_rect)

    # After viewport
    ax2, ay, aw, ah = compute_viewport(
        after.get("ZoomX", 1), after.get("ZoomY", 1),
        after.get("Pan", 0), after.get("Tilt", 0),
        frame_w, frame_h
    )
    after_rect = patches.Rectangle(
        (ax2, ay), aw, ah,
        linewidth=2.5, edgecolor="#ff7043", facecolor="#ff704322",
        linestyle="-", label="After"
    )
    ax.add_patch(after_rect)

    # Center crosshairs
    bcx, bcy = bx + bw / 2, by + bh / 2
    acx, acy = ax2 + aw / 2, ay + ah / 2
    ax.plot(bcx, bcy, "+", color="#4fc3f7", markersize=12, markeredgewidth=2)
    ax.plot(acx, acy, "+", color="#ff7043", markersize=12, markeredgewidth=2)

    # Arrow showing pan/tilt shift
    if abs(acx - bcx) > 0.5 or abs(acy - bcy) > 0.5:
        ax.annotate("", xy=(acx, acy), xytext=(bcx, bcy),
                     arrowprops=dict(arrowstyle="->", color="#ffee58",
                                     lw=2, connectionstyle="arc3,rad=0.1"))

    # Annotation text
    lines = []
    zx_b, zx_a = before.get("ZoomX", 1), after.get("ZoomX", 1)
    zy_b, zy_a = before.get("ZoomY", 1), after.get("ZoomY", 1)
    p_b, p_a = before.get("Pan", 0), after.get("Pan", 0)
    t_b, t_a = before.get("Tilt", 0), after.get("Tilt", 0)

    if zx_b != zx_a or zy_b != zy_a:
        lines.append(f"Zoom: {zx_b}x -> {zx_a}x")
    if p_b != p_a:
        lines.append(f"Pan: {p_b} -> {p_a}")
    if t_b != t_a:
        lines.append(f"Tilt: {t_b} -> {t_a}")

    if lines:
        ax.text(frame_w + 80, frame_h / 2, "\n".join(lines),
                ha="right", va="center", fontsize=8,
                color="#ccc", fontstyle="italic",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#2a2a3e",
                          edgecolor="#555", alpha=0.9))

    ax.legend(loc="upper left", fontsize=8, facecolor="#1a1a2e",
              edgecolor="#555", labelcolor="#ccc")
    ax.set_facecolor("#0d0d1a")
    ax.tick_params(colors="#555", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#333")


def main():
    snap_dir = os.path.expanduser("~/.resolve-snapshots/SampleProject")
    snap1 = load_snapshot(os.path.join(snap_dir, "BeforeEdit_20260319.json"))
    snap2 = load_snapshot(os.path.join(snap_dir, "AfterEdit_20260320.json"))

    tl_name = "Main Edit"
    clips_before = {c["name"]: c for c in get_video_clips(snap1, tl_name)}
    clips_after = {c["name"]: c for c in get_video_clips(snap2, tl_name)}

    # Find clips with zoom/pan/tilt changes
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
        print("No zoom/pan changes found.")
        return

    fig, axes = plt.subplots(1, len(changed), figsize=(7 * len(changed), 5))
    fig.patch.set_facecolor("#0d0d1a")

    if len(changed) == 1:
        axes = [axes]

    for ax_obj, name in zip(axes, changed):
        draw_clip_comparison(ax_obj, name, clips_before[name], clips_after[name])

    fig.suptitle(
        f"Zoom & Pan Changes:  {snap1['snapshot_name']}  vs  {snap2['snapshot_name']}",
        color="#eee", fontsize=13, fontweight="bold", y=0.98
    )
    fig.tight_layout(rect=[0, 0, 1, 0.93])

    out = os.path.expanduser("~/Desktop/snapshot_diff_visual.png")
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
