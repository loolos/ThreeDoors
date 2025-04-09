// static/main.js

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
  const res = await fetch("/buttonAction", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ index: index })
  });
  const data = await res.json();
  addLog(data.log);
  getStateAndRender();
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
  // 1秒后关闭窗口
  setTimeout(() => {
    window.close();
  }, 1000);
}

async function getStateAndRender() {
  const res = await fetch("/getState");
  const state = await res.json();
  renderState(state);
}

function renderState(state) {
  const statusArea = document.getElementById("status-area");
  statusArea.textContent = `回合: ${state.round} | HP: ${state.player.hp}, ATK: ${state.player.atk}, Gold: ${state.player.gold}, 状态: ${state.player.status_desc}`;

  // 显示库存内容
  const inventoryArea = document.getElementById("inventory-area");
  if (state.player.inventory) {
    let invText = "库存：";
    // 合并所有类型的物品名称
    const allItems = [];
    for (const itemType in state.player.inventory) {
      const items = state.player.inventory[itemType];
      allItems.push(...items.map(item => item.name));
    }
    invText += allItems.join(", ");
    inventoryArea.textContent = invText;
  } else {
    inventoryArea.textContent = "库存：暂无道具";
  }

  const btn1 = document.getElementById("btn1");
  const btn2 = document.getElementById("btn2");
  const btn3 = document.getElementById("btn3");

  // 使用后端提供的按钮文本
  btn1.textContent = state.button_texts[0];
  btn2.textContent = state.button_texts[1];
  btn3.textContent = state.button_texts[2];
}

function addLog(msg) {
  const logArea = document.getElementById("log-area");
  const div = document.createElement("div");
  div.textContent = msg;
  logArea.appendChild(div);
  logArea.scrollTop = logArea.scrollHeight;
}
