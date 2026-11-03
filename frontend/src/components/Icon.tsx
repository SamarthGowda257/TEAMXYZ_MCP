import { Accessibility, Ambulance, Baby, BedDouble, Bone, Brain, Droplets, FlaskConical, HeartPulse, Hospital, Microscope, Pill, ScanLine,
  Stethoscope, type LucideProps } from "lucide-react";

const MAP = { Accessibility, Ambulance, Baby, BedDouble, Bone, Brain, Droplets, FlaskConical, HeartPulse, Hospital, Microscope, Pill, ScanLine, Stethoscope };

/** Named hospital icon from the content file (one outline icon set: lucide). */
export function Icon({ name, ...rest }: { name: string } & LucideProps) {
  const C = (MAP as Record<string, typeof Stethoscope>)[name] || Stethoscope;
  return <C aria-hidden="true" {...rest} />;
}
