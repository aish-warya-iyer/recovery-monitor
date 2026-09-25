// Display names for the six exercises the models support (plus the original prototype's leg extension).
export const EXERCISES = {
  squat: { name: 'Squats', one: 'squat', area: 'Lower body' },
  leg_lunge: { name: 'Lunges', one: 'lunge', area: 'Lower body' },
  leg_abduction: { name: 'Leg raises to the side', one: 'leg raise', area: 'Lower body' },
  arm_abduction: { name: 'Arm raises to the side', one: 'arm raise', area: 'Upper body' },
  arm_vw: { name: 'Arm V-W', one: 'arm V-W', area: 'Upper body' },
  push_ups: { name: 'Push-ups (hands on table)', one: 'push-up', area: 'Upper body' },
  seated_leg_extension: { name: 'Seated leg extension', one: 'leg extension', area: 'Lower body' },
};
export const exerciseName = (key) => EXERCISES[key]?.name ?? key ?? '—';
