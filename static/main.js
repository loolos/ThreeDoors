// static/main.js

document.addEventListener("DOMContentLoaded", () => {
  initUI();
  getStateAndRender();
  document.getElementById("startOverBtn").addEventListener("click", startOver);
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

async function getStateAndRender() {
  const res = await fetch("/getState");
  const state = await res.json();
  renderState(state);
}

function renderState(state) {
  const statusArea = document.getElementById("status-area");
  statusArea.textContent = `回合: ${state.round} | HP: ${state.player.hp}, ATK: ${state.player.atk}, Gold: ${state.player.gold}, 状态: ${state.player.status_desc}`;

  // 新增：显示库存内容
  const inventoryArea = document.getElementById("inventory-area");
  if (state.player.inventory && state.player.inventory.length > 0) {
    let invText = "库存：";
    // 列表显示所有道具名称（你也可以显示数量、效果等信息）
    invText += state.player.inventory.map(item => item.name).join(", ");
    inventoryArea.textContent = invText;
  } else {
    inventoryArea.textContent = "库存：暂无道具";
  }

  const btn1 = document.getElementById("btn1");
  const btn2 = document.getElementById("btn2");
  const btn3 = document.getElementById("btn3");

  if (state.scene === "DoorScene") {
    if (state.door_events && state.door_events.length === 3) {
      btn1.textContent = "门1 - " + state.door_events[0].hint;
      btn2.textContent = "门2 - " + state.door_events[1].hint;
      btn3.textContent = "门3 - " + state.door_events[2].hint;
    } else {
      btn1.textContent = "门1";
      btn2.textContent = "门2";
      btn3.textContent = "门3";
    }
  } else if (state.scene === "BattleScene") {
    // 战斗场景：第一个按钮显示攻击，第二显示“使用道具”，第三显示逃跑
    btn1.textContent = "攻击";
    btn2.textContent = "使用道具";
    btn3.textContent = "逃跑";
  } else if (state.scene === "ShopScene") {
    if (state.shop_items && state.shop_items.length === 3) {
      btn1.textContent = `${state.shop_items[0].name} (${state.shop_items[0].cost}G)`;
      btn2.textContent = `${state.shop_items[1].name} (${state.shop_items[1].cost}G)`;
      btn3.textContent = `${state.shop_items[2].name} (${state.shop_items[2].cost}G)`;
    }
  } else if (state.scene === "UseItemScene") {
    // 使用道具场景，显示库存中可主动使用的物品，若不足三个则显示“无”
    if (state.active_items && state.active_items.length > 0) {
      btn1.textContent = state.active_items[0] ? state.active_items[0].name : "无";
      btn2.textContent = state.active_items[1] ? state.active_items[1].name : "无";
      btn3.textContent = state.active_items[2] ? state.active_items[2].name : "无";
    } else {
      btn1.textContent = "无";
      btn2.textContent = "无";
      btn3.textContent = "无";
    }
  } else if (state.scene === "GameOver") {
    btn1.textContent = "重启游戏";
    btn2.textContent = "使用复活卷轴";
    btn3.textContent = "退出游戏";
  }
}

function addLog(msg) {
  const logArea = document.getElementById("log-area");
  const div = document.createElement("div");
  div.textContent = msg;
  logArea.appendChild(div);
  logArea.scrollTop = logArea.scrollHeight;
}
