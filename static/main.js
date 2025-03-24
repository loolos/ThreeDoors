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
  statusArea.textContent = `回合: ${state.round} | HP: ${state.player.hp}, ATK: ${state.player.atk}, Gold: ${state.player.gold}, 卷轴: ${state.player.revive_scroll_count}, 状态: ${state.player.status_desc}`;

  // 如果有 last_message，则显示在日志中
  if(state.last_message) {
    addLog(state.last_message);
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
    btn1.textContent = "攻击";
    btn2.textContent = "防御";
    btn3.textContent = "逃跑";
  } else if (state.scene === "ShopScene") {
    if (state.shop_items && state.shop_items.length === 3) {
      btn1.textContent = `${state.shop_items[0].name} (${state.shop_items[0].cost}G)`;
      btn2.textContent = `${state.shop_items[1].name} (${state.shop_items[1].cost}G)`;
      btn3.textContent = `${state.shop_items[2].name} (${state.shop_items[2].cost}G)`;
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
