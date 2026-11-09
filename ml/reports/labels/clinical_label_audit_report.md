# Clinical Label Audit & MDS-UPDRS Mapping Report

## 1. Clinical Scale & Target Identification

- **Clinical Rating Scale**: Movement Disorder Society Unified Parkinson's Disease Rating Scale (MDS-UPDRS) Part III (Motor Examination), alongside traditional UPDRS Part III.
- **Target Definition**: The intended research target is an individual ordinal motor severity score from 0 to 4 (0 = Normal, 1 = Slight, 2 = Mild, 3 = Moderate, 4 = Severe).
- **Current Label Availability**: **50 task-level scores** are available (healthy cohort ground truth plus Clinical Score.xlsx mappings).
- **Audit of Existing Workbooks**: `UPDRS Assessment Sheet.xlsx` and `Patient Tests and Parameters for Data Collection.xlsx` were inspected cell-by-cell. Both workbooks are protocol/rubric reference templates. No clinical examination ratings were populated for any participant.

## 2. Ethical and Methodological Supervised Learning Rules

> [!IMPORTANT]
> **Rule 1: Never Treat Healthy Status as Automatic Zero**
Healthy elderly or adult control participants frequently exhibit physiological tremor, mild stiffness, or age-related motor slowing that may receive non-zero clinical scores or non-zero sensor variability. Setting healthy scores to 0 without clinician rating introduces severe label bias.

> [!IMPORTANT]
> **Rule 2: Never Infer Scores from Diagnosis**
Parkinson's disease patients present with heterogeneous motor manifestations: some have predominant resting tremor with normal postural stability; others have severe rigidity and bradykinesia with absent resting tremor. Treating diagnosis as a universal score destroys the clinical validity of the target score.

> [!WARNING]
> **Supervised Machine Learning Status**: **BLOCKED**
Supervised model training and cross-validation cannot be performed until verified clinician ratings (0-4) are entered into `reports/labels/label_mapping_template.csv`.

## 3. Discovered Task to MDS-UPDRS Item Mapping

| task                 | clinical_scale                           | clinical_item_id   | clinical_item_name                      | target_score_range                                                                                                               |
|:---------------------|:-----------------------------------------|:-------------------|:----------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------|
| Arm Extended Forward | MDS-UPDRS Part III                       | 3.15               | Postural Tremor of the Hands            | 0-4 (0=No tremor, 1=Slight <=1cm, 2=Mild >1 to 3cm, 3=Moderate >3 to 10cm, 4=Severe >10cm)                                       |
| Finger Tapping       | MDS-UPDRS Part III                       | 3.4                | Finger Tapping                          | 0-4 (0=Normal, 1=Slight decrement/hesitation, 2=Mild 3-5 halts/decrements, 3=Moderate >5 halts, 4=Severe barely perform)         |
| Finger to Nose       | MDS-UPDRS Part III                       | 3.16               | Kinetic Tremor of the Hands             | 0-4 (0=No tremor, 1=Slight <=1cm, 2=Mild >1 to 3cm, 3=Moderate >3 to 10cm, 4=Severe >10cm)                                       |
| Hand Resting         | MDS-UPDRS Part III                       | 3.17               | Rest Tremor Amplitude                   | 0-4 (0=Normal, 1=Slight <=1cm, 2=Mild >1 to 3cm, 3=Moderate >3 to 10cm, 4=Severe >10cm)                                          |
| Normal Walking       | MDS-UPDRS Part III                       | 3.10               | Gait                                    | 0-4 (0=Normal, 1=Slow walking/shuffling, 2=Walks with difficulty/little assistance, 3=Severe disturbance/aid, 4=Cannot walk)     |
| Quiet Standing       | MDS-UPDRS Part III                       | 3.13               | Posture & Sway                          | 0-4 (0=Normal erect, 1=Not quite erect, 2=Definite flexion, 3=Moderate flexion/leaning, 4=Severe flexion)                        |
| Fist Open and Close  | MDS-UPDRS Part III                       | 3.5                | Hand Movements                          | 0-4 (0=Normal, 1=Slight slowing/reduction, 2=Mild, 3=Moderate, 4=Severe)                                                         |
| Pronation Supination | MDS-UPDRS Part III                       | 3.6                | Pronation-Supination Movements of Hands | 0-4 (0=Normal, 1=Slight slowing, 2=Mild, 3=Moderate, 4=Severe)                                                                   |
| Sit-to-Stand         | MDS-UPDRS Part III                       | 3.9                | Arising from Chair                      | 0-4 (0=Normal, 1=Slow/more than one attempt, 2=Pushes up from chair arms, 3=Falls back/multiple attempts, 4=Unable without help) |
| TUG                  | MDS-UPDRS Part III & Functional Mobility | 3.14               | Global Spontaneity / Timed Up & Go      | 0-4 (or completion time in seconds; normal < 10s)                                                                                |
| Turning Task         | MDS-UPDRS Part III Sub-element           | 3.10-Turn          | Turning Movement & Hesitation           | 0-4 (0=Smooth pivot <=3 steps, 1=Slight hesitation, 2=4-5 steps, 3=Freeze/severe hesitation, 4=Cannot turn)                      |


## 4. Clinician Data Collection Requirements

To unblock supervised learning, the clinician must supply:
1. **Item Rating (0-4)**: Specific MDS-UPDRS Part III score for each task performed.
2. **Assessment Session Date**: Confirming the clinical exam occurred on the exact same date as the sensor recording.
3. **Medication State**: ON-medication or OFF-medication state at the time of data collection.
4. **Sensor Limb Laterality**: Clarifying whether sensor was placed on the clinically most-affected or least-affected side (Left vs Right).
