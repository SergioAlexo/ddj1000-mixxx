// Offline test for the DDJ-1000 mapping: runs the script against a mock of
// Mixxx's controller engine and replays every MIDI message the XML declares.
//
// Run:  node tools/test_mapping.js

"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const root = path.resolve(__dirname, "..");
const xml = fs.readFileSync(path.join(root, "controllers", "Pioneer-DDJ-1000-Complete.midi.xml"), "utf8");
const code = fs.readFileSync(path.join(root, "controllers", "Pioneer-DDJ-1000-Complete-scripts.js"), "utf8");

// ---------------------------------------------------------------- mock engine
const values = new Map();
const connections = [];
const timers = new Map();
let timerId = 0;
let sent = [];
const sysex = [];
const warnings = [];
let now = 1000000;

const defaults = {
    "[App],num_samplers": 16,
    "[Controls],ShowDurationRemaining": 1,
};
const k = (g, c) => g + "," + c;
const get = (g, c) => {
    const key = k(g, c);
    if (values.has(key)) return values.get(key);
    if (key in defaults) return defaults[key];
    if (/hotcue_\d+_position/.test(c) || /hotcue_\d+_color/.test(c)) return -1;
    if (c === "cue_point" || c === "loop_start_position" || c === "loop_end_position") return -1;
    if (c === "rate_dir") return 1;
    return 0;
};
const set = (g, c, v) => {
    if (typeof v !== "number" || Number.isNaN(v)) {
        throw new Error(`setValue(${g}, ${c}) with non-number ${v}`);
    }
    values.set(k(g, c), v);
    connections.filter((x) => x.g === g && x.c === c && x.live).forEach((x) => x.cb(v, g, c));
};

const engine = {
    getValue: get,
    setValue: set,
    getParameter: get,
    setParameter: set,
    makeConnection(g, c, cb) {
        const conn = { g, c, cb, live: true };
        conn.trigger = () => cb(get(g, c), g, c);
        conn.disconnect = () => { conn.live = false; };
        connections.push(conn);
        return conn;
    },
    beginTimer(ms, cb, oneShot) {
        if (typeof cb !== "function") throw new Error("timer callback must be a function");
        timers.set(++timerId, { ms, cb, oneShot, due: now + ms });
        return timerId;
    },
    stopTimer(id) { timers.delete(id); },
    softTakeover() {},
    scratching: {},
    scratchEnable(deck, ticks, rpm, a, b) {
        assert(ticks > 0 && rpm > 0 && a > 0 && b > 0);
        this.scratching[deck] = true;
    },
    scratchTick(deck, t) { assert(Number.isFinite(t)); },
    scratchDisable(deck) { this.scratching[deck] = false; },
    isScratching(deck) { return !!this.scratching[deck]; },
    brake(deck, on) { set(`[Channel${deck}]`, "_brake", on ? 1 : 0); },
    spinback(deck, on) { set(`[Channel${deck}]`, "_spinback", on ? 1 : 0); },
};
const midi = {
    sendShortMsg(s, d1, d2) {
        [s, d1, d2].forEach((b, i) => {
            if (!Number.isInteger(b) || b < 0 || b > (i === 0 ? 0xFF : 0x7F)) {
                throw new Error(`bad MIDI byte ${b} in ${s},${d1},${d2}`);
            }
        });
        sent.push([s, d1, d2]);
    },
    sendSysexMsg(data, length) {
        if (data[0] !== 0xF0 || data[data.length - 1] !== 0xF7 || length !== data.length
                || data.slice(1, -1).some((b) => !Number.isInteger(b) || b < 0 || b > 0x7F)) {
            throw new Error(`bad SysEx ${JSON.stringify(data)} length ${length}`);
        }
        sysex.push(data);
    },
};
const script = {
    deckFromGroup(g) { const m = /\[Channel(\d)\]/.exec(g); return m ? +m[1] : 0; },
};
const ctx = { engine, midi, script, print: (s) => warnings.push(String(s)), Date: { now: () => now }, Math, Object, Number, JSON };
vm.createContext(ctx);
vm.runInContext(code, ctx, { filename: "Pioneer-DDJ-1000-Complete-scripts.js" });
const DDJ = ctx.DDJ1000;

function advance(ms) {
    const end = now + ms;
    while (true) {
        let next = null;
        for (const [id, t] of timers) if (t.due <= end && (!next || t.due < next[1].due)) next = [id, t];
        if (!next) break;
        now = next[1].due;
        const [id, t] = next;
        if (t.oneShot) timers.delete(id); else t.due += t.ms;
        t.cb();
    }
    now = end;
}

// ------------------------------------------------------------ parse the XML
const entries = [...xml.matchAll(/<control>([\s\S]*?)<\/control>/g)].map((m) => {
    const tag = (t) => (new RegExp(`<${t}>([^<]*)</${t}>`).exec(m[1]) || [])[1];
    return {
        group: tag("group"), key: tag("key"), status: parseInt(tag("status"), 16),
        midino: parseInt(tag("midino"), 16), script: m[1].includes("<script-binding/>"),
    };
});
const byAddr = new Map(entries.map((e) => [e.status * 256 + e.midino, e]));

function send(status, midino, value) {
    const e = byAddr.get(status * 256 + midino);
    assert(e, `no mapping for ${status.toString(16)} ${midino.toString(16)}`);
    if (!e.script) return;
    const fn = e.key.split(".").slice(1).reduce((o, p) => o[p], DDJ);
    assert.strictEqual(typeof fn, "function", `handler ${e.key} missing`);
    fn(status & 0x0F, midino, value, status, e.group);
}

// ---------------------------------------------------------------- 1. startup
DDJ.init("DDJ-1000", false);
assert.strictEqual(sent.length, 0, "nothing may be sent from init (output not open yet)");
advance(50);
assert(sent.some(([s, d1, d2]) => s === 0x90 && d1 === 0x5D && d2 === 0x00), "jog display info shown");
assert(sent.some(([s, d1, d2]) => s === 0x90 && d1 === 0x5B && d2 === 0x01), "jog ring lit");
assert.strictEqual(get("[Channel1]", "rateRange"), 0.10);
assert.strictEqual(get("[Channel1]", "cue_mode"), 1);
assert.strictEqual(get("[Master]", "headMix"), -1);
assert(sysex.some((m) => m.join(",") === "240,0,64,5,0,0,2,0,0,3,1,247"), "position request SysEx sent at startup");
console.log("startup ok,", sent.length, "opening messages");

// ------------------------------------------------ 2. every declared message
let handled = 0;
for (const e of entries) {
    if (!e.script) continue;
    for (const v of [0x7F, 0x00, 0x41, 0x3F, 0x01, 0x7E]) send(e.status, e.midino, v);
    handled++;
    advance(5);
}
advance(2000);
console.log("replayed", handled, "script bindings x 6 values without error");

// Reset state for scenario tests.
values.clear();
sent = [];
DDJ.decks.forEach((d) => { DDJ.deck[d] = DDJ.newDeckState(); });
DDJ.beatFx.on = false;
DDJ.beatFx.rolling = [];
DDJ.beatFx.beatIndex = DDJ.settings.defaultBeatIndex;
DDJ.colorFx = 0;

// ------------------------------------------------------ 3. display scenario
const g1 = "[Channel1]";
set(g1, "track_samplerate", 44100);
set(g1, "duration", 300);
set(g1, "track_samples", 300 * 44100 * 2);
set(g1, "bpm", 128.0);
set(g1, "key", 22); // A minor
set(g1, "playposition", 0.5);
set(g1, "rate_ratio", 1.08);
set(g1, "track_loaded", 1);
set(g1, "cue_point", 10 * 44100 * 2);
set("[Controls]", "ShowDurationRemaining", 1);
DDJ.sent = {};
advance(100);
const last = (s, d1) => { const m = sent.filter((x) => x[0] === s && x[1] === d1); return m.length ? m[m.length - 1][2] : undefined; };
const last14 = (s, msb) => (last(s, msb) << 7) | last(s, msb + 0x20);
assert.strictEqual(last14(0xB0, 0x15), 1280, "BPM 128.0 -> 1280");
assert.strictEqual(last(0x90, 0x49), 2, "A minor -> key code 2");
assert.strictEqual(last(0x90, 0x44), 0x7F, "remaining time mode");
assert.strictEqual(last(0x90, 0x42), 2, "150 s remaining -> 2 min");
assert.strictEqual(last(0x90, 0x43), 30, "150 s remaining -> 30 s");
assert.strictEqual(last14(0xB0, 0x16), Math.round(1.08 * 4999.5), "+8% speed");
const bar = last14(0xB0, 0x14);
assert(bar >= 0 && bar <= 359, "position bar in degrees");
assert(Math.abs(bar - ((150 / 1.8) % 1) * 360) <= 1, "position bar spins at 33 1/3");
console.log("jog display ok: bpm/key/time/speed/position");

// Smooth jog display: between Mixxx's 15/s position reports the bar keeps turning.
{
    set(g1, "rate_ratio", 1);
    set(g1, "play", 1);
    set(g1, "playposition", 0.5);           // reported now
    const before = DDJ.estimateElapsed(1, g1, 300);
    now += 60;
    const after = DDJ.estimateElapsed(1, g1, 300);
    assert(Math.abs(after - before - 0.06) < 1e-9, "advances 60 ms at normal speed");
    set(g1, "rate_ratio", 1.1);
    assert(Math.abs(DDJ.estimateElapsed(1, g1, 300) - before - 0.066) < 1e-9, "follows the tempo");
    now += 500;
    assert(Math.abs(DDJ.estimateElapsed(1, g1, 300) - before - 0.11) < 1e-9, "never predicts more than 100 ms");
    set(g1, "play", 0);
    assert.strictEqual(DDJ.estimateElapsed(1, g1, 300), 150, "paused: the reported position");
    set(g1, "rate_ratio", 1.08);
    console.log("smooth jog display prediction ok");
}


// Key codes against the table in the MIDI message list.
const table = ["---", "C", "Am", "Db", "Bbm", "D", "Bm", "Eb", "Cm", "E", "Dbm", "F", "Dm", "F#", "Ebm", "G", "Em", "Ab", "Fm", "A", "F#m", "Bb", "Gm", "B", "Abm"];
const mixxxKeys = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B", "Cm", "Dbm", "Dm", "Ebm", "Em", "Fm", "F#m", "Gm", "Abm", "Am", "Bbm", "Bm"];
mixxxKeys.forEach((name, i) => assert.strictEqual(table[DDJ.keyCode(i + 1)], name, `key ${name}`));
console.log("all 24 key codes match the DDJ table");

// ------------------------------------------------------- 4. tempo slider
set(g1, "rate_dir", 1);
send(0xB0, 0x00, 0x00); send(0xB0, 0x20, 0x00);
assert.strictEqual(get(g1, "rate"), -1, "top of slider = slowest");
send(0xB0, 0x00, 0x7F); send(0xB0, 0x20, 0x7F);
assert.strictEqual(get(g1, "rate"), 1, "bottom = fastest");
send(0xB0, 0x00, 0x40); send(0xB0, 0x20, 0x00);
assert(Math.abs(get(g1, "rate")) < 0.001, "centre = 0");
set(g1, "rate_dir", -1);
send(0xB0, 0x00, 0x7F); send(0xB0, 0x20, 0x7F);
assert.strictEqual(get(g1, "rate"), -1, "respects Mixxx slider direction");
set(g1, "rate_dir", 1);
set(g1, "rateRange", 0.10);
send(0x90, 0x60, 0x7F); assert.strictEqual(get(g1, "rateRange"), 0.16);
send(0x90, 0x60, 0x7F); assert.strictEqual(get(g1, "rateRange"), 1.00);
send(0x90, 0x60, 0x7F); assert.strictEqual(get(g1, "rateRange"), 0.06);
send(0x90, 0x60, 0x7F); assert.strictEqual(get(g1, "rateRange"), 0.10);
console.log("tempo slider and TEMPO RANGE ok");

// ---------------------------------------------------------- 5. hot cues
send(0x97, 0x00, 0x7F);
assert.strictEqual(get(g1, "hotcue_1_activate"), 1);
send(0x97, 0x00, 0x00);
assert.strictEqual(get(g1, "hotcue_1_activate"), 0, "release ends preview");
send(0x98, 0x02, 0x7F);
assert.strictEqual(get(g1, "hotcue_3_clear"), 1, "SHIFT + pad deletes");
send(0x97, 0x09, 0x7F);
assert.strictEqual(get(g1, "hotcue_10_activate"), 1, "page 2 pad 2 = hot cue 10");
set(g1, "hotcue_1_status", 1);
set(g1, "hotcue_1_color", 0xFF0000);
DDJ.deck[1].mode = 0;
advance(50);
assert.strictEqual(last(0x97, 0x00), 41, "red hot cue -> pad colour 41");
set(g1, "hotcue_2_status", 1);
set(g1, "hotcue_2_color", 0x0000FF);
advance(50);
assert.strictEqual(last(0x97, 0x01), 1, "blue hot cue -> pad colour 1");
console.log("hot cues ok");

// ------------------------------------------------------ 6. other pad modes
send(0x97, 0x20, 0x7F); // BEAT JUMP pad 1 = REV1
assert.strictEqual(get(g1, "beatjump"), -1);
send(0x90, 0x2E, 0x7F); // PAGE > in beat jump: double range
send(0x97, 0x23, 0x7F); // pad 4 = FWD2
assert.strictEqual(get(g1, "beatjump"), 4);
send(0x97, 0x60, 0x7F); // BEAT LOOP page 1 pad 1 = 1/4
assert.strictEqual(get(g1, "beatloop_size"), 0.25);
assert.strictEqual(get(g1, "beatloop_activate"), 1);
send(0x97, 0x74, 0x7F); // KEY SHIFT pad 5 = 0 semitones
assert.strictEqual(get(g1, "pitch_adjust"), 0);
send(0x97, 0x73, 0x7F); // KEY SHIFT pad 4 = +7
assert.strictEqual(get(g1, "pitch_adjust"), 7);
send(0x97, 0x73, 0x7F); // again -> back to 0
assert.strictEqual(get(g1, "pitch_adjust"), 0);
send(0x97, 0x44, 0x7F); // KEYBOARD pad 5 = 0 semitones, plays hot cue 1 (unset -> cue)
assert.strictEqual(get(g1, "cue_gotoandplay"), 1);
send(0x97, 0x34, 0x7F); // SAMPLER pad 5 -> sampler 5 (empty -> load)
assert.strictEqual(get("[Sampler5]", "LoadSelectedTrack"), 1);
set("[Sampler5]", "track_loaded", 1);
send(0x97, 0x34, 0x7F);
assert.strictEqual(get("[Sampler5]", "cue_gotoandplay"), 1);
send(0x98, 0x34, 0x7F);
assert.strictEqual(get("[Sampler5]", "cue_gotoandstop"), 1);
send(0x97, 0x10, 0x7F); // PAD FX1 pad 1 = ECHO 1/2
assert.strictEqual(get("[EffectRack1_EffectUnit3]", "loaded_chain_preset"), DDJ.PRESET.ECHO);
assert.strictEqual(get("[EffectRack1_EffectUnit3]", "enabled"), 1);
assert.strictEqual(get("[EffectRack1_EffectUnit3]", "group_[Channel1]_enable"), 1);
assert.strictEqual(get("[EffectRack1_EffectUnit3_Effect1]", "parameter1"), 0.5);
send(0x97, 0x10, 0x00);
assert.strictEqual(get("[EffectRack1_EffectUnit3]", "enabled"), 0);
send(0x97, 0x14, 0x7F); // PAD FX1 pad 5 = roll 1/16
assert.strictEqual(get(g1, "beatloop_size"), 1 / 16);
assert.strictEqual(get(g1, "beatlooproll_activate"), 1);
send(0x97, 0x14, 0x00);
assert.strictEqual(get(g1, "beatlooproll_activate"), 0);
console.log("beat jump / beat loop / key shift / keyboard / sampler / pad FX ok");

// ----------------------------------------------------------- 7. loops
send(0x90, 0x10, 0x7F);
assert.strictEqual(get(g1, "loop_in"), 1);
send(0x90, 0x12, 0x7F);
assert.strictEqual(get(g1, "loop_halve"), 1);
set(g1, "loop_enabled", 1);
advance(50);
assert.strictEqual(last(0x9F, 0x04), 0x7F, "unit told a loop is running");
send(0x90, 0x14, 0x7F);
assert.strictEqual(get(g1, "loop_enabled"), 0, "4 BEAT/EXIT exits a running loop");
send(0x90, 0x14, 0x7F);
assert.strictEqual(get(g1, "beatloop_4_activate"), 1, "4 BEAT/EXIT starts a 4 beat loop");
set(g1, "loop_start_position", 441000);
set(g1, "loop_end_position", 882000);
set(g1, "loop_enabled", 1);
send(0x90, 0x4C, 0x7F); // loop in adjust
assert.strictEqual(DDJ.deck[1].loopAdjust, "in");
send(0xB0, 0x21, 0x40 + 20);
assert(get(g1, "loop_start_position") > 441000, "jog moves the loop in point");
send(0x90, 0x4C, 0x7F);
assert.strictEqual(DDJ.deck[1].loopAdjust, null);
console.log("loops ok");

// ---------------------------------------------------------------- 8. jog
DDJ.deck[1].vinyl = true;
send(0x90, 0x36, 0x7F);
assert(engine.isScratching(1), "touch starts scratching in VINYL mode");
send(0xB0, 0x22, 0x45);
send(0x90, 0x36, 0x00);
advance(200);
assert(!engine.isScratching(1), "released, stopped platter hands back to playback");
send(0x90, 0x17, 0x7F); // VINYL off
send(0x90, 0x36, 0x7F);
assert(!engine.isScratching(1), "no scratch with VINYL off");
send(0x90, 0x36, 0x00);
send(0xB0, 0x23, 0x48);
assert(get(g1, "jog") > 0, "platter bends pitch with VINYL off");
console.log("jog ok");

// ------------------------------------------------------------- 9. Beat FX
send(0x94, 0x21, 0x7F); // ECHO
send(0x94, 0x14, 0x7F); // MASTER
send(0xB4, 0x02, 0x40); send(0xB4, 0x22, 0x00);
send(0x94, 0x47, 0x7F);
assert.strictEqual(get("[EffectRack1_EffectUnit1]", "enabled"), 1);
assert.strictEqual(get("[EffectRack1_EffectUnit1]", "group_[Master]_enable"), 1);
assert(Math.abs(get("[EffectRack1_EffectUnit1]", "mix") - 0.5) < 0.01);
send(0x94, 0x4B, 0x7F); // BEAT > : 1 -> 2 beats
assert.strictEqual(get("[EffectRack1_EffectUnit1_Effect1]", "parameter1"), 2);
send(0x94, 0x10, 0x7F); // CH1
assert.strictEqual(get("[EffectRack1_EffectUnit1]", "group_[Channel1]_enable"), 1);
assert.strictEqual(get("[EffectRack1_EffectUnit1]", "group_[Master]_enable"), 0);
send(0x94, 0x2A, 0x7F); // SLIP ROLL while on
assert.strictEqual(get(g1, "beatlooproll_activate"), 1, "roll runs on CH1");
send(0x94, 0x47, 0x7F);
assert.strictEqual(get(g1, "beatlooproll_activate"), 0);
console.log("beat FX ok");

// ------------------------------------------------------ 10. color FX
send(0x96, 0x03, 0x7F); // FILTER
assert.strictEqual(get("[QuickEffectRack1_[Channel2]]", "loaded_chain_preset"), DDJ.QUICK.FILTER);
assert.strictEqual(get("[QuickEffectRack1_[Channel2]]", "enabled"), 1);
send(0x96, 0x03, 0x7F); // off again
assert.strictEqual(get("[QuickEffectRack1_[Channel2]]", "enabled"), 0);
console.log("sound color FX ok");

// ------------------------------------------------------ 11. memory cues
set(g1, "playposition", 0.25);
send(0x90, 0x3D, 0x7F);
assert.strictEqual(get(g1, "hotcue_17_set"), 1, "MEMORY stores in hot cue 17");
set(g1, "hotcue_17_position", 0.25 * get(g1, "track_samples"));
set(g1, "playposition", 0.5);
send(0x90, 0x51, 0x7F); // CUE/LOOP CALL <
assert(Math.abs(get(g1, "playposition") - 0.25) < 1e-9, "call jumps back to the memory cue");
send(0x90, 0x3E, 0x7F);
assert.strictEqual(get(g1, "hotcue_17_clear"), 1, "DELETE clears it");
console.log("memory cues ok");

// Backspin: once the deck is handed back, a still-coasting platter must not
// pitch-bend the track (that is what sounded off-key).
{
    const g = "[Channel2]";
    set(g, "play", 1);
    set(g, "jog", 0);
    DDJ.deck[2].vinyl = true;
    send(0x91, 0x36, 0x7F);                                    // touch
    for (let i = 0; i < 6; i++) { send(0xB1, 0x22, 0x40 - 60); now += 10; } // spin backwards
    send(0x91, 0x36, 0x00);                                    // let go
    // The heavy platter keeps turning backwards, slowing down, and the outer
    // ring reports it all the way.
    let bent = false;
    for (let speed = 60; speed >= 1; speed -= 1) {
        send(0xB1, 0x21, 0x40 - speed);
        advance(10);
        if (!engine.isScratching(2) && get(g, "jog") !== 0) { bent = true; }
    }
    assert(!engine.isScratching(2), "deck handed back once the platter slowed down");
    assert.strictEqual(bent, false, "coasting platter never bends the pitch");
    advance(400);                                              // platter at rest
    send(0xB1, 0x21, 0x40 + 5);
    assert(get(g, "jog") > 0, "outer ring bends again once the platter has stopped");
    console.log("backspin: no off-key bend while the platter coasts");
}

// SHIFT + QUANTIZE: headphones mono split, with the QUANTIZE light showing it.
{
    set("[Master]", "headSplit", 0);
    send(0x90, 0x39, 0x7F);
    assert.strictEqual(get("[Master]", "headSplit"), 1, "split on");
    advance(50);
    assert.strictEqual(last(0x90, 0x39), 0x7F, "light on");
    send(0x92, 0x39, 0x7F);
    assert.strictEqual(get("[Master]", "headSplit"), 0, "any deck turns it off again");
    advance(50);
    assert.strictEqual(last(0x93, 0x39), 0x00, "light off on every deck");
    console.log("mono split toggle ok");
}


// ---------------------------------------------------------- 12. shutdown
DDJ.shutdown();
assert.strictEqual(timers.size === 0 || [...timers.values()].every((t) => t.oneShot), true, "display timer stopped");
console.log("\nALL TESTS PASSED");
if (warnings.length) console.log("script printed:", warnings.slice(0, 5));
