/** Flat illustration of the CareLine hospital building (drawn in code; no stock photos). */
export function HospitalArt() {
  const windows = [];
  for (let r = 0; r < 5; r++) {
    for (let c = 0; c < 4; c++) {
      windows.push(<rect key={`l${r}${c}`} x={62 + c * 30} y={150 + r * 34} width="20" height="22" rx="3" fill="#cfe2f7" />);
      windows.push(<rect key={`r${r}${c}`} x={338 + c * 30} y={150 + r * 34} width="20" height="22" rx="3" fill="#cfe2f7" />);
    }
  }
  for (let r = 0; r < 7; r++) {
    for (let c = 0; c < 3; c++) windows.push(<rect key={`m${r}${c}`} x={206 + c * 34} y={110 + r * 30} width="24" height="20" rx="3" fill="#dcebfb" />);
  }
  return (
    <svg viewBox="0 0 520 420" role="img" aria-label="Illustration of the CareLine Hospitals building" className="hospital-art">
      <rect x="0" y="0" width="520" height="420" rx="24" fill="#e8f2fd" />
      <circle cx="430" cy="78" r="34" fill="#fff4dc" />
      <path d="M40 92c18-14 44-14 60 0 14-10 34-8 44 4H40z" fill="#fff" />
      <path d="M300 60c14-10 34-10 46 0 10-7 26-6 34 3h-80z" fill="#fff" />
      {/* wings */}
      <rect x="44" y="130" width="148" height="232" rx="6" fill="#ffffff" stroke="#c9daee" strokeWidth="2" />
      <rect x="328" y="130" width="148" height="232" rx="6" fill="#ffffff" stroke="#c9daee" strokeWidth="2" />
      {/* tower */}
      <rect x="188" y="88" width="144" height="274" rx="6" fill="#0b5cad" />
      <rect x="196" y="98" width="128" height="230" rx="4" fill="#0a529b" />
      {windows}
      {/* cross sign */}
      <rect x="230" y="40" width="60" height="60" rx="12" fill="#ffffff" stroke="#c9daee" strokeWidth="2" />
      <path d="M253 50h14v15h15v14h-15v15h-14V79h-15V65h15z" fill="#d0312d" />
      {/* entrance */}
      <rect x="224" y="318" width="72" height="44" rx="4" fill="#ffffff" />
      <rect x="232" y="326" width="26" height="36" fill="#bcd6f2" /><rect x="262" y="326" width="26" height="36" fill="#bcd6f2" />
      <rect x="210" y="306" width="100" height="14" rx="3" fill="#08458a" />
      <text x="260" y="317" textAnchor="middle" fontFamily="Poppins, sans-serif" fontSize="9" fontWeight="600" fill="#fff">CARELINE</text>
      {/* ground */}
      <rect x="0" y="362" width="520" height="58" fill="#d6e7f8" />
      <rect x="0" y="384" width="520" height="12" fill="#c4dbf3" />
      {/* trees */}
      <circle cx="26" cy="338" r="22" fill="#9fd3c0" /><rect x="23" y="350" width="6" height="16" fill="#6a9f8c" />
      <circle cx="500" cy="336" r="24" fill="#9fd3c0" /><rect x="497" y="350" width="6" height="16" fill="#6a9f8c" />
      {/* ambulance */}
      <g transform="translate(352 330)">
        <rect x="0" y="8" width="92" height="40" rx="6" fill="#ffffff" stroke="#c9daee" strokeWidth="2" />
        <path d="M92 18h18l14 16v14H92z" fill="#ffffff" stroke="#c9daee" strokeWidth="2" />
        <rect x="98" y="22" width="14" height="10" rx="2" fill="#bcd6f2" />
        <rect x="0" y="34" width="124" height="5" fill="#d0312d" />
        <path d="M38 14h10v8h8v10h-8v8H38v-8h-8V22h8z" fill="#d0312d" />
        <rect x="36" y="0" width="16" height="8" rx="2" fill="#0b5cad" />
        <circle cx="24" cy="50" r="9" fill="#0d2240" /><circle cx="24" cy="50" r="4" fill="#cfd8e3" />
        <circle cx="102" cy="50" r="9" fill="#0d2240" /><circle cx="102" cy="50" r="4" fill="#cfd8e3" />
      </g>
    </svg>
  );
}
