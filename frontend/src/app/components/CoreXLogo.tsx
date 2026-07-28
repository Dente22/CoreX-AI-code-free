import React from 'react';

interface CoreXLogoProps {
  className?: string;
}

/** Neural Forge Nexus — локальное AI-ядро, X как слияние кода и нейросети, 3 узла оркестрации. */
export function CoreXLogo({ className = 'w-4 h-4' }: CoreXLogoProps) {
  const uid = React.useId().replace(/:/g, '');
  const g = (name: string) => `corex-${name}-${uid}`;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 256 256"
      fill="none"
      className={className}
      role="img"
      aria-label="CoreX logo"
    >
      <defs>
        <linearGradient id={g('chamber')} x1="40" y1="32" x2="216" y2="224" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1A1030" />
          <stop offset="1" stopColor="#0A1424" />
        </linearGradient>
        <linearGradient id={g('rim')} x1="32" y1="48" x2="224" y2="208" gradientUnits="userSpaceOnUse">
          <stop stopColor="#9A5EFF" stopOpacity="0.7" />
          <stop offset="0.5" stopColor="#00D2FF" stopOpacity="0.45" />
          <stop offset="1" stopColor="#7C3AED" stopOpacity="0.7" />
        </linearGradient>
        <linearGradient id={g('beam-p')} x1="70" y1="70" x2="186" y2="186" gradientUnits="userSpaceOnUse">
          <stop stopColor="#C49AFF" />
          <stop offset="1" stopColor="#7C3AED" />
        </linearGradient>
        <linearGradient id={g('beam-c')} x1="186" y1="70" x2="70" y2="186" gradientUnits="userSpaceOnUse">
          <stop stopColor="#7DF5FF" />
          <stop offset="1" stopColor="#0891B2" />
        </linearGradient>
        <radialGradient
          id={g('pulse')}
          cx="0"
          cy="0"
          r="1"
          gradientUnits="userSpaceOnUse"
          gradientTransform="translate(128 128) rotate(90) scale(44)"
        >
          <stop stopColor="#FFFFFF" stopOpacity="0.95" />
          <stop offset="0.25" stopColor="#00D2FF" stopOpacity="0.75" />
          <stop offset="0.7" stopColor="#9A5EFF" stopOpacity="0.25" />
          <stop offset="1" stopColor="#9A5EFF" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Кузница — локальная мастерская */}
      <rect x="24" y="24" width="208" height="208" rx="54" fill={`url(#${g('chamber')})`} />
      <rect
        x="24"
        y="24"
        width="208"
        height="208"
        rx="54"
        stroke={`url(#${g('rim')})`}
        strokeWidth="3"
      />

      {/* Орбита оркестрации */}
      <circle
        cx="128"
        cy="128"
        r="84"
        stroke="#9A5EFF"
        strokeOpacity="0.16"
        strokeWidth="2"
        strokeDasharray="9 13"
      />

      {/* X — пересечение редактора и AI */}
      <path
        d="M76 76L180 180"
        stroke={`url(#${g('beam-p')})`}
        strokeWidth="22"
        strokeLinecap="round"
      />
      <path
        d="M180 76L76 180"
        stroke={`url(#${g('beam-c')})`}
        strokeWidth="22"
        strokeLinecap="round"
      />

      {/* Локальное ядро (Ollama / нейрочип) */}
      <circle cx="128" cy="128" r="40" fill={`url(#${g('pulse')})`} />
      <path
        d="M128 104L146 114V138L128 148L110 138V114L128 104Z"
        fill="#0B0F17"
        stroke="#00D2FF"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <circle cx="128" cy="128" r="6" fill="#FFFFFF" />

      {/* Скил · Агент · Команда */}
      <circle cx="128" cy="54" r="9" fill="#00D2FF" />
      <circle cx="68" cy="178" r="9" fill="#9A5EFF" />
      <circle cx="188" cy="178" r="9" fill="#00D2FF" />
      <circle cx="128" cy="54" r="4" fill="#FFFFFF" fillOpacity="0.85" />
      <circle cx="68" cy="178" r="4" fill="#FFFFFF" fillOpacity="0.85" />
      <circle cx="188" cy="178" r="4" fill="#FFFFFF" fillOpacity="0.85" />

      {/* Синапсы к ядру */}
      <path d="M128 128V66" stroke="#00D2FF" strokeWidth="2" strokeOpacity="0.4" strokeLinecap="round" />
      <path d="M128 128L76 170" stroke="#9A5EFF" strokeWidth="2" strokeOpacity="0.4" strokeLinecap="round" />
      <path d="M128 128L180 170" stroke="#00D2FF" strokeWidth="2" strokeOpacity="0.4" strokeLinecap="round" />
    </svg>
  );
}
