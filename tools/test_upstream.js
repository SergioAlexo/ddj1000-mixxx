// Offline test for the upstream (mixxxdj/mixxx) DDJ-1000 mapping: runs the script against a mock of
// Mixxx's controller engine and replays every MIDI message the XML declares.
//
// Run:  node tools/test_upstream.js [path to mixxx checkout]

"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const root = path.resolve(__dirname, "..");
const repo = process.argv[2] || path.resolve(root, "..", "mixxx");
const xml = fs.readFileSync(path.join(repo, "res", "controllers", "Pioneer-DDJ-1000.midi.xml"), "utf8");
const code = fs.readFileSync(path.join(repo, "res", "controllers", "Pioneer-DDJ-1000-scripts.js"), "utf8");

// ---------------------------------------------------------------- mock engine
const values = new Map();
const connections = [];
const timers = new Map();
let timerId = 0;
let sent = [];
const warnings = [];
let now = 1000000;

const defaults = {
    "[App],num_samplers": 16,
    "[App],num_microphones": 4,
    "[App],num_auxiliaries": 4,
    "[App],num_preview_decks": 1,
    "[Controls],ShowDurationRemaining": 1,
};
const k = (g, c) => g + "," + c;
let reads = 0;
const get = (g, c) => {
    reads++;
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

const settings = {};
const engine = {
    getSetting: (name) => settings[name],
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
};
const script = {
    deckFromGroup(g) { const m = /\[Channel(\d)\]/.exec(g); return m ? +m[1] : 0; },
};
// Mixxx's ColorMapper: nearest colour by RGB distance.
class ColorMapper {
    constructor(map) { this.map = map; }
    getValueForNearestColor(rgb) {
        let best, bestD = Infinity;
        for (const [c, v] of Object.entries(this.map)) {
            const n = Number(c);
            const d = ((n >> 16) - (rgb >> 16 & 255)) ** 2 + ((n >> 8 & 255) - (rgb >> 8 & 255)) ** 2 + ((n & 255) - (rgb & 255)) ** 2;
            if (d < bestD) { bestD = d; best = v; }
        }
        return best;
    }
}
const ctx = { engine, midi, script, ColorMapper, print: (s) => warnings.push(String(s)), Date: { now: () => now }, Math, Object, Number, JSON };
vm.createContext(ctx);
vm.runInContext(code, ctx, { filename: "Pioneer-DDJ-1000-scripts.js" });
const DDJ = ctx.PioneerDDJ1000;

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
assert.strictEqual(values.has("[Channel1],cue_mode"), false, "cue mode left to the user's preference");
assert.strictEqual(values.has("[Channel1],rateRange"), false, "tempo range left to the user's preference");
assert.strictEqual(get("[Master]", "headMix"), -1, "hardware headphone mix on by default");
console.log("startup ok,", sent.length, "opening messages; user preferences untouched");

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

// Fresh state for the scenarios.
DDJ.shutdown();
values.clear();
sent = [];
connections.length = 0;
timers.clear();
Object.assign(DDJ, { opened: false, sent: {}, colorFx: 0, heldUnits: {}, overrides: {}, samplersConnected: 0, padQueue: [] });
DDJ.beatFx = { position: 1, beatIndex: DDJ.config.defaultBeatIndex, target: null, on: false, rolling: [], rollSlip: false };
settings.tempoRange = "10";
settings.hardwareHeadphoneMix = false;
DDJ.init("DDJ-1000", false);
advance(50);
assert.strictEqual(get("[Channel1]", "rateRange"), 0.10, "tempoRange setting applies");
assert.strictEqual(values.has("[Master],headMix"), false, "headphone mix setting can be turned off");
console.log("settings ok");

// ------------------------------------------------------ 3. display
const g1 = "[Channel1]";
set(g1, "track_samplerate", 44100);
set(g1, "duration", 300);
set(g1, "track_samples", 300 * 44100 * 2);
set(g1, "bpm", 128.0);
set(g1, "key", 22);
set(g1, "playposition", 0.5);
set(g1, "rate_ratio", 1.08);
set(g1, "track_loaded", 1);
set("[Controls]", "ShowDurationRemaining", 1);
advance(100);
const last = (s, d1) => { const m = sent.filter((x) => x[0] === s && x[1] === d1); return m.length ? m[m.length - 1][2] : undefined; };
const last14 = (s, msb) => (last(s, msb) << 7) | last(s, msb + 0x20);
assert.strictEqual(last14(0xB0, 0x15), 1280, "BPM");
assert.strictEqual(last(0x90, 0x49), 2, "A minor");
assert.strictEqual(last(0x90, 0x42), 2);
assert.strictEqual(last(0x90, 0x43), 30);
assert.strictEqual(last14(0xB0, 0x16), Math.round(1.08 * 4999.5));
const table = ["---", "C", "Am", "Db", "Bbm", "D", "Bm", "Eb", "Cm", "E", "Dbm", "F", "Dm", "F#", "Ebm", "G", "Em", "Ab", "Fm", "A", "F#m", "Bb", "Gm", "B", "Abm"];
["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B", "Cm", "Dbm", "Dm", "Ebm", "Em", "Fm", "F#m", "Gm", "Abm", "Am", "Bbm", "Bm"]
    .forEach((name, i) => assert.strictEqual(table[DDJ.keyCode(i + 1)], name));
console.log("jog display ok, all 24 key codes match");

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


// ------------------------------------------------------ 4. tempo
set(g1, "rate_dir", 1);
send(0xB0, 0x00, 0x00); send(0xB0, 0x20, 0x00);
assert.strictEqual(get(g1, "rate"), -1);
send(0xB0, 0x00, 0x7F); send(0xB0, 0x20, 0x7F);
assert.strictEqual(get(g1, "rate"), 1);
[0.16, 1.00, 0.06, 0.10].forEach((range) => { send(0x90, 0x60, 0x7F); assert.strictEqual(get(g1, "rateRange"), range); });
console.log("tempo ok");

// ------------------------------------------------------ 5. hot cues + colours
send(0x97, 0x00, 0x7F);
assert.strictEqual(get(g1, "hotcue_1_activate"), 1);
send(0x97, 0x00, 0x00);
assert.strictEqual(get(g1, "hotcue_1_activate"), 0);
send(0x98, 0x02, 0x7F);
assert.strictEqual(get(g1, "hotcue_3_clear"), 1);
send(0x97, 0x09, 0x7F);
assert.strictEqual(get(g1, "hotcue_10_activate"), 1);
DDJ.deck[1].mode = 0;
[[0xFF0000, 41], [0x0000FF, 1], [0x00FF00, 21], [0xFFFF00, 29], [0xFFFFFF, 127]].forEach(([rgb, pad], i) => {
    set(g1, `hotcue_${i + 4}_status`, 1);
    set(g1, `hotcue_${i + 4}_color`, rgb);
    advance(50);
    assert.strictEqual(last(0x97, i + 3), pad, `colour ${rgb.toString(16)} -> ${pad}`);
});
console.log("hot cues and ColorMapper palette ok");

// ------------------------------------------------------ 6. pads
send(0x97, 0x20, 0x7F);
assert.strictEqual(get(g1, "beatjump"), -1);
send(0x90, 0x2E, 0x7F);
send(0x97, 0x23, 0x7F);
assert.strictEqual(get(g1, "beatjump"), 4, "PAGE > doubles jumps");
send(0x97, 0x60, 0x7F);
assert.strictEqual(get(g1, "beatloop_size"), 0.25);
send(0x97, 0x73, 0x7F);
assert.strictEqual(get(g1, "pitch_adjust"), 7);
send(0x97, 0x73, 0x7F);
assert.strictEqual(get(g1, "pitch_adjust"), 0);
send(0x97, 0x34, 0x7F);
assert.strictEqual(get("[Sampler5]", "LoadSelectedTrack"), 1);
// PAD FX: hold effect unit 3 slot 2 on deck 1, then hand it back unchanged.
const u3 = "[EffectRack1_EffectUnit3]";
set(u3, "group_[Channel2]_enable", 1);
set("[EffectRack1_EffectUnit3_Effect1]", "enabled", 1);
set("[EffectRack1_EffectUnit3_Effect2]", "enabled", 1);
send(0x97, 0x11, 0x7F);
assert.strictEqual(get(u3, "enabled"), 1);
assert.strictEqual(get(u3, "group_[Channel1]_enable"), 1);
assert.strictEqual(get(u3, "group_[Channel2]_enable"), 0);
assert.strictEqual(get("[EffectRack1_EffectUnit3_Effect1]", "enabled"), 0, "only the held slot plays");
send(0x97, 0x11, 0x00);
assert.strictEqual(get(u3, "enabled"), 0);
assert.strictEqual(get(u3, "group_[Channel2]_enable"), 1, "routing restored");
assert.strictEqual(get("[EffectRack1_EffectUnit3_Effect1]", "enabled"), 1, "slots restored");
send(0x97, 0x14, 0x7F);
assert.strictEqual(get(g1, "beatlooproll_activate"), 1);
send(0x97, 0x14, 0x00);
assert.strictEqual(get(g1, "beatlooproll_activate"), 0);
console.log("pad modes and pad FX ok");

// ------------------------------------------------------ 7. loops
set(g1, "loop_enabled", 1);
advance(50);
assert.strictEqual(last(0x9F, 0x04), 0x7F);
send(0x90, 0x14, 0x7F);
assert.strictEqual(get(g1, "loop_enabled"), 0);
set(g1, "loop_start_position", 441000);
set(g1, "loop_end_position", 882000);
set(g1, "loop_enabled", 1);
send(0x90, 0x4C, 0x7F);
send(0xB0, 0x21, 0x40 + 20);
assert(get(g1, "loop_start_position") > 441000);
send(0x90, 0x4C, 0x7F);
assert.strictEqual(DDJ.deck[1].loopAdjust, null);
console.log("loops ok");

// ------------------------------------------------------ 8. jog free spin
DDJ.deck[1].vinyl = true;
send(0x90, 0x36, 0x7F);
assert(engine.isScratching(1));
for (let i = 0; i < 8; i++) { send(0xB0, 0x22, 0x40 + 60); now += 10; }
send(0x90, 0x36, 0x00);
advance(40);
assert(engine.isScratching(1), "a platter let go at speed keeps driving the record");
for (let i = 0; i < 5; i++) { send(0xB0, 0x21, 0x40 + 60); advance(10); }
assert(engine.isScratching(1), "still spinning");
advance(200);
assert(!engine.isScratching(1), "handed back once the ring stops reporting");
send(0x90, 0x36, 0x7F);
send(0x90, 0x36, 0x00);
advance(40);
assert(!engine.isScratching(1), "a still platter is handed back at once");
console.log("jog ok");

// ------------------------------------------------------ 9. Beat FX
const u1 = "[EffectRack1_EffectUnit1]";
set(u1, "num_chain_presets", 20);
send(0x94, 0x22, 0x7F); // MT DELAY -> preset 3
assert.strictEqual(get(u1, "loaded_chain_preset"), 3);
send(0x94, 0x2C, 0x7F); // MOBIUS SAW -> preset 11 (rolls are skipped)
assert.strictEqual(get(u1, "loaded_chain_preset"), 11);
send(0x94, 0x14, 0x7F);
send(0x94, 0x47, 0x7F);
assert.strictEqual(get(u1, "enabled"), 1);
assert.strictEqual(get(u1, "group_[Master]_enable"), 1);
send(0x94, 0x10, 0x7F);
assert.strictEqual(get(u1, "group_[Channel1]_enable"), 1);
assert.strictEqual(get(u1, "enabled"), 1, "stays on across CH SELECT");
send(0x94, 0x2A, 0x7F); // SLIP ROLL
assert.strictEqual(get(u1, "enabled"), 0);
assert.strictEqual(get(g1, "beatlooproll_activate"), 1);
send(0x94, 0x47, 0x7F);
assert.strictEqual(get(g1, "beatlooproll_activate"), 0);
set(u1, "num_chain_presets", 3);
send(0x94, 0x2D, 0x7F); // MOBIUS TRI -> preset 12 does not exist
assert.strictEqual(get(u1, "loaded_chain_preset"), 11, "missing preset leaves the unit alone");
console.log("beat FX ok");

// ------------------------------------------------------ 10. Color FX
const q2 = "[QuickEffectRack1_[Channel2]]";
set(q2, "enabled", 1);
send(0x96, 0x03, 0x7F);
assert.strictEqual(get(q2, "enabled"), 1, "COLOR knobs work without a button by default");
send(0x96, 0x03, 0x7F);
settings.colorFxNeedsButton = true;
settings.colorFxPreset2 = 16;
set(q2, "num_chain_presets", 20);
DDJ.applyColorFx();
assert.strictEqual(get(q2, "enabled"), 0, "rekordbox style: silent until a button is on");
send(0x96, 0x01, 0x7F);
assert.strictEqual(get(q2, "enabled"), 1);
assert.strictEqual(get(q2, "loaded_chain_preset"), 16, "button loads its configured preset");
console.log("sound color FX ok");

// ------------------------------------------------------ 11. memory cues
set(g1, "playposition", 0.25);
send(0x90, 0x3D, 0x7F);
assert.strictEqual(get(g1, "hotcue_17_set"), 1);
set(g1, "hotcue_17_position", 0.25 * get(g1, "track_samples"));
set(g1, "playposition", 0.5);
send(0x90, 0x51, 0x7F);
assert(Math.abs(get(g1, "playposition") - 0.25) < 1e-9);
send(0x90, 0x3E, 0x7F);
assert.strictEqual(get(g1, "hotcue_17_clear"), 1);
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

// ------------------------------------------- 12. review: mixxxdj/mixxx#17174

// DECK 1/3 or 2/4 only redraws: KEY SYNC stays on and the load animation does
// not play; a real track load still resets KEY SYNC and plays it.
{
    send(0x90, 0x65, 0x7F);
    assert.strictEqual(DDJ.deck[1].keySync, true, "KEY SYNC on");
    sent = [];
    send(0x91, 0x72, 0x7F);
    assert.strictEqual(DDJ.deck[1].keySync, true, "deck switch keeps KEY SYNC");
    assert(!sent.some(([s, d1, d2]) => s === 0x9F && d1 <= 0x03 && d2 === 0x7F), "no load animation on a deck switch");
    assert.strictEqual(last(0x90, 0x65), 0x7F, "KEY SYNC light redrawn");
    set(g1, "track_loaded", 1); // Mixxx force-sets this on every load
    assert.strictEqual(DDJ.deck[1].keySync, false, "a real load resets KEY SYNC");
    assert.strictEqual(last(0x9F, 0x00), 0x7F, "a real load plays the animation");
    advance(1100);
    console.log("deck switch: no KEY SYNC reset, no load animation");
}

// After a full refresh the pads arrive a mode per tick, not in one burst.
{
    advance(1000);
    sent = [];
    send(0x91, 0x72, 0x7F);
    const padMessages = () => sent.filter(([s]) => s >= 0x97 && s <= 0x9E).length;
    assert(padMessages() <= 4 * 32, "only the modes on screen at once");
    let before = padMessages();
    for (let i = 0; i < 28; i++) {
        advance(20);
        assert(padMessages() - before <= 32 + 8, "at most one mode per tick");
        before = padMessages();
    }
    assert.strictEqual(DDJ.padQueue.length, 0, "every mode drawn");
    console.log("pad redraw spread over ticks ok");
}

// RELEASE FX never stops the mix: on MASTER only the Beat FX goes off; on a
// channel that one deck brakes.
{
    const playing = ["[Channel1]", "[Channel2]", "[Channel3]"];
    playing.forEach((g) => { set(g, "play", 1); set(g, "_brake", 0); });
    send(0x94, 0x21, 0x7F); // ECHO
    send(0x94, 0x14, 0x7F); // MASTER
    send(0x94, 0x47, 0x7F); // on
    assert.strictEqual(get(u1, "enabled"), 1);
    send(0x94, 0x43, 0x7F);
    send(0x94, 0x43, 0x00);
    assert.strictEqual(get(u1, "enabled"), 0, "Beat FX off");
    playing.forEach((g) => assert.strictEqual(get(g, "_brake"), 0, `${g} not braked on MASTER`));
    send(0x94, 0x11, 0x7F); // CH2
    send(0x94, 0x47, 0x7F);
    send(0x94, 0x43, 0x7F);
    assert.strictEqual(get("[Channel2]", "_brake"), 1, "CH2 brakes");
    assert.strictEqual(get("[Channel1]", "_brake"), 0, "CH1 untouched");
    assert.strictEqual(get("[Channel3]", "_brake"), 0, "CH3 untouched");
    console.log("RELEASE FX: brakes only the selected channel");
}

// MIC routes the Beat FX to Mixxx's microphones.
{
    send(0x94, 0x15, 0x7F);
    assert.strictEqual(get(u1, "group_[Microphone]_enable"), 1);
    assert.strictEqual(get(u1, "group_[Microphone4]_enable"), 1);
    assert.strictEqual(get(u1, "group_[Master]_enable"), 0);
    assert.strictEqual(get(u1, "group_[Channel2]_enable"), 0);
    console.log("CH SELECT MIC -> microphones");
}

// PAD FX brake / backspin: a paused deck stays paused, a playing deck plays on,
// slip goes back to what it was.
{
    const g = "[Channel3]";
    send(0x92, 0x1B, 0x7F); // deck 3 HOT CUE... then PAD FX2
    send(0x92, 0x6B, 0x7F);
    set(g, "play", 0);
    set(g, "slip_enabled", 0);
    send(0x9B, 0x50, 0x7F); // PAD FX2 page 1 pad 1: brake
    assert.strictEqual(get(g, "slip_enabled"), 1, "slip while held");
    send(0x9B, 0x50, 0x00);
    assert.strictEqual(get(g, "play"), 0, "paused deck stays paused");
    assert.strictEqual(get(g, "slip_enabled"), 0, "slip restored");
    set(g, "play", 1);
    send(0x9B, 0x51, 0x7F); // backspin
    set(g, "play", 0); // the backspin stopped the deck
    send(0x9B, 0x51, 0x00);
    assert.strictEqual(get(g, "play"), 1, "playing deck plays on");
    assert.strictEqual(get(g, "slip_enabled"), 0, "slip restored");
    console.log("PAD FX brake/backspin restore play and slip");
}

// A held PAD FX unit reaches this deck only, also when it was on Main or the samplers.
{
    const u4 = "[EffectRack1_EffectUnit4]";
    set(u4, "group_[Master]_enable", 1);
    set(u4, "group_[Sampler3]_enable", 1);
    send(0x97, 0x1B, 0x7F); // PAD FX1 page 2 pad 4: whole unit 4
    assert.strictEqual(get(u4, "group_[Channel1]_enable"), 1);
    assert.strictEqual(get(u4, "group_[Master]_enable"), 0, "off Main while held");
    assert.strictEqual(get(u4, "group_[Sampler3]_enable"), 0, "off the samplers while held");
    send(0x97, 0x1B, 0x00);
    assert.strictEqual(get(u4, "group_[Master]_enable"), 1, "Main routing restored");
    assert.strictEqual(get(u4, "group_[Sampler3]_enable"), 1, "sampler routing restored");
    assert.strictEqual(get(u4, "group_[Channel1]_enable"), 0);
    console.log("held PAD FX unit isolated to its deck");
}

// Sampler banks stop at the samplers Mixxx has; samplers added later are connected.
{
    for (let i = 0; i < 10; i++) send(0x90, 0x7A, 0x7F); // SHIFT + PAGE >
    assert.strictEqual(DDJ.deck[1].samplerBank, 1, "16 samplers: two banks");
    assert.strictEqual(get("[App]", "num_samplers"), 16, "never adds samplers");
    set("[App]", "num_samplers", 24);
    send(0x90, 0x7A, 0x7F);
    assert.strictEqual(DDJ.deck[1].samplerBank, 2, "a third bank once Mixxx has 24");
    set("[Sampler20]", "pfl", 1);
    assert.strictEqual(last(0x96, 0x69), 0x7F, "new sampler lights SAMPLER CUE");
    set("[Sampler20]", "pfl", 0);
    set("[App]", "num_samplers", 16);
    console.log("sampler banks capped, new samplers connected");
}

// 14-bit inputs: the MSB alone never moves the tempo.
{
    send(0xB0, 0x00, 0x3F); send(0xB0, 0x20, 0x7F);
    const rate = get(g1, "rate");
    send(0xB0, 0x00, 0x40);
    assert.strictEqual(get(g1, "rate"), rate, "MSB alone ignored");
    send(0xB0, 0x20, 0x00);
    assert(Math.abs(get(g1, "rate") - ((0x40 << 7) / 0x3FFF * 2 - 1)) < 1e-12, "applied with its LSB");
    console.log("14-bit tempo applies on LSB");
}

// An idle tick reads only what the jog displays need.
{
    advance(300);
    reads = 0;
    advance(20 * 50);
    assert(reads / 50 < 60, `${reads / 50} reads per tick`);
    console.log(`idle timer: ${(reads / 50).toFixed(1)} control reads per tick`);
}

// A running saved loop blinks on its pad.
{
    DDJ.deck[1].mode = 0;
    set(g1, "hotcue_2_color", 0x0000FF);
    set(g1, "hotcue_2_type", 4);
    set(g1, "hotcue_2_status", 2);
    const seen = new Set();
    for (let i = 0; i < 4; i++) { advance(250); seen.add(last(0x97, 0x01)); }
    assert(seen.has(0) && seen.has(1), "blinks between blue and off");
    set(g1, "hotcue_2_status", 1);
    advance(250);
    assert.strictEqual(last(0x97, 0x01), 1, "steady once the loop stops");
    console.log("running saved loop blinks");
}

// shutdown() puts back what the mapping changed on its own, but leaves what
// the user changed since.
{
    DDJ.shutdown();
    values.clear();
    sent = [];
    connections.length = 0;
    timers.clear();
    Object.assign(DDJ, { opened: false, sent: {}, heldUnits: {}, overrides: {}, samplersConnected: 0, padQueue: [] });
    DDJ.beatFx.target = null;
    delete settings.hardwareHeadphoneMix;
    settings.tempoRange = "16";
    set("[Master]", "headMix", 0.3);
    set("[Channel1]", "rateRange", 0.08);
    set("[Channel2]", "rateRange", 0.08);
    set(u1, "group_[Channel1]_enable", 1);
    DDJ.init("DDJ-1000", false);
    advance(50);
    assert.strictEqual(get(u1, "group_[Channel1]_enable"), 1, "Beat FX routing untouched at startup");
    assert.strictEqual(get("[Master]", "headMix"), -1);
    send(0x94, 0x14, 0x7F); // MASTER
    assert.strictEqual(get(u1, "group_[Master]_enable"), 1);
    send(0x90, 0x60, 0x7F); // deck 1 TEMPO RANGE: the user's own change
    DDJ.shutdown();
    assert.strictEqual(get("[Master]", "headMix"), 0.3, "headphone mix restored");
    assert.strictEqual(get(u1, "group_[Channel1]_enable"), 1, "Beat FX routing restored");
    assert.strictEqual(get(u1, "group_[Master]_enable"), 0, "Beat FX routing restored");
    assert.strictEqual(get("[Channel2]", "rateRange"), 0.08, "startup tempo range restored");
    assert.strictEqual(get("[Channel1]", "rateRange"), 1.00, "range changed on the unit is kept");
    console.log("shutdown restores headMix, tempo range and Beat FX routing");
}

console.log("\nALL UPSTREAM TESTS PASSED");
