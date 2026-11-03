// MDS-UPDRS Part III: Motor Examination
// The official 18 items contain 33 scored elements.

const MDS_UPDRS_SECTIONS = [
  {
    id: 'speech-expression',
    number: 1,
    title: 'Speech & Facial Expression',
    subtitle: 'Rate the patient from clinical observation and conversation',
    itemIds: ['3.1', '3.2']
  },
  {
    id: 'rigidity',
    number: 2,
    title: 'Rigidity',
    subtitle: 'Rate the neck and each limb separately during passive movement',
    itemIds: ['3.3a', '3.3b', '3.3c', '3.3d', '3.3e']
  },
  {
    id: 'bradykinesia',
    number: 3,
    title: 'Bradykinesia',
    subtitle: 'Rate each side separately for finger, hand, pronation, toe and leg movements',
    itemIds: ['3.4a', '3.4b', '3.5a', '3.5b', '3.6a', '3.6b', '3.7a', '3.7b', '3.8a', '3.8b']
  },
  {
    id: 'gait-posture',
    number: 4,
    title: 'Gait, Postural Stability & Posture',
    subtitle: 'Observe arising, walking, freezing, pull response and standing posture',
    itemIds: ['3.9', '3.10', '3.11', '3.12', '3.13']
  },
  {
    id: 'global-tremor',
    number: 5,
    title: 'Global Movement & Tremor',
    subtitle: 'Rate global spontaneity, postural tremor and kinetic tremor',
    itemIds: ['3.14', '3.15a', '3.15b', '3.16a', '3.16b']
  },
  {
    id: 'rest-tremor',
    number: 6,
    title: 'Rest Tremor',
    subtitle: 'Rate maximum rest tremor amplitude and its constancy during the examination',
    itemIds: ['3.17a', '3.17b', '3.17c', '3.17d', '3.17e', '3.18']
  },
  {
    id: 'summary-report',
    number: 7,
    title: 'Summary & Report',
    subtitle: 'Review the clinician-rated examination, export and print the report',
    itemIds: []
  }
];

const SCORE_OPTIONS = {
  '0': 'Normal',
  '1': 'Slight',
  '2': 'Mild',
  '3': 'Moderate',
  '4': 'Severe',
  'UR': 'Unable to Rate'
};

const TREMOR_OPTIONS = {
  '0': 'Normal: No tremor',
  '1': 'Slight: Less than 1 cm',
  '2': 'Mild: 1 to less than 3 cm',
  '3': 'Moderate: 3 to less than 10 cm',
  '4': 'Severe: 10 cm or greater',
  'UR': 'Unable to Rate'
};

const LIP_JAW_TREMOR_OPTIONS = {
  '0': 'Normal: No tremor',
  '1': 'Slight: Less than 1 cm',
  '2': 'Mild: 1 to less than 2 cm',
  '3': 'Moderate: 2 to less than 3 cm',
  '4': 'Severe: 3 cm or greater',
  'UR': 'Unable to Rate'
};

const CONSTANCY_OPTIONS = {
  '0': 'Normal: No tremor',
  '1': 'Slight: Present 25% or less of examination',
  '2': 'Mild: Present 26-50% of examination',
  '3': 'Moderate: Present 51-75% of examination',
  '4': 'Severe: Present more than 75% of examination',
  'UR': 'Unable to Rate'
};

const MDS_UPDRS_PART_III_ITEMS = [
  ['3.1', 'Speech', 'Listen to free-flowing speech and rate volume, modulation and clarity.'],
  ['3.2', 'Facial Expression', 'Observe at rest and while talking, including blinking, smiling and parted lips.'],
  ['3.3a', 'Rigidity - Neck', 'Passively move the neck with the patient relaxed; use activation if needed.'],
  ['3.3b', 'Rigidity - Right Upper Extremity', 'Passively move the right wrist and elbow; use activation if needed.'],
  ['3.3c', 'Rigidity - Left Upper Extremity', 'Passively move the left wrist and elbow; use activation if needed.'],
  ['3.3d', 'Rigidity - Right Lower Extremity', 'Passively move the right hip and knee; use activation if needed.'],
  ['3.3e', 'Rigidity - Left Lower Extremity', 'Passively move the left hip and knee; use activation if needed.'],
  ['3.4a', 'Finger Tapping - Right', 'Tap the index finger on the thumb 10 times as quickly and as big as possible.'],
  ['3.4b', 'Finger Tapping - Left', 'Tap the index finger on the thumb 10 times as quickly and as big as possible.'],
  ['3.5a', 'Hand Movements - Right', 'Open and close the right hand 10 times as fully and quickly as possible.'],
  ['3.5b', 'Hand Movements - Left', 'Open and close the left hand 10 times as fully and quickly as possible.'],
  ['3.6a', 'Pronation-Supination - Right', 'Turn the right palm up and down 10 times as quickly and fully as possible.'],
  ['3.6b', 'Pronation-Supination - Left', 'Turn the left palm up and down 10 times as quickly and fully as possible.'],
  ['3.7a', 'Toe Tapping - Right', 'Raise and stomp the right toes 10 times as big and fast as possible.'],
  ['3.7b', 'Toe Tapping - Left', 'Raise and stomp the left toes 10 times as big and fast as possible.'],
  ['3.8a', 'Leg Agility - Right', 'Raise and stomp the right foot 10 times as high and fast as possible.'],
  ['3.8b', 'Leg Agility - Left', 'Raise and stomp the left foot 10 times as high and fast as possible.'],
  ['3.9', 'Arising from Chair', 'Rise from a straight-backed chair with arms crossed, following the examination instructions.'],
  ['3.10', 'Gait', 'Walk at least 10 meters away and back; assess stride, speed, lift, heel strike, turning and arm swing.'],
  ['3.11', 'Freezing of Gait', 'Assess start hesitation, turning and doorway freezing during gait.'],
  ['3.12', 'Postural Stability', 'Assess the response to a quick, forceful pull on the shoulders.'],
  ['3.13', 'Posture', 'Rate the worst posture observed after arising, during walking and during postural testing.'],
  ['3.14', 'Global Spontaneity of Movement', 'Rate global slowness, hesitancy, small amplitude and poverty of spontaneous movement.'],
  ['3.15a', 'Postural Tremor - Right Hand', 'Hold both arms out with palms down for 10 seconds; rate the highest amplitude.'],
  ['3.15b', 'Postural Tremor - Left Hand', 'Hold both arms out with palms down for 10 seconds; rate the highest amplitude.'],
  ['3.16a', 'Kinetic Tremor - Right Hand', 'Perform at least three slow right finger-to-nose maneuvers; rate the highest amplitude.'],
  ['3.16b', 'Kinetic Tremor - Left Hand', 'Perform at least three slow left finger-to-nose maneuvers; rate the highest amplitude.'],
  ['3.17a', 'Rest Tremor Amplitude - Right Upper Extremity', 'Rate the maximum amplitude observed at rest during the entire examination.'],
  ['3.17b', 'Rest Tremor Amplitude - Left Upper Extremity', 'Rate the maximum amplitude observed at rest during the entire examination.'],
  ['3.17c', 'Rest Tremor Amplitude - Right Lower Extremity', 'Rate the maximum amplitude observed at rest during the entire examination.'],
  ['3.17d', 'Rest Tremor Amplitude - Left Lower Extremity', 'Rate the maximum amplitude observed at rest during the entire examination.'],
  ['3.17e', 'Rest Tremor Amplitude - Lip/Jaw', 'Rate the maximum amplitude observed at rest during the entire examination.'],
  ['3.18', 'Constancy of Rest Tremor', 'Rate the percentage of the examination during which rest tremor is present.']
].map(([id, name, question]) => ({
  id,
  name,
  question,
  options: id === '3.18'
    ? CONSTANCY_OPTIONS
    : id === '3.17e'
      ? LIP_JAW_TREMOR_OPTIONS
      : id.startsWith('3.15') || id.startsWith('3.16') || id.startsWith('3.17')
        ? TREMOR_OPTIONS
        : SCORE_OPTIONS,
  sensor: ''
}));
