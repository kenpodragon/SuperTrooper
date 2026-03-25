export interface BulletRef {
  ref?: string;
  id?: number;
  literal?: string;
}

export interface SkillRef {
  ref?: string;
  ids?: number[];
  literal?: string;
}

export interface RecipeV2 {
  header?: { ref?: string; id?: number; literal?: string };
  headline?: { ref?: string; id?: number; literal?: string };
  summary?: { ref?: string; id?: number; literal?: string };
  experience?: Array<{
    ref?: string; id?: number;
    synopsis?: BulletRef;
    bullets: BulletRef[];
  }>;
  skills?: SkillRef[];
  education?: Array<{ ref?: string; id?: number; literal?: string }>;
  certifications?: Array<{ ref?: string; id?: number; literal?: string }>;
  highlights?: BulletRef[];
  additional_experience?: Array<{ ref?: string; id?: number; literal?: string }>;
  [key: string]: unknown;
}

export interface ResolvedV2 {
  header?: Record<string, string>;
  headline?: string;
  summary?: string;
  experience?: Array<{
    id?: number; employer?: string; title?: string; start_date?: string; end_date?: string;
    location?: string; synopsis?: string; bullets?: string[];
  }>;
  skills?: string[];
  education?: string[];
  certifications?: string[];
  highlights?: string[];
  additional_experience?: string[];
}

export interface ThemeSettings {
  font_family?: string;
  font_size_body?: number;
  font_size_heading?: number;
  font_size_name?: number;
  accent_color?: string;
  header_alignment?: string;
  [key: string]: unknown;
}
