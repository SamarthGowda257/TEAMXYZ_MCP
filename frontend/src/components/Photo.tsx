import { useState } from "react";
import { Icon } from "./Icon";

/**
 * Stock photograph (Unsplash licence) with a designed fallback: if the image can't load,
 * a tinted panel with a hospital icon takes its place, so the layout never shows a broken image.
 * These photos are atmosphere for a fictional hospital, not pictures of real WellNest staff.
 */
export function Photo({ src, alt, icon = "Stethoscope", className = "", eager = false }:
  { src: string; alt: string; icon?: string; className?: string; eager?: boolean }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className={`photo ${className}`}>
      {failed ? (
        <div className="photo-fallback" role="img" aria-label={alt}><Icon name={icon} size={56} strokeWidth={1.4} /></div>
      ) : (
        <img src={src} alt={alt} loading={eager ? "eager" : "lazy"} decoding="async" onError={() => setFailed(true)} />
      )}
    </div>
  );
}
