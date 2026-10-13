/** UI presentation only. Authoritative Qwen contracts are in soul-api.ts. */
export type PersonaColor = 1 | 2 | 3 | 4 | 5;
export interface Persona {
  id: string;
  name: string;
  segment?: string;
  situation: string;
  interests: string[];
  worries: string[];
  notes?: string;
  quote?: string;
  checkpoint?: string;
  criticalUnknowns?: string[];
  evidenceLevel?: number;
  reason?: string;
  color: PersonaColor;
  source: "recommended" | "edited" | "custom";
}
