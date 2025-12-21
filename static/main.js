// static/main.js

let lastSceneKey = ""; // 用于防止重复记录日志

const delay = ms => new Promise(res => setTimeout(res, ms));

document.addEventListener("DOMContentLoaded", () => {
  initUI();
  getStateAndRender();
  document.getElementById("startOverBtn").addEventListener("click", startOver);
  document.getElementById("exitGameBtn").addEventListener("click", exitGame);
});

function initUI() {
  // Clear old button listeners if any (relying on dynamic binding now)
  // We will dynamic bind events in renderState
}

// Map logic for result emoji
function getResultEmoji(sceneInfo) {
  if (sceneInfo.type === 'BATTLE') return getMonsterEmoji(sceneInfo.monster_name);
  if (sceneInfo.type === 'SHOP') return "🛒";
  if (sceneInfo.type === 'EVENT') return "❔";
  if (sceneInfo.type === 'GAME_OVER') return "💀";
  return "✨";
}

async function handleDoorClick(index) {
  try {
    // 1. Commit Action
    const actionRes = await fetch("/buttonAction", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: index })
    });
    const actionData = await actionRes.json();

    // 2. Get New State (to peek at result)
    const stateRes = await fetch("/getState");
    const newState = await stateRes.json();

    // 3. Reveal Animation
    const card = document.querySelectorAll('.door-card')[index];
    const backFace = card.querySelector('.back');

    // Set emoji based on what we found behind the door
    backFace.textContent = getResultEmoji(newState.scene_info);
    card.classList.add('flipped');

    // 4. Wait for flip
    await delay(1000);

    // 5. Render Full State (transition to next scene)
    if (actionData.log) addLog(actionData.log);
    renderState(newState);

  } catch (err) {
    console.error("Door Click Error:", err);
  }
}

async function buttonAction(index) {
  try {
    const res = await fetch("/buttonAction", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: index })
    });
    const data = await res.json();
    if (data.log) {
      addLog(data.log);
    }
    getStateAndRender();
  } catch (err) {
    console.error("Action error:", err);
  }
}

async function startOver() {
  const res = await fetch("/startOver", { method: "POST" });
  const data = await res.json();
  addLog(data.log || data.msg);
  getStateAndRender();
}

async function exitGame() {
  try {
    const res = await fetch("/exitGame", {
      method: "POST"
    });
    const data = await res.json();
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
    const res = await fetch("/getState");
    const state = await res.json();
    renderState(state);
  } catch (err) {
    console.error("GetState error:", err);
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
    (sceneInfo.choices || []).forEach((choiceText, idx) => {
      const card = document.createElement('div');
      card.className = 'door-card';
      card.innerHTML = `
            <div class="door-card-inner">
                <div class="door-face front">🚪</div>
                <div class="door-face back">?</div>
            </div>
          `;
      card.onclick = () => handleDoorClick(idx);
      doorArea.appendChild(card);
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

  if (state.button_texts) {
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
  if (name.includes("史莱姆")) return "💧";
  if (name.includes("哥布林")) return "👺";
  if (name.includes("狼")) return "🐺";
  if (name.includes("龙")) return "🐉";
  if (name.includes("鬼")) return "👻";
  if (name.includes("熊")) return "🐻";
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
  return "🎭";
}

function addLog(msg) {
  if (!msg) return;
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
