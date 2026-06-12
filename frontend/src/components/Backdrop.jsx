import React from "react";

const ARCS = [
  { d: "M -100 720 Q 420 380 880 560", delay: "0s" },
  { d: "M 1540 200 Q 1050 80 620 300", delay: "6s" },
  { d: "M 200 -60 Q 520 330 1160 420", delay: "12s" },
];

export default function Backdrop() {
  return (
    <div className="backdrop" aria-hidden="true">
      <svg
        className="backdrop-svg"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* pitch markings */}
        <g className="pitch-lines" fill="none" stroke="currentColor" strokeWidth="2.5">
          <circle cx="720" cy="450" r="180" />
          <circle cx="720" cy="450" r="5" fill="currentColor" stroke="none" />
          <line x1="720" y1="0" x2="720" y2="900" />
          <rect x="-80" y="240" width="280" height="420" />
          <rect x="1240" y="240" width="280" height="420" />
        </g>

        {/* telestrator arcs */}
        {ARCS.map((arc, i) => (
          <g key={i} className="arc-group" style={{ "--delay": arc.delay }}>
            <path
              className="arc"
              d={arc.d}
              pathLength="1"
              fill="none"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray="0.06 0.025"
            />
            <circle className="arc-ball" r="7">
              <animateMotion
                dur="18s"
                begin={arc.delay}
                repeatCount="indefinite"
                path={arc.d}
                keyPoints="0;1;1"
                keyTimes="0;0.45;1"
                calcMode="linear"
              />
            </circle>
          </g>
        ))}
      </svg>
    </div>
  );
}