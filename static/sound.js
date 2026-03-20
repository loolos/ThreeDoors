// static/sound.js — 音效系统（依赖 Tone.js，需在 main.js 前加载）

const SOUND_STORAGE_KEY = "three_doors_sound_enabled";
const SoundSystem = {
  enabled: true,
  unlocked: false,
  lastTriggerAt: {},
  endingRollLoopTimer: null,
  endingRollLoopActive: false,

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

  /** 银羽秘藏（取回剧本）专属：轻柔的发现/秘藏感旋律，多音符短句 */
  playScriptVault() {
    if (!this.canTrigger("script_vault", 2000)) return;
    this.withPolySynth({
      oscillator: { type: "sine" },
      envelope: { attack: 0.02, decay: 0.1, sustain: 0.12, release: 0.3 },
      volume: -10,
    }, (synth, now) => {
      const notes = ["G4", "B4", "D5", "G5", "D5", "B4", "A4", "C5", "E5", "G5"];
      notes.forEach((note, i) => {
        const len = i >= 6 ? "16n" : "8n";
        synth.triggerAttackRelease(note, len, now + i * 0.1);
      });
    }, 1400);
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

  playEndingRollBgm() {
    if (!this.enabled || typeof Tone === "undefined") return;
    if (!this.canTrigger("ending_roll_phrase", 2500)) return;
    try {
      this.ensureReady();
      const now = Tone.now();
      const reverb = new Tone.Reverb({
        decay: 5.5,
        wet: 0.35,
      }).toDestination();
      const pad = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sine" },
        envelope: { attack: 0.8, decay: 1.2, sustain: 0.35, release: 2.2 },
        volume: -19,
      }).connect(reverb);
      const bell = new Tone.Synth({
        oscillator: { type: "triangle" },
        envelope: { attack: 0.15, decay: 0.35, sustain: 0.06, release: 1.5 },
        volume: -17,
      }).connect(reverb);

      const chords = [
        ["D4", "A4", "F5"],
        ["G4", "B4", "D5"],
        ["A3", "E4", "C5"],
        ["F4", "A4", "D5"],
      ];
      chords.forEach((chord, i) => {
        pad.triggerAttackRelease(chord, "2n", now + i * 1.25, 0.42);
      });
      ["A5", "G5", "F5", "E5"].forEach((note, i) => {
        bell.triggerAttackRelease(note, "8n", now + 0.65 + i * 0.95, 0.32);
      });

      setTimeout(() => {
        pad.dispose();
        bell.dispose();
        reverb.dispose();
      }, 9000);
    } catch (e) {}
  },

  startEndingRollBgm() {
    if (this.endingRollLoopActive) return;
    this.endingRollLoopActive = true;
    const run = () => {
      if (!this.endingRollLoopActive) return;
      this.playEndingRollBgm();
      this.endingRollLoopTimer = setTimeout(run, 8200);
    };
    run();
  },

  stopEndingRollBgm() {
    this.endingRollLoopActive = false;
    if (this.endingRollLoopTimer) {
      clearTimeout(this.endingRollLoopTimer);
      this.endingRollLoopTimer = null;
    }
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
    if (/刻着银羽暗号的宝物门|秘藏室中央.*防尘匣/.test(text)) this.playScriptVault();
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
      } else {
        SoundSystem.stopEndingRollBgm();
      }
    });
  }

  document.addEventListener("pointerdown", () => {
    SoundSystem.ensureReady();
  }, { passive: true });
}

// 暴露给 main.js 使用（sound.js 在 main.js 前加载）
window.SoundSystem = SoundSystem;
window.initSoundControls = initSoundControls;
window.updateSoundToggleBtn = updateSoundToggleBtn;
