// Plain-language text for backend codes. Wording stays within what the backend
// claims: visual/acoustic measurements and an exploratory proxy, never a diagnosis.

const QUALITY: Record<string, string> = {
  require_exactly_one_face: 'Keep exactly one face in the frame',
  low_tracking_score: 'Your face was lost too often; hold the phone steady',
  poor_brightness: 'Lighting was too dark or too bright',
  low_sharpness: 'The image was blurry; wipe the lens and hold still',
  excessive_head_pose: 'Face the camera directly',
  less_than_8_usable_seconds: 'Not enough usable seconds were captured',
  less_than_80_percent_usable_coverage: 'Too much of the recording was unusable',
  too_little_signal_activity: 'Too little speech was detected; speak a bit louder and closer',
  excessive_clipping: 'The recording was too loud and distorted',
  stereo_phase_cancellation: 'The audio channels cancelled out; try again',
};

export function qualityTips(reasons: string[]) {
  return [...new Set(reasons.map((r) => QUALITY[r] ?? r.replaceAll('_', ' ')))];
}

export const LEVEL: Record<string, { title: string; tone: 'success' | 'warn' | 'error'; text: string }> = {
  within_reference_range: { title: 'Within your usual range', tone: 'success', text: 'Your facial movement looked similar to your reference recordings.' },
  moderate_visual_change: { title: 'Moderate visual change', tone: 'warn', text: 'Your facial movement differed somewhat from your reference recordings.' },
  large_visual_change: { title: 'Large visual change', tone: 'error', text: 'Your facial movement differed clearly from your reference recordings.' },
};

const TEMPORAL: Record<string, string> = {
  no_observed_task_increase_over_neutral: 'The task did not change your expression enough to measure a return.',
  each_phase_requires_at_least_5_usable_seconds: 'A phase had too few usable seconds to measure a return.',
  task_deviation_too_small_for_stable_fraction: 'The task change was too small to measure a return reliably.',
  neutral_only_protocol: 'Reference recordings have no task phase.',
};

export function temporalText(temporal: any): string | null {
  if (!temporal) return null;
  if (temporal.status !== 'measured') return TEMPORAL[temporal.reason] ?? 'Return toward your reference could not be measured.';
  const pct = Math.round(temporal.return_fraction * 100);
  return pct >= 0
    ? `During quiet observation you moved ${pct}% of the way back toward your reference.`
    : 'During quiet observation you moved further from your reference than during the task.';
}

export const RISK_STATUS: Record<string, { title: string; text: string }> = {
  insufficient_history: { title: 'No score yet', text: 'A forecast needs at least 7 earlier days of diary entries.' },
  model_unavailable: { title: 'Model unavailable', text: 'Your entries are saved, but the forecast model is not loaded on the backend.' },
  awaiting_source_matched_model: { title: 'Saved, not scored', text: 'Your real entries are stored. The bundled model was trained only on simulated people, so it does not score real records.' },
  demo_only_prediction: { title: 'Simulation score', text: 'From a model trained only on simulated people. It has no meaning for a real student.' },
  exploratory_local_prediction: { title: 'Exploratory score', text: 'An exploratory proxy from a locally fitted model, with validation limits.' },
};

export const CATEGORY_ICON = { pause: 'pause-circle-outline', movement: 'directions-walk', planning: 'checklist', reflection: 'edit-note', audio: 'headphones' } as const;
export const GOAL_ICON = { rest: 'bedtime', refocus: 'center-focus-strong', organize: 'view-list', reflect: 'psychology' } as const;
export const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1).replaceAll('_', ' ');
