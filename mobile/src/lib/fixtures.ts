// Synthetic test data, ported from backend/scripts/facial_demo_data.py and
// backend/scripts/risk_demo_data.py. Never participant observations.

const CENTRE = { eye_aspect_ratio: 0.3, brow_lowering: 0.1, lip_press: 0.08, jaw_open: 0.04, head_motion_deg: 1.0 };
const QUALITY = { face_count: 1, tracking_score: 0.95, brightness: 0.55, sharpness: 0.85, yaw_deg: 2.0, pitch_deg: 1.0 };
const PHASES = ['neutral', 'task', 'recovery'] as const;

export type FacialScenario = 'stable' | 'return' | 'persistent' | 'poor_quality';

const SHIFTS: Record<FacialScenario, [number, number, number]> = {
  stable: [0, 0.005, 0],
  return: [0, 0.09, 0.015],
  persistent: [0, 0.09, 0.105],
  poor_quality: [0, 0.09, 0.015],
};

export function facialSession(opts: {
  participantId: string;
  clientSessionId: string;
  recordedAt: Date;
  calibrationIndex?: number;
  scenario?: FacialScenario;
}) {
  const calibration = opts.calibrationIndex !== undefined;
  const scenario = opts.scenario ?? 'return';
  const windows = Array.from({ length: calibration ? 6 : 18 }, (_, i) => {
    const phaseIndex = calibration ? 0 : Math.floor(i / 6);
    let shift = calibration ? ((opts.calibrationIndex! % 3) - 1) * 0.003 : SHIFTS[scenario][phaseIndex];
    shift += (i % 2 ? -1 : 1) * 0.001;
    const features = Object.fromEntries(
      Object.entries(CENTRE).map(([k, v]) => [k, k === 'eye_aspect_ratio' ? v - shift : k === 'head_motion_deg' ? v + shift * 10 : v + shift]),
    );
    const quality = scenario === 'poor_quality' && !calibration ? { ...QUALITY, face_count: 0, tracking_score: 0.1, brightness: 0.05 } : QUALITY;
    return { t_start_sec: i * 2.5, duration_sec: 2.5, phase: PHASES[phaseIndex], features, quality };
  });
  return {
    participant_id: opts.participantId,
    client_session_id: opts.clientSessionId,
    data_source: 'synthetic_demo',
    feature_schema_version: 'facial-window-v1',
    extractor_version: 'synthetic-v1',
    recorded_at: opts.recordedAt.toISOString(),
    consent: true,
    baseline_condition_confirmed: calibration,
    protocol: calibration ? 'neutral_only' : 'neutral_task_recovery',
    windows,
  };
}

// C3 uses Asia/Colombo study days (UTC+05:30, no daylight saving).
const COLOMBO_OFFSET_MS = 5.5 * 3600 * 1000;

export function colomboDate(offsetDays = 0) {
  return new Date(Date.now() + COLOMBO_OFFSET_MS + offsetDays * 86400000).toISOString().slice(0, 10);
}

/** 21:00 Colombo time on a study date, as UTC ISO. */
function colomboEvening(date: string) {
  return new Date(Date.parse(`${date}T21:00:00+05:30`)).toISOString();
}

export type RiskProfile = 'steady' | 'rising';

export function sampleDiary(participantId: string, profile: RiskProfile) {
  const rising = profile === 'rising';
  const daily = Array.from({ length: 14 }, (_, i) => {
    const day = colomboDate(-(14 - i));
    const study = rising ? 180 + i * 16 : 160;
    const fatigue = rising ? Math.min(5, 2 + Math.floor(i / 3)) : 2;
    return {
      participant_id: participantId,
      client_record_id: `sample-daily-${i}`,
      data_source: 'synthetic_demo',
      consent: true,
      observed_on: day,
      reported_at: colomboEvening(day),
      sleep_hours: rising ? Math.round((7.9 - 0.23 * i) * 100) / 100 : 7.8,
      study_minutes: study,
      break_minutes: rising ? Math.max(10, 65 - i * 4) : 65,
      late_study_minutes: rising ? Math.min(study, 25 + i * 11) : 10,
      planned_tasks: 6,
      completed_tasks: rising ? Math.max(1, 5 - Math.floor(i / 3)) : 6,
      fatigue,
      mental_strain: fatigue,
      concentration_readiness: 6 - fatigue,
    };
  });
  const weekly = [8, 1].map((daysAgo, i) => {
    const day = colomboDate(-daysAgo);
    return {
      participant_id: participantId,
      client_record_id: `sample-weekly-${i}`,
      data_source: 'synthetic_demo',
      consent: true,
      observed_on: day,
      reported_at: colomboEvening(day),
      instrument_version: 'exploratory-exhaustion-item-v1',
      exhaustion: rising ? (i === 0 ? 3 : 5) : 2,
      disengagement: rising ? 4 : 2,
      academic_efficacy: rising ? 2 : 4,
    };
  });
  return { daily, weekly };
}
