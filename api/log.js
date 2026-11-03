// Vercel Serverless Function: MDS-UPDRS Part III Patient Evaluation Logger
// Logs evaluation data to Vercel Runtime Logs and stores recent records in memory/tmp

const fs = require('fs');
const path = require('path');

const TMP_FILE = path.join('/tmp', 'mds_updrs_submissions.json');
const PART_III_SCORE_IDS = [
  '3.1', '3.2', '3.3a', '3.3b', '3.3c', '3.3d', '3.3e',
  '3.4a', '3.4b', '3.5a', '3.5b', '3.6a', '3.6b', '3.7a', '3.7b',
  '3.8a', '3.8b', '3.9', '3.10', '3.11', '3.12', '3.13', '3.14',
  '3.15a', '3.15b', '3.16a', '3.16b', '3.17a', '3.17b', '3.17c',
  '3.17d', '3.17e', '3.18'
];

function getStoredLogs() {
  globalThis.__MDS_LOGS__ = globalThis.__MDS_LOGS__ || [];
  try {
    if (fs.existsSync(TMP_FILE)) {
      const fileData = fs.readFileSync(TMP_FILE, 'utf8');
      const parsed = JSON.parse(fileData);
      if (Array.isArray(parsed) && parsed.length > globalThis.__MDS_LOGS__.length) {
        globalThis.__MDS_LOGS__ = parsed;
      }
    }
  } catch (e) {
    // ignore read errors
  }
  return globalThis.__MDS_LOGS__;
}

function saveLog(record) {
  const logs = getStoredLogs();
  // Prepend new record so newest is first
  logs.unshift(record);
  // Keep last 100 records
  if (logs.length > 100) logs.pop();
  globalThis.__MDS_LOGS__ = logs;

  try {
    fs.writeFileSync(TMP_FILE, JSON.stringify(logs, null, 2), 'utf8');
  } catch (e) {
    // ignore write errors on read-only environments
  }
}

module.exports = async function handler(req, res) {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Credentials', true);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
  res.setHeader('Access-Control-Allow-Headers', 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  // POST: Log patient assessment
  if (req.method === 'POST') {
    try {
      const body = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
      const record = {
        id: `LOG_${Date.now()}`,
        timestamp: new Date().toISOString(),
        patientId: body.patientId || '',
        sessionId: body.sessionId || '',
        patientName: body.patientName || '',
        updrsNumber: body.updrsNumber || '',
        examDate: body.examDate || new Date().toISOString().split('T')[0],
        medState: body.medState || 'NA',
        levodopaStatus: body.levodopaStatus || 'UNKNOWN',
        lastLevodopaDose: body.lastLevodopaDose || '',
        dyskinesiaPresent: body.dyskinesiaPresent || 'UNKNOWN',
        dyskinesiaInterference: body.dyskinesiaInterference || 'UNKNOWN',
        hoehnYahrStage: body.hoehnYahrStage || '',
        clinicianName: body.clinicianName || '',
        recipientEmail: body.recipientEmail || '',
        clinicalNotes: body.clinicalNotes || '',
        totalScore: body.totalScore !== undefined ? body.totalScore : 0,
        scoredCount: body.scoredCount !== undefined ? body.scoredCount : 0,
        domainStats: body.domainStats || [],
        scores: body.scores || {}
      };

      // 1. Output clearly formatted log to Vercel Runtime Logs Console
      console.log('========================================================');
      console.log(`[MDS-UPDRS LOG] PATIENT: ${record.patientName || 'N/A'} | ID: ${record.patientId} | SESSION: ${record.sessionId}`);
      console.log(`Date: ${record.examDate} | Medication: ${record.medState} | Levodopa: ${record.levodopaStatus} | Last dose: ${record.lastLevodopaDose || 'N/A'} | Dyskinesia: ${record.dyskinesiaPresent} | Interference: ${record.dyskinesiaInterference} | Examiner: ${record.clinicianName || 'N/A'}`);
      console.log(`TOTAL PART III SCORE: ${record.totalScore} / 132 (${record.scoredCount}/33 items evaluated)`);
      if (record.clinicalNotes) {
        console.log(`Notes: ${record.clinicalNotes}`);
      }
      console.log('MOTOR DOMAINS:', JSON.stringify(record.domainStats));
      console.log('33 ITEM SCORES:', JSON.stringify(record.scores));
      console.log('[FULL_JSON_RECORD]:', JSON.stringify(record));
      console.log('========================================================');

      // 2. Save in memory & /tmp
      saveLog(record);

      return res.status(200).json({
        status: 'success',
        message: `Evaluation for ${record.patientId} saved to Vercel logs!`,
        logId: record.id,
        timestamp: record.timestamp
      });
    } catch (err) {
      console.error('Error logging evaluation:', err);
      return res.status(400).json({ status: 'error', message: err.message });
    }
  }

  // GET: View logged evaluations or export CSV
  if (req.method === 'GET') {
    const rawLogs = getStoredLogs();

    function getPatientSessionKey(log) {
      const p = (log.patientId || '').trim().toLowerCase();
      const s = (log.sessionId || '').trim().toLowerCase();
      if (!p || !s) return log.id || `${log.timestamp || Date.now()}|${log.patientName || ''}`;
      return `${p}|${s}`;
    }

    function getRecordTime(item) {
      if (item.timestamp) {
        const t = new Date(item.timestamp).getTime();
        if (!isNaN(t)) return t;
      }
      if (item.examDate) {
        const t = new Date(item.examDate).getTime();
        if (!isNaN(t)) return t;
      }
      return 0;
    }

    // Deduplicate: Unique row per Patient + Session (scores NOT considered), keeping the latest date value
    const dedupeMap = new Map();
    rawLogs.forEach(log => {
      const key = getPatientSessionKey(log);
      const existing = dedupeMap.get(key);
      if (!existing) {
        dedupeMap.set(key, log);
      } else {
        if (getRecordTime(log) > getRecordTime(existing)) {
          dedupeMap.set(key, log);
        }
      }
    });
    const logs = Array.from(dedupeMap.values())
      .sort((a, b) => getRecordTime(b) - getRecordTime(a));

    const { format } = req.query || {};

    if (format === 'csv') {
      // Export wide-format CSV compatible with tremor_gait_pipeline.py
      const headers = [
        'patient_id',
        'patient_name',
        'session_id',
        'updrs_number',
        'date',
        'med_state',
        'pd_medication_status',
        'levodopa_status',
        'last_levodopa_dose',
        'dyskinesia_present',
        'dyskinesia_interference',
        'hoehn_yahr_stage',
        'examiner',
        'total_score',
        'items_scored'
      ];
      PART_III_SCORE_IDS.forEach(id => headers.push(`item_${id}`));
      headers.push('clinical_notes');

      const rows = [headers.join(',')];
      logs.forEach(log => {
        const r = [
          `"${log.patientId}"`,
          `"${(log.patientName || '').replace(/"/g, '""')}"`,
          `"${log.sessionId}"`,
          `"${(log.updrsNumber || '').replace(/"/g, '""')}"`,
          `"${log.examDate}"`,
          `"${log.medState}"`,
          `"${log.pdMedicationStatus || ''}"`,
          `"${log.levodopaStatus || ''}"`,
          `"${log.lastLevodopaDose || ''}"`,
          `"${log.dyskinesiaPresent || ''}"`,
          `"${log.dyskinesiaInterference || ''}"`,
          `"${log.hoehnYahrStage || ''}"`,
          `"${(log.clinicianName || '').replace(/"/g, '""')}"`,
          log.totalScore,
          log.scoredCount
        ];
        PART_III_SCORE_IDS.forEach(id => {
          const val = log.scores[id] !== undefined && log.scores[id] !== null ? log.scores[id] : '';
          r.push(val);
        });
        r.push(`"${(log.clinicalNotes || '').replace(/"/g, '""')}"`);
        rows.push(r.join(','));
      });

      res.setHeader('Content-Type', 'text/csv');
      res.setHeader('Content-Disposition', 'attachment; filename="mds_updrs_logged_patients.csv"');
      return res.status(200).send(rows.join('\n'));
    }

    return res.status(200).json({
      status: 'success',
      totalLogs: logs.length,
      logs: logs
    });
  }

  return res.status(405).json({ status: 'error', message: 'Method not allowed' });
};
