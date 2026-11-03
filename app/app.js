// MDS-UPDRS Part III: Motor Function Examination Application Logic
// Supports Multi-Page Stepper Navigation, Done Stats Modal, Excel (.xlsx) Export, and Emailing

(function () {
  'use strict';

  const STORAGE_KEY = 'mds_updrs_part3_data_v3';
  let scores = {}; // itemId -> 0..4 or null
  let currentSectionIndex = 0; // 0 to 6 (7 pages)
  let isViewAllMode = false;

  // Motor Domains for Clinical Subscores
  const MOTOR_DOMAINS = [
    { name: 'Speech & Facial Expression', itemIds: ['3.1', '3.2'], max: 8 },
    { name: 'Rigidity', itemIds: ['3.3a', '3.3b', '3.3c', '3.3d', '3.3e'], max: 20 },
    { name: 'Bradykinesia', itemIds: ['3.4a', '3.4b', '3.5a', '3.5b', '3.6a', '3.6b', '3.7a', '3.7b', '3.8a', '3.8b'], max: 40 },
    { name: 'Gait, Postural Stability & Posture', itemIds: ['3.9', '3.10', '3.11', '3.12', '3.13'], max: 20 },
    { name: 'Global Movement & Tremor', itemIds: ['3.14', '3.15a', '3.15b', '3.16a', '3.16b'], max: 20 },
    { name: 'Rest Tremor', itemIds: ['3.17a', '3.17b', '3.17c', '3.17d', '3.17e', '3.18'], max: 24 }
  ];

  // Always start freshly on app open: clean slate, scores empty (0 total score), no patient ID or session ID
  function loadState() {
    scores = {};
    currentSectionIndex = 0;
    isViewAllMode = false;

    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      console.warn('Could not clear saved state', e);
    }

    const patientInput = document.getElementById('patientId');
    if (patientInput) {
      patientInput.value = '';
      patientInput.classList.remove('input-error');
    }

    const sessionInput = document.getElementById('sessionId');
    if (sessionInput) {
      sessionInput.value = '';
      sessionInput.classList.remove('input-error');
    }

    ['patientName', 'updrsNumber', 'lastLevodopaDose'].forEach(id => {
      const input = document.getElementById(id);
      if (input) input.value = '';
    });
    const levodopaStatus = document.getElementById('levodopaStatus');
    if (levodopaStatus) levodopaStatus.value = 'UNKNOWN';

    const dateInput = document.getElementById('examDate');
    if (dateInput) {
      dateInput.value = new Date().toISOString().split('T')[0];
    }
  }

  // Patient identifiers are optional in the MDS-UPDRS examination workflow.
  function validateRequiredPatientInfo() {
    return true;
  }

  function saveState() {
    const patientData = {
      patientName: document.getElementById('patientName').value,
      patientId: document.getElementById('patientId').value,
      sessionId: document.getElementById('sessionId').value,
      updrsNumber: document.getElementById('updrsNumber').value,
      examDate: document.getElementById('examDate').value,
      medState: document.getElementById('medState').value,
      pdMedicationStatus: document.getElementById('pdMedicationStatus').value,
      levodopaStatus: document.getElementById('levodopaStatus').value,
      lastLevodopaDose: document.getElementById('lastLevodopaDose').value,
      clinicianName: document.getElementById('clinicianName').value,
      recipientEmail: document.getElementById('recipientEmail').value,
      clinicalNotes: document.getElementById('clinicalNotes').value,
      dyskinesiaPresent: document.getElementById('dyskinesiaPresent').value,
      dyskinesiaInterference: document.getElementById('dyskinesiaInterference').value,
      hoehnYahrStage: document.getElementById('hoehnYahrStage').value
    };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        scores,
        currentSectionIndex,
        patient: patientData
      }));
    } catch (e) {
      console.warn('Could not save state', e);
    }
  }

  // Calculate score stats & domain breakdowns
  function calculateStats() {
    let total = 0;
    let scoredCount = 0;
    const totalItems = MDS_UPDRS_PART_III_ITEMS.length;

    MDS_UPDRS_PART_III_ITEMS.forEach(item => {
      const s = scores[item.id];
      if (s !== undefined && s !== null) {
        if (typeof s === 'number') total += s;
        scoredCount++;
      }
    });

    let severityText = 'Normal (0)';
    let severityClass = 'badge-normal';

    if (total === 0 && scoredCount === 0) {
      severityText = 'Unrated (0)';
      severityClass = 'badge-normal';
    } else if (total === 0) {
      severityText = 'Normal (0)';
      severityClass = 'badge-normal';
    } else if (total <= 32) {
      severityText = `Mild (${total})`;
      severityClass = 'badge-mild';
    } else if (total <= 58) {
      severityText = `Moderate (${total})`;
      severityClass = 'badge-moderate';
    } else {
      severityText = `Severe (${total})`;
      severityClass = 'badge-severe';
    }

    // Domain subscores
    const domainStats = MOTOR_DOMAINS.map(d => {
      let dScore = 0;
      let dRated = 0;
      d.itemIds.forEach(id => {
        if (scores[id] !== undefined && scores[id] !== null) {
          if (typeof scores[id] === 'number') dScore += scores[id];
          dRated++;
        }
      });
      return {
        name: d.name,
        score: dScore,
        max: d.max,
        ratedCount: dRated,
        totalCount: d.itemIds.length
      };
    });

    return { total, scoredCount, totalItems, severityText, severityClass, domainStats };
  }

  // Update HUD
  function updateScoreHUD() {
    const stats = calculateStats();

    document.getElementById('totalScore').textContent = stats.total;
    const pct = Math.round((stats.scoredCount / stats.totalItems) * 100);
    document.getElementById('progressText').textContent = `${stats.scoredCount} of ${stats.totalItems} items scored (${pct}%)`;
    document.getElementById('progressBarFill').style.width = `${pct}%`;

    // Severity Level display commented out while scoring for now
    /*
    const badge = document.getElementById('severityBadge');
    if (badge) {
      badge.className = `badge ${stats.severityClass}`;
      badge.textContent = stats.severityText;
    }
    */

    const printSummary = document.getElementById('printScoreSummary');
    if (printSummary) {
      printSummary.textContent = `Part III Score: ${stats.total} / 132`;
    }

    updateStepperNav();
    renderSummarySection();
    saveState();
  }

  // Render Stepper Navigation
  function updateStepperNav() {
    const nav = document.getElementById('stepperNav');
    nav.innerHTML = '';

    MDS_UPDRS_SECTIONS.forEach((sec, idx) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'step-tab';
      if (idx === currentSectionIndex && !isViewAllMode) {
        btn.classList.add('active');
      }

      let completedInSec = 0;
      sec.itemIds.forEach(id => {
        if (scores[id] !== undefined && scores[id] !== null) {
          completedInSec++;
        }
      });
      const isComplete = sec.itemIds.length > 0 && completedInSec === sec.itemIds.length;
      if (isComplete) {
        btn.classList.add('completed');
      }

      const num = document.createElement('span');
      num.className = 'step-tab-num';
      num.textContent = isComplete ? '✓' : sec.number;

      const title = document.createElement('span');
      title.textContent = sec.title;

      const badge = document.createElement('span');
      badge.className = 'step-tab-badge';
      badge.textContent = sec.itemIds.length > 0 ? `${completedInSec}/${sec.itemIds.length}` : 'Report';

      btn.appendChild(num);
      btn.appendChild(title);
      btn.appendChild(badge);

      btn.addEventListener('click', () => {
        if (idx > 0 && !validateRequiredPatientInfo()) {
          return;
        }
        if (isViewAllMode) {
          isViewAllMode = false;
          document.getElementById('viewAllToggle').checked = false;
          document.getElementById('toggleViewText').textContent = 'Paginated';
        }
        goToPage(idx);
      });

      nav.appendChild(btn);
    });
  }

  // Navigate to Page (0 to 6)
  function goToPage(index) {
    if (index > 0 && !validateRequiredPatientInfo()) {
      return;
    }
    currentSectionIndex = index;
    const sec = MDS_UPDRS_SECTIONS[currentSectionIndex];

    const patientCard = document.getElementById('patientCard');
    const banner = document.getElementById('sectionHeaderBanner');
    const itemsSection = document.getElementById('itemsSection');
    const summarySection = document.getElementById('summarySection');
    const pageNavBar = document.getElementById('pageNavBar');

    // Show patient info card ONLY on Page 1 (index 0) or in All Items mode
    if (patientCard) {
      if (isViewAllMode || currentSectionIndex === 0) {
        patientCard.style.display = 'block';
      } else {
        patientCard.style.display = 'none';
      }
    }

    if (isViewAllMode) {
      banner.style.display = 'none';
      itemsSection.style.display = 'flex';
      summarySection.style.display = 'block';
      pageNavBar.style.display = 'none';
      renderSummarySection();
      renderItems();
      return;
    }

    pageNavBar.style.display = 'flex';

    if (sec.id === 'summary-report') {
      banner.style.display = 'none';
      itemsSection.style.display = 'none';
      summarySection.style.display = 'block';
      renderSummarySection();
    } else {
      banner.style.display = 'flex';
      itemsSection.style.display = 'flex';
      summarySection.style.display = 'none';

      document.getElementById('currentSectionBadge').textContent = `Page ${sec.number} of 7`;
      document.getElementById('currentSectionTitle').textContent = `${sec.number}. ${sec.title}`;
      document.getElementById('currentSectionSubtitle').textContent = sec.subtitle;

      renderItems();
    }

    const btnPrev = document.getElementById('btnPrevPage');
    const btnNext = document.getElementById('btnNextPage');
    const btnDoneBottom = document.getElementById('btnDoneBottom');
    const pageIndicator = document.getElementById('pageIndicatorText');

    btnPrev.disabled = currentSectionIndex === 0;

    // Bottom "Done" button is ONLY shown in the end (Page 7: Summary & Report) or in View All mode
    if (btnDoneBottom) {
      if (currentSectionIndex === MDS_UPDRS_SECTIONS.length - 1 || isViewAllMode) {
        btnDoneBottom.style.display = 'inline-flex';
      } else {
        btnDoneBottom.style.display = 'none';
      }
    }

    if (currentSectionIndex === MDS_UPDRS_SECTIONS.length - 1) {
      btnNext.style.display = 'none';
    } else {
      btnNext.style.display = 'inline-flex';
      const nextSec = MDS_UPDRS_SECTIONS[currentSectionIndex + 1];
      if (currentSectionIndex === MDS_UPDRS_SECTIONS.length - 2) {
        btnNext.innerHTML = `Complete & View Summary <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>`;
      } else {
        btnNext.innerHTML = `Next: ${nextSec.title} <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>`;
      }
    }

    pageIndicator.textContent = `Page ${currentSectionIndex + 1} of 7 · ${sec.title}`;

    updateStepperNav();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Render assessment cards for active section or all
  function renderItems() {
    const container = document.getElementById('itemsContainer');
    container.innerHTML = '';

    const sec = MDS_UPDRS_SECTIONS[currentSectionIndex];
    let itemsToRender = MDS_UPDRS_PART_III_ITEMS;

    if (!isViewAllMode && sec.itemIds.length > 0) {
      itemsToRender = MDS_UPDRS_PART_III_ITEMS.filter(it => sec.itemIds.includes(it.id));
    }

    itemsToRender.forEach((item) => {
      const card = document.createElement('div');
      card.className = 'item-card';
      card.id = `item-card-${item.id}`;
      card.setAttribute('tabindex', '0');
      card.setAttribute('data-id', item.id);

      const currentScore = scores[item.id];
      if (currentScore !== undefined && currentScore !== null) {
        card.classList.add('is-scored');
      }

      // Card Header
      const header = document.createElement('div');
      header.className = 'item-header';

      const titleGroup = document.createElement('div');
      titleGroup.className = 'item-title-group';

      const numberBadge = document.createElement('span');
      numberBadge.className = 'item-number';
      numberBadge.textContent = `#${item.id}`;

      const title = document.createElement('span');
      title.className = 'item-name';
      title.textContent = item.name;

      titleGroup.appendChild(numberBadge);
      titleGroup.appendChild(title);

      // Sensor badge intentionally hidden during scoring (still visible in summary table)

      const actions = document.createElement('div');
      actions.className = 'item-actions';

      const clearBtn = document.createElement('button');
      clearBtn.type = 'button';
      clearBtn.className = 'btn-clear-item';
      clearBtn.title = 'Clear this score';
      clearBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      `;
      clearBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        setScore(item.id, null);
      });
      actions.appendChild(clearBtn);

      header.appendChild(titleGroup);
      header.appendChild(actions);
      card.appendChild(header);

      // Question
      if (item.question) {
        const question = document.createElement('div');
        question.className = 'item-question';
        question.textContent = item.question;
        card.appendChild(question);
      }

      // Rating Buttons (0 to 4)
      const ratingGroup = document.createElement('div');
      ratingGroup.className = 'rating-group';

      [0, 1, 2, 3, 4, 'UR'].forEach(s => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'score-btn';
        btn.setAttribute('data-score', s);
        if (currentScore === s) {
          btn.classList.add('selected');
        }

        const btnTop = document.createElement('div');
        btnTop.className = 'score-btn-top';

        const numSpan = document.createElement('span');
        numSpan.className = 'score-num';
        numSpan.textContent = s;

        btnTop.appendChild(numSpan);

        const labelSpan = document.createElement('span');
        labelSpan.className = 'score-label';
        labelSpan.textContent = item.options[s] || '';

        btn.appendChild(btnTop);
        btn.appendChild(labelSpan);

        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          if (scores[item.id] === s) {
            setScore(item.id, null);
          } else {
            setScore(item.id, s);
          }
        });

        ratingGroup.appendChild(btn);
      });

      card.appendChild(ratingGroup);
      container.appendChild(card);
    });

    applyFilter();
  }

  // Set Score
  function setScore(itemId, score) {
    if (score === null) {
      delete scores[itemId];
    } else {
      scores[itemId] = score;
    }

    const card = document.getElementById(`item-card-${itemId}`);
    if (card) {
      if (score === null) {
        card.classList.remove('is-scored');
      } else {
        card.classList.add('is-scored');
      }

      const buttons = card.querySelectorAll('.score-btn');
      buttons.forEach(btn => {
        const btnScore = parseInt(btn.getAttribute('data-score'), 10);
        if (btnScore === score) {
          btn.classList.add('selected');
        } else {
          btn.classList.remove('selected');
        }
      });
    }

    updateScoreHUD();
  }

  // Filter & Search
  function applyFilter() {
    const query = document.getElementById('searchInput').value.trim().toLowerCase();
    const filter = document.getElementById('filterStatus').value;

    const cards = document.querySelectorAll('.item-card');
    cards.forEach(card => {
      const itemId = parseInt(card.getAttribute('data-id'), 10);
      const item = MDS_UPDRS_PART_III_ITEMS.find(i => i.id === itemId);
      if (!item) return;

      const score = scores[itemId];
      const hasScore = score !== undefined && score !== null;

      let matchesStatus = true;
      if (filter === 'unrated') {
        matchesStatus = !hasScore;
      } else if (filter === 'positive') {
        matchesStatus = hasScore && score > 0;
      }

      let matchesQuery = true;
      if (query) {
        const text = `${item.id} ${item.name} ${item.question} ${item.sensor} ${Object.values(item.options).join(' ')}`.toLowerCase();
        matchesQuery = text.includes(query);
      }

      if (matchesStatus && matchesQuery) {
        card.style.display = 'flex';
      } else {
        card.style.display = 'none';
      }
    });
  }

  // Render Page 7: Final Summary Section
  function renderSummarySection() {
    const stats = calculateStats();

    // Sync Patient Details to Summary Card
    const patientName = document.getElementById('patientName').value.trim() || 'Not provided';
    const pId = document.getElementById('patientId').value.trim() || 'Not provided';
    const sId = document.getElementById('sessionId').value.trim() || 'Not provided';
    const updrsNumber = document.getElementById('updrsNumber').value.trim() || 'Not provided';
    const examDate = document.getElementById('examDate').value || new Date().toISOString().split('T')[0];
    const clinician = document.getElementById('clinicianName').value || '—';
    const medState = document.getElementById('medState').value;
    const pdMedicationStatus = document.getElementById('pdMedicationStatus').value;
    const levodopaStatus = document.getElementById('levodopaStatus').value;
    const lastLevodopaDose = document.getElementById('lastLevodopaDose').value;
    const dyskinesiaPresent = document.getElementById('dyskinesiaPresent').value;
    const dyskinesiaInterference = document.getElementById('dyskinesiaInterference').value;
    const hoehnYahrStage = document.getElementById('hoehnYahrStage').value || 'Not recorded';
    const notes = document.getElementById('clinicalNotes').value;

    const patientSessionEl = document.getElementById('summaryPatientSession');
    if (patientSessionEl) patientSessionEl.textContent = `${patientName} · ${pId} · ${sId}`;

    const examinerDateEl = document.getElementById('summaryExaminerDate');
    if (examinerDateEl) examinerDateEl.textContent = `${clinician} (${examDate})`;

    const notesBlock = document.getElementById('summaryNotesBlock');
    const notesText = document.getElementById('summaryNotesText');
    if (notesBlock && notesText) {
      if (notes.trim()) {
        notesBlock.style.display = 'block';
        notesText.textContent = notes;
      } else {
        notesBlock.style.display = 'none';
      }

      const dyskinesiaBlock = document.getElementById('summaryDyskinesiaBlock');
      const dyskinesiaText = document.getElementById('summaryDyskinesiaText');
      if (dyskinesiaBlock && dyskinesiaText) {
        dyskinesiaText.textContent = `${dyskinesiaPresent} · Interfered with ratings: ${dyskinesiaInterference}`;
        dyskinesiaBlock.style.display = 'block';
      }
    }

    const totalEl = document.getElementById('summaryTotalScore');
    if (totalEl) totalEl.textContent = stats.total;

    const sevEl = document.getElementById('summarySeverityText');
    if (sevEl) sevEl.textContent = stats.severityText;

    const compEl = document.getElementById('summaryCompletionText');
    if (compEl) compEl.textContent = `${stats.scoredCount} / 33 (${Math.round((stats.scoredCount / 33) * 100)}%)`;

    const medEl = document.getElementById('summaryMedState');
    if (medEl) medEl.textContent = `${medState}${levodopaStatus === 'YES' && lastLevodopaDose ? ` · Last levodopa: ${lastLevodopaDose}` : ''}`;

    // Render domain cards on Page 7
    const domainGrid = document.getElementById('domainGrid');
    if (domainGrid) {
      domainGrid.innerHTML = '';
      stats.domainStats.forEach(d => {
        const item = document.createElement('div');
        item.className = 'domain-item';
        item.innerHTML = `
          <div class="domain-item-title">${d.name} (${d.ratedCount}/${d.totalCount})</div>
          <div class="domain-item-score">${d.score} / ${d.max}</div>
        `;
        domainGrid.appendChild(item);
      });
    }

    const tbody = document.getElementById('summaryTableBody');
    tbody.innerHTML = '';

    MDS_UPDRS_PART_III_ITEMS.forEach(item => {
      const s = scores[item.id];
      const hasScore = s !== undefined && s !== null;

      const tr = document.createElement('tr');

      const tdNum = document.createElement('td');
      tdNum.innerHTML = `<strong>#${item.id}</strong>`;

      const tdName = document.createElement('td');
      tdName.innerHTML = `<div><strong>${item.name}</strong></div><div style="color: #64748b; font-size: 0.8rem;">${item.question || ''}</div>`;

      const tdScore = document.createElement('td');
      tdScore.style.textAlign = 'center';
      if (hasScore) {
        tdScore.innerHTML = `<span class="score-pill score-${s}">${s}</span>`;
      } else {
        tdScore.innerHTML = `<span class="score-pill unrated">—</span>`;
      }

      const tdAnchor = document.createElement('td');
      tdAnchor.textContent = hasScore ? (item.options[s] || '') : 'Not rated';
      if (!hasScore) {
        tdAnchor.style.color = '#94a3b8';
        tdAnchor.style.fontStyle = 'italic';
      }

      tr.appendChild(tdNum);
      tr.appendChild(tdName);
      tr.appendChild(tdScore);
      tr.appendChild(tdAnchor);

      tbody.appendChild(tr);
    });
  }

  // Done Modal Handler: Show stats, domain breakdown, save/send options
  function openDoneModal() {
    if (!validateRequiredPatientInfo()) {
      return;
    }
    const stats = calculateStats();
    const patientName = document.getElementById('patientName').value.trim() || 'Not provided';
    const patientId = document.getElementById('patientId').value.trim() || 'Not provided';
    const sessionId = document.getElementById('sessionId').value.trim() || 'Not provided';
    const updrsNumber = document.getElementById('updrsNumber').value.trim() || 'Not provided';
    const medState = document.getElementById('medState').value;
    const pdMedicationStatus = document.getElementById('pdMedicationStatus').value;
    const levodopaStatus = document.getElementById('levodopaStatus').value;
    const lastLevodopaDose = document.getElementById('lastLevodopaDose').value;
    const dyskinesiaPresent = document.getElementById('dyskinesiaPresent').value;
    const dyskinesiaInterference = document.getElementById('dyskinesiaInterference').value;
    const hoehnYahrStage = document.getElementById('hoehnYahrStage').value || 'Not recorded';

    document.getElementById('modalTotalScore').textContent = stats.total;
    const modalBadge = document.getElementById('modalSeverityBadge');
    if (modalBadge) {
      modalBadge.className = `badge ${stats.severityClass}`;
      modalBadge.textContent = stats.severityText;
    }

    document.getElementById('modalPatientLine').textContent = `Patient: ${patientName} · ID: ${patientId} · Session: ${sessionId} · MDS-UPDRS No.: ${updrsNumber} · Medication: ${medState}${levodopaStatus === 'YES' && lastLevodopaDose ? ` · Last levodopa: ${lastLevodopaDose}` : ''}`;
    document.getElementById('modalCompletionLine').textContent = `${stats.scoredCount} of 33 items evaluated (${Math.round((stats.scoredCount / 33) * 100)}%)`;

    // Populate domains grid inside modal
    const modalDomainGrid = document.getElementById('modalDomainGrid');
    modalDomainGrid.innerHTML = '';
    stats.domainStats.forEach(d => {
      const el = document.createElement('div');
      el.className = 'domain-item';
      el.innerHTML = `
        <span class="domain-item-title">${d.name}</span>
        <span class="domain-item-score">${d.score} / ${d.max}</span>
      `;
      modalDomainGrid.appendChild(el);
    });

    document.getElementById('doneModal').classList.add('show');

  }

  function closeDoneModal() {
    document.getElementById('doneModal').classList.remove('show');
  }

  function resetForNewAssessment() {
    scores = {};
    currentSectionIndex = 0;
    isViewAllMode = false;

    ['patientName', 'patientId', 'sessionId', 'updrsNumber', 'lastLevodopaDose', 'clinicianName', 'recipientEmail', 'clinicalNotes'].forEach(id => {
      const input = document.getElementById(id);
      if (input) input.value = '';
    });

    ['levodopaStatus', 'pdMedicationStatus', 'dyskinesiaPresent', 'dyskinesiaInterference'].forEach(id => {
      const select = document.getElementById(id);
      if (select) select.value = 'UNKNOWN';
    });
    const medState = document.getElementById('medState');
    if (medState) medState.value = 'ON';
    const hoehnYahrStage = document.getElementById('hoehnYahrStage');
    if (hoehnYahrStage) hoehnYahrStage.value = '';
    const examDate = document.getElementById('examDate');
    if (examDate) examDate.value = new Date().toISOString().split('T')[0];

    const viewToggle = document.getElementById('viewAllToggle');
    if (viewToggle) viewToggle.checked = false;
    document.getElementById('toggleViewText').textContent = 'Paginated';
    document.getElementById('searchInput').value = '';
    document.getElementById('filterStatus').value = 'all';
    closeDoneModal();
    goToPage(0);
    renderItems();
    updateScoreHUD();
    showToast('✓ Log saved successfully. Assessment cleared and ready for the next patient.');
  }

  async function saveLogAndStartNewAssessment() {
    const saveButton = document.getElementById('btnModalSaveLog');
    saveButton.disabled = true;
    saveButton.textContent = 'Saving...';
    const saved = await logToVercel(false);
    saveButton.disabled = false;
    saveButton.textContent = 'Save Log';
    if (saved) {
      resetForNewAssessment();
    }
  }

  // Quick Action: Mark all unrated items as 0 (Normal)
  function quickBaseline() {
    let filled = 0;
    MDS_UPDRS_PART_III_ITEMS.forEach(item => {
      if (scores[item.id] === undefined || scores[item.id] === null) {
        scores[item.id] = 0;
        filled++;
      }
    });
    renderItems();
    updateScoreHUD();
    showToast(`Marked ${filled} unrated items as 0 (Normal).`);
  }

  // Quick Action: Clear all scores
  function clearAll() {
    if (Object.keys(scores).length === 0) {
      showToast('Scores are already empty.');
      return;
    }
    if (confirm('Are you sure you want to clear all 33 scores?')) {
      scores = {};
      renderItems();
      updateScoreHUD();
      showToast('All scores have been reset.');
    }
  }

  // Clinical Summary Text Generation
  function generateSummaryText() {
    const patientName = document.getElementById('patientName').value.trim() || 'N/A';
    const patientId = document.getElementById('patientId').value.trim() || 'N/A';
    const sessionId = document.getElementById('sessionId').value.trim() || 'N/A';
    const updrsNumber = document.getElementById('updrsNumber').value.trim() || 'N/A';
    const examDate = document.getElementById('examDate').value || new Date().toISOString().split('T')[0];
    const medState = document.getElementById('medState').value;
    const pdMedicationStatus = document.getElementById('pdMedicationStatus').value;
    const levodopaStatus = document.getElementById('levodopaStatus').value;
    const lastLevodopaDose = document.getElementById('lastLevodopaDose').value;
    const dyskinesiaPresent = document.getElementById('dyskinesiaPresent').value;
    const dyskinesiaInterference = document.getElementById('dyskinesiaInterference').value;
    const doctor = document.getElementById('clinicianName').value || 'N/A';
    const notes = document.getElementById('clinicalNotes').value;

    const stats = calculateStats();
    const itemLines = [];

    MDS_UPDRS_PART_III_ITEMS.forEach(item => {
      const s = scores[item.id];
      if (s !== undefined && s !== null) {
        itemLines.push(`  - #${item.id} ${item.name}: ${s} (${item.options[s] || ''})`);
      } else {
        itemLines.push(`  - #${item.id} ${item.name}: UNRATED`);
      }
    });

    const domainLines = stats.domainStats.map(d => `  - ${d.name}: ${d.score} / ${d.max}`).join('\n');

    return `MDS-UPDRS PART III: MOTOR FUNCTION EXAMINATION REPORT
============================================================
Patient Name:      ${patientName}
Patient ID:        ${patientId}
Session ID:        ${sessionId}
MDS-UPDRS Number:  ${updrsNumber}
Assessment Date:   ${examDate}
Medication State:  ${medState}
PD Medication:      ${pdMedicationStatus}
Levodopa:          ${levodopaStatus}
Last Levodopa:     ${lastLevodopaDose || 'N/A'}
 dyskinesia:       ${dyskinesiaPresent}
Dyskinesia impact:  ${dyskinesiaInterference}
Hoehn & Yahr stage:  ${hoehnYahrStage}
Examiner:          ${doctor}
${notes ? `Clinical Notes:   ${notes}\n` : ''}
TOTAL SCORE:       ${stats.total} / 132 points
Severity Category: ${stats.severityText} (${stats.scoredCount}/33 items evaluated)

MOTOR DOMAIN SUBSCORES:
${domainLines}

============================================================
ITEM-BY-ITEM EVALUATION (33 Items):
${itemLines.join('\n')}
============================================================
Report generated by MDS-UPDRS Scoring Tool on ${new Date().toLocaleString()}
`;
  }

  function copySummary() {
    const text = generateSummaryText();
    navigator.clipboard.writeText(text).then(() => {
      showToast('Clinical summary copied to clipboard!');
    }).catch(() => {
      showToast('Failed to copy. Please allow clipboard permissions.');
    });
  }

  // Vercel Serverless Function & Local Log Storage
  const LOCAL_LOGS_KEY = 'mds_updrs_client_logged_evaluations_v1';

  function getLocalLogs() {
    try {
      return JSON.parse(localStorage.getItem(LOCAL_LOGS_KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  // Only deduplicate when both stable identifiers are present; optional identifiers
  // must not cause separate assessments to overwrite each other.
  function getPatientSessionKey(record) {
    const p = (record.patientId || '').trim().toLowerCase();
    const s = (record.sessionId || '').trim().toLowerCase();
    if (!p || !s) return record.id || `${record.timestamp || Date.now()}|${record.patientName || ''}`;
    return `${p}|${s}`;
  }

  // Show duplicate-warning modal; returns Promise<true> = overwrite, Promise<false> = skip
  function showDuplicateModal(record, existingRecord) {
    return new Promise((resolve) => {
      const modal = document.getElementById('duplicateModal');
      const msgEl = document.getElementById('duplicateModalMsg');
      const btnSkip = document.getElementById('btnDuplicateSkip');
      const btnContinue = document.getElementById('btnDuplicateContinue');

      const existingDate = existingRecord.examDate || 'previous date';
      const existingTime = existingRecord.timestamp ? new Date(existingRecord.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
      const patient = record.patientId || 'Not provided';
      const session = record.sessionId || 'Not provided';

      msgEl.textContent =
        `A log for Patient "${patient}" · Session "${session}" already exists (recorded on ${existingDate}${existingTime ? ' at ' + existingTime : ''}). ` +
        `Choose Skip to keep the existing record, or Continue to take this latest version.`;

      modal.classList.add('show');

      function cleanup(result) {
        modal.classList.remove('show');
        btnSkip.removeEventListener('click', onSkip);
        btnContinue.removeEventListener('click', onContinue);
        resolve(result);
      }

      function onSkip() { cleanup(false); }
      function onContinue() { cleanup(true); }

      btnSkip.addEventListener('click', onSkip);
      btnContinue.addEventListener('click', onContinue);
    });
  }

  async function saveLocalLog(record, skipDuplicateCheck = false) {
    const list = getLocalLogs();
    const recordKey = getPatientSessionKey(record);
    const existingIndex = list.findIndex(r => getPatientSessionKey(r) === recordKey);

    if (existingIndex >= 0 && !skipDuplicateCheck) {
      const existing = list[existingIndex];
      const overwrite = await showDuplicateModal(record, existing);

      if (!overwrite) {
        showToast(`Skipped: Kept existing log for ${record.patientId} · ${record.sessionId}.`);
        return false; // Signal: not saved
      }
      // User chose Continue: overwrite with the latest version
      list[existingIndex] = record;
      showToast(`Updated log for ${record.patientId} · ${record.sessionId} with latest date & scores.`);
    } else if (existingIndex >= 0 && skipDuplicateCheck) {
      list[existingIndex] = record;
    } else {
      list.unshift(record);
    }

    if (list.length > 100) list.pop();
    try {
      localStorage.setItem(LOCAL_LOGS_KEY, JSON.stringify(list));
    } catch (e) {
      console.warn('LocalStorage save error:', e);
    }
    return true; // Signal: saved successfully
  }

  async function logToVercel(silent = true) {
    const patientName = document.getElementById('patientName').value.trim();
    const patientId = document.getElementById('patientId').value.trim();
    const sessionId = document.getElementById('sessionId').value.trim();
    const updrsNumber = document.getElementById('updrsNumber').value.trim();
    const examDate = document.getElementById('examDate').value || new Date().toISOString().split('T')[0];
    const medState = document.getElementById('medState').value;
    const pdMedicationStatus = document.getElementById('pdMedicationStatus').value;
    const levodopaStatus = document.getElementById('levodopaStatus').value;
    const lastLevodopaDose = document.getElementById('lastLevodopaDose').value;
    const dyskinesiaPresent = document.getElementById('dyskinesiaPresent').value;
    const dyskinesiaInterference = document.getElementById('dyskinesiaInterference').value;
    const hoehnYahrStage = document.getElementById('hoehnYahrStage').value;
    const clinicianName = document.getElementById('clinicianName').value.trim();
    const recipientEmail = document.getElementById('recipientEmail').value.trim();
    const clinicalNotes = document.getElementById('clinicalNotes').value.trim();
    const stats = calculateStats();

    const record = {
      id: `LOG_${Date.now()}`,
      timestamp: new Date().toISOString(),
      patientId,
      sessionId,
      patientName,
      updrsNumber,
      examDate,
      medState,
      pdMedicationStatus,
      levodopaStatus,
      lastLevodopaDose,
      dyskinesiaPresent,
      dyskinesiaInterference,
      hoehnYahrStage,
      clinicianName,
      recipientEmail,
      clinicalNotes,
      totalScore: stats.total,
      scoredCount: stats.scoredCount,
      domainStats: stats.domainStats,
      scores
    };

    // Save to client-side database; if user declines duplicate overwrite, abort
    const wasSaved = await saveLocalLog(record);
    if (!wasSaved) {
      // User chose to keep existing record — do not log to Vercel either
      const statusEl = document.getElementById('vercelLogStatusText');
      if (statusEl) statusEl.textContent = `Existing log kept for ${patientId}.`;
      return false;
    }

    const statusEl = document.getElementById('vercelLogStatusText');
    if (statusEl) {
      statusEl.textContent = `Logging patient ${patientId} to Vercel...`;
    }

    try {
      const response = await fetch('/api/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(record)
      });

      if (response.ok) {
        if (statusEl) statusEl.textContent = `Saved to Vercel logs & database! (${patientId})`;
        if (!silent) showToast(`Patient ${patientId} saved to Vercel logs! ✓`);
        return true;
      } else {
        console.warn('Vercel logger returned status:', response.status);
        if (statusEl) statusEl.textContent = `Saved in local logs (offline mode).`;
        if (!silent) showToast('Saved in local logs. Server logging was unavailable.');
        return true;
      }
    } catch (err) {
      console.warn('Vercel log network issue (stored locally):', err);
      if (statusEl) statusEl.textContent = `Saved in local logs (offline mode).`;
      if (!silent) showToast('Saved in local logs. Server logging was unavailable.');
      return true;
    }
  }

  // Export native Excel (.xlsx) file
  function exportExcel() {
    if (!validateRequiredPatientInfo()) {
      return;
    }
    if (typeof XLSX === 'undefined') {
      showToast('Excel library loading... Please try again in a moment.');
      return;
    }

    const { wb, filename } = buildWorkbookData();
    XLSX.writeFile(wb, filename);
    showToast(`Excel spreadsheet saved: ${filename}`);

    // Automatically record to Vercel & local database
    logToVercel(true);
  }

  // Helper to build workbook
  function buildWorkbookData() {
    const patientName = document.getElementById('patientName').value.trim() || 'Not provided';
    const patientId = document.getElementById('patientId').value.trim() || 'Patient';
    const sessionId = document.getElementById('sessionId').value.trim() || 'Session';
    const updrsNumber = document.getElementById('updrsNumber').value.trim() || 'Not provided';
    const examDate = document.getElementById('examDate').value || new Date().toISOString().split('T')[0];
    const medState = document.getElementById('medState').value;
    const pdMedicationStatus = document.getElementById('pdMedicationStatus').value;
    const levodopaStatus = document.getElementById('levodopaStatus').value;
    const lastLevodopaDose = document.getElementById('lastLevodopaDose').value || 'Not provided';
    const doctor = document.getElementById('clinicianName').value || 'Unspecified';
    const notes = document.getElementById('clinicalNotes').value || '';
    const dyskinesiaPresent = document.getElementById('dyskinesiaPresent').value;
    const dyskinesiaInterference = document.getElementById('dyskinesiaInterference').value;
    const hoehnYahrStage = document.getElementById('hoehnYahrStage').value || 'Not recorded';

    const stats = calculateStats();

    // 1. Data rows for Part III Items
    const part3Data = [
      ['MDS-UPDRS Part III: Motor Function Examination Record'],
      [],
      ['Patient Name', patientName, 'Patient ID', patientId],
      ['Session ID', sessionId, 'MDS-UPDRS Number', updrsNumber],
      ['Assessment Date', examDate, 'Medication State', medState],
      ['PD Medication', pdMedicationStatus, 'Levodopa', levodopaStatus],
      ['Last Levodopa Dose', lastLevodopaDose, 'Dyskinesia Present', dyskinesiaPresent],
      ['Interfered with Ratings', dyskinesiaInterference],
      ['Hoehn & Yahr Stage', hoehnYahrStage],
      ['Examiner / Doctor', doctor, 'Total Motor Score', `${stats.total} / 132`],
      ['Clinical Notes', notes],
      [],
      ['Item #', 'Category / Domain', 'Item Name', 'Clinical Examination Prompt', 'Score (0-4)', 'Clinical Finding / Definition']
    ];

    function getDomainForItem(id) {
      for (const d of MOTOR_DOMAINS) {
        if (d.itemIds.includes(id)) return d.name;
      }
      return 'Motor Examination';
    }

    MDS_UPDRS_PART_III_ITEMS.forEach(item => {
      const s = scores[item.id] !== undefined && scores[item.id] !== null ? scores[item.id] : '';
      const def = s !== '' ? (item.options[s] || '') : 'UNRATED';
      part3Data.push([
        item.id,
        getDomainForItem(item.id),
        item.name,
        item.question,
        s,
        def
      ]);
    });

    // 2. Data rows for Domain Summary sheet
    const domainData = [
      ['Motor Domain Summary (MDS-UPDRS Part III)'],
      [],
      ['Patient Name', patientName, 'Patient ID', patientId],
      ['Session ID', sessionId, 'MDS-UPDRS Number', updrsNumber],
      ['Date', examDate, 'Medication State', medState],
      ['PD Medication', pdMedicationStatus, 'Levodopa', levodopaStatus],
      ['Last Levodopa Dose', lastLevodopaDose, 'Dyskinesia Present', dyskinesiaPresent],
      ['Interfered with Ratings', dyskinesiaInterference],
      ['Hoehn & Yahr Stage', hoehnYahrStage],
      [],
      ['Motor Domain', 'Items Included', 'Score Obtained', 'Max Possible', 'Percentage (%)']
    ];

    stats.domainStats.forEach(d => {
      const pct = Math.round((d.score / d.max) * 100);
      domainData.push([
        d.name,
        `${d.ratedCount} / ${d.totalCount}`,
        d.score,
        d.max,
        `${pct}%`
      ]);
    });

    domainData.push([
      'TOTAL PART III MOTOR SCORE',
      `${stats.scoredCount} / 33`,
      stats.total,
      132,
      `${Math.round((stats.total / 132) * 100)}%`
    ]);

    const wb = XLSX.utils.book_new();

    const wsPart3 = XLSX.utils.aoa_to_sheet(part3Data);
    wsPart3['!cols'] = [
      { wch: 8 },  // Item #
      { wch: 26 }, // Category
      { wch: 36 }, // Name
      { wch: 45 }, // Question
      { wch: 12 }, // Score
      { wch: 45 }  // Finding
    ];

    const wsDomains = XLSX.utils.aoa_to_sheet(domainData);
    wsDomains['!cols'] = [
      { wch: 32 },
      { wch: 16 },
      { wch: 16 },
      { wch: 14 },
      { wch: 16 }
    ];

    XLSX.utils.book_append_sheet(wb, wsPart3, 'MDS-UPDRS Part III');
    XLSX.utils.book_append_sheet(wb, wsDomains, 'Domain Summary');

    const filename = `Report-${patientId}-${sessionId}.xlsx`;
    return { wb, filename, patientId, sessionId };
  }

  // Send via Email: share excel with subject Report-patient-sessionid, no body text
  async function sendEmail() {
    if (!validateRequiredPatientInfo()) {
      return;
    }
    if (typeof XLSX === 'undefined') {
      showToast('Excel library loading... Please try again in a moment.');
      return;
    }

    const { wb, filename, patientId, sessionId } = buildWorkbookData();
    const recipient = document.getElementById('recipientEmail').value.trim();
    const subject = `Report-${patientId}-${sessionId}`;

    // Generate Excel File blob
    try {
      const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
      const excelBlob = new Blob([wbout], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });
      const excelFile = new File([excelBlob], filename, {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });

      // Try native Web Share API (attaches file directly into Mail app on macOS / iOS / Android)
      if (navigator.canShare && navigator.canShare({ files: [excelFile] })) {
        await navigator.share({
          files: [excelFile],
          title: subject
        });
        showToast(`Excel shared with subject: ${subject}`);
        return;
      }
    } catch (e) {
      if (e.name === 'AbortError') return;
      console.warn('Web share not supported or cancelled, using mailto fallback', e);
    }

    // Fallback for standard browsers: Download the Excel file and open mailto link with exact subject
    XLSX.writeFile(wb, filename);

    const mailtoUrl = `mailto:${encodeURIComponent(recipient)}?subject=${encodeURIComponent(subject)}`;
    window.location.href = mailtoUrl;

    showToast(`Excel saved (${filename}). Email draft opened with subject: ${subject}`);
  }

  function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 3200);
  }

  // Setup Event Listeners
  function setupEvents() {
    document.getElementById('btnQuickBaseline').addEventListener('click', quickBaseline);
    document.getElementById('btnClearAll').addEventListener('click', clearAll);
    document.getElementById('btnExportExcel').addEventListener('click', exportExcel);
    document.getElementById('btnSendEmail').addEventListener('click', sendEmail);
    document.getElementById('btnPrint').addEventListener('click', () => window.print());

    // Done Buttons
    document.getElementById('btnDoneHeader').addEventListener('click', openDoneModal);
    document.getElementById('btnDoneBottom').addEventListener('click', openDoneModal);

    // Modal Actions
    document.getElementById('btnCloseModal').addEventListener('click', closeDoneModal);
    document.getElementById('btnModalClose').addEventListener('click', closeDoneModal);
    document.getElementById('btnModalDownloadExcel').addEventListener('click', () => {
      exportExcel();
    });
    document.getElementById('btnModalSendEmail').addEventListener('click', () => {
      sendEmail();
    });
    document.getElementById('btnModalCopyText').addEventListener('click', () => {
      copySummary();
    });
    document.getElementById('btnModalSaveLog').addEventListener('click', saveLogAndStartNewAssessment);
    document.getElementById('btnModalViewReport').addEventListener('click', () => {
      closeDoneModal();
      goToPage(6); // Page 7: Summary & Report
    });

    // Close modal if clicking outside
    document.getElementById('doneModal').addEventListener('click', (e) => {
      if (e.target.id === 'doneModal') {
        closeDoneModal();
      }
    });

    // Summary Page Actions
    document.getElementById('btnSummaryExcel').addEventListener('click', exportExcel);
    document.getElementById('btnSummaryEmail').addEventListener('click', sendEmail);
    document.getElementById('btnSummaryCopy').addEventListener('click', copySummary);
    document.getElementById('btnSummaryPrint').addEventListener('click', () => window.print());

    document.getElementById('btnPrevPage').addEventListener('click', () => {
      if (currentSectionIndex > 0) {
        goToPage(currentSectionIndex - 1);
      }
    });

    document.getElementById('btnNextPage').addEventListener('click', () => {
      if (currentSectionIndex === 0 && !validateRequiredPatientInfo()) {
        return;
      }
      if (currentSectionIndex < MDS_UPDRS_SECTIONS.length - 1) {
        goToPage(currentSectionIndex + 1);
      }
    });

    // Toggle view mode: Paginated vs All Items
    const viewToggle = document.getElementById('viewAllToggle');
    viewToggle.addEventListener('change', (e) => {
      if (e.target.checked && !validateRequiredPatientInfo()) {
        e.target.checked = false;
        return;
      }
      isViewAllMode = e.target.checked;
      document.getElementById('toggleViewText').textContent = isViewAllMode ? 'All Items' : 'Paginated';
      goToPage(currentSectionIndex);
    });

    document.getElementById('searchInput').addEventListener('input', applyFilter);
    document.getElementById('filterStatus').addEventListener('change', applyFilter);

    ['patientId', 'sessionId'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('input', () => {
          if (el.value.trim()) el.classList.remove('input-error');
        });
      }
    });

    ['patientName', 'patientId', 'sessionId', 'updrsNumber', 'examDate', 'medState', 'pdMedicationStatus', 'levodopaStatus', 'lastLevodopaDose', 'clinicianName', 'recipientEmail', 'clinicalNotes', 'dyskinesiaPresent', 'dyskinesiaInterference', 'hoehnYahrStage'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('input', () => {
          saveState();
          renderSummarySection();
        });
        el.addEventListener('change', () => {
          saveState();
          renderSummarySection();
        });
      }
    });
  }

  function setupPWA() {
    // Register Service Worker
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('./sw.js').then((reg) => {
          console.log('PWA ServiceWorker registered with scope:', reg.scope);
        }).catch((err) => {
          console.warn('PWA ServiceWorker registration failed:', err);
        });
      });
    }

    // PWA Install prompt handling
    let deferredPrompt;
    const btnInstall = document.getElementById('btnInstallApp');

    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredPrompt = e;
      if (btnInstall) {
        btnInstall.style.display = 'inline-flex';
      }
    });

    if (btnInstall) {
      btnInstall.addEventListener('click', async () => {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          const { outcome } = await deferredPrompt.userChoice;
          if (outcome === 'accepted') {
            showToast('App installed successfully!');
          }
          deferredPrompt = null;
          btnInstall.style.display = 'none';
        } else {
          const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
          if (isIOS) {
            alert("To install as an app on your iPad/iPhone:\n1. Tap the Share button in Safari (square with arrow up)\n2. Select 'Add to Home Screen'\n3. Tap 'Add'");
          } else {
            showToast('To install: click the Install icon in your browser address bar.');
          }
        }
      });
    }

    window.addEventListener('appinstalled', () => {
      if (btnInstall) btnInstall.style.display = 'none';
      showToast('MDS-UPDRS Part III installed as application!');
    });
  }

  function init() {
    loadState();
    updateScoreHUD();
    setupEvents();
    setupPWA();
    goToPage(currentSectionIndex);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
