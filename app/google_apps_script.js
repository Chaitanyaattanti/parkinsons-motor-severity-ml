/**
 * MDS-UPDRS Part III Motor Examination - Google Sheets Webhook
 * 
 * Instructions:
 * 1. Open a new or existing Google Sheet.
 * 2. Click "Extensions" -> "Apps Script".
 * 3. Delete any code in the editor and paste this entire code.
 * 4. Click "Deploy" (top right) -> "New deployment".
 * 5. Click the gear icon next to "Select type" -> select "Web app".
 * 6. Set Description: "MDS-UPDRS Receiver"
 * 7. Set "Execute as": "Me"
 * 8. Set "Who has access": "Anyone"  <-- IMPORTANT
 * 9. Click "Deploy", authorize permissions, and COPY the Web App URL (ending in /exec).
 * 10. Paste that URL into the MDS-UPDRS web app under "Google Sheet Sync".
 */

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data = JSON.parse(e.postData.contents);
    
    // Create header row if sheet is empty
    if (sheet.getLastRow() === 0) {
      var headers = [
        "Timestamp",
        "Patient Name",
        "Patient ID",
        "Session ID",
        "MDS-UPDRS Number",
        "Assessment Date",
        "Medication State",
        "PD Medication",
        "Levodopa",
        "Last Levodopa Dose",
        "Dyskinesia Present",
        "Dyskinesia Interfered",
        "Levodopa",
        "Last Levodopa Dose",
        "Examiner",
        "Total Score (0-132)",
        "Items Completed",
        "Craniofacial (0-20)",
        "Tremors (0-24)",
        "Rigidity (0-12)",
        "Limb Agility (0-16)",
        "Gait & Posture (0-24)",
        "Orofacial (0-20)",
        "Involuntary & Axial (0-16)"
      ];
      
      // Add columns for all 33 individual item scores
      for (var i = 1; i <= 33; i++) {
        headers.push("Item " + i);
      }
      headers.push("Clinical Notes");
      headers.push("Doctor Email");
      
      sheet.appendRow(headers);
      
      // Format header row (bold, dark blue background)
      var headerRange = sheet.getRange(1, 1, 1, headers.length);
      headerRange.setFontWeight("bold");
      headerRange.setBackground("#2563eb");
      headerRange.setFontColor("#ffffff");
      sheet.setFrozenRows(1);
    }
    
    // Extract domain subscores
    var domainMap = {};
    if (data.domainStats) {
      data.domainStats.forEach(function(d) {
        domainMap[d.name] = d.score;
      });
    }
    
    var row = [
      new Date().toLocaleString(),
      data.patientName || "",
      data.patientId || "",
      data.sessionId || "",
      data.updrsNumber || "",
      data.examDate || "",
      data.medState || "",
      data.pdMedicationStatus || "",
      data.levodopaStatus || "",
      data.lastLevodopaDose || "",
      data.dyskinesiaPresent || "",
      data.dyskinesiaInterference || "",
      data.levodopaStatus || "",
      data.lastLevodopaDose || "",
      data.clinicianName || "",
      data.totalScore !== undefined ? data.totalScore : "",
      data.scoredCount !== undefined ? (data.scoredCount + " / 33") : "",
      domainMap["Craniofacial & Speech"] !== undefined ? domainMap["Craniofacial & Speech"] : "",
      domainMap["Tremors (Resting & Action)"] !== undefined ? domainMap["Tremors (Resting & Action)"] : "",
      domainMap["Rigidity (Limbs & Axial)"] !== undefined ? domainMap["Rigidity (Limbs & Axial)"] : "",
      domainMap["Limb Agility / Bradykinesia"] !== undefined ? domainMap["Limb Agility / Bradykinesia"] : "",
      domainMap["Gait, Posture & Balance"] !== undefined ? domainMap["Gait, Posture & Balance"] : "",
      domainMap["Orofacial Movements"] !== undefined ? domainMap["Orofacial Movements"] : "",
      domainMap["Involuntary Movements & Axial"] !== undefined ? domainMap["Involuntary Movements & Axial"] : ""
    ];
    
    // Add individual scores 1 to 33
    var scores = data.scores || {};
    for (var j = 1; j <= 33; j++) {
      var s = scores[j];
      row.push(s !== undefined && s !== null ? s : "");
    }
    
    row.push(data.clinicalNotes || "");
    row.push(data.recipientEmail || "");
    
    sheet.appendRow(row);
    
    return ContentService.createTextOutput(JSON.stringify({ status: "success", rowCount: sheet.getLastRow() }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({ status: "active", message: "MDS-UPDRS Sheet Webhook is online." }))
    .setMimeType(ContentService.MimeType.JSON);
}
