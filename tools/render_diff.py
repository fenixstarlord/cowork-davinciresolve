#!/usr/bin/env python3
"""Render a diff report PNG from two snapshot files."""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches


def load_snapshot(path):
    with open(path) as f:
        return json.load(f)


def get_video_clips(snap, tl_name):
    for tl in snap["timelines"]:
        if tl["name"] == tl_name:
            return [c for c in tl["clips"] if c.get("track_type") == "video"]
    return []


def viewport(zx, zy, pan, tilt, fw=1920, fh=1080):
    vw, vh = fw / zx, fh / zy
    cx, cy = fw / 2 + pan, fh / 2 + tilt
    return cx - vw / 2, cy - vh / 2, vw, vh


def draw_card(ax, name, before, after, fw=1920, fh=1080):
    ax.set_xlim(-60, fw + 60)
    ax.set_ylim(fh + 60, -60)
    ax.set_aspect("equal")
    ax.set_title(name, color="#e0e0e0", fontsize=11, fontweight="bold", pad=10)

    # Source frame
    ax.add_patch(patches.Rectangle((0, 0), fw, fh,
        lw=1.2, ec="#444", fc="#1a1a2e"))
    ax.text(fw/2, fh/2, f"{fw}x{fh}", ha="center", va="center",
            color="#333", fontsize=9)

    # Before
    bx, by, bw, bh = viewport(
        before.get("ZoomX", 1), before.get("ZoomY", 1),
        before.get("Pan", 0), before.get("Tilt", 0), fw, fh)
    ax.add_patch(patches.Rectangle((bx, by), bw, bh,
        lw=2.5, ec="#4fc3f7", fc="#4fc3f715", ls="--", label="Snapshot"))

    # After
    ax2, ay, aw, ah = viewport(
        after.get("ZoomX", 1), after.get("ZoomY", 1),
        after.get("Pan", 0), after.get("Tilt", 0), fw, fh)
    ax.add_patch(patches.Rectangle((ax2, ay), aw, ah,
        lw=2.5, ec="#ff7043", fc="#ff704318", label="Current"))

    # Crosshairs
    bcx, bcy = bx + bw/2, by + bh/2
    acx, acy = ax2 + aw/2, ay + ah/2
    ax.plot(bcx, bcy, "+", color="#4fc3f7", ms=14, mew=2)
    ax.plot(acx, acy, "+", color="#ff7043", ms=14, mew=2)

    # Arrow
    if abs(acx - bcx) > 1 or abs(acy - bcy) > 1:
        ax.annotate("", xy=(acx, acy), xytext=(bcx, bcy),
            arrowprops=dict(arrowstyle="->,head_width=0.4,head_length=0.3",
                            color="#ffee58", lw=2))

    # Annotations
    notes = []
    zxb, zxa = before.get("ZoomX", 1), after.get("ZoomX", 1)
    pb, pa = before.get("Pan", 0), after.get("Pan", 0)
    tb, ta = before.get("Tilt", 0), after.get("Tilt", 0)
    if zxb != zxa:
        notes.append(f"Zoom: {zxb}x \u2192 {zxa}x")
    if pb != pa:
        notes.append(f"Pan: {pb} \u2192 {pa}")
    if tb != ta:
        notes.append(f"Tilt: {tb} \u2192 {ta}")

    if notes:
        ax.text(fw - 20, fh + 40, "  |  ".join(notes),
                ha="right", va="center", fontsize=9, color="#bbb",
                fontstyle="italic")

    ax.legend(loc="upper left", fontsize=8, facecolor="#1a1a2e",
              edgecolor="#444", labelcolor="#ccc")
    ax.set_facecolor("#0f0f1a")
    ax.axis("off")


def render(snap1_path, snap2_path, tl_name, out_path):
    snap1 = load_snapshot(snap1_path)
    snap2 = load_snapshot(snap2_path)

    before_clips = {c["name"]: c for c in get_video_clips(snap1, tl_name)}
    after_clips = {c["name"]: c for c in get_video_clips(snap2, tl_name)}

    changed = []
    for name in before_clips:
        if name not in after_clips:
            continue
        b, a = before_clips[name], after_clips[name]
        if any(b.get(p) != a.get(p) for p in ("ZoomX", "ZoomY", "Pan", "Tilt")):
            changed.append(name)

    if not changed:
        print("No transform changes.")
        return

    n = len(changed)
    fig, axes = plt.subplots(1, n, figsize=(6 * n, 4.2))
    fig.patch.set_facecolor("#0a0a14")
    if n == 1:
        axes = [axes]

    for ax_obj, name in zip(axes, changed):
        draw_card(ax_obj, name, before_clips[name], after_clips[name])

    fig.suptitle(
        f"Transform Changes:  {snap1['snapshot_name']}  \u2192  {snap2['snapshot_name']}",
        color="#e8e8e8", fontsize=14, fontweight="bold", y=0.99)
    fig.tight_layout(rect=[0, 0.02, 1, 0.91])

    fig.savefig(out_path, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    snap_dir = os.path.expanduser("~/.resolve-snapshots/SampleProject")
    render(
        os.path.join(snap_dir, "BeforeEdit_20260319.json"),
        os.path.join(snap_dir, "AfterEdit_20260320.json"),
        "Main Edit",
        os.path.expanduser("~/Desktop/diff_transforms.png"),
    )
