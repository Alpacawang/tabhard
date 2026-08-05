(function () {
  const teamDataNode = document.getElementById('ceremony-team-data');
  const originalTeams = teamDataNode ? JSON.parse(teamDataNode.textContent) : [];
  const state = {
    drawOrder: [],
    drawIndex: 0,
    pairings: [],
    firstSide: 'Prosecution',
    blockingMessage: '',
    manualSchoolSides: {},
    isSpinning: false,
    wheelRotation: 0,
    spinToken: 0,
  };

  const tabs = document.querySelectorAll('.draw-tab');
  const panels = document.querySelectorAll('.draw-panel');
  const drawButton = document.getElementById('draw-team');
  const resetButton = document.getElementById('reset-draw');
  const clearManualButton = document.getElementById('clear-manual-sides');
  const statusNode = document.getElementById('draw-status');
  const currentSlotNode = document.getElementById('current-slot');
  const pairingList = document.getElementById('pairing-list');
  const manualAssignmentTable = document.getElementById('manual-assignment-table');
  const modal = document.getElementById('draw-modal');
  const modalSide = document.getElementById('modal-side');
  const modalTeam = document.getElementById('modal-team');
  const modalSchool = document.getElementById('modal-school');
  const schoolCount = document.getElementById('school-count');
  const pairCount = document.getElementById('pair-count');
  const wheel = document.getElementById('draw-wheel');
  const wheelCenter = document.getElementById('wheel-center');

  const wheelColors = ['#5e2e91', '#2f6f73', '#b84242', '#305f9f', '#8a6d1f', '#5f6267'];

  function normalizeSchool(team) {
    return String(team.school || 'Unknown School').trim().toLowerCase();
  }

  function shuffle(items) {
    const copy = items.slice();
    for (let index = copy.length - 1; index > 0; index -= 1) {
      const swapIndex = Math.floor(Math.random() * (index + 1));
      [copy[index], copy[swapIndex]] = [copy[swapIndex], copy[index]];
    }
    return copy;
  }

  function getFirstSide() {
    const checked = document.querySelector('input[name="first_side"]:checked');
    return checked ? checked.value : 'Prosecution';
  }

  function groupTeamsBySchool(teams) {
    return teams.reduce((groups, team) => {
      const school = normalizeSchool(team);
      if (!groups[school]) {
        groups[school] = {
          school,
          displaySchool: team.school,
          teams: [],
        };
      }
      groups[school].teams.push(team);
      return groups;
    }, {});
  }

  function chooseFirstSideSchools(schoolGroups, targetTeamCount) {
    const groups = shuffle(Object.values(schoolGroups));
    const fixedFirst = groups.filter((group) => state.manualSchoolSides[group.school] === 'First');
    const fixedDefense = groups.filter((group) => state.manualSchoolSides[group.school] === 'Defense');
    const flexible = groups.filter((group) => !state.manualSchoolSides[group.school]);
    const fixedFirstCount = fixedFirst.reduce((sum, group) => sum + group.teams.length, 0);
    const fixedDefenseCount = fixedDefense.reduce((sum, group) => sum + group.teams.length, 0);
    const remainingTarget = targetTeamCount - fixedFirstCount;

    if (fixedFirstCount > targetTeamCount || fixedDefenseCount > targetTeamCount) {
      return null;
    }
    if (remainingTarget < 0) {
      return null;
    }

    const sums = new Map();
    sums.set(0, { previous: null, group: null });

    flexible.forEach((group) => {
      const count = group.teams.length;
      shuffle(Array.from(sums.keys())).forEach((sum) => {
        const nextSum = sum + count;
        if (nextSum > remainingTarget || sums.has(nextSum)) {
          return;
        }
        sums.set(nextSum, { previous: sum, group });
      });
    });

    if (!sums.has(remainingTarget)) {
      return null;
    }

    const chosen = new Set(fixedFirst.map((group) => group.school));
    let cursor = remainingTarget;
    while (cursor !== 0) {
      const entry = sums.get(cursor);
      chosen.add(entry.group.school);
      cursor = entry.previous;
    }
    return chosen;
  }

  function buildRandomSchedule() {
    const teams = originalTeams.map((team, index) => ({
      ...team,
      id: index,
    }));

    if (!teams.length) {
      return { pairings: [], error: '' };
    }
    if (teams.length % 2 === 1) {
      return { pairings: [], error: 'The draw needs an even number of teams.' };
    }

    const schoolGroups = groupTeamsBySchool(teams);
    const firstSideSchools = chooseFirstSideSchools(schoolGroups, teams.length / 2);
    if (!firstSideSchools) {
      return {
        pairings: [],
        error: 'These manual choices cannot produce even sides while keeping every school together.',
      };
    }

    const firstTeams = [];
    const defenseTeams = [];
    Object.values(schoolGroups).forEach((group) => {
      const sideTeams = firstSideSchools.has(group.school) ? firstTeams : defenseTeams;
      sideTeams.push(...shuffle(group.teams));
    });

    const shuffledDefenseTeams = shuffle(defenseTeams);
    return {
      pairings: shuffle(firstTeams).map((firstTeam, index) => ({
        first: firstTeam,
        second: shuffledDefenseTeams[index],
      })),
      error: '',
    };
  }

  function setActiveTab(panelId) {
    tabs.forEach((tab) => tab.classList.toggle('is-active', tab.dataset.tabTarget === panelId));
    panels.forEach((panel) => panel.classList.toggle('is-active', panel.id === panelId));
  }

  function renderSummary() {
    const schools = new Set(originalTeams.map(normalizeSchool));
    schoolCount.textContent = schools.size;
    pairCount.textContent = Math.floor(originalTeams.length / 2);
  }

  function renderManualAssignments() {
    if (!manualAssignmentTable) {
      return;
    }
    if (!originalTeams.length) {
      manualAssignmentTable.innerHTML = '<p class="manual-empty">Load teams to set manual sides.</p>';
      return;
    }

    const rows = originalTeams.map((team, index) => {
      const school = normalizeSchool(team);
      const selectedSide = state.manualSchoolSides[school] || '';
      return [
        '<tr>',
        `<td><strong>${escapeHtml(team.name)}</strong><small>${escapeHtml(team.school)}</small></td>`,
        '<td>',
        `<select class="manual-side-select" data-school="${escapeHtml(school)}" data-team-index="${index}">`,
        `<option value=""${selectedSide === '' ? ' selected' : ''}>Random</option>`,
        `<option value="First"${selectedSide === 'First' ? ' selected' : ''}>${escapeHtml(state.firstSide)}</option>`,
        `<option value="Defense"${selectedSide === 'Defense' ? ' selected' : ''}>Defense</option>`,
        '</select>',
        '</td>',
        '</tr>',
      ].join('');
    });

    manualAssignmentTable.innerHTML = [
      '<table class="manual-table">',
      '<thead><tr><th>Team</th><th>Manual side</th></tr></thead>',
      `<tbody>${rows.join('')}</tbody>`,
      '</table>',
    ].join('');

    manualAssignmentTable.querySelectorAll('.manual-side-select').forEach((select) => {
      select.addEventListener('change', () => {
        const school = select.dataset.school;
        if (select.value) {
          state.manualSchoolSides[school] = select.value;
        } else {
          delete state.manualSchoolSides[school];
        }
        resetDraw();
        renderManualAssignments();
      });
    });
  }

  function renderPairings() {
    pairingList.innerHTML = '';
    const table = document.createElement('table');
    table.className = 'pairing-table';
    table.innerHTML = [
      '<thead>',
      '<tr>',
      '<th>Pairing</th>',
      `<th>${escapeHtml(state.firstSide)}</th>`,
      '<th>Defense</th>',
      '</tr>',
      '</thead>',
      '<tbody></tbody>',
    ].join('');

    const tbody = table.querySelector('tbody');
    state.pairings.forEach((pairing, index) => {
      const row = document.createElement('tr');
      row.innerHTML = [
        `<td>${index + 1}</td>`,
        `<td>${teamCellMarkup(pairing.first)}</td>`,
        `<td>${teamCellMarkup(pairing.second)}</td>`,
      ].join('');
      tbody.appendChild(row);
    });

    pairingList.appendChild(table);
  }

  function teamCellMarkup(team) {
    if (!team) {
      return '<span class="pending-team">Awaiting draw</span>';
    }
    return `<strong>${escapeHtml(team.name)}</strong><small>${escapeHtml(team.school)}</small>`;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function getRemainingDraws() {
    return state.drawOrder.slice(state.drawIndex);
  }

  function updateWheel() {
    const remainingDraws = getRemainingDraws();
    if (!remainingDraws.length) {
      wheel.style.background = '#e9e6ef';
      wheelCenter.textContent = state.pairings.length ? 'Done' : 'Ready';
      return;
    }

    const sliceSize = 100 / remainingDraws.length;
    const segments = remainingDraws.map((draw, index) => {
      const start = index * sliceSize;
      const end = (index + 1) * sliceSize;
      return `${wheelColors[index % wheelColors.length]} ${start}% ${end}%`;
    });
    wheel.style.background = `conic-gradient(${segments.join(', ')})`;
    wheelCenter.textContent = state.isSpinning ? 'Spinning' : `${remainingDraws.length}`;
  }

  function updateStage() {
    const nextDraw = state.drawOrder[state.drawIndex];
    const nextSide = nextDraw && nextDraw.side === 'Defense' ? 'Defense' : state.firstSide;
    currentSlotNode.textContent = `${nextSide} team`;

    if (state.blockingMessage) {
      drawButton.disabled = true;
      statusNode.textContent = state.blockingMessage;
      updateWheel();
      return;
    }

    if (state.drawIndex >= state.drawOrder.length) {
      drawButton.disabled = true;
      statusNode.textContent = state.pairings.length ? 'All teams have been paired.' : 'Load an Excel workbook to begin.';
      updateWheel();
      return;
    }

    drawButton.disabled = state.isSpinning;
    const teamsRemaining = state.drawOrder.length - state.drawIndex;
    statusNode.textContent = state.isSpinning
      ? 'Spinning...'
      : `${teamsRemaining} team${teamsRemaining === 1 ? '' : 's'} remaining.`;
    updateWheel();
  }

  function revealTeam(side, team) {
    modalSide.textContent = side;
    modalTeam.textContent = team.name;
    modalSchool.textContent = team.school;
    modal.classList.add('is-visible');
    modal.setAttribute('aria-hidden', 'false');
    modalTeam.focus();
  }

  function closeModal() {
    modal.classList.remove('is-visible');
    modal.setAttribute('aria-hidden', 'true');
    drawButton.focus();
  }

  function finishDraw(nextDraw, spinToken) {
    if (spinToken !== state.spinToken) {
      return;
    }
    state.drawIndex += 1;
    nextDraw.pairing[nextDraw.field] = nextDraw.team;
    state.isSpinning = false;
    renderPairings();
    updateStage();
    revealTeam(nextDraw.side === 'Defense' ? 'Defense' : state.firstSide, nextDraw.team);
  }

  function spinWheelToNext(nextDraw) {
    const remainingCount = state.drawOrder.length - state.drawIndex;
    const sliceDegrees = 360 / Math.max(remainingCount, 1);
    const selectedSliceCenter = sliceDegrees / 2;
    const fullSpins = 5 + Math.floor(Math.random() * 3);
    state.wheelRotation += (fullSpins * 360) + (360 - selectedSliceCenter);
    wheel.style.transform = `rotate(${state.wheelRotation}deg)`;
    const spinToken = state.spinToken;
    window.setTimeout(() => finishDraw(nextDraw, spinToken), 2600);
  }

  function drawTeam() {
    if (state.isSpinning) {
      return;
    }
    state.firstSide = getFirstSide();
    const nextDraw = state.drawOrder[state.drawIndex];
    if (!nextDraw) {
      updateStage();
      return;
    }

    state.isSpinning = true;
    state.spinToken += 1;
    updateStage();
    spinWheelToNext(nextDraw);
  }

  function resetDraw() {
    state.firstSide = getFirstSide();
    const schedule = buildRandomSchedule();
    state.pairings = schedule.pairings.map((pairing) => ({
      first: null,
      second: null,
      scheduledFirst: pairing.first,
      scheduledSecond: pairing.second,
    }));
    state.drawOrder = [];
    state.pairings.forEach((pairing) => {
      state.drawOrder.push({
        side: 'First',
        team: pairing.scheduledFirst,
        pairing,
        field: 'first',
      });
      state.drawOrder.push({
        side: 'Defense',
        team: pairing.scheduledSecond,
        pairing,
        field: 'second',
      });
    });
    state.drawIndex = 0;
    state.blockingMessage = schedule.error;
    state.isSpinning = false;
    state.spinToken += 1;
    wheel.style.transform = `rotate(${state.wheelRotation}deg)`;
    renderPairings();
    updateStage();
  }

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => setActiveTab(tab.dataset.tabTarget));
  });

  document.querySelectorAll('input[name="first_side"]').forEach((input) => {
    input.addEventListener('change', () => {
      state.firstSide = getFirstSide();
      resetDraw();
      renderManualAssignments();
    });
  });

  drawButton.addEventListener('click', drawTeam);
  resetButton.addEventListener('click', resetDraw);
  clearManualButton.addEventListener('click', () => {
    state.manualSchoolSides = {};
    resetDraw();
    renderManualAssignments();
  });
  modalTeam.addEventListener('click', closeModal);

  modal.addEventListener('click', (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('is-visible')) {
      closeModal();
    }
  });

  renderSummary();
  renderManualAssignments();
  resetDraw();

  if (originalTeams.length) {
    setActiveTab('ceremony-panel');
  }
}());
