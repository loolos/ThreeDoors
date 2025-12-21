// static/main.js

let lastSceneKey = ""; // 用于防止重复记录日志

document.addEventListener("DOMContentLoaded", () => {
  initUI();
  getStateAndRender();
  document.getElementById("startOverBtn").addEventListener("click", startOver);
  document.getElementById("exitGameBtn").addEventListener("click", exitGame);
});

function initUI() {
  document.getElementById("btn1").addEventListener("click", () => buttonAction(0));
  document.getElementById("btn2").addEventListener("click", () => buttonAction(1));
  document.getElementById("btn3").addEventListener("click", () => buttonAction(2));
}

async function buttonAction(index) {
  try {
    const res = await fetch("/buttonAction", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: index })
    });
    const data = await res.json();
    // 如果有日志，先解析颜色再添加
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
  const res = await fetch("/exitGame", { method: "POST" });
  const data = await res.json();
  addLog(data.log || data.msg);

  // 禁用所有按钮
  document.querySelectorAll("button").forEach(b => b.disabled = true);

  // 1秒后关闭窗口
  setTimeout(() => {
    window.close();
  }, 1000);
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
  // 1. Render Status Area (HP Bar, etc)
  const p = state.player;
  const maxHp = p.max_hp || 20; // 默认20防错
  const hpPercent = Math.max(0, Math.min(100, (p.hp / maxHp) * 100));

  document.getElementById("hp-bar-fill").style.width = hpPercent + "%";
  document.getElementById("hp-text").textContent = `${p.hp}`;

  let statsText = `ATK: ${p.atk} | Gold: ${p.gold} | Round: ${state.round}`;
  if (p.status_desc && p.status_desc !== "无") {
    statsText += ` | ${p.status_desc}`;
  }
  document.getElementById("other-stats").textContent = statsText;

  // 2. Render Scene Emoji
  const sceneInfo = state.scene_info || {};
  const sceneEmojiDiv = document.getElementById("scene-emoji");

  let emoji = "❓";
  let desc = "";

  switch (sceneInfo.type) {
    case "DOOR":
      emoji = "🚪";
      desc = "面对三扇门，命运在你手中...";
      break;
    case "BATTLE":
      emoji = getMonsterEmoji(sceneInfo.monster_name);
      desc = `遭遇 ${sceneInfo.monster_name} ！`;
      break;
    case "SHOP":
      emoji = "🛒";
      desc = "神秘商人的店铺";
      break;
    case "USE_ITEM":
      emoji = "🎒";
      desc = "选择要使用的道具";
      break;
    case "GAME_OVER":
      emoji = "💀";
      desc = "胜败乃兵家常事...";
      break;
    case "EVENT":
      emoji = getEventEmoji(state.event_info ? state.event_info.title : "");
      if (state.event_info) {
        desc = state.event_info.description;
        // Add title to description for context if needed, or just rely on desc
        // desc = `【${state.event_info.title}】\n${state.event_info.description}`; 
      } else {
        desc = "发生了一个事件...";
      }
      break;
    default:
      emoji = "✨";
      desc = "未知领域";
  }

  sceneEmojiDiv.textContent = emoji;

  // 生成一个唯一的场景 Key，包含场景类型和怪物名称（如果有）
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
