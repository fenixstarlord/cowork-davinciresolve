const DiffVisual = ({ snapshotName, clips }) => {
  const fw = 1920;
  const fh = 1080;
  const scale = 0.18;
  const cardW = fw * scale + 80;
  const cardH = fh * scale + 100;

  const viewport = (zx, zy, pan, tilt) => {
    const vw = fw / zx;
    const vh = fh / zy;
    const cx = fw / 2 + pan;
    const cy = fh / 2 + tilt;
    return {
      x: (cx - vw / 2) * scale,
      y: (cy - vh / 2) * scale,
      w: vw * scale,
      h: vh * scale,
      cx: cx * scale,
      cy: cy * scale,
    };
  };

  const ox = 40;
  const oy = 50;

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      gap: 16,
      fontFamily: "'Inter', 'SF Pro Display', -apple-system, sans-serif",
    }}>
      {/* Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "12px 16px",
        background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
        borderRadius: 12,
        border: "1px solid #2a2a4a",
      }}>
        <div style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: "#ff7043",
          boxShadow: "0 0 8px #ff704366",
        }} />
        <span style={{ color: "#e0e0e0", fontSize: 14, fontWeight: 600 }}>
          Transform Changes
        </span>
        <span style={{ color: "#888", fontSize: 12, marginLeft: "auto" }}>
          vs {snapshotName}
        </span>
      </div>

      {/* Clip cards */}
      <div style={{
        display: "flex",
        gap: 12,
        flexWrap: "wrap",
      }}>
        {clips.map((clip, i) => {
          const before = viewport(
            clip.before.ZoomX ?? 1, clip.before.ZoomY ?? 1,
            clip.before.Pan ?? 0, clip.before.Tilt ?? 0,
          );
          const after = viewport(
            clip.after.ZoomX ?? 1, clip.after.ZoomY ?? 1,
            clip.after.Pan ?? 0, clip.after.Tilt ?? 0,
          );

          const changes = [];
          if (clip.before.ZoomX !== clip.after.ZoomX)
            changes.push({ label: "Zoom", from: `${clip.before.ZoomX}x`, to: `${clip.after.ZoomX}x` });
          if (clip.before.Pan !== clip.after.Pan)
            changes.push({ label: "Pan", from: clip.before.Pan, to: clip.after.Pan });
          if (clip.before.Tilt !== clip.after.Tilt)
            changes.push({ label: "Tilt", from: clip.before.Tilt, to: clip.after.Tilt });

          const hasPanShift = Math.abs(after.cx - before.cx) > 0.5 || Math.abs(after.cy - before.cy) > 0.5;

          return (
            <div key={i} style={{
              flex: "1 1 340px",
              background: "linear-gradient(180deg, #111119 0%, #0d0d1a 100%)",
              borderRadius: 12,
              border: "1px solid #282838",
              padding: 16,
              minWidth: 340,
            }}>
              {/* Clip name */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 12,
              }}>
                <span style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#0d0d1a",
                  background: "#ff7043",
                  padding: "2px 8px",
                  borderRadius: 4,
                  letterSpacing: 0.3,
                }}>V{clip.track}</span>
                <span style={{ color: "#e0e0e0", fontSize: 13, fontWeight: 600 }}>
                  {clip.name}
                </span>
              </div>

              {/* SVG viewport diagram */}
              <svg
                viewBox={`0 0 ${cardW} ${cardH}`}
                width="100%"
                style={{ borderRadius: 8, background: "#0a0a14" }}
              >
                {/* Source frame */}
                <rect
                  x={ox} y={oy}
                  width={fw * scale} height={fh * scale}
                  fill="#1a1a2e" stroke="#333" strokeWidth={1}
                />
                <text
                  x={ox + fw * scale / 2} y={oy + fh * scale / 2 + 4}
                  textAnchor="middle" fill="#282838"
                  fontSize={10} fontFamily="monospace"
                >
                  {fw}x{fh}
                </text>

                {/* Before viewport */}
                <rect
                  x={ox + before.x} y={oy + before.y}
                  width={before.w} height={before.h}
                  fill="rgba(79,195,247,0.06)"
                  stroke="#4fc3f7" strokeWidth={2}
                  strokeDasharray="8 4"
                />

                {/* After viewport */}
                <rect
                  x={ox + after.x} y={oy + after.y}
                  width={after.w} height={after.h}
                  fill="rgba(255,112,67,0.08)"
                  stroke="#ff7043" strokeWidth={2}
                />

                {/* Before crosshair */}
                <line x1={ox + before.cx - 7} y1={oy + before.cy}
                      x2={ox + before.cx + 7} y2={oy + before.cy}
                      stroke="#4fc3f7" strokeWidth={1.5} />
                <line x1={ox + before.cx} y1={oy + before.cy - 7}
                      x2={ox + before.cx} y2={oy + before.cy + 7}
                      stroke="#4fc3f7" strokeWidth={1.5} />

                {/* After crosshair */}
                <line x1={ox + after.cx - 7} y1={oy + after.cy}
                      x2={ox + after.cx + 7} y2={oy + after.cy}
                      stroke="#ff7043" strokeWidth={1.5} />
                <line x1={ox + after.cx} y1={oy + after.cy - 7}
                      x2={ox + after.cx} y2={oy + after.cy + 7}
                      stroke="#ff7043" strokeWidth={1.5} />

                {/* Shift arrow */}
                {hasPanShift && (
                  <>
                    <defs>
                      <marker id={`arrow-${i}`} markerWidth="8" markerHeight="6"
                              refX="8" refY="3" orient="auto">
                        <path d="M0,0 L8,3 L0,6" fill="#ffee58" />
                      </marker>
                    </defs>
                    <line
                      x1={ox + before.cx} y1={oy + before.cy}
                      x2={ox + after.cx} y2={oy + after.cy}
                      stroke="#ffee58" strokeWidth={1.5}
                      markerEnd={`url(#arrow-${i})`}
                    />
                  </>
                )}

                {/* Legend */}
                <rect x={ox + 4} y={oy + fh * scale - 24} width={8} height={3} fill="#4fc3f7" />
                <text x={ox + 16} y={oy + fh * scale - 21} fill="#4fc3f7"
                      fontSize={8} fontFamily="sans-serif">Snapshot</text>
                <rect x={ox + 4} y={oy + fh * scale - 14} width={8} height={3} fill="#ff7043" />
                <text x={ox + 16} y={oy + fh * scale - 11} fill="#ff7043"
                      fontSize={8} fontFamily="sans-serif">Current</text>
              </svg>

              {/* Change pills */}
              <div style={{
                display: "flex",
                gap: 6,
                flexWrap: "wrap",
                marginTop: 10,
              }}>
                {changes.map((c, j) => (
                  <div key={j} style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 10px",
                    borderRadius: 20,
                    background: "#1a1a2e",
                    border: "1px solid #2a2a4a",
                    fontSize: 11,
                  }}>
                    <span style={{ color: "#888", fontWeight: 500 }}>{c.label}</span>
                    <span style={{ color: "#4fc3f7" }}>{c.from}</span>
                    <span style={{ color: "#555" }}>&rarr;</span>
                    <span style={{ color: "#ff7043" }}>{c.to}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// Example usage with sample data:
//
// <DiffVisual
//   snapshotName="BeforeEdit_20260319"
//   clips={[
//     {
//       name: "Interview_A.mov",
//       track: 1,
//       before: { ZoomX: 1.0, ZoomY: 1.0, Pan: 0, Tilt: 0 },
//       after:  { ZoomX: 1.1, ZoomY: 1.1, Pan: -15, Tilt: 0 },
//     },
//     {
//       name: "Broll_Park.mp4",
//       track: 1,
//       before: { ZoomX: 1.2, ZoomY: 1.2, Pan: 10, Tilt: 0 },
//       after:  { ZoomX: 1.5, ZoomY: 1.5, Pan: 25, Tilt: 0 },
//     },
//   ]}
// />

export default DiffVisual;
