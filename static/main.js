// static/main.js

let lastSceneKey = ""; // 用于防止重复记录日志
let actionInProgress = false; // 防止战斗等场景下双击导致连续请求被误解析为选门
let currentSceneType = "UNKNOWN";
let currentChoices = [];
let hasRenderedState = false;

const delay = ms => new Promise(res => setTimeout(res, ms));
const REQUEST_TIMEOUT_MS = 8000;
const STATE_TIMEOUT_MS = 6000;
const RETRY_DELAY_MS = 900;
const CATCHUP_DELAY_MS = 2200;
const RETRY_AFTER_SECONDS = 3;
const NETWORK_FUNNY_HINTS = [
  "🕯️ 地牢信号忽明忽暗，信鸽正在申请第二次起飞许可。",
  "🧭 罗盘刚刚打了个喷嚏，路线正在重新计算。",
  "🐌 后端快递员被一只蜗牛超车了，包裹正在追回。",
  "📮 你的请求卡在异次元邮箱，邮差正努力敲门。",
  "🌩️ 天空闪过静电，卷轴边缘有点焦，但消息还活着。",
  "🛡️ 守门骑士在核验暗号，马上放行下一班数据马车。"
];
let lastNetworkHintAt = 0;

const SOUND_STORAGE_KEY = "three_doors_sound_enabled";
const SoundSystem = {
  enabled: true,
  unlocked: false,
  lastTriggerAt: {},

  canTrigger(key, gap = 120) {
    const now = Date.now();
    if (!this.lastTriggerAt[key] || now - this.lastTriggerAt[key] > gap) {
      this.lastTriggerAt[key] = now;
      return true;
    }
    return false;
  },

  ensureReady() {
    if (!this.enabled || typeof Tone === "undefined") return false;
    if (this.unlocked) return true;
    try {
      Tone.start().then(() => {
        this.unlocked = true;
      }).catch(() => {});
      return true;
    } catch (e) {
      return false;
    }
  },

  withSynth(SynthClass, options, playFn, disposeAfter = 1000) {
    if (!this.enabled || typeof Tone === "undefined") return;
    try {
      this.ensureReady();
      const synth = new SynthClass(options).toDestination();
      playFn(synth, Tone.now());
      setTimeout(() => synth.dispose(), disposeAfter);
    } catch (e) {}
  },

  withPolySynth(options, playFn, disposeAfter = 1000) {
    if (!this.enabled || typeof Tone === "undefined") return;
    try {
      this.ensureReady();
      const synth = new Tone.PolySynth(Tone.Synth, options).toDestination();
      playFn(synth, Tone.now());
      setTimeout(() => synth.dispose(), disposeAfter);
    } catch (e) {}
  },

  playStartFanfare() {
    if (!this.canTrigger("start_fanfare", 1000)) return;
    this.withPolySynth({
      oscillator: { type: "triangle" },
      envelope: { attack: 0.05, decay: 0.2, sustain: 0.3, release: 0.4 },
      volume: -6,
    }, (synth, now) => {
      ["G3", "C4", "E4", "G4", "C5"].forEach((n, i) => {
        synth.triggerAttackRelease(n, "8n", now + i * 0.15);
      });
    }, 1200);
  },

  playDoorOpen(textureKey) {
    if (!this.canTrigger("door_open", 130)) return;
    const profile = {
      door_oak: { osc: "triangle", notes: ["C3", "G3"], vol: -8 },
      door_obsidian: { osc: "sawtooth", notes: ["D2", "A2"], vol: -10 },
      door_vine: { osc: "sine", notes: ["E4", "B4"], vol: -13 },
      door_rune: { osc: "triangle", notes: ["G4", "C5"], vol: -12 },
      door_iron: { osc: "square", notes: ["B2", "F#3"], vol: -9 },
      door_bone: { osc: "fatsawtooth", notes: ["A2", "C3"], vol: -12 },
    }[textureKey] || { osc: "triangle", notes: ["C3", "G3"], vol: -10 };
    this.withSynth(Tone.Synth, {
      oscillator: { type: profile.osc },
      envelope: { attack: 0.005, decay: 0.14, sustain: 0.12, release: 0.2 },
      volume: profile.vol,
    }, (synth, now) => {
      synth.triggerAttackRelease(profile.notes[0], "16n", now);
      synth.triggerAttackRelease(profile.notes[1], "16n", now + 0.08);
    }, 500);
  },

  playDoorOutcome(outcome) {
    if (!outcome) return;
    if (outcome === "TRAP") return this.playTrap();
    if (outcome === "REWARD") return this.playReward();
    if (outcome === "SHOP") return this.playShop();
    if (outcome === "EVENT") return this.playEventChoice();
    if (outcome === "MONSTER") return this.playBattleEnter();
  },

  playTrap() {
    if (!this.canTrigger("trap", 150)) return;
    this.withSynth(Tone.NoiseSynth, {
      noise: { type: "brown" },
      envelope: { attack: 0.001, decay: 0.2, sustain: 0.02, release: 0.08 },
      volume: -8,
    }, (synth) => {
      synth.triggerAttackRelease("16n");
    }, 400);
  },

  playReward() {
    if (!this.canTrigger("reward", 150)) return;
    this.withPolySynth({
      oscillator: { type: "sine" },
      envelope: { attack: 0.01, decay: 0.15, sustain: 0.2, release: 0.25 },
      volume: -10,
    }, (synth, now) => {
      ["E5", "G5", "B5"].forEach((note, i) => synth.triggerAttackRelease(note, "16n", now + i * 0.08));
    }, 600);
  },

  playShop() {
    if (!this.canTrigger("shop", 120)) return;
    this.withSynth(Tone.MembraneSynth, {
      pitchDecay: 0.01,
      octaves: 2,
      envelope: { attack: 0.001, decay: 0.15, sustain: 0, release: 0.05 },
      volume: -14,
    }, (synth, now) => {
      synth.triggerAttackRelease("C4", "32n", now);
      synth.triggerAttackRelease("E4", "32n", now + 0.08);
    }, 400);
  },

  playEventChoice() {
    if (!this.canTrigger("event_choice", 120)) return;
    this.withSynth(Tone.FMSynth, {
      harmonicity: 2,
      modulationIndex: 6,
      oscillator: { type: "triangle" },
      envelope: { attack: 0.01, decay: 0.1, sustain: 0.08, release: 0.15 },
      modulation: { type: "square" },
      modulationEnvelope: { attack: 0.01, decay: 0.1, sustain: 0, release: 0.1 },
      volume: -12,
    }, (synth, now) => {
      synth.triggerAttackRelease("D5", "16n", now);
      synth.triggerAttackRelease("A4", "16n", now + 0.08);
    }, 500);
  },

  playUseItem() {
    if (!this.canTrigger("use_item", 120)) return;
    this.withSynth(Tone.Synth, {
      oscillator: { type: "triangle" },
      envelope: { attack: 0.01, decay: 0.08, sustain: 0.1, release: 0.12 },
      volume: -10,
    }, (synth, now) => {
      synth.triggerAttackRelease("A4", "32n", now);
      synth.triggerAttackRelease("E5", "16n", now + 0.05);
    }, 450);
  },

  playPlayerAttack() {
    if (!this.canTrigger("player_attack", 100)) return;
    this.withSynth(Tone.MetalSynth, {
      frequency: 250,
      envelope: { attack: 0.001, decay: 0.12, release: 0.06 },
      harmonicity: 5.1,
      modulationIndex: 20,
      resonance: 1800,
      octaves: 1.2,
      volume: -20,
    }, (synth, now) => {
      synth.triggerAttackRelease("16n", now);
    }, 400);
  },

  playMonsterAttack() {
    if (!this.canTrigger("monster_attack", 120)) return;
    this.withSynth(Tone.MonoSynth, {
      oscillator: { type: "sawtooth" },
      filter: { Q: 2, type: "lowpass", rolloff: -24 },
      envelope: { attack: 0.01, decay: 0.2, sustain: 0.1, release: 0.15 },
      filterEnvelope: { attack: 0.001, decay: 0.15, sustain: 0.05, release: 0.15, baseFrequency: 120, octaves: 3 },
      volume: -10,
    }, (synth, now) => {
      synth.triggerAttackRelease("A2", "16n", now);
      synth.triggerAttackRelease("F2", "16n", now + 0.09);
    }, 550);
  },

  playBattleEnter() {
    if (!this.canTrigger("battle_enter", 250)) return;
    this.withSynth(Tone.MonoSynth, {
      oscillator: { type: "fatsawtooth" },
      envelope: { attack: 0.01, decay: 0.25, sustain: 0.2, release: 0.2 },
      volume: -11,
    }, (synth, now) => {
      synth.triggerAttackRelease("D2", "8n", now);
      synth.triggerAttackRelease("G1", "8n", now + 0.15);
    }, 800);
  },

  playSceneEnter(sceneType) {
    if (sceneType === "BATTLE") return this.playBattleEnter();
    if (sceneType === "SHOP") return this.playShop();
    if (sceneType === "EVENT") return this.playEventChoice();
    if (sceneType === "USE_ITEM") return this.playUseItem();
    if (sceneType === "GAME_OVER") return this.playTrap();
  },


  playPuppetCue() {
    if (!this.canTrigger("puppet_cue", 180)) return;
    this.withSynth(Tone.FMSynth, {
      harmonicity: 1.8,
      modulationIndex: 9,
      oscillator: { type: "triangle" },
      envelope: { attack: 0.01, decay: 0.16, sustain: 0.1, release: 0.2 },
      volume: -11,
    }, (synth, now) => {
      synth.triggerAttackRelease("E4", "8n", now);
      synth.triggerAttackRelease("B3", "8n", now + 0.12);
    }, 700);
  },

  playPuppetFinale() {
    if (!this.canTrigger("puppet_finale", 1200)) return;
    this.withPolySynth({
      oscillator: { type: "sine" },
      envelope: { attack: 0.04, decay: 0.2, sustain: 0.25, release: 0.5 },
      volume: -8,
    }, (synth, now) => {
      ["C4", "E4", "G4", "B4", "C5"].forEach((note, i) => {
        synth.triggerAttackRelease(note, "4n", now + i * 0.18);
      });
    }, 1800);
  },

  playUiClick() {
    if (!this.canTrigger("ui_click", 60)) return;
    this.withSynth(Tone.Synth, {
      oscillator: { type: "sine" },
      envelope: { attack: 0.001, decay: 0.05, sustain: 0, release: 0.05 },
      volume: -18,
    }, (synth, now) => {
      synth.triggerAttackRelease("C5", "64n", now);
    }, 250);
  },

  scanLogAndPlay(msg) {
    if (!msg || !this.enabled) return;
    const text = String(msg);
    if (/触发了机关|尖刺|中毒|虚弱诅咒|伏击|诅咒/.test(text)) this.playTrap();
    if (/你受到了\s*\d+\s*点伤害|揍了一顿|被击败了/.test(text)) this.playMonsterAttack();
    if (/你攻击|你击败了/.test(text)) this.playPlayerAttack();
    if (/购买了|花费\s*\d+\s*金币/.test(text)) this.playShop();
    if (/进入使用道具界面|飞锤|结界|卷轴|恢复\s*\d+\s*HP/.test(text)) this.playUseItem();
    if (/获得了?\s*\d+\s*金币|获得道具|掉落：/.test(text)) this.playReward();
    if (/木偶音效|木偶终战|木偶结局|阶段切换/.test(text)) this.playPuppetCue();
    if (/木偶终曲|收束旋律|完全体战斗主题/.test(text)) this.playPuppetFinale();
  },
};

function updateSoundToggleBtn() {
  const soundBtn = document.getElementById("soundToggleBtn");
  if (!soundBtn) return;
  soundBtn.textContent = SoundSystem.enabled ? "音效：开" : "音效：关";
}

function initSoundControls() {
  const stored = localStorage.getItem(SOUND_STORAGE_KEY);
  SoundSystem.enabled = stored !== "0";
  updateSoundToggleBtn();

  const soundBtn = document.getElementById("soundToggleBtn");
  if (soundBtn) {
    soundBtn.addEventListener("click", () => {
      SoundSystem.enabled = !SoundSystem.enabled;
      localStorage.setItem(SOUND_STORAGE_KEY, SoundSystem.enabled ? "1" : "0");
      updateSoundToggleBtn();
      if (SoundSystem.enabled) {
        SoundSystem.ensureReady();
        SoundSystem.playUiClick();
      }
    });
  }

  document.addEventListener("pointerdown", () => {
    SoundSystem.ensureReady();
  }, { passive: true });
}

function getFrontDoorStyle(textureKey) {
  // 主体始终是门，差异只通过小装饰体现
  const map = {
    door_oak: { main: "🚪", accent: "🪵" },
    door_obsidian: { main: "🚪", accent: "🪨" },
    door_vine: { main: "🚪", accent: "🌿" },
    door_rune: { main: "🚪", accent: "✨" },
    door_iron: { main: "🚪", accent: "🔒" },
    door_bone: { main: "🚪", accent: "🦴" },
  };
  return map[textureKey] || { main: "🚪", accent: "🔑" };
}

function pickRandom(items) {
  return items[Math.floor(Math.random() * items.length)];
}

function isTimeoutError(err) {
  if (!err) return false;
  if (err.name === "AbortError") return true;
  const msg = String(err.message || "").toLowerCase();
  return msg.includes("timeout");
}

function shouldLogNetworkHintNow() {
  const now = Date.now();
  if (now - lastNetworkHintAt < 1200) return false;
  lastNetworkHintAt = now;
  return true;
}

function logNetworkIssue(context, err, attempt, maxAttempts) {
  if (!shouldLogNetworkHintNow()) return;
  const primary = isTimeoutError(err)
    ? `⏳ ${context}超时，回声信道暂时堵塞。`
    : `📡 ${context}失败，地牢通信暂时中断。`;
  const suffix = attempt < maxAttempts
    ? `正在重连（${attempt}/${maxAttempts}）...`
    : `请 ${RETRY_AFTER_SECONDS} 秒后重试，我们会继续尝试追上进度。`;
  addLog(`${primary}\n${pickRandom(NETWORK_FUNNY_HINTS)}\n${suffix}`);
}

async function fetchJsonWithTimeout(url, options = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status} ${res.statusText}`);
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

async function requestJsonWithRetry(
  url,
  options = {},
  { timeoutMs = REQUEST_TIMEOUT_MS, maxAttempts = 2, context = "请求" } = {}
) {
  let lastErr = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fetchJsonWithTimeout(url, options, timeoutMs);
    } catch (err) {
      lastErr = err;
      logNetworkIssue(context, err, attempt, maxAttempts);
      if (attempt < maxAttempts) {
        await delay(RETRY_DELAY_MS * attempt);
      }
    }
  }
  throw lastErr;
}

async function catchupStateSync() {
  addLog("🧵 正在重新缝合时间线，尝试同步最新局势...");
  try {
    await delay(CATCHUP_DELAY_MS);
    const state = await requestJsonWithRetry("/getState", {}, {
      timeoutMs: STATE_TIMEOUT_MS,
      maxAttempts: 2,
      context: "状态回补"
    });
    renderState(state);
    addLog("✅ 已重新连上命运主线，你可以继续行动。");
  } catch (err) {
    console.error("Catch-up sync error:", err);
    addLog(`🌫️ 连接仍不稳定，请 ${RETRY_AFTER_SECONDS} 秒后再试一次。`);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initUI();
  initSoundControls();
  initStartScreen();
  document.getElementById("startOverBtn").addEventListener("click", startOver);
  document.getElementById("exitGameBtn").addEventListener("click", exitGame);
});

function initUI() {
  // Clear old button listeners if any (relying on dynamic binding now)
  // We will dynamic bind events in renderState
}

function playStartFanfare() {
  SoundSystem.playStartFanfare();
}

function initStartScreen() {
  const startScreen = document.getElementById("start-screen");
  const overlay = document.getElementById("start-screen-overlay");
  const video = document.getElementById("opening-video");
  const gameContainer = document.getElementById("game-container");
  let videoEnded = false;

  function onVideoEnded() {
    videoEnded = true;
    overlay.classList.add("ready");
  }
  video.addEventListener("ended", onVideoEnded);
  video.addEventListener("error", () => {
    onVideoEnded();
  });
  if (video.ended) onVideoEnded();

  overlay.addEventListener("click", () => {
    if (!videoEnded) return;
    playStartFanfare();
    startScreen.classList.add("hidden");
    gameContainer.style.display = "block";
    setTimeout(() => {
      startScreen.style.display = "none";
      getStateAndRender();
    }, 650);
  });
}

// Map logic for result emoji
function getResultEmoji(sceneInfo) {
  if (sceneInfo.type === 'BATTLE') return getMonsterEmoji(sceneInfo.monster_name);
  if (sceneInfo.type === 'SHOP') return "🛒";
  if (sceneInfo.type === 'EVENT') return "❔";
  if (sceneInfo.type === 'GAME_OVER') return "💀";
  return "✨";
}

async function handleDoorClick(index, card) {
  if (card.classList.contains('flipped')) return; // Prevent clicking already flipped

  // Disable all doors immediately
  const doorArea = document.getElementById("door-area");
  doorArea.style.pointerEvents = "none";
  SoundSystem.playDoorOpen(card && card.dataset ? card.dataset.textureKey : "");

  try {
    // 1. Commit Action
    const actionData = await requestJsonWithRetry("/buttonAction", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: index })
    }, {
      timeoutMs: REQUEST_TIMEOUT_MS,
      maxAttempts: 2,
      context: "开门动作"
    });

    // 2. Get New State (to peek at result)
    const newState = await requestJsonWithRetry("/getState", {}, {
      timeoutMs: STATE_TIMEOUT_MS,
      maxAttempts: 2,
      context: "开门结果同步"
    });

    // 3. Reveal Animation
    // We use the passed 'card' element directly. 
    // Fallback just in case, though 'card' should be correct.
    const targetCard = card || document.querySelectorAll('.door-card')[index];
    const backFace = targetCard.querySelector('.back');

    // Set back-face emoji based on what we found behind the door
    let revealEmoji = "❓";
    if (actionData.outcome === "TRAP") {
      revealEmoji = "🧨";
    } else if (actionData.outcome === "REWARD") {
      revealEmoji = "💎";
    } else if (actionData.outcome === "SHOP") {
      revealEmoji = "🛒";
    } else if (actionData.outcome === "EVENT") {
      revealEmoji = "❔";
    } else {
      revealEmoji = getResultEmoji(newState.scene_info);
    }
    backFace.textContent = revealEmoji;
    targetCard.classList.add('flipped');
    SoundSystem.playDoorOutcome(actionData.outcome);

    // 4. Wait for flip
    await delay(1000);

    // 5. Render Full State (transition to next scene)
    if (actionData.log) addLog(actionData.log);
    renderState(newState);

  } catch (err) {
    console.error("Door Click Error:", err);
    await catchupStateSync();
  } finally {
    // Re-enable pointer events (though renderState usually rebuilds the area)
    if (doorArea) doorArea.style.pointerEvents = "auto";
  }
}

async function buttonAction(index) {
  if (actionInProgress) return;
  actionInProgress = true;
  const sceneTypeBefore = currentSceneType;
  const selectedText = currentChoices[index] || "";

  if (sceneTypeBefore === "BATTLE" && index === 0) {
    SoundSystem.playPlayerAttack();
  } else if (sceneTypeBefore === "BATTLE" && index === 1) {
    SoundSystem.playUseItem();
  } else if (sceneTypeBefore === "EVENT") {
    SoundSystem.playEventChoice();
  } else if (sceneTypeBefore === "USE_ITEM" && selectedText && selectedText !== "返回") {
    SoundSystem.playUseItem();
  } else if (sceneTypeBefore === "SHOP") {
    SoundSystem.playShop();
  } else {
    SoundSystem.playUiClick();
  }
  const buttonArea = document.getElementById("buttons");
  if (buttonArea) buttonArea.style.pointerEvents = "none";

  try {
    const data = await requestJsonWithRetry("/buttonAction", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: index })
    }, {
      timeoutMs: REQUEST_TIMEOUT_MS,
      maxAttempts: 2,
      context: "执行动作"
    });
    if (data.log) {
      addLog(data.log);
    }

    if (data.outcome === "EXIT_GAME") {
      exitGame();
      return;
    }

    await getStateAndRender();
  } catch (err) {
    console.error("Action error:", err);
    await catchupStateSync();
  } finally {
    actionInProgress = false;
    if (buttonArea) buttonArea.style.pointerEvents = "auto";
  }
}

async function startOver() {
  try {
    const data = await requestJsonWithRetry("/startOver", { method: "POST" }, {
      timeoutMs: REQUEST_TIMEOUT_MS,
      maxAttempts: 2,
      context: "重置游戏"
    });
    addLog(data.log || data.msg);
    await getStateAndRender();
  } catch (err) {
    console.error("StartOver error:", err);
    await catchupStateSync();
  }
}

async function exitGame() {
  try {
    const data = await requestJsonWithRetry("/exitGame", {
      method: "POST"
    }, {
      timeoutMs: REQUEST_TIMEOUT_MS,
      maxAttempts: 1,
      context: "关闭游戏"
    });
    addLog(data.log || data.msg);

    document.querySelectorAll("button").forEach(b => b.disabled = true);

    // UI Feedback
    setTimeout(() => {
      document.body.innerHTML = `
            <div style="display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column;font-family:sans-serif;">
                <h1>游戏已关闭</h1>
                <p>服务器已停止运行，您可以关闭此标签页了。</p>
            </div>
        `;
      window.close(); // Try to close
    }, 1000);

  } catch (e) {
    console.error("Exit error:", e);
    addLog("关闭游戏失败，可能是服务器已断开。");
  }
}

async function getStateAndRender() {
  try {
    const state = await requestJsonWithRetry("/getState", {}, {
      timeoutMs: STATE_TIMEOUT_MS,
      maxAttempts: 2,
      context: "获取状态"
    });
    renderState(state);
  } catch (err) {
    console.error("GetState error:", err);
    await catchupStateSync();
  }
}

function renderState(state) {
  const p = state.player;

  // 1. Status Text (HP Included Here)
  let statsText = `HP: ${p.hp} | ATK: ${p.atk} | Gold: ${p.gold} | Round: ${state.round}`;
  if (p.status_desc && p.status_desc !== "无") {
    statsText += ` | ${p.status_desc}`;
  }
  document.getElementById("other-stats").textContent = statsText;

  // 2. Scene Rendering
  const sceneInfo = state.scene_info || {};
  const prevSceneType = currentSceneType;
  currentSceneType = sceneInfo.type || "UNKNOWN";
  currentChoices = sceneInfo.choices || [];
  if (hasRenderedState && prevSceneType && prevSceneType !== currentSceneType) {
    SoundSystem.playSceneEnter(currentSceneType);
  }
  hasRenderedState = true;
  const sceneEmojiDiv = document.getElementById("scene-emoji");
  const doorArea = document.getElementById("door-area");
  const buttonArea = document.getElementById("buttons");

  // Reset Areas
  doorArea.style.display = 'none';
  doorArea.innerHTML = '';
  buttonArea.style.display = 'flex';
  buttonArea.innerHTML = ''; // Clear old buttons

  let emoji = "❓";
  let desc = "";

  // Special Handling for Door Scene
  if (sceneInfo.type === "DOOR") {
    emoji = ""; // No main emoji, cards are the focus
    desc = "命运三岔口：选择你的道路...";

    doorArea.style.display = 'flex';
    buttonArea.style.display = 'none'; // Hide standard buttons

    // Generate 3 Cards
    const doors = sceneInfo.doors || [];
    (sceneInfo.choices || []).forEach((choiceText, idx) => {
      const hint = (doors[idx] && doors[idx].hint) ? doors[idx].hint : choiceText.replace(/^门\d+\s*-\s*/, '');
      const textureKey = (doors[idx] && doors[idx].texture_key) ? doors[idx].texture_key : "door_oak";
      const frontStyle = getFrontDoorStyle(textureKey);

      const wrapper = document.createElement('div');
      wrapper.className = 'door-wrapper';

      const card = document.createElement('div');
      card.className = 'door-card';
      card.dataset.textureKey = textureKey;
      card.innerHTML = `
            <div class="door-card-inner">
                <div class="door-face front">
                  <span class="door-front-main">${frontStyle.main}</span>
                  <span class="door-front-accent">${frontStyle.accent}</span>
                </div>
                <div class="door-face back">❔</div>
            </div>
          `;
      card.onclick = () => handleDoorClick(idx, card);

      const hintDiv = document.createElement('div');
      hintDiv.className = 'door-hint';
      hintDiv.textContent = hint;

      wrapper.appendChild(card);
      wrapper.appendChild(hintDiv);
      doorArea.appendChild(wrapper);
    });

  } else {
    // Standard Scenes (Battle, Shop, Event, etc)
    switch (sceneInfo.type) {
      case "BATTLE":
        emoji = getMonsterEmoji(sceneInfo.monster_name);
        desc = `遭遇 ${sceneInfo.monster_name} ！`;
        break;
      case "SHOP":
        emoji = "🛒";
        desc = "神秘商人的店铺";
        break;
      case "EVENT":
        emoji = getEventEmoji(state.event_info ? state.event_info.title : "");
        if (state.event_info && state.event_info.description) {
          desc = state.event_info.description;
        } else {
          desc = "发生了一些意外...";
        }
        break;
      case "GAME_OVER":
        emoji = "💀";
        desc = "胜败乃兵家常事...";
        break;
      case "USE_ITEM":
        emoji = "🎒";
        desc = "打开背包...";
        break;
    }

    // Render Standard Buttons
    (sceneInfo.choices || []).forEach((text, idx) => {
      if (!text) return;
      const btn = document.createElement("button");
      btn.className = "main-btn";
      btn.textContent = text;
      btn.onclick = () => buttonAction(idx);
      buttonArea.appendChild(btn);
    });
  }

  sceneEmojiDiv.textContent = emoji;

  const currentSceneKey = `${sceneInfo.type}_${sceneInfo.monster_name || ""}`;
  if (desc && currentSceneKey !== lastSceneKey) {
    addLog(desc);
    lastSceneKey = currentSceneKey;
  }



  // 3. Render Inventory
  const inventoryArea = document.getElementById("inventory-area");
  if (p.inventory) {
    let invText = "";
    const allItems = [];
    for (const itemType in p.inventory) {
      const items = p.inventory[itemType];
      items.forEach(item => {
        allItems.push(`<span class="inv-item">${item.name}</span>`);
      });
    }
    if (allItems.length > 0) {
      inventoryArea.innerHTML = "库存: " + allItems.join(", ");
    } else {
      inventoryArea.textContent = "库存: 暂无道具";
    }
  } else {
    inventoryArea.textContent = "库存: 暂无道具";
  }

  // 4. Update Buttons
  // 如果是 GameOver 场景，可能需要禁用某些按钮或者显示特定文本
  // Server 端已经返回了 button_texts
  const btn1 = document.getElementById("btn1");
  const btn2 = document.getElementById("btn2");
  const btn3 = document.getElementById("btn3");

  if (state.button_texts && btn1 && btn2 && btn3) {
    btn1.textContent = state.button_texts[0] || "-";
    btn2.textContent = state.button_texts[1] || "-";
    btn3.textContent = state.button_texts[2] || "-";

    // 简单的禁用逻辑：如果文本是空或者是 "-"，可能禁用
    btn1.disabled = !state.button_texts[0];
    btn2.disabled = !state.button_texts[1];
    btn3.disabled = !state.button_texts[2];
  }

  // 如果有 last_message 需要显示 (在 getState 中返回的)
  if (state.last_message) {
    addLog(state.last_message);
  }
}

function getMonsterEmoji(name) {
  if (!name) return "👾";
  // 精确匹配优先，避免子串重叠
  const emojiMap = {
    "小哥布林": "👺", "史莱姆": "🟢", "蝙蝠": "🦇", "野狼": "🐺",
    "食人花": "🌸", "小蜥蜴人": "🦎", "土匪": "🗡️", "小鸟妖": "🧚",
    "半人马": "🏹", "牛头人": "🐂", "树人": "🌳", "狼人": "🌙",
    "食人魔": "👹", "美杜莎": "🐍", "巨型蝎子": "🦂", "幽灵": "👻",
    "巨魔酋长": "🧌", "九头蛇": "🐲", "石像鬼": "🗿", "吸血鬼": "🧛",
    "独眼巨人": "👁️", "精灵法师": "🧙", "地狱犬": "🔥", "巨型蜘蛛": "🕷️",
    "青铜龙": "🐉", "白银龙": "💎", "黄金龙": "🌟",
    "死亡骑士": "💀", "冰霜巨人": "❄️", "暗影刺客": "🥷", "雷鸟": "⚡",
    "海妖": "🧜", "地穴领主": "🏛️", "炎魔": "😈",
    "利维坦": "🐋", "凤凰": "🦅", "泰坦": "🏔️", "冥界使者": "🕴️",
    "天使": "😇", "混沌巫师": "🌀", "远古守卫": "🛡️",
    "克拉肯": "🐙", "天启骑士": "☠️", "世界之蛇": "🌐", "深渊领主": "🦑",
    "创世神官": "✨", "混沌之主": "💫", "永恒守护者": "🔮",
  };
  if (emojiMap[name]) return emojiMap[name];
  // 关键词回退
  if (name.includes("龙")) return "🐉";
  if (name.includes("蛇")) return "🐍";
  if (name.includes("狼")) return "🐺";
  if (name.includes("哥布林")) return "👺";
  if (name.includes("蝎")) return "🦂";
  if (name.includes("蜘蛛")) return "🕷️";
  if (name.includes("鸟")) return "🦅";
  if (name.includes("花")) return "🌸";
  if (name.includes("蜥蜴")) return "🦎";
  if (name.includes("人") || name.includes("骑")) return "⚔️";
  if (name.includes("鬼") || name.includes("灵")) return "👻";
  if (name.includes("魔") || name.includes("妖")) return "😈";
  return "👾";
}

function getEventEmoji(title) {
  if (!title) return "❔";
  if (title.includes("Stranger")) return "🤕";
  if (title.includes("Smuggler")) return "🕵️";
  if (title.includes("Shrine")) return "⛩️";
  if (title.includes("Gambler")) return "🎲";
  if (title.includes("Lost Child")) return "👧";
  if (title.includes("Cursed Chest")) return "🧰";
  if (title.includes("Wise Sage")) return "🧙";
  if (title.includes("Refugee Caravan")) return "🧺";
  if (title.includes("Fallen Knight")) return "🛡️";
  return "🎭";
}

function addLog(msg) {
  if (!msg) return;
  SoundSystem.scanLogAndPlay(msg);
  const logArea = document.getElementById("log-area");

  // 支持多行文本
  const lines = msg.split("\n");

  lines.forEach(line => {
    if (!line.trim()) return;

    const div = document.createElement("div");

    // Colorize Logic
    let html = line;

    // Round headers
    if (line.includes("回合：")) {
      div.className = "log-round";
    }

    // Damage (Red)
    if (line.includes("伤害")) {
      html = html.replace(/(\d+)(\s*点伤害)/g, '<span class="log-damage">$1$2</span>');
      // Check for player taking damage vs monster
      if (line.includes("你受到了")) {
        div.style.backgroundColor = "#ffebee"; // Light red background for player hurt
      }
    }

    // Heal (Green)
    if (line.includes("恢复") || line.includes("治疗")) {
      html = html.replace(/恢复\s*(\d+)\s*HP/g, '恢复 <span class="log-heal">$1 HP</span>');
    }

    // Gold (Yellow/Gold)
    if (line.includes("金币")) {
      html = html.replace(/(\d+)(\s*金币)/g, '<span class="log-gold">$1$2</span>');
    }

    // Items (Blue)
    if (line.includes("获得") && !line.includes("金币")) {
      // 简单的 heuristic: 获得 [something]
      html = html.replace(/获得\s*([^！!]+)/g, '获得 <span class="log-item">$1</span>');
    }

    div.innerHTML = html;
    logArea.appendChild(div);
  });

  logArea.scrollTop = logArea.scrollHeight;
}
