(function () {
  const teamDataNode = document.getElementById('ceremony-team-data');
  const originalTeams = teamDataNode ? JSON.parse(teamDataNode.textContent) : [];
  const state = {
    drawOrder: [],
    drawIndex: 0,
    pairings: [],
    firstSide: 'Prosecution',
    blockingMessage: '',
  };

  const tabs = document.querySelectorAll('.draw-tab');
  const panels = document.querySelectorAll('.draw-panel');
  const drawButton = document.getElementById('draw-team');
  const resetButton = document.getElementById('reset-draw');
  const statusNode = document.getElementById('draw-status');
  const currentSlotNode = document.getElementById('current-slot');
  const pairingList = document.getElementById('pairing-list');
  const modal = document.getElementById('draw-modal');
  const modalSide = document.getElementById('modal-side');
  const modalTeam = document.getElementById('modal-team');
  const modalSchool = document.getElementById('modal-school');
  const schoolCount = document.getElementById('school-count');
  const pairCount = document.getElementById('pair-count');

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
    const sums = new Map();
    sums.set(0, { previous: null, group: null });

    groups.forEach((group) => {
      const count = group.teams.length;
      shuffle(Array.from(sums.keys())).forEach((sum) => {
        const nextSum = sum + count;
        if (nextSum > targetTeamCount || sums.has(nextSum)) {
          return;
        }
        sums.set(nextSum, { previous: sum, group });
      });
    });

    if (!sums.has(targetTeamCount)) {
      return null;
    }

    const chosen = new Set();
    let cursor = targetTeamCount;
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
        error: 'These teams cannot be split evenly while keeping every school on one side.',
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

  function updateStage() {
    const nextDraw = state.drawOrder[state.drawIndex];
    const nextSide = nextDraw && nextDraw.side === 'Defense' ? 'Defense' : state.firstSide;
    currentSlotNode.textContent = `${nextSide} team`;

    if (state.blockingMessage) {
      drawButton.disabled = true;
      statusNode.textContent = state.blockingMessage;
      return;
    }

    if (state.drawIndex >= state.drawOrder.length) {
      drawButton.disabled = true;
      statusNode.textContent = state.pairings.length ? 'All teams have been paired.' : 'Load an Excel workbook to begin.';
      return;
    }

    drawButton.disabled = false;
    const teamsRemaining = state.drawOrder.length - state.drawIndex;
    statusNode.textContent = `${teamsRemaining} team${teamsRemaining === 1 ? '' : 's'} remaining.`;
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

  function drawTeam() {
    state.firstSide = getFirstSide();
    const nextDraw = state.drawOrder[state.drawIndex];
    if (!nextDraw) {
      updateStage();
      return;
    }

    state.drawIndex += 1;
    nextDraw.pairing[nextDraw.field] = nextDraw.team;
    revealTeam(nextDraw.side === 'Defense' ? 'Defense' : state.firstSide, nextDraw.team);
    renderPairings();
    updateStage();
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
    renderPairings();
    updateStage();
  }

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => setActiveTab(tab.dataset.tabTarget));
  });

  document.querySelectorAll('input[name="first_side"]').forEach((input) => {
    input.addEventListener('change', () => {
      state.firstSide = getFirstSide();
      renderPairings();
      updateStage();
    });
  });

  drawButton.addEventListener('click', drawTeam);
  resetButton.addEventListener('click', resetDraw);
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
  resetDraw();

  if (originalTeams.length) {
    setActiveTab('ceremony-panel');
  }
}());
