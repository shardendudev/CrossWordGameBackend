const API_BASE_URL = 'http://localhost:8000/api/v1';

// App State
let currentUser = null;
let currentLevel = null;
let timerInterval = null;
let secondsElapsed = 0;
let hintsUsedCount = 0;
let activeClue = null;

// DOM Elements
const backendStatus = document.getElementById('backendStatus');
const usernameInput = document.getElementById('usernameInput');
const btnCreateUser = document.getElementById('btnCreateUser');
const userRegisterSection = document.getElementById('userRegisterSection');
const userInfoSection = document.getElementById('userInfoSection');
const statUserId = document.getElementById('statUserId');
const statUsername = document.getElementById('statUsername');
const statSkill = document.getElementById('statSkill');
const skillBarFill = document.getElementById('skillBarFill');
const statGamesPlayed = document.getElementById('statGamesPlayed');
const difficultySelect = document.getElementById('difficultySelect');
const btnGenerateLevel = document.getElementById('btnGenerateLevel');
const emptyState = document.getElementById('emptyState');
const gameWorkspace = document.getElementById('gameWorkspace');
const gameplayControlsCard = document.getElementById('gameplayControlsCard');
const timerText = document.getElementById('timerText');
const btnRevealHint = document.getElementById('btnRevealHint');
const btnCheckGrid = document.getElementById('btnCheckGrid');
const btnSubmitLevel = document.getElementById('btnSubmitLevel');
const crosswordGrid = document.getElementById('crosswordGrid');
const acrossCluesList = document.getElementById('acrossCluesList');
const downCluesList = document.getElementById('downCluesList');
const telemetryModal = document.getElementById('telemetryModal');
const btnCloseModal = document.getElementById('btnCloseModal');
const btnModalNextLevel = document.getElementById('btnModalNextLevel');

// --- 1. Health Check & API Connectivity ---
async function checkBackendHealth() {
  try {
    const res = await fetch('http://localhost:8000/');
    if (res.ok) {
      backendStatus.className = 'backend-badge online';
      backendStatus.innerHTML = '<span class="status-dot"></span> Backend: Online (localhost:8000)';
    } else {
      throw new Error();
    }
  } catch {
    backendStatus.className = 'backend-badge offline';
    backendStatus.innerHTML = '<span class="status-dot"></span> Backend: Offline (Start uvicorn)';
  }
}
setInterval(checkBackendHealth, 5000);
checkBackendHealth();

// --- 2. User Profile API Integration ---
btnCreateUser.addEventListener('click', async () => {
  const username = usernameInput.value.trim();
  if (!username) return alert('Please enter a valid username');

  try {
    const res = await fetch(`${API_BASE_URL}/users/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username })
    });

    if (res.status === 400) {
      // Username exists, let's fetch profile by generating random uuid or notification
      alert(`Username '${username}' exists. Generating user with random suffix.`);
      return btnCreateUser.click();
    }

    if (!res.ok) throw new Error(await res.text());

    currentUser = await res.json();
    updateUserUI();
  } catch (err) {
    alert('User registration failed: ' + err.message);
  }
});

function updateUserUI() {
  if (!currentUser) return;

  statUserId.textContent = currentUser.user_id.slice(0, 8) + '...';
  statUsername.textContent = currentUser.username;
  statSkill.textContent = currentUser.current_skill_level.toFixed(3);
  statGamesPlayed.textContent = currentUser.total_games_played;
  skillBarFill.style.width = `${Math.min(100, currentUser.current_skill_level * 100)}%`;

  userRegisterSection.classList.add('hidden');
  userInfoSection.classList.remove('hidden');
  btnGenerateLevel.disabled = false;
}

// --- 3. Level Generator API Integration ---
btnGenerateLevel.addEventListener('click', async () => {
  if (!currentUser) return alert('Please register a user first');

  btnGenerateLevel.disabled = true;
  btnGenerateLevel.textContent = '⏳ Generating Solver Grid...';

  const diffVal = difficultySelect.value;
  const reqDiff = diffVal === 'auto' ? currentUser.current_skill_level : parseFloat(diffVal);

  try {
    const res = await fetch(`${API_BASE_URL}/gameplay/generate-level`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: currentUser.user_id,
        requested_difficulty: reqDiff
      })
    });

    if (!res.ok) throw new Error(await res.text());

    currentLevel = await res.json();
    renderLevelWorkspace();
  } catch (err) {
    alert('Failed to generate level: ' + err.message);
  } finally {
    btnGenerateLevel.disabled = false;
    btnGenerateLevel.textContent = '⚡ Generate Level';
  }
});

// --- 4. Render Crossword Grid & Clues ---
function renderLevelWorkspace() {
  if (!currentLevel || !currentLevel.grid) return;

  emptyState.classList.add('hidden');
  gameWorkspace.classList.remove('hidden');
  gameplayControlsCard.classList.remove('hidden');

  // Reset timer & hints
  clearInterval(timerInterval);
  secondsElapsed = 0;
  hintsUsedCount = 0;
  updateTimerDisplay();
  timerInterval = setInterval(() => {
    secondsElapsed++;
    updateTimerDisplay();
  }, 1000);

  // Clear container
  crosswordGrid.innerHTML = '';
  acrossCluesList.innerHTML = '';
  downCluesList.innerHTML = '';

  const grid = currentLevel.grid;
  const clues = currentLevel.clues || [];

  // Build grid cell number mapping
  const numMap = {};
  clues.forEach((c, idx) => {
    const key = `${c.row},${c.col}`;
    if (!numMap[key]) numMap[key] = idx + 1;
    c.number = numMap[key];
  });

  // Render 10x10 Grid Cells
  for (let r = 0; r < 10; r++) {
    for (let c = 0; c < 10; c++) {
      const cellVal = grid[r][c];
      const isBlock = cellVal === '' || cellVal === '.';

      const cellDiv = document.createElement('div');
      cellDiv.className = `grid-cell ${isBlock ? 'block' : 'active'}`;
      cellDiv.dataset.row = r;
      cellDiv.dataset.col = c;

      if (!isBlock) {
        // Number badge
        const numKey = `${r},${c}`;
        if (numMap[numKey]) {
          const numSpan = document.createElement('span');
          numSpan.className = 'cell-number';
          numSpan.textContent = numMap[numKey];
          cellDiv.appendChild(numSpan);
        }

        const input = document.createElement('input');
        input.type = 'text';
        input.maxLength = 1;
        input.dataset.row = r;
        input.dataset.col = c;
        input.dataset.solution = cellVal.toUpperCase();

        input.addEventListener('focus', () => handleCellFocus(r, c));
        input.addEventListener('keydown', (e) => handleKeyNav(e, r, c));

        cellDiv.appendChild(input);
      }

      crosswordGrid.appendChild(cellDiv);
    }
  }

  // Render Clues Lists
  clues.forEach(clue => {
    const li = document.createElement('li');
    li.className = 'clue-item';
    li.id = `clue-${clue.slot_id}`;
    li.innerHTML = `<span class="clue-num">${clue.number}.</span> <span class="clue-title">${clue.display_title || ''}</span>: ${clue.hint}`;

    li.addEventListener('click', () => selectClue(clue));

    if (clue.direction === 'ACROSS' || clue.direction === 'H') {
      acrossCluesList.appendChild(li);
    } else {
      downCluesList.appendChild(li);
    }
  });
}

function updateTimerDisplay() {
  const m = String(Math.floor(secondsElapsed / 60)).padStart(2, '0');
  const s = String(secondsElapsed % 60).padStart(2, '0');
  timerText.textContent = `${m}:${s}`;
}

function handleCellFocus(r, c) {
  document.querySelectorAll('.grid-cell').forEach(el => el.classList.remove('focused'));
  const cell = document.querySelector(`.grid-cell[data-row="${r}"][data-col="${c}"]`);
  if (cell) cell.classList.add('focused');
}

function handleKeyNav(e, r, c) {
  let nextR = r, nextC = c;

  if (e.key === 'ArrowRight') nextC = Math.min(9, c + 1);
  else if (e.key === 'ArrowLeft') nextC = Math.max(0, c - 1);
  else if (e.key === 'ArrowDown') nextR = Math.min(9, r + 1);
  else if (e.key === 'ArrowUp') nextR = Math.max(0, r - 1);
  else if (e.key === 'Backspace' && !e.target.value) nextC = Math.max(0, c - 1);

  const nextInput = document.querySelector(`input[data-row="${nextR}"][data-col="${nextC}"]`);
  if (nextInput && (nextR !== r || nextC !== c)) {
    nextInput.focus();
  }
}

function selectClue(clue) {
  activeClue = clue;
  document.querySelectorAll('.clue-item').forEach(el => el.classList.remove('active-clue'));
  document.querySelectorAll('.grid-cell').forEach(el => el.classList.remove('highlight-word'));

  const item = document.getElementById(`clue-${clue.slot_id}`);
  if (item) item.classList.add('active-clue');

  // Highlight word cells on grid
  const { row, col, length, direction } = clue;
  for (let i = 0; i < length; i++) {
    const r = (direction === 'ACROSS' || direction === 'H') ? row : row + i;
    const c = (direction === 'ACROSS' || direction === 'H') ? col + i : col;
    const cell = document.querySelector(`.grid-cell[data-row="${r}"][data-col="${c}"]`);
    if (cell) cell.classList.add('highlight-word');
  }

  // Focus first cell
  const firstInput = document.querySelector(`input[data-row="${row}"][data-col="${col}"]`);
  if (firstInput) firstInput.focus();
}

// --- 5. Hint & Validation Helpers ---
btnRevealHint.addEventListener('click', () => {
  if (!currentLevel) return;
  const inputs = Array.from(document.querySelectorAll('.grid-cell input'));
  const emptyInputs = inputs.filter(inp => inp.value.toUpperCase() !== inp.dataset.solution);

  if (emptyInputs.length === 0) return alert('All cells already solved!');

  const targetInput = emptyInputs[Math.floor(Math.random() * emptyInputs.length)];
  targetInput.value = targetInput.dataset.solution;
  targetInput.parentElement.classList.add('correct');
  hintsUsedCount++;
});

btnCheckGrid.addEventListener('click', () => {
  let errors = 0;
  const inputs = document.querySelectorAll('.grid-cell input');
  inputs.forEach(inp => {
    inp.parentElement.classList.remove('correct', 'error');
    if (inp.value) {
      if (inp.value.toUpperCase() === inp.dataset.solution) {
        inp.parentElement.classList.add('correct');
      } else {
        inp.parentElement.classList.add('error');
        errors++;
      }
    }
  });
  alert(errors === 0 ? '✨ Great job! All entered letters are correct so far.' : `⚠️ Found ${errors} error(s) in red.`);
});

// --- 6. Telemetry API Integration ---
btnSubmitLevel.addEventListener('click', async () => {
  if (!currentLevel || !currentUser) return;

  clearInterval(timerInterval);

  let cellErrors = 0;
  const inputs = document.querySelectorAll('.grid-cell input');
  inputs.forEach(inp => {
    if (inp.value.toUpperCase() !== inp.dataset.solution) cellErrors++;
  });

  const imdbIds = (currentLevel.clues || []).map(c => c.imdb_id).filter(Boolean);

  const payload = {
    user_id: currentUser.user_id,
    session_id: crypto.randomUUID(),
    level_id: currentLevel.level_id,
    imdb_ids: imdbIds,
    time_taken_seconds: Math.max(1, secondsElapsed),
    free_hints_used: hintsUsedCount,
    cell_error_count: cellErrors,
    is_completed: cellErrors === 0
  };

  try {
    const res = await fetch(`${API_BASE_URL}/gameplay/submit-telemetry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(await res.text());

    const result = await res.json();
    showTelemetryModal(result, payload);

    // Refresh user profile
    const userRes = await fetch(`${API_BASE_URL}/users/${currentUser.user_id}`);
    if (userRes.ok) {
      currentUser = await userRes.json();
      updateUserUI();
    }
  } catch (err) {
    alert('Failed to submit telemetry: ' + err.message);
  }
});

function showTelemetryModal(result, payload) {
  document.getElementById('telTime').textContent = `${payload.time_taken_seconds}s`;
  document.getElementById('telHints').textContent = payload.free_hints_used;
  document.getElementById('telErrors').textContent = payload.cell_error_count;
  
  const sign = result.skill_delta >= 0 ? '+' : '';
  document.getElementById('telDelta').textContent = `${sign}${result.skill_delta.toFixed(3)}`;
  document.getElementById('telOldSkill').textContent = result.previous_skill_level.toFixed(3);
  document.getElementById('telNewSkill').textContent = result.new_skill_level.toFixed(3);

  telemetryModal.classList.remove('hidden');
}

btnCloseModal.addEventListener('click', () => telemetryModal.classList.add('hidden'));
btnModalNextLevel.addEventListener('click', () => {
  telemetryModal.classList.add('hidden');
  btnGenerateLevel.click();
});
