// Pioneer DDJ-1000 — complete Mixxx 2.5 mapping (script half).
//
// Sources, in order of authority:
//   1. AlphaTheta "DDJ-1000 List of MIDI message version 1.00"  (what the unit sends/accepts)
//   2. rekordbox 7.2 "MidiMappings/DDJ-1000.midi.csv"           (what rekordbox does with each message)
//   3. DDJ-1000 Operating Instructions                          (button behaviour, SHIFT functions)
//
// Things about the hardware that shape this file:
//   * Mixxx opens the MIDI output only after init() returns, so init() sends
//     nothing; the first timer tick sends the opening state instead.
//   * HEADPHONES LEVEL/MIX, MASTER LEVEL, BOOTH LEVEL, MASTER CUE and the MIC
//     section are analogue on the unit. rekordbox leaves them unassigned and so
//     does this mapping. Mixxx sends Main on outputs 1-2 and a pure cue mix on
//     outputs 3-4; the unit blends them with the HEADPHONES MIX knob.
//   * Deck controls arrive on MIDI channels 1-4 = decks 1-4. DECK 1/3 and 2/4
//     switch the channel inside the unit, so no deck-layer logic is needed.
//   * The unit only sends the LOOP 1/2X and 2X notes once the host tells it a
//     loop is running (note 0x04+deck on MIDI channel 16).
//   * Pad LEDs take a colour number: a hue wheel from 1 (blue) through green,
//     yellow, orange, red and pink to 61 (purple); 127 is near-white, 0 dims.

var DDJ1000 = {};

// ---------------------------------------------------------------------------
// Settings you may want to tune
// ---------------------------------------------------------------------------

DDJ1000.settings = {
    // Jog. 12900 ticks per platter revolution was measured on the hardware;
    // raise it if scratching feels too fast, lower it if too slow.
    jogTicksPerRevolution: 12900,
    vinylRpm: 33 + 1 / 3,
    scratchAlpha: 1 / 8,
    scratchBeta: 1 / 8 / 32,
    pitchBendPerRevolution: 200,
    jogSearchSecondsPerRevolution: 30,
    loopAdjustMsPerRevolution: 2000,
    throwReleaseFraction: 0.25,
    throwSpinDownMs: 80,

    // SEARCH buttons, held: start gently and wind up like a CDJ.
    searchRate: 2.0,
    searchMaxRate: 20.0,
    searchRampSeconds: 2.5,

    // TEMPO RANGE (SHIFT + MASTER TEMPO) cycles through these; rekordbox's.
    tempoRanges: [0.06, 0.10, 0.16, 1.00],
    defaultTempoRange: 0.10,

    // Rotary selector: pressing twice this quickly makes an instant double.
    doublePressMs: 400,
    // SLIP REVERSE lets go by itself after this many beats (manual p. 7).
    slipReverseBeats: 8,
    // BEAT FX beat values, reached with BEAT < and >.
    beatValues: [1 / 16, 1 / 8, 1 / 4, 1 / 2, 3 / 4, 1, 2, 4, 8, 16, 32],
    defaultBeatIndex: 5,
    // Sampler: pads 1-8 play slots 1-8 of the current bank; 8 banks.
    samplerBanks: 8,

    // Mixxx's shortest timer. The display predicts the position between
    // Mixxx's 15-per-second position updates, so the bar turns smoothly.
    displayIntervalMs: 20,
    blinkMs: 250,

    // Jog display flashes over the last stretch of the track, like a CDJ/rekordbox.
    endOfTrackWarningSec: 30,

    // Set true to light the pads with raw colour numbers instead of the
    // mapping: deck 1 pads show base..base+7, deck 2 pads base+8..base+15.
    // Deck 1 PAGE > / < steps base by 16. The base is printed to the log.
    padPaletteTest: false,
};

// ---------------------------------------------------------------------------
// Effect chain presets. The installer adds these to Mixxx's preset lists,
// first and in this order, so their indexes are fixed. 0 = empty.
// ---------------------------------------------------------------------------

DDJ1000.PRESET = {
    LOW_CUT_ECHO: 1, ECHO: 2, MT_DELAY: 3, SPIRAL: 4, REVERB: 5, TRANS: 6,
    ENIGMA_JET: 7, FLANGER: 8, PHASER: 9, PITCH: 10, MOBIUS_SAW: 11,
    MOBIUS_TRI: 12, PAD_HPF: 13, PAD_LPF: 14, PAD_CRUSH: 15, PAD_NOISE: 16,
};

DDJ1000.QUICK = { DUB_ECHO: 1, PITCH: 2, NOISE: 3, FILTER: 4 };

// Which effect parameter "beat" moves, per preset. kind "beats" writes the
// beat value, "rate" writes cycles per beat. parameterK counts only the
// effect's knob parameters, in the order Mixxx lists them.
DDJ1000.BEAT_PARAM = {};
(function () {
    var P = DDJ1000.PRESET;
    var beats = function (slot, param) { return { slot: slot, param: param, kind: "beats" }; };
    DDJ1000.BEAT_PARAM[P.LOW_CUT_ECHO] = beats(1, 1); // Echo: delay_time
    DDJ1000.BEAT_PARAM[P.ECHO] = beats(1, 1);
    DDJ1000.BEAT_PARAM[P.MT_DELAY] = beats(1, 1);
    DDJ1000.BEAT_PARAM[P.SPIRAL] = beats(1, 1);
    DDJ1000.BEAT_PARAM[P.TRANS] = { slot: 1, param: 2, kind: "rate" }; // Tremolo: rate
    DDJ1000.BEAT_PARAM[P.ENIGMA_JET] = beats(1, 1); // Flanger: speed
    DDJ1000.BEAT_PARAM[P.FLANGER] = beats(1, 1);
    DDJ1000.BEAT_PARAM[P.PHASER] = beats(1, 1); // Phaser: lfo_period
    DDJ1000.BEAT_PARAM[P.MOBIUS_SAW] = beats(1, 1);
    DDJ1000.BEAT_PARAM[P.MOBIUS_TRI] = beats(1, 1);
})();

// FX SELECT positions, notes 0x20..0x2D on MIDI channel 5.
DDJ1000.BEAT_FX_TYPES = [
    { name: "LOW CUT ECHO", preset: DDJ1000.PRESET.LOW_CUT_ECHO },
    { name: "ECHO", preset: DDJ1000.PRESET.ECHO },
    { name: "MT DELAY", preset: DDJ1000.PRESET.MT_DELAY },
    { name: "SPIRAL", preset: DDJ1000.PRESET.SPIRAL },
    { name: "REVERB", preset: DDJ1000.PRESET.REVERB },
    { name: "TRANS", preset: DDJ1000.PRESET.TRANS },
    { name: "ENIGMA JET", preset: DDJ1000.PRESET.ENIGMA_JET },
    { name: "FLANGER", preset: DDJ1000.PRESET.FLANGER },
    { name: "PHASER", preset: DDJ1000.PRESET.PHASER },
    { name: "PITCH", preset: DDJ1000.PRESET.PITCH, depthIsSuper: true },
    { name: "SLIP ROLL", roll: "slip" },
    { name: "ROLL", roll: "loop" },
    { name: "MOBIUS SAW", preset: DDJ1000.PRESET.MOBIUS_SAW },
    { name: "MOBIUS TRI", preset: DDJ1000.PRESET.MOBIUS_TRI },
];

// ---------------------------------------------------------------------------
// Pad colours
// ---------------------------------------------------------------------------

DDJ1000.COLOR = {
    OFF: 0, BLUE: 1, AZURE: 9, SKY: 13, CYAN: 17, GREEN: 21, LIME: 25,
    YELLOW: 29, AMBER: 33, ORANGE: 37, RED: 41, ROSE: 45, PINK: 53,
    MAGENTA: 57, PURPLE: 61, WHITE: 127,
};

// Pad colour numbers exactly as rekordbox sends them (captured from rekordbox 7.2.18, see
// RB_LED_COMPARISON.md). Index 0 = page 1, index 1 = page 2, pads 1-8.
DDJ1000.RB = {
    PAD_FX1: [[73, 78, 78, 65, 69, 69, 86, 65], [73, 120, 78, 65, 69, 69, 86, 65]],
    PAD_FX2: [[73, 73, 73, 73, 73, 73, 73, 73], [73, 73, 73, 73, 69, 69, 69, 69]],
    BEAT_JUMP: [[106, 106, 101, 101, 101, 101, 106, 106], [63, 63, 63, 63, 63, 63, 63, 63]],
    BEAT_LOOP: [100, 102],
    KEY_SHIFT: [39, 9],
    KEY_SHIFT_CENTRE: 64, // pad 5 of page 1 blinks 64/0 in rekordbox
    SAMPLER_EMPTY: 63,
    SAMPLER_LOADED: 120,
    // Colour while a pad is held: rekordbox switches to the same hue from the lower half
    // of the range (measured: 73>9, 78>14, 65>1, 106>42, 101>38, 100>37), else idle - 64.
    PRESSED: { 73: 9, 78: 14, 65: 1, 106: 42, 101: 38, 100: 37, 102: 39 },
};

DDJ1000.pressedColor = function (idle) {
    var known = DDJ1000.RB.PRESSED[idle];
    if (known !== undefined) {
        return known;
    }
    return idle > 64 ? idle - 64 : idle;
};

// Pad value -> approximate hue, for matching Mixxx hot cue colours.
DDJ1000.HUE_WHEEL = [
    { v: 1, h: 240 }, { v: 5, h: 228 }, { v: 9, h: 216 }, { v: 13, h: 200 },
    { v: 17, h: 180 }, { v: 21, h: 120 }, { v: 25, h: 85 }, { v: 29, h: 60 },
    { v: 33, h: 45 }, { v: 37, h: 30 }, { v: 41, h: 0 }, { v: 45, h: 350 },
    { v: 49, h: 340 }, { v: 53, h: 330 }, { v: 57, h: 300 }, { v: 61, h: 275 },
];

DDJ1000.rgbToPad = function (rgb) {
    if (!(rgb >= 0)) {
        return DDJ1000.COLOR.WHITE;
    }
    var r = (rgb >> 16) & 0xFF, g = (rgb >> 8) & 0xFF, b = rgb & 0xFF;
    var max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
    if (max === 0 || d / max < 0.18) {
        return DDJ1000.COLOR.WHITE;
    }
    var h;
    if (max === r) {
        h = ((g - b) / d) % 6;
    } else if (max === g) {
        h = (b - r) / d + 2;
    } else {
        h = (r - g) / d + 4;
    }
    h *= 60;
    if (h < 0) {
        h += 360;
    }
    var best = DDJ1000.HUE_WHEEL[0], bestDist = 999;
    DDJ1000.HUE_WHEEL.forEach(function (entry) {
        var dist = Math.abs(h - entry.h) % 360;
        dist = dist > 180 ? 360 - dist : dist;
        if (dist < bestDist) {
            bestDist = dist;
            best = entry;
        }
    });
    return best.v;
};

// ---------------------------------------------------------------------------
// Pad modes. The note a pad sends is mode * 16 + page * 8 + pad.
// ---------------------------------------------------------------------------

DDJ1000.MODE = {
    HOT_CUE: 0, PAD_FX1: 1, BEAT_JUMP: 2, SAMPLER: 3,
    KEYBOARD: 4, PAD_FX2: 5, BEAT_LOOP: 6, KEY_SHIFT: 7,
};

// Mode buttons; SHIFT + the first four select the last four.
DDJ1000.MODE_BUTTONS = [0x1B, 0x1E, 0x20, 0x22, 0x69, 0x6B, 0x6D, 0x6F];
// PAGE < and PAGE > send a different note in each mode.
DDJ1000.PAGE_PREV_NOTES = [0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B];
DDJ1000.PAGE_NEXT_NOTES = [0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33];
DDJ1000.SHIFT_PAGE_PREV_NOTES = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08];
DDJ1000.SHIFT_PAGE_NEXT_NOTES = [0x09, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F, 0x00];

// Pads are numbered 0-3 on the top row, 4-7 on the bottom row.
// BEAT JUMP: rekordbox's REV1 FWD1 REV2 FWD2 / REV3 FWD3 REV4 FWD4.
DDJ1000.BEAT_JUMP_BEATS = [-1, 1, -2, 2, -4, 4, -8, 8];
DDJ1000.BEAT_LOOP_BEATS = [
    [1 / 4, 1 / 2, 1, 2, 4, 8, 16, 32],
    [1 / 32, 1 / 16, 1 / 8, 1 / 4, 1 / 2, 1, 2, 4],
];
// KEYBOARD and KEY SHIFT: semitones, lowest note bottom left.
DDJ1000.SEMITONES = [
    [4, 5, 6, 7, 0, 1, 2, 3],
    [-4, -3, -2, -1, -8, -7, -6, -5],
];

(function () {
    var P = DDJ1000.PRESET, C = DDJ1000.COLOR;
    DDJ1000.PAD_FX = {};
    DDJ1000.PAD_FX[DDJ1000.MODE.PAD_FX1] = [
        [
            { fx: P.ECHO, beats: 1 / 2, color: C.BLUE },
            { fx: P.ECHO, beats: 3 / 4, color: C.BLUE },
            { fx: P.REVERB, color: C.PURPLE },
            { fx: P.SPIRAL, beats: 1 / 2, color: C.MAGENTA },
            { roll: 1 / 16, color: C.GREEN },
            { roll: 1 / 8, color: C.GREEN },
            { roll: 1 / 4, color: C.GREEN },
            { roll: 1 / 2, color: C.GREEN },
        ],
        [
            { fx: P.TRANS, beats: 1 / 4, color: C.YELLOW },
            { fx: P.TRANS, beats: 1 / 2, color: C.YELLOW },
            { fx: P.FLANGER, beats: 8, color: C.CYAN },
            { fx: P.PHASER, beats: 1, color: C.CYAN },
            { fx: P.LOW_CUT_ECHO, beats: 1, color: C.AZURE },
            { fx: P.MT_DELAY, beats: 3 / 4, color: C.AZURE },
            { fx: P.ENIGMA_JET, beats: 4, color: C.SKY },
            { fx: P.PITCH, superValue: 0.75, color: C.PINK },
        ],
    ];
    DDJ1000.PAD_FX[DDJ1000.MODE.PAD_FX2] = [
        [
            { fx: P.PAD_HPF, color: C.ORANGE },
            { fx: P.PAD_LPF, color: C.ORANGE },
            { fx: P.PAD_CRUSH, color: C.RED },
            { fx: P.PAD_NOISE, color: C.ROSE },
            { brake: true, color: C.AMBER },
            { spinback: true, color: C.AMBER },
            { reverse: true, color: C.AMBER },
            { roll: 1 / 32, color: C.LIME },
        ],
        [
            { fx: P.ECHO, beats: 1, color: C.BLUE },
            { fx: P.ECHO, beats: 2, color: C.BLUE },
            { fx: P.REVERB, superValue: 0.9, color: C.PURPLE },
            { fx: P.TRANS, beats: 1 / 8, color: C.YELLOW },
            { roll: 1, color: C.GREEN },
            { roll: 2, color: C.GREEN },
            { roll: 4, color: C.GREEN },
            { roll: 3 / 4, color: C.LIME },
        ],
    ];
})();

// ---------------------------------------------------------------------------
// Jog display addresses (MIDI OUT "for JOG display")
// ---------------------------------------------------------------------------

DDJ1000.DISPLAY = {
    positionBarMsb: 0x14, bpmMsb: 0x15, speedMsb: 0x16, cueMarkerMsb: 0x17,
    timeMinute: 0x42, timeSecond: 0x43, timeMode: 0x44,
    keyValue: 0x49, keyVariation: 0x4A,
    syncMaster: 0x59, syncState: 0x5A, ringLed: 0x5B, showInfo: 0x5D,
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

DDJ1000.decks = [1, 2, 3, 4];
DDJ1000.deck = {};
DDJ1000.connections = [];
DDJ1000.timer = 0;
DDJ1000.opened = false;
DDJ1000.blink = false;
DDJ1000.blinkAt = 0;
DDJ1000.fullRenderAt = 0;
DDJ1000.fullRenderDeck = 0;
DDJ1000.sent = {};          // "status:data1" -> last data2, so unchanged LEDs are not resent
DDJ1000.hiRes = {};         // 14-bit MSB/LSB halves, keyed by "status:msb"
DDJ1000.paletteBase = 1;

DDJ1000.beatFx = {
    type: 1,                // index into BEAT_FX_TYPES; ECHO until the knob moves
    beatIndex: DDJ1000.settings.defaultBeatIndex,
    channel: "master",      // 1-4, "master", "mic" or "sampler"
    on: false,
    depth: 0.5,
    rolling: [],            // decks a ROLL / SLIP ROLL is running on
};

DDJ1000.colorFx = 0;        // 0 = none, 1-4 = DUB ECHO, PITCH, NOISE, FILTER

DDJ1000.padFxUnitPreset = {};   // effect unit number -> preset loaded for pad FX

DDJ1000.newDeckState = function () {
    return {
        vinyl: true,
        touched: false,
        throwing: false,
        lastTick: 0,
        speed: undefined,
        mode: DDJ1000.MODE.HOT_CUE,
        page: [1, 1, 1, 1, 1, 1, 1, 1],
        jumpMultiplier: 1,
        samplerBank: 0,
        keyboardHotcue: 1,
        pressed: {},            // mode -> {pad: true}
        loopAdjust: null,       // "in" / "out" while the jog moves a loop point
        search: null,
        searchLong: false,
        keySync: false,
        reverseTimer: 0,
        gridMode: null,         // "adjust" / "slide" while rekordbox-style grid edit is on
        padFxHeld: null,        // entry currently held in a pad FX mode
        slipBeforePadFx: 0,
        lastLoadPress: 0,
        loadFlashTimer: 0,
    };
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

DDJ1000.group = function (deck) {
    return "[Channel" + deck + "]";
};

DDJ1000.deckFromStatus = function (status) {
    return (status & 0x0F) + 1;
};

// Pad statuses: 0x97/0x98 deck 1, 0x99/0x9A deck 2, 0x9B/0x9C deck 3, 0x9D/0x9E deck 4.
DDJ1000.padDeckFromStatus = function (status) {
    return (((status & 0x0F) - 7) >> 1) + 1;
};

DDJ1000.padStatus = function (deck, shifted) {
    return 0x97 + (deck - 1) * 2 + (shifted ? 1 : 0);
};

DDJ1000.clamp = function (value, lo, hi) {
    return Math.max(lo, Math.min(hi, value));
};

DDJ1000.send = function (status, data1, data2, force) {
    var key = status + ":" + data1;
    data2 &= 0x7F;
    if (!force && DDJ1000.sent[key] === data2) {
        return;
    }
    DDJ1000.sent[key] = data2;
    if (DDJ1000.opened) {
        midi.sendShortMsg(status, data1, data2);
    }
};

DDJ1000.led = function (status, data1, on) {
    DDJ1000.send(status, data1, on ? 0x7F : 0x00);
};

DDJ1000.deckLed = function (deck, note, on) {
    DDJ1000.led(0x90 + deck - 1, note, on);
};

DDJ1000.send14 = function (status, msb, value) {
    value = Math.round(value) & 0x3FFF;
    var key = status + ":14:" + msb;
    if (DDJ1000.sent[key] === value) {
        return;
    }
    DDJ1000.sent[key] = value;
    if (DDJ1000.opened) {
        midi.sendShortMsg(status, msb, value >> 7);
        midi.sendShortMsg(status, msb + 0x20, value & 0x7F);
    }
};

// Combine a 14-bit knob from its MSB (sent first) and LSB. Returns 0..1.
DDJ1000.take14 = function (status, control, value) {
    var isLsb = control >= 0x20 && control < 0x40;
    var msb = isLsb ? control - 0x20 : control;
    var key = status + ":" + msb;
    var entry = DDJ1000.hiRes[key] || (DDJ1000.hiRes[key] = { msb: 0, lsb: 0 });
    if (isLsb) {
        entry.lsb = value;
    } else {
        entry.msb = value;
    }
    return ((entry.msb << 7) | entry.lsb) / 16383;
};

// Pioneer relative encoders count away from 0x40 (jog) or from 0 (browse).
DDJ1000.jogTicks = function (value) {
    return value - 0x40;
};

DDJ1000.encoderTicks = function (value) {
    return value > 0x40 ? value - 0x80 : value;
};

DDJ1000.connect = function (group, key, callback) {
    var connection = engine.makeConnection(group, key, callback);
    if (connection) {
        DDJ1000.connections.push(connection);
    }
    return connection;
};

DDJ1000.toggle = function (group, key) {
    engine.setValue(group, key, engine.getValue(group, key) ? 0 : 1);
};

DDJ1000.samplesPerSecond = function (group) {
    // Engine positions are interleaved stereo samples: two per frame.
    return (engine.getValue(group, "track_samplerate") || 44100) * 2;
};

DDJ1000.positionSamples = function (group) {
    return engine.getValue(group, "playposition") * engine.getValue(group, "track_samples");
};

DDJ1000.seekSamples = function (group, samples) {
    var total = engine.getValue(group, "track_samples");
    if (total > 0) {
        engine.setValue(group, "playposition", DDJ1000.clamp(samples / total, 0, 1));
    }
};

DDJ1000.numSamplers = function () {
    return engine.getValue("[App]", "num_samplers") || 16;
};

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

DDJ1000.init = function () {
    DDJ1000.decks.forEach(function (deck) {
        var group = DDJ1000.group(deck);
        DDJ1000.deck[deck] = DDJ1000.newDeckState();

        engine.setValue(group, "rateRange", DDJ1000.settings.defaultTempoRange);
        engine.setValue(group, "cue_mode", 1); // Pioneer: CUE behaves like a CDJ
        // No soft takeover: the tempo fader is a plain pot on this unit, just
        // like on rekordbox, so its physical position is always the value —
        // moving it jumps the tempo straight to where the fader sits.
        engine.softTakeover(group, "rate", false);

        DDJ1000.connectDeckLeds(deck);
    });

    // The unit blends cue and master itself (HEADPHONES MIX is analogue), so
    // the headphone output carries the cue mix only.
    engine.setValue("[Master]", "headMix", -1);

    DDJ1000.connectMixerLeds();
    DDJ1000.setupBeatFx();
    DDJ1000.applyColorFx();

    DDJ1000.timer = engine.beginTimer(DDJ1000.settings.displayIntervalMs, DDJ1000.tick);
};

DDJ1000.shutdown = function () {
    if (DDJ1000.timer) {
        engine.stopTimer(DDJ1000.timer);
        DDJ1000.timer = 0;
    }
    DDJ1000.connections.forEach(function (connection) {
        connection.disconnect();
    });
    DDJ1000.connections = [];

    if (!DDJ1000.opened) {
        return;
    }
    DDJ1000.decks.forEach(function (deck) {
        var status = 0x90 + deck - 1;
        midi.sendShortMsg(status, DDJ1000.DISPLAY.showInfo, 0x7F);
        midi.sendShortMsg(status, DDJ1000.DISPLAY.ringLed, 0x00);
        for (var note = 0; note < 0x80; note++) {
            midi.sendShortMsg(DDJ1000.padStatus(deck, false), note, 0x00);
        }
    });
    Object.keys(DDJ1000.sent).forEach(function (key) {
        var parts = key.split(":");
        if (parts.length === 2 && (parts[0] & 0xF0) === 0x90) {
            midi.sendShortMsg(Number(parts[0]), Number(parts[1]), 0x00);
        }
    });
};

// Everything the unit must be told once, sent from the first timer tick:
// anything sent from init() is dropped because the output is not open yet.
DDJ1000.sendOpeningState = function () {
    DDJ1000.opened = true;
    DDJ1000.decks.forEach(function (deck) {
        var status = 0x90 + deck - 1;
        midi.sendShortMsg(status, DDJ1000.DISPLAY.showInfo, 0x00);
        midi.sendShortMsg(status, DDJ1000.DISPLAY.ringLed, 0x01);
        // rekordbox sends this at startup too; on its own it does nothing visible.
        midi.sendShortMsg(status, 0x21, 0x20);
    });
    // Asks the unit to report where its knobs, faders and switches sit, as rekordbox does
    // (verified on hardware: it answers with the position of every control).
    midi.sendSysexMsg([0xF0, 0x00, 0x40, 0x05, 0x00, 0x00, 0x02, 0x00, 0x00, 0x03, 0x01, 0xF7], 12);
    DDJ1000.resendAll();
};

// Forget the LED cache and send everything again (also used after a deck switch).
DDJ1000.resendAll = function () {
    DDJ1000.sent = {};
    DDJ1000.connections.forEach(function (connection) {
        connection.trigger();
    });
    DDJ1000.decks.forEach(function (deck) {
        DDJ1000.updateModeLeds(deck);
        DDJ1000.updateVinylLed(deck);
        DDJ1000.updateLoopAdjustLeds(deck);
        DDJ1000.deckLed(deck, 0x65, DDJ1000.deck[deck].keySync);
        DDJ1000.renderPads(deck, false);
    });
    DDJ1000.updateBeatFxLeds();
    DDJ1000.updateColorFxLeds();
};

DDJ1000.tick = function () {
    if (!DDJ1000.opened) {
        DDJ1000.sendOpeningState();
    }
    var now = Date.now();
    if (now - DDJ1000.blinkAt >= DDJ1000.settings.blinkMs) {
        DDJ1000.blink = !DDJ1000.blink;
        DDJ1000.blinkAt = now;
        DDJ1000.decks.forEach(DDJ1000.updateLoopAdjustLeds);
        DDJ1000.decks.forEach(DDJ1000.updateModeLeds);
    }
    // The pads of the other modes are refreshed one deck at a time, so the
    // unit never gets a flood of pad messages at once.
    var fullDeck = 0;
    if (now - DDJ1000.fullRenderAt >= 250) {
        DDJ1000.fullRenderAt = now;
        DDJ1000.fullRenderDeck = DDJ1000.fullRenderDeck % 4 + 1;
        fullDeck = DDJ1000.fullRenderDeck;
    }
    DDJ1000.decks.forEach(function (deck) {
        DDJ1000.checkThrow(deck);
        DDJ1000.updateSearch(deck);
        DDJ1000.updateDisplay(deck);
        DDJ1000.renderPads(deck, deck === fullDeck);
    });
};

// ---------------------------------------------------------------------------
// LED connections
// ---------------------------------------------------------------------------

DDJ1000.connectDeckLeds = function (deck) {
    var group = DDJ1000.group(deck);
    var status = 0x90 + deck - 1;
    var bind = function (key, notes, transform) {
        DDJ1000.connect(group, key, function (value) {
            var on = transform ? transform(value) : value > 0;
            notes.forEach(function (note) {
                DDJ1000.led(status, note, on);
            });
        });
    };

    bind("play_indicator", [0x0B, 0x47]);
    bind("cue_indicator", [0x0C, 0x48]);
    bind("sync_enabled", [0x58]);
    bind("sync_mode", [0x5C], function (value) { return value === 2; });
    bind("keylock", [0x1A, 0x60]);
    bind("loop_enabled", [0x14, 0x50]);
    bind("quantize", [0x35]);
    bind("slip_enabled", [0x40]);
    bind("reverse", [0x38]);
    bind("pfl", [0x54]);

    DDJ1000.connect(group, "loop_enabled", function (value) {
        // Tells the unit to send LOOP 1/2X and 2X instead of LOOP IN/OUT.
        DDJ1000.send(0x9F, 0x03 + deck, value > 0 ? 0x7F : 0x00);
        DDJ1000.updateLoopAdjustLeds(deck);
    });
    DDJ1000.connect(group, "slip_enabled", function (value) {
        DDJ1000.send(0x9F, 0x23 + deck, value > 0 ? 0x7F : 0x00);
    });
    DDJ1000.connect(group, "reverseroll", function (value) {
        DDJ1000.led(status, 0x15, value > 0);
    });
    DDJ1000.connect(group, "track_loaded", function (value) {
        DDJ1000.onTrackLoaded(deck, value > 0);
    });
    DDJ1000.connect(group, "playposition", function (value) {
        DDJ1000.deck[deck].position = { value: value, at: Date.now() };
    });
    DDJ1000.connect(group, "vu_meter", function (value) {
        DDJ1000.send(0xB0 + deck - 1, 0x02, Math.round(value * 127));
    });
};

DDJ1000.connectMixerLeds = function () {
    DDJ1000.connect("[Master]", "headSplit", function (value) {
        DDJ1000.decks.forEach(function (deck) {
            DDJ1000.deckLed(deck, 0x39, value > 0);
        });
    });
    DDJ1000.connect("[EffectRack1_EffectUnit1]", "enabled", function (value) {
        DDJ1000.led(0x94, 0x47, value > 0 || DDJ1000.beatFx.rolling.length > 0);
    });
    // SAMPLER CUE lights while any sampler is cued.
    for (var i = 1; i <= DDJ1000.numSamplers(); i++) {
        DDJ1000.connect("[Sampler" + i + "]", "pfl", DDJ1000.updateSamplerCueLed);
    }
};

DDJ1000.updateSamplerCueLed = function () {
    var any = false;
    for (var i = 1; i <= DDJ1000.numSamplers(); i++) {
        if (engine.getValue("[Sampler" + i + "]", "pfl")) {
            any = true;
            break;
        }
    }
    DDJ1000.led(0x96, 0x69, any);
};

DDJ1000.onTrackLoaded = function (deck, loaded) {
    var state = DDJ1000.deck[deck];
    // Pitch shift from KEY SHIFT / KEYBOARD belongs to the old track.
    state.keySync = false;
    DDJ1000.deckLed(deck, 0x65, false);
    if (!loaded || !DDJ1000.opened) {
        return;
    }
    // "Trigger for Load illumination": the jog ring's load animation.
    DDJ1000.send(0x9F, deck - 1, 0x7F, true);
    if (state.loadFlashTimer) {
        engine.stopTimer(state.loadFlashTimer);
    }
    state.loadFlashTimer = engine.beginTimer(1000, function () {
        state.loadFlashTimer = 0;
        DDJ1000.send(0x9F, deck - 1, 0x00, true);
    }, true);
};

// ---------------------------------------------------------------------------
// Jog dial display
// ---------------------------------------------------------------------------

DDJ1000.secondsPerRevolution = function () {
    return 60 / DDJ1000.settings.vinylRpm;
};

// Mixxx key (1-12 major C..B, 13-24 minor Cm..Bm) -> DDJ display code (*3).
DDJ1000.keyCode = function (mixxxKey) {
    mixxxKey = Math.round(mixxxKey);
    if (mixxxKey >= 1 && mixxxKey <= 12) {
        return 2 * (mixxxKey - 1) + 1;
    }
    if (mixxxKey >= 13 && mixxxKey <= 24) {
        return 2 * ((mixxxKey - 13 + 3) % 12) + 2;
    }
    return 0;
};

// Mixxx updates playposition only 15 times a second. Between updates,
// advance it by the time passed at the current playing speed.
DDJ1000.estimateElapsed = function (deck, group, duration) {
    var sample = DDJ1000.deck[deck].position;
    var reported = DDJ1000.clamp(engine.getValue(group, "playposition"), 0, 1) * duration;
    if (!sample || !engine.getValue(group, "play") || engine.isScratching(deck) || duration <= 0) {
        return reported;
    }
    var speed = (engine.getValue(group, "rate_ratio") || 1) * (engine.getValue(group, "reverse") ? -1 : 1);
    var seconds = Math.min(0.1, (Date.now() - sample.at) / 1000);
    return DDJ1000.clamp(DDJ1000.clamp(sample.value, 0, 1) * duration + seconds * speed, 0, duration);
};

DDJ1000.updateDisplay = function (deck) {
    var group = DDJ1000.group(deck);
    var status = 0x90 + deck - 1;
    var cc = 0xB0 + deck - 1;
    var D = DDJ1000.DISPLAY;

    DDJ1000.send(status, D.syncMaster, engine.getValue(group, "sync_mode") === 2 ? 0x7F : 0x00);
    DDJ1000.send(status, D.syncState, engine.getValue(group, "sync_enabled") ? 0x7F : 0x00);

    if (!engine.getValue(group, "track_loaded")) {
        DDJ1000.send(status, D.timeMinute, 0);
        DDJ1000.send(status, D.timeSecond, 0);
        DDJ1000.send14(cc, D.bpmMsb, 0);
        DDJ1000.send14(cc, D.cueMarkerMsb, 0x3FFF);
        DDJ1000.send(status, D.keyValue, 0);
        DDJ1000.send(status, D.keyVariation, 0x0D);
        DDJ1000.send(status, D.ringLed, 0x01);
        return;
    }

    var duration = engine.getValue(group, "duration");
    var elapsed = DDJ1000.estimateElapsed(deck, group, duration);
    var remainingMode = engine.getValue("[Controls]", "ShowDurationRemaining") !== 0;
    var shown = remainingMode ? Math.max(0, duration - elapsed) : elapsed;
    DDJ1000.send(status, D.timeMode, remainingMode ? 0x7F : 0x00);
    DDJ1000.send(status, D.timeMinute, Math.min(99, Math.floor(shown / 60)));
    DDJ1000.send(status, D.timeSecond, Math.floor(shown % 60));

    // The position bar spins like a record at 33 1/3, not as track progress.
    var turns = elapsed / DDJ1000.secondsPerRevolution();
    DDJ1000.send14(cc, D.positionBarMsb, Math.floor((turns - Math.floor(turns)) * 360) % 360);

    // Like a CDJ/rekordbox, the jog display flashes once only a little track is left.
    var nearEnd = duration - elapsed <= DDJ1000.settings.endOfTrackWarningSec;
    DDJ1000.send(status, D.ringLed, nearEnd && !DDJ1000.blink ? 0x00 : 0x01);

    var cuePoint = engine.getValue(group, "cue_point");
    if (cuePoint >= 0) {
        var cueTurns = cuePoint / DDJ1000.samplesPerSecond(group) / DDJ1000.secondsPerRevolution();
        DDJ1000.send14(cc, D.cueMarkerMsb, Math.floor((cueTurns - Math.floor(cueTurns)) * 360) % 360);
    } else {
        DDJ1000.send14(cc, D.cueMarkerMsb, 0x3FFF);
    }

    DDJ1000.send14(cc, D.bpmMsb, DDJ1000.clamp(engine.getValue(group, "bpm") * 10, 0, 9999));

    var ratio = engine.getValue(group, "rate_ratio");
    if (!ratio) {
        ratio = 1 + engine.getValue(group, "rate") * engine.getValue(group, "rateRange")
            * engine.getValue(group, "rate_dir");
    }
    DDJ1000.send14(cc, D.speedMsb, DDJ1000.clamp(ratio * 4999.5, 0, 9999));

    DDJ1000.send(status, D.keyValue, DDJ1000.keyCode(engine.getValue(group, "key")));
    var shift = Math.round(engine.getValue(group, "pitch"));
    DDJ1000.send(status, D.keyVariation, 0x0D + DDJ1000.clamp(shift, -12, 12));
};

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

DDJ1000.play = function (channel, control, value, status, group) {
    if (value) {
        DDJ1000.toggle(group, "play");
    }
};

DDJ1000.cue = function (channel, control, value, status, group) {
    engine.setValue(group, "cue_default", value ? 1 : 0);
};

// SHIFT + CUE: jump to the start of the track.
DDJ1000.jumpToStart = function (channel, control, value, status, group) {
    if (value) {
        engine.setValue(group, "start", 1);
    }
};

// ---------------------------------------------------------------------------
// Tempo, sync, key
// ---------------------------------------------------------------------------

DDJ1000.tempo = function (channel, control, value, status, group) {
    // Top of the slider is "-" (MSB 0x00), bottom is "+".
    var x = DDJ1000.take14(status, control, value) * 2 - 1;
    engine.setValue(group, "rate", x * (engine.getValue(group, "rate_dir") || 1));
};

DDJ1000.masterTempo = function (channel, control, value, status, group) {
    if (value) {
        DDJ1000.toggle(group, "keylock");
    }
};

// SHIFT + MASTER TEMPO: TEMPO RANGE, ±6 -> ±10 -> ±16 -> WIDE.
DDJ1000.tempoRange = function (channel, control, value, status, group) {
    if (!value) {
        return;
    }
    var ranges = DDJ1000.settings.tempoRanges;
    var current = engine.getValue(group, "rateRange");
    var next = ranges[0];
    for (var i = 0; i < ranges.length; i++) {
        if (ranges[i] > current + 0.001) {
            next = ranges[i];
            break;
        }
    }
    engine.setValue(group, "rateRange", next);
};

DDJ1000.sync = function (channel, control, value, status, group) {
    if (value) {
        DDJ1000.toggle(group, "sync_enabled");
    }
};

// SHIFT + BEAT SYNC: make this deck the sync master.
DDJ1000.syncMaster = function (channel, control, value, status, group) {
    if (value) {
        var isLeader = engine.getValue(group, "sync_mode") === 2;
        engine.setValue(group, "sync_leader", isLeader ? 0 : 1);
    }
};

DDJ1000.keySync = function (channel, control, value, status, group) {
    if (!value) {
        return;
    }
    var deck = script.deckFromGroup(group);
    var state = DDJ1000.deck[deck];
    state.keySync = !state.keySync;
    if (state.keySync) {
        engine.setValue(group, "sync_key", 1);
    }
    DDJ1000.deckLed(deck, 0x65, state.keySync);
};

DDJ1000.keyReset = function (channel, control, value, status, group) {
    if (!value) {
        return;
    }
    var deck = script.deckFromGroup(group);
    engine.setValue(group, "reset_key", 1);
    DDJ1000.deck[deck].keySync = false;
    DDJ1000.deckLed(deck, 0x65, false);
};

// ---------------------------------------------------------------------------
// Loops
// ---------------------------------------------------------------------------

DDJ1000.loopIn = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    if (DDJ1000.deck[deck].loopAdjust) {
        if (value) {
            DDJ1000.setLoopAdjust(deck, null);
        }
        return;
    }
    engine.setValue(group, "loop_in", value ? 1 : 0);
};

DDJ1000.loopOut = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    if (DDJ1000.deck[deck].loopAdjust) {
        if (value) {
            DDJ1000.setLoopAdjust(deck, null);
        }
        return;
    }
    engine.setValue(group, "loop_out", value ? 1 : 0);
};

// Sent instead of LOOP IN / LOOP OUT while a loop runs.
DDJ1000.loopHalve = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    if (DDJ1000.deck[deck].loopAdjust) {
        if (value) {
            DDJ1000.setLoopAdjust(deck, null);
        }
        return;
    }
    engine.setValue(group, "loop_halve", value ? 1 : 0);
};

DDJ1000.loopDouble = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    if (DDJ1000.deck[deck].loopAdjust) {
        if (value) {
            DDJ1000.setLoopAdjust(deck, null);
        }
        return;
    }
    engine.setValue(group, "loop_double", value ? 1 : 0);
};

// SHIFT + LOOP IN: move the loop-in point with the jog, until pressed again.
DDJ1000.loopInAdjust = function (channel, control, value, status, group) {
    if (!value) {
        return;
    }
    var deck = script.deckFromGroup(group);
    if (engine.getValue(group, "loop_start_position") < 0) {
        return;
    }
    DDJ1000.setLoopAdjust(deck, DDJ1000.deck[deck].loopAdjust === "in" ? null : "in");
};

// SHIFT + LOOP OUT: adjust loop-out while looping, otherwise RELOOP.
DDJ1000.loopOutShift = function (channel, control, value, status, group) {
    if (!value) {
        return;
    }
    var deck = script.deckFromGroup(group);
    if (engine.getValue(group, "loop_enabled") || DDJ1000.deck[deck].loopAdjust) {
        DDJ1000.setLoopAdjust(deck, DDJ1000.deck[deck].loopAdjust === "out" ? null : "out");
    } else {
        engine.setValue(group, "reloop_toggle", 1);
    }
};

DDJ1000.setLoopAdjust = function (deck, which) {
    DDJ1000.deck[deck].loopAdjust = which;
    DDJ1000.updateLoopAdjustLeds(deck);
};

DDJ1000.updateLoopAdjustLeds = function (deck) {
    var group = DDJ1000.group(deck);
    var adjust = DDJ1000.deck[deck] ? DDJ1000.deck[deck].loopAdjust : null;
    var looping = engine.getValue(group, "loop_enabled") > 0;
    var inOn = adjust === "in" ? DDJ1000.blink : (adjust === "out" ? true : looping);
    var outOn = adjust === "out" ? DDJ1000.blink : (adjust === "in" ? true : looping);
    DDJ1000.deckLed(deck, 0x10, inOn);
    DDJ1000.deckLed(deck, 0x4C, inOn);
    DDJ1000.deckLed(deck, 0x11, outOn);
    DDJ1000.deckLed(deck, 0x4D, outOn);
};

DDJ1000.nudgeLoop = function (deck, ticks) {
    var group = DDJ1000.group(deck);
    var which = DDJ1000.deck[deck].loopAdjust;
    var key = which === "in" ? "loop_start_position" : "loop_end_position";
    var point = engine.getValue(group, key);
    if (point < 0) {
        return;
    }
    var ms = ticks * DDJ1000.settings.loopAdjustMsPerRevolution / DDJ1000.settings.jogTicksPerRevolution;
    var moved = point + ms * DDJ1000.samplesPerSecond(group) / 1000;
    moved = Math.round(moved / 2) * 2; // stay on a frame boundary
    if (which === "in") {
        moved = DDJ1000.clamp(moved, 0, engine.getValue(group, "loop_end_position") - 2);
    } else {
        moved = Math.max(engine.getValue(group, "loop_start_position") + 2, moved);
    }
    engine.setValue(group, key, moved);
};

// 4 BEAT LOOP / EXIT.
DDJ1000.beatLoop4 = function (channel, control, value, status, group) {
    if (!value) {
        return;
    }
    var deck = script.deckFromGroup(group);
    if (DDJ1000.deck[deck].loopAdjust) {
        DDJ1000.setLoopAdjust(deck, null);
        return;
    }
    if (engine.getValue(group, "loop_enabled")) {
        engine.setValue(group, "loop_enabled", 0);
    } else {
        engine.setValue(group, "beatloop_4_activate", 1);
    }
};

// SHIFT + 4 BEAT LOOP: make the stored loop active / inactive.
DDJ1000.loopActive = function (channel, control, value, status, group) {
    if (value && engine.getValue(group, "loop_start_position") >= 0) {
        DDJ1000.toggle(group, "loop_enabled");
    }
};

// ---------------------------------------------------------------------------
// Deck buttons
// ---------------------------------------------------------------------------

// QUANTIZE is global in rekordbox.
DDJ1000.quantize = function (channel, control, value, status, group) {
    if (!value) {
        return;
    }
    var on = engine.getValue(group, "quantize") ? 0 : 1;
    DDJ1000.decks.forEach(function (deck) {
        engine.setValue(DDJ1000.group(deck), "quantize", on);
    });
};

DDJ1000.slip = function (channel, control, value, status, group) {
    if (value) {
        DDJ1000.toggle(group, "slip_enabled");
    }
};

// SHIFT + SLIP: VINYL mode for the jog.
DDJ1000.vinyl = function (channel, control, value, status, group) {
    if (!value) {
        return;
    }
    var deck = script.deckFromGroup(group);
    DDJ1000.deck[deck].vinyl = !DDJ1000.deck[deck].vinyl;
    DDJ1000.updateVinylLed(deck);
};

// The unit reports its own VINYL state here (rekordbox "VinylState", RO).
DDJ1000.vinylState = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    DDJ1000.deck[deck].vinyl = value > 0;
    DDJ1000.updateVinylLed(deck);
};

DDJ1000.updateVinylLed = function (deck) {
    DDJ1000.deckLed(deck, 0x17, DDJ1000.deck[deck].vinyl);
};

// SLIP REVERSE: reverse while held, lets go by itself after 8 beats.
DDJ1000.slipReverse = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    var state = DDJ1000.deck[deck];
    if (state.reverseTimer) {
        engine.stopTimer(state.reverseTimer);
        state.reverseTimer = 0;
    }
    if (!value) {
        engine.setValue(group, "reverseroll", 0);
        return;
    }
    engine.setValue(group, "reverseroll", 1);
    var bpm = engine.getValue(group, "bpm");
    if (bpm > 0) {
        var ms = DDJ1000.settings.slipReverseBeats * 60000 / bpm;
        state.reverseTimer = engine.beginTimer(Math.round(ms), function () {
            state.reverseTimer = 0;
            engine.setValue(group, "reverseroll", 0);
        }, true);
    }
};

// SHIFT + SLIP REVERSE: REVERSE on/off.
DDJ1000.reverse = function (channel, control, value, status, group) {
    if (value) {
        DDJ1000.toggle(group, "reverse");
    }
};

// SHIFT + QUANTIZE: headphones mono split (cue in the left ear, master in the
// right). Set the HEADPHONES MIX knob fully to CUE while it is on.
DDJ1000.monoSplit = function (channel, control, value) {
    if (value) {
        DDJ1000.toggle("[Master]", "headSplit");
    }
};

DDJ1000.headphoneCue = function (channel, control, value, status, group) {
    if (value) {
        DDJ1000.toggle(group, "pfl");
    }
};

// SHIFT + headphones CUE: TAP BPM.
DDJ1000.tapBpm = function (channel, control, value, status, group) {
    if (value) {
        engine.setValue(group, "bpm_tap", 1);
    }
};

// CH FADER / CROSSFADER fader start (SHIFT + fader).
DDJ1000.faderStartPlay = function (channel, control, value, status, group) {
    if (value && !engine.getValue(group, "play")) {
        engine.setValue(group, "play", 1);
    }
};

DDJ1000.faderStartCue = function (channel, control, value, status, group) {
    if (value) {
        engine.setValue(group, "cue_gotoandstop", 1);
    }
};

DDJ1000.crossfaderAssign = function (channel, control, value, status, group) {
    if (!value) {
        return;
    }
    var orientation = { 0x16: 0, 0x1D: 1, 0x18: 2 }[control];
    if (orientation !== undefined) {
        engine.setValue(group, "orientation", orientation);
    }
};

DDJ1000.deckSelect = function (channel, control, value) {
    if (value) {
        // The unit may redraw this side from scratch; send it everything again.
        DDJ1000.resendAll();
    }
};

// rekordbox's GRID ADJUST / GRID SLIDE state buttons: SHIFT + jog edits the grid.
DDJ1000.gridAdjustState = function (channel, control, value, status, group) {
    DDJ1000.deck[script.deckFromGroup(group)].gridMode = value ? "adjust" : null;
};

DDJ1000.gridSlideState = function (channel, control, value, status, group) {
    DDJ1000.deck[script.deckFromGroup(group)].gridMode = value ? "slide" : null;
};

DDJ1000.shift = function () {
    // SHIFT is resolved inside the unit (it sends different notes); nothing to do.
};

// ---------------------------------------------------------------------------
// SEARCH, CUE/LOOP CALL, MEMORY
// ---------------------------------------------------------------------------

// Press: track search (|<< start of track / previous, >>| next track).
// Hold: fast search. The unit sends a second note once a press becomes a hold.
DDJ1000.searchBack = function (channel, control, value, status, group) {
    DDJ1000.searchPress(script.deckFromGroup(group), -1, value);
};

DDJ1000.searchForward = function (channel, control, value, status, group) {
    DDJ1000.searchPress(script.deckFromGroup(group), 1, value);
};

DDJ1000.searchBackLong = function (channel, control, value, status, group) {
    DDJ1000.searchHold(script.deckFromGroup(group), -1, value);
};

DDJ1000.searchForwardLong = function (channel, control, value, status, group) {
    DDJ1000.searchHold(script.deckFromGroup(group), 1, value);
};

DDJ1000.searchPress = function (deck, direction, value) {
    var state = DDJ1000.deck[deck];
    if (value) {
        state.searchLong = false;
        return;
    }
    DDJ1000.stopSearch(deck);
    if (!state.searchLong) {
        DDJ1000.trackSearch(deck, direction);
    }
    state.searchLong = false;
};

DDJ1000.searchHold = function (deck, direction, value) {
    var state = DDJ1000.deck[deck];
    if (!value) {
        DDJ1000.stopSearch(deck);
        return;
    }
    state.searchLong = true;
    state.search = { direction: direction, since: Date.now() };
    engine.setValue(DDJ1000.group(deck), "rateSearch", direction * DDJ1000.settings.searchRate);
};

DDJ1000.stopSearch = function (deck) {
    if (DDJ1000.deck[deck].search) {
        DDJ1000.deck[deck].search = null;
        engine.setValue(DDJ1000.group(deck), "rateSearch", 0);
    }
};

DDJ1000.updateSearch = function (deck) {
    var search = DDJ1000.deck[deck].search;
    if (!search) {
        return;
    }
    var s = DDJ1000.settings;
    var through = Math.min(1, (Date.now() - search.since) / 1000 / s.searchRampSeconds);
    var rate = s.searchRate + (s.searchMaxRate - s.searchRate) * through * through;
    engine.setValue(DDJ1000.group(deck), "rateSearch", search.direction * rate);
};

DDJ1000.trackSearch = function (deck, direction) {
    var group = DDJ1000.group(deck);
    if (direction < 0 && engine.getValue(group, "playposition") * engine.getValue(group, "duration") > 1) {
        engine.setValue(group, "start", 1);
        return;
    }
    if (engine.getValue(group, "play")) {
        return; // never swap the track under a playing deck
    }
    engine.setValue("[Library]", "MoveVertical", direction);
    engine.setValue(group, "LoadSelectedTrack", 1);
};

// Memory cues live in Mixxx hot cues 17-36 (pads use 1-16).
DDJ1000.MEMORY_FIRST = 17;
DDJ1000.MEMORY_LAST = 36;
DDJ1000.MEMORY_COLOR = 0xE8201E;

// SHIFT + SEARCH: CUE/LOOP CALL, the previous / next stored point.
DDJ1000.cueCallBack = function (channel, control, value, status, group) {
    if (value) {
        DDJ1000.cueCall(group, -1);
    }
};

DDJ1000.cueCallForward = function (channel, control, value, status, group) {
    if (value) {
        DDJ1000.cueCall(group, 1);
    }
};

DDJ1000.cueCall = function (group, direction) {
    if (!engine.getValue(group, "track_loaded")) {
        return;
    }
    var here = DDJ1000.positionSamples(group);
    var margin = DDJ1000.samplesPerSecond(group) * 0.05;
    var points = [];
    var cuePoint = engine.getValue(group, "cue_point");
    if (cuePoint >= 0) {
        points.push(cuePoint);
    }
    for (var i = 1; i <= DDJ1000.MEMORY_LAST; i++) {
        var position = engine.getValue(group, "hotcue_" + i + "_position");
        if (position >= 0) {
            points.push(position);
        }
    }
    var target = -1;
    points.forEach(function (point) {
        if (direction < 0 && point < here - margin && (target < 0 || point > target)) {
            target = point;
        }
        if (direction > 0 && point > here + margin && (target < 0 || point < target)) {
            target = point;
        }
    });
    if (target < 0) {
        return;
    }
    DDJ1000.seekSamples(group, target);
    if (!engine.getValue(group, "play")) {
        engine.setValue(group, "cue_set", 1); // a called cue becomes the CUE point, as on a CDJ
    }
};

// MEMORY: store the current point (or the running loop) as a memory cue.
DDJ1000.memory = function (channel, control, value, status, group) {
    if (!value || !engine.getValue(group, "track_loaded")) {
        return;
    }
    var here = DDJ1000.positionSamples(group);
    var margin = DDJ1000.samplesPerSecond(group) * 0.05;
    var free = 0;
    for (var i = DDJ1000.MEMORY_FIRST; i <= DDJ1000.MEMORY_LAST; i++) {
        var position = engine.getValue(group, "hotcue_" + i + "_position");
        if (position < 0) {
            free = free || i;
        } else if (Math.abs(position - here) < margin) {
            return; // already stored here
        }
    }
    if (!free) {
        return;
    }
    engine.setValue(group, "hotcue_" + free + "_set", 1);
    engine.setValue(group, "hotcue_" + free + "_color", DDJ1000.MEMORY_COLOR);
};

// SHIFT + MEMORY: DELETE the memory cue at (or nearest) the current position.
DDJ1000.memoryDelete = function (channel, control, value, status, group) {
    if (!value || !engine.getValue(group, "track_loaded")) {
        return;
    }
    var here = DDJ1000.positionSamples(group);
    var best = 0, bestDistance = DDJ1000.samplesPerSecond(group) * 1.0;
    for (var i = DDJ1000.MEMORY_FIRST; i <= DDJ1000.MEMORY_LAST; i++) {
        var position = engine.getValue(group, "hotcue_" + i + "_position");
        if (position >= 0 && Math.abs(position - here) <= bestDistance) {
            best = i;
            bestDistance = Math.abs(position - here);
        }
    }
    if (best) {
        engine.setValue(group, "hotcue_" + best + "_clear", 1);
    }
};

// ---------------------------------------------------------------------------
// Jog wheel
// ---------------------------------------------------------------------------

DDJ1000.jogTouch = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    var state = DDJ1000.deck[deck];
    var s = DDJ1000.settings;
    if (value) {
        state.touched = true;
        state.throwing = false;
        state.speed = undefined;
        if (state.vinyl && !state.loopAdjust) {
            engine.scratchEnable(deck, s.jogTicksPerRevolution, s.vinylRpm,
                s.scratchAlpha, s.scratchBeta, true);
        }
    } else {
        state.touched = false;
        // Let go of a spinning platter and the record keeps going with it;
        // the outer ring carries the throw until the platter slows down.
        state.throwing = engine.isScratching(deck);
        state.lastTick = Date.now();
    }
    state.settling = false;
};

// Platter turned while touched in VINYL mode: scratch.
DDJ1000.jogScratch = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    var state = DDJ1000.deck[deck];
    var ticks = DDJ1000.jogTicks(value);
    if (state.loopAdjust) {
        DDJ1000.nudgeLoop(deck, ticks);
        return;
    }
    if (engine.isScratching(deck)) {
        state.lastTick = Date.now();
        engine.scratchTick(deck, ticks);
    } else {
        DDJ1000.pitchBend(group, ticks);
    }
};

// Platter top with VINYL off: pitch bend.
DDJ1000.jogBend = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    var ticks = DDJ1000.jogTicks(value);
    if (DDJ1000.deck[deck].loopAdjust) {
        DDJ1000.nudgeLoop(deck, ticks);
        return;
    }
    DDJ1000.pitchBend(group, ticks);
};

// Outer ring: pitch bend, or the tail of a throw.
DDJ1000.jogRing = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    var state = DDJ1000.deck[deck];
    var ticks = DDJ1000.jogTicks(value);
    if (state.loopAdjust) {
        DDJ1000.nudgeLoop(deck, ticks);
        return;
    }
    if (engine.isScratching(deck)) {
        if (state.throwing && !state.touched) {
            DDJ1000.coast(deck, ticks);
        }
        return;
    }
    if (state.settling) {
        // The platter is still coasting after a scratch or backspin; bending
        // with it would play the track off-speed (and off-key).
        state.lastTick = Date.now();
        return;
    }
    DDJ1000.pitchBend(group, ticks);
};

DDJ1000.pitchBend = function (group, ticks) {
    engine.setValue(group, "jog",
        ticks * DDJ1000.settings.pitchBendPerRevolution / DDJ1000.settings.jogTicksPerRevolution);
};

DDJ1000.coast = function (deck, ticks) {
    var state = DDJ1000.deck[deck];
    var s = DDJ1000.settings;
    var now = Date.now();
    var elapsed = now - (state.lastTick || now);
    state.lastTick = now;
    engine.scratchTick(deck, ticks);
    if (elapsed <= 0) {
        return;
    }
    var speed = Math.abs(ticks) * 1000 / elapsed;
    state.speed = state.speed === undefined ? speed : state.speed + (speed - state.speed) * 0.25;
    var playingSpeed = s.jogTicksPerRevolution / DDJ1000.secondsPerRevolution();
    if (state.speed < playingSpeed * s.throwReleaseFraction) {
        DDJ1000.endThrow(deck);
    }
};

DDJ1000.checkThrow = function (deck) {
    var state = DDJ1000.deck[deck];
    if (state.settling && Date.now() - state.lastTick > 150) {
        state.settling = false; // platter has come to rest
    }
    if (state.touched) {
        return;
    }
    if (engine.isScratching(deck)
            && Date.now() - (state.lastTick || 0) >= DDJ1000.settings.throwSpinDownMs) {
        DDJ1000.endThrow(deck);
    }
};

DDJ1000.endThrow = function (deck) {
    var state = DDJ1000.deck[deck];
    state.throwing = false;
    state.speed = undefined;
    state.settling = true;
    state.lastTick = Date.now();
    engine.scratchDisable(deck, true);
};

// SHIFT + platter / SHIFT + ring: track search (rekordbox), or the beat grid
// while rekordbox's GRID ADJUST / GRID SLIDE state is on (manual p. 6).
DDJ1000.gridCarry = {};

DDJ1000.jogShiftTop = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    var ticks = DDJ1000.jogTicks(value);
    var mode = DDJ1000.deck[deck].gridMode;
    if (mode === "adjust") {
        DDJ1000.gridSteps(deck, group, ticks, "beats_adjust_faster", "beats_adjust_slower");
    } else if (mode === "slide") {
        DDJ1000.gridSteps(deck, group, ticks, "beats_translate_later", "beats_translate_earlier");
    } else {
        DDJ1000.jogSearch(group, ticks, 1);
    }
};

DDJ1000.jogShiftRing = function (channel, control, value, status, group) {
    var deck = script.deckFromGroup(group);
    var ticks = DDJ1000.jogTicks(value);
    if (DDJ1000.deck[deck].gridMode) {
        DDJ1000.gridSteps(deck, group, ticks, "beats_translate_later", "beats_translate_earlier");
    } else {
        DDJ1000.jogSearch(group, ticks, 1);
    }
};

// SEARCH held + platter: fast search.
DDJ1000.jogSearchFast = function (channel, control, value, status, group) {
    DDJ1000.jogSearch(group, DDJ1000.jogTicks(value), 4);
};

DDJ1000.jogSearch = function (group, ticks, speed) {
    var duration = engine.getValue(group, "duration");
    if (duration <= 0) {
        return;
    }
    var seconds = ticks * DDJ1000.settings.jogSearchSecondsPerRevolution
        / DDJ1000.settings.jogTicksPerRevolution;
    var acceleration = Math.min(6, 1 + Math.abs(ticks) / 4) * speed;
    var position = engine.getValue(group, "playposition") + seconds * acceleration / duration;
    engine.setValue(group, "playposition", DDJ1000.clamp(position, 0, 1));
};

DDJ1000.gridSteps = function (deck, group, ticks, forwardKey, backwardKey) {
    var perStep = DDJ1000.settings.jogTicksPerRevolution / 32;
    var carry = (DDJ1000.gridCarry[deck] || 0) + ticks;
    while (Math.abs(carry) >= perStep) {
        engine.setValue(group, carry > 0 ? forwardKey : backwardKey, 1);
        carry -= carry > 0 ? perStep : -perStep;
    }
    DDJ1000.gridCarry[deck] = carry;
};

// ---------------------------------------------------------------------------
// Browser
// ---------------------------------------------------------------------------

DDJ1000.browse = function (channel, control, value) {
    var ticks = DDJ1000.encoderTicks(value);
    if (ticks) {
        engine.setValue("[Library]", "MoveVertical", ticks);
    }
};

// SHIFT + rotary: waveform size (right enlarges).
DDJ1000.browseShift = function (channel, control, value) {
    var ticks = DDJ1000.encoderTicks(value);
    DDJ1000.decks.forEach(function (deck) {
        var group = DDJ1000.group(deck);
        var zoom = engine.getValue(group, "waveform_zoom") - ticks * 0.5;
        engine.setValue(group, "waveform_zoom", DDJ1000.clamp(zoom, 1, 10));
    });
};

// Rotary press: load to the deck on that side; on the tree it opens the
// folder instead; pressed twice quickly it makes an instant double.
DDJ1000.browsePress = function (channel, control, value) {
    if (!value) {
        return;
    }
    var deck = control - 0x46 + 1; // 0x46 deck 1, 0x47 deck 2, 0x48 deck 3, 0x49 deck 4
    var group = DDJ1000.group(deck);
    var state = DDJ1000.deck[deck];
    var now = Date.now();
    if (engine.getValue("[Library]", "focused_widget") === 2) {
        // On the tree: open the item and go to its track list. Mixxx never
        // opens Tracks or Auto DJ from a controller, so move focus as well.
        engine.setValue("[Library]", "GoToItem", 1);
        if (engine.getValue("[Library]", "focused_widget") === 2) {
            engine.setValue("[Library]", "focused_widget", 3);
        }
        return;
    }
    if (now - state.lastLoadPress < DDJ1000.settings.doublePressMs) {
        state.lastLoadPress = 0;
        var partner = deck <= 2 ? deck + 2 : deck - 2; // the other deck on the same side
        engine.setValue(group, "CloneFromDeck", partner);
        return;
    }
    state.lastLoadPress = now;
    engine.setValue(group, "LoadSelectedTrack", 1);
};

// BACK: move between the tree and the track list.
DDJ1000.back = function (channel, control, value) {
    if (value) {
        var focused = engine.getValue("[Library]", "focused_widget");
        engine.setValue("[Library]", "focused_widget", focused === 2 ? 3 : 2);
    }
};

// VIEW: enlarge the browser / back to the decks.
DDJ1000.view = function (channel, control, value) {
    if (value) {
        DDJ1000.toggle("[Skin]", "show_maximized_library");
    }
};

// VIEW held: rekordbox's tag list; Mixxx's nearest is the Auto DJ queue.
DDJ1000.viewLong = function (channel, control, value) {
    if (value) {
        engine.setValue("[Library]", "AutoDjAddBottom", 1);
    }
};

// ---------------------------------------------------------------------------
// Sampler section (mixer)
// ---------------------------------------------------------------------------

DDJ1000.samplerVolume = function (channel, control, value, status) {
    var level = DDJ1000.take14(status, control, value);
    for (var i = 1; i <= DDJ1000.numSamplers(); i++) {
        engine.setParameter("[Sampler" + i + "]", "volume", level);
    }
};

DDJ1000.samplerCue = function (channel, control, value) {
    if (!value) {
        return;
    }
    var on = engine.getValue("[Sampler1]", "pfl") ? 0 : 1;
    for (var i = 1; i <= DDJ1000.numSamplers(); i++) {
        engine.setValue("[Sampler" + i + "]", "pfl", on);
    }
    DDJ1000.updateSamplerCueLed();
};

// ---------------------------------------------------------------------------
// SOUND COLOR FX
// ---------------------------------------------------------------------------

// Buttons 0x00-0x03 (0x08-0x0B with SHIFT): DUB ECHO, PITCH, NOISE, FILTER.
DDJ1000.colorFxButton = function (channel, control, value) {
    if (!value) {
        return;
    }
    var which = (control & 0x03) + 1;
    DDJ1000.colorFx = DDJ1000.colorFx === which ? 0 : which;
    DDJ1000.applyColorFx();
};

// The unit also reports which one is on (rekordbox "CFXnState", 0x10-0x13).
DDJ1000.colorFxState = function (channel, control, value) {
    var which = (control & 0x03) + 1;
    if (value) {
        DDJ1000.colorFx = which;
    } else if (DDJ1000.colorFx === which) {
        DDJ1000.colorFx = 0;
    } else {
        return;
    }
    DDJ1000.applyColorFx();
};

DDJ1000.applyColorFx = function () {
    var presets = [0, DDJ1000.QUICK.DUB_ECHO, DDJ1000.QUICK.PITCH, DDJ1000.QUICK.NOISE, DDJ1000.QUICK.FILTER];
    DDJ1000.decks.forEach(function (deck) {
        var unit = "[QuickEffectRack1_" + DDJ1000.group(deck) + "]";
        if (DDJ1000.colorFx) {
            if (engine.getValue(unit, "loaded_chain_preset") !== presets[DDJ1000.colorFx]) {
                engine.setValue(unit, "loaded_chain_preset", presets[DDJ1000.colorFx]);
            }
            engine.setValue(unit, "enabled", 1);
        } else {
            // As in rekordbox, the COLOR knobs do nothing until an FX is chosen.
            engine.setValue(unit, "enabled", 0);
        }
    });
    DDJ1000.updateColorFxLeds();
};

DDJ1000.updateColorFxLeds = function () {
    for (var i = 0; i < 4; i++) {
        var on = DDJ1000.colorFx === i + 1;
        DDJ1000.led(0x96, i, on);
        DDJ1000.led(0x96, 0x08 + i, on);
    }
};

// ---------------------------------------------------------------------------
// BEAT FX (effect unit 1)
// ---------------------------------------------------------------------------

DDJ1000.BEAT_FX_UNIT = "[EffectRack1_EffectUnit1]";

DDJ1000.setupBeatFx = function () {
    engine.setValue(DDJ1000.BEAT_FX_UNIT, "enabled", 0);
    DDJ1000.loadBeatFx();
    DDJ1000.routeBeatFx();
};

DDJ1000.beatFxType = function () {
    return DDJ1000.BEAT_FX_TYPES[DDJ1000.beatFx.type];
};

DDJ1000.beatValue = function () {
    return DDJ1000.settings.beatValues[DDJ1000.beatFx.beatIndex];
};

DDJ1000.loadBeatFx = function () {
    var type = DDJ1000.beatFxType();
    var preset = type.roll ? 0 : type.preset;
    if (engine.getValue(DDJ1000.BEAT_FX_UNIT, "loaded_chain_preset") !== preset) {
        engine.setValue(DDJ1000.BEAT_FX_UNIT, "loaded_chain_preset", preset);
    }
    DDJ1000.applyBeatFxDepth();
    DDJ1000.applyBeats(1, type.preset, DDJ1000.beatValue());
};

DDJ1000.applyBeats = function (unitNumber, preset, beats) {
    var param = DDJ1000.BEAT_PARAM[preset];
    if (!param || !beats) {
        return;
    }
    var slot = "[EffectRack1_EffectUnit" + unitNumber + "_Effect" + param.slot + "]";
    engine.setValue(slot, "parameter" + param.param, param.kind === "rate" ? 1 / beats : beats);
};

DDJ1000.applyBeatFxDepth = function () {
    var type = DDJ1000.beatFxType();
    if (type.depthIsSuper) {
        engine.setValue(DDJ1000.BEAT_FX_UNIT, "mix", 1);
        engine.setValue(DDJ1000.BEAT_FX_UNIT, "super1", DDJ1000.beatFx.depth);
    } else {
        engine.setValue(DDJ1000.BEAT_FX_UNIT, "mix", DDJ1000.beatFx.depth);
    }
};

DDJ1000.routeBeatFx = function () {
    var unit = DDJ1000.BEAT_FX_UNIT;
    var channel = DDJ1000.beatFx.channel;
    DDJ1000.decks.forEach(function (deck) {
        engine.setValue(unit, "group_[Channel" + deck + "]_enable", channel === deck ? 1 : 0);
    });
    engine.setValue(unit, "group_[Master]_enable", channel === "master" ? 1 : 0);
    for (var i = 1; i <= DDJ1000.numSamplers(); i++) {
        engine.setValue(unit, "group_[Sampler" + i + "]_enable", channel === "sampler" ? 1 : 0);
    }
};

// The decks a ROLL acts on: the selected channel, or every playing deck on MASTER.
DDJ1000.beatFxDecks = function () {
    var channel = DDJ1000.beatFx.channel;
    if (typeof channel === "number") {
        return [channel];
    }
    if (channel === "master") {
        return DDJ1000.decks.filter(function (deck) {
            return engine.getValue(DDJ1000.group(deck), "play") > 0;
        });
    }
    return [];
};

DDJ1000.beatFxSelect = function (channel, control, value) {
    if (!value) {
        return;
    }
    var index = control - 0x20;
    if (index < 0 || index >= DDJ1000.BEAT_FX_TYPES.length || index === DDJ1000.beatFx.type) {
        return;
    }
    var wasOn = DDJ1000.beatFx.on;
    if (wasOn) {
        DDJ1000.setBeatFxOn(false);
    }
    DDJ1000.beatFx.type = index;
    DDJ1000.loadBeatFx();
    if (wasOn) {
        DDJ1000.setBeatFxOn(true);
    }
};

// CH SELECT positions 0x10-0x16: CH1, CH2, CH3, CH4, MASTER, MIC, SAMPLER.
DDJ1000.beatFxChannel = function (channel, control, value) {
    if (!value) {
        return;
    }
    var targets = [1, 2, 3, 4, "master", "mic", "sampler"];
    var target = targets[control - 0x10];
    if (target === undefined) {
        return;
    }
    var wasOn = DDJ1000.beatFx.on;
    if (wasOn && DDJ1000.beatFxType().roll) {
        DDJ1000.setBeatFxOn(false);
    }
    DDJ1000.beatFx.channel = target;
    DDJ1000.routeBeatFx();
    if (wasOn && DDJ1000.beatFxType().roll) {
        DDJ1000.setBeatFxOn(true);
    }
};

DDJ1000.beatFxLevel = function (channel, control, value, status) {
    DDJ1000.beatFx.depth = DDJ1000.take14(status, control, value);
    DDJ1000.applyBeatFxDepth();
};

DDJ1000.beatFxOn = function (channel, control, value) {
    if (value) {
        DDJ1000.setBeatFxOn(!DDJ1000.beatFx.on);
    }
};

DDJ1000.setBeatFxOn = function (on) {
    var fx = DDJ1000.beatFx;
    var type = DDJ1000.beatFxType();
    fx.on = on;
    if (type.roll) {
        engine.setValue(DDJ1000.BEAT_FX_UNIT, "enabled", 0);
        if (on) {
            fx.rolling = DDJ1000.beatFxDecks();
            fx.rolling.forEach(function (deck) {
                DDJ1000.startRoll(deck, DDJ1000.beatValue(), type.roll === "slip");
            });
        } else {
            fx.rolling.forEach(function (deck) {
                DDJ1000.stopRoll(deck, type.roll === "slip");
            });
            fx.rolling = [];
        }
    } else {
        engine.setValue(DDJ1000.BEAT_FX_UNIT, "enabled", on ? 1 : 0);
    }
    DDJ1000.updateBeatFxLeds();
};

DDJ1000.startRoll = function (deck, beats, slip) {
    var group = DDJ1000.group(deck);
    engine.setValue(group, "beatloop_size", beats);
    engine.setValue(group, slip ? "beatlooproll_activate" : "beatloop_activate", 1);
};

DDJ1000.stopRoll = function (deck, slip) {
    var group = DDJ1000.group(deck);
    if (slip) {
        engine.setValue(group, "beatlooproll_activate", 0);
    } else {
        engine.setValue(group, "loop_enabled", 0);
    }
};

// SHIFT + BEAT FX ON: RELEASE FX — Beat FX off and a vinyl brake on its channel.
DDJ1000.releaseFx = function (channel, control, value) {
    DDJ1000.led(0x94, 0x43, value > 0);
    if (!value) {
        return;
    }
    var decks = DDJ1000.beatFxDecks();
    if (DDJ1000.beatFx.on) {
        DDJ1000.setBeatFxOn(false);
    }
    decks.forEach(function (deck) {
        engine.brake(deck, true);
    });
};

DDJ1000.beatDown = function (channel, control, value) {
    DDJ1000.beatStep(-1, value, 0x4A);
};

DDJ1000.beatUp = function (channel, control, value) {
    DDJ1000.beatStep(1, value, 0x4B);
};

DDJ1000.beatStep = function (direction, value, note) {
    DDJ1000.led(0x94, note, value > 0);
    if (!value) {
        return;
    }
    var fx = DDJ1000.beatFx;
    fx.beatIndex = DDJ1000.clamp(fx.beatIndex + direction, 0, DDJ1000.settings.beatValues.length - 1);
    var type = DDJ1000.beatFxType();
    if (type.roll) {
        fx.rolling.forEach(function (deck) {
            engine.setValue(DDJ1000.group(deck), "beatloop_size", DDJ1000.beatValue());
        });
    } else {
        DDJ1000.applyBeats(1, type.preset, DDJ1000.beatValue());
    }
};

// SHIFT + BEAT <: AUTO BPM, SHIFT + BEAT >: TAP. Mixxx effects always follow the
// deck BPM automatically, so both just flash.
DDJ1000.beatAuto = function (channel, control, value) {
    DDJ1000.led(0x94, 0x66, value > 0);
};

DDJ1000.beatTap = function (channel, control, value) {
    DDJ1000.led(0x94, 0x6B, value > 0);
};

DDJ1000.updateBeatFxLeds = function () {
    var on = DDJ1000.beatFx.on;
    DDJ1000.led(0x94, 0x47, on);
};

// ---------------------------------------------------------------------------
// Performance pads
// ---------------------------------------------------------------------------

DDJ1000.padMode = function (channel, control, value, status, group) {
    if (!value) {
        return;
    }
    var deck = script.deckFromGroup(group);
    var mode = DDJ1000.MODE_BUTTONS.indexOf(control);
    if (mode >= 0) {
        DDJ1000.deck[deck].mode = mode;
        DDJ1000.updateModeLeds(deck);
    }
};

DDJ1000.pagePrev = function (channel, control, value, status, group) {
    DDJ1000.pageStep(script.deckFromGroup(group), DDJ1000.PAGE_PREV_NOTES.indexOf(control), -1, value, control);
};

DDJ1000.pageNext = function (channel, control, value, status, group) {
    DDJ1000.pageStep(script.deckFromGroup(group), DDJ1000.PAGE_NEXT_NOTES.indexOf(control), 1, value, control);
};

DDJ1000.pageStep = function (deck, mode, direction, value, note) {
    if (!value || mode < 0) {
        return;
    }
    var state = DDJ1000.deck[deck];
    var M = DDJ1000.MODE;
    state.mode = mode;
    if (DDJ1000.settings.padPaletteTest && deck === 1) {
        DDJ1000.paletteBase = DDJ1000.clamp(DDJ1000.paletteBase + direction * 16, 1, 113);
        print("DDJ-1000 pad palette test: deck 1 pads = " + DDJ1000.paletteBase
            + ".." + (DDJ1000.paletteBase + 7) + ", deck 2 pads = "
            + (DDJ1000.paletteBase + 8) + ".." + (DDJ1000.paletteBase + 15));
        return;
    }
    if (mode === M.BEAT_JUMP) {
        // BEAT JUMP: PAGE < / > halve / double the jump range.
        state.jumpMultiplier = DDJ1000.clamp(state.jumpMultiplier * (direction > 0 ? 2 : 0.5), 1 / 8, 16);
    } else if (mode === M.SAMPLER) {
        DDJ1000.samplerBankStep(deck, direction);
    } else {
        state.page[mode] = direction > 0 ? 2 : 1;
    }
    DDJ1000.updateModeLeds(deck);
};

// SHIFT + PAGE < / >: sampler bank, in every pad mode (rekordbox).
DDJ1000.bankPrev = function (channel, control, value, status, group) {
    if (value) {
        DDJ1000.samplerBankStep(script.deckFromGroup(group), -1);
    }
};

DDJ1000.bankNext = function (channel, control, value, status, group) {
    if (value) {
        DDJ1000.samplerBankStep(script.deckFromGroup(group), 1);
    }
};

DDJ1000.samplerBankStep = function (deck, direction) {
    var state = DDJ1000.deck[deck];
    state.samplerBank = DDJ1000.clamp(state.samplerBank + direction, 0, DDJ1000.settings.samplerBanks - 1);
    var needed = (state.samplerBank + 1) * 8;
    if (DDJ1000.numSamplers() < needed) {
        engine.setValue("[App]", "num_samplers", needed);
    }
};

DDJ1000.updateModeLeds = function (deck) {
    var state = DDJ1000.deck[deck];
    if (!state) {
        return;
    }
    // Lighting a mode button tells the unit to switch to that mode, so only
    // the active mode is lit, never blinked; PAGE lights are left to the unit.
    var status = 0x90 + deck - 1;
    DDJ1000.MODE_BUTTONS.forEach(function (note, index) {
        DDJ1000.led(status, note, index === state.mode);
    });
};

DDJ1000.pad = function (channel, control, value, status) {
    var deck = DDJ1000.padDeckFromStatus(status);
    var shifted = ((status & 0x0F) - 7) & 1;
    var mode = control >> 4;
    var pad = control & 0x07;
    var state = DDJ1000.deck[deck];
    // The unit tracks PAGE itself and sends page 2 pads 8 notes higher.
    var page = (control & 0x08) ? 2 : 1;
    var M = DDJ1000.MODE;

    if (DDJ1000.settings.padPaletteTest) {
        return;
    }
    state.mode = mode;
    var pressed = state.pressed[mode] || (state.pressed[mode] = {});
    if (value) {
        pressed[pad] = true;
    } else {
        delete pressed[pad];
    }

    switch (mode) {
    case M.HOT_CUE:
        DDJ1000.padHotCue(deck, pad + 1 + (page - 1) * 8, value, shifted);
        break;
    case M.PAD_FX1:
    case M.PAD_FX2:
        DDJ1000.padFx(deck, DDJ1000.PAD_FX[mode][page - 1][pad], value);
        break;
    case M.BEAT_JUMP:
        if (value) {
            engine.setValue(DDJ1000.group(deck), "beatjump",
                DDJ1000.BEAT_JUMP_BEATS[pad] * state.jumpMultiplier);
        }
        break;
    case M.SAMPLER:
        DDJ1000.padSampler(state.samplerBank * 8 + pad + 1, value, shifted);
        break;
    case M.KEYBOARD:
        DDJ1000.padKeyboard(deck, DDJ1000.SEMITONES[page - 1][pad], pad, value, shifted);
        break;
    case M.BEAT_LOOP:
        if (value && !shifted) {
            DDJ1000.padBeatLoop(deck, DDJ1000.BEAT_LOOP_BEATS[page - 1][pad]);
        }
        break;
    case M.KEY_SHIFT:
        if (value) {
            DDJ1000.padKeyShift(deck, DDJ1000.SEMITONES[page - 1][pad]);
        }
        break;
    }
    DDJ1000.renderPads(deck);
};

DDJ1000.padHotCue = function (deck, number, value, shifted) {
    var group = DDJ1000.group(deck);
    if (shifted) {
        if (value) {
            engine.setValue(group, "hotcue_" + number + "_clear", 1);
        }
        return;
    }
    // Sets the cue (or saves the running loop) when empty, otherwise jumps;
    // held while paused it previews, like rekordbox.
    engine.setValue(group, "hotcue_" + number + "_activate", value ? 1 : 0);
    if (value) {
        DDJ1000.deck[deck].keyboardHotcue = number;
    }
};

DDJ1000.padFxUnitFor = function (deck) {
    return deck % 2 === 1 ? 3 : 4; // left decks use unit 3, right decks unit 4
};

DDJ1000.padFx = function (deck, entry, value) {
    var state = DDJ1000.deck[deck];
    var group = DDJ1000.group(deck);
    if (!entry) {
        return;
    }
    if (value) {
        state.padFxHeld = entry;
    } else if (state.padFxHeld === entry) {
        state.padFxHeld = null;
    }

    if (entry.roll !== undefined) {
        if (value) {
            DDJ1000.startRoll(deck, entry.roll, true);
        } else {
            DDJ1000.stopRoll(deck, true);
        }
        return;
    }
    if (entry.brake || entry.spinback) {
        // Slip keeps the timeline running underneath, so letting go drops
        // back in where the track would have been.
        if (value) {
            state.slipBeforePadFx = engine.getValue(group, "slip_enabled");
            engine.setValue(group, "slip_enabled", 1);
            if (entry.brake) {
                engine.brake(deck, true);
            } else {
                engine.spinback(deck, true);
            }
        } else {
            if (entry.brake) {
                engine.brake(deck, false);
            } else {
                engine.spinback(deck, false);
            }
            engine.setValue(group, "play", 1);
            engine.setValue(group, "slip_enabled", state.slipBeforePadFx);
        }
        return;
    }
    if (entry.reverse) {
        engine.setValue(group, "reverseroll", value ? 1 : 0);
        return;
    }

    var unitNumber = DDJ1000.padFxUnitFor(deck);
    var unit = "[EffectRack1_EffectUnit" + unitNumber + "]";
    if (!value) {
        engine.setValue(unit, "enabled", 0);
        return;
    }
    if (DDJ1000.padFxUnitPreset[unitNumber] !== entry.fx) {
        engine.setValue(unit, "loaded_chain_preset", entry.fx);
        DDJ1000.padFxUnitPreset[unitNumber] = entry.fx;
    }
    DDJ1000.decks.forEach(function (d) {
        engine.setValue(unit, "group_[Channel" + d + "]_enable", d === deck ? 1 : 0);
    });
    engine.setValue(unit, "mix", 1);
    engine.setValue(unit, "super1", entry.superValue !== undefined ? entry.superValue : 0.5);
    DDJ1000.applyBeats(unitNumber, entry.fx, entry.beats);
    engine.setValue(unit, "enabled", 1);
};

// SAMPLER: pad plays the slot from its start; SHIFT + pad stops it. An empty
// slot loads the track selected in the library.
DDJ1000.padSampler = function (number, value, shifted) {
    if (!value) {
        return;
    }
    if (DDJ1000.numSamplers() < number) {
        engine.setValue("[App]", "num_samplers", Math.ceil(number / 8) * 8);
    }
    var group = "[Sampler" + number + "]";
    if (shifted) {
        engine.setValue(group, "cue_gotoandstop", 1);
    } else if (engine.getValue(group, "track_loaded")) {
        engine.setValue(group, "cue_gotoandplay", 1);
    } else {
        engine.setValue(group, "LoadSelectedTrack", 1);
    }
};

// KEYBOARD: plays the chosen hot cue at a different key per pad.
// SHIFT + pad chooses the hot cue (pads 1-8 = hot cues 1-8).
DDJ1000.padKeyboard = function (deck, semitones, pad, value, shifted) {
    var group = DDJ1000.group(deck);
    var state = DDJ1000.deck[deck];
    if (shifted) {
        if (value) {
            state.keyboardHotcue = pad + 1;
        }
        return;
    }
    var cue = state.keyboardHotcue;
    if (value) {
        engine.setValue(group, "pitch_adjust", semitones);
    }
    if (engine.getValue(group, "hotcue_" + cue + "_position") >= 0) {
        engine.setValue(group, "hotcue_" + cue + "_activate", value ? 1 : 0);
    } else if (value) {
        engine.setValue(group, "cue_gotoandplay", 1);
    }
};

DDJ1000.padBeatLoop = function (deck, beats) {
    var group = DDJ1000.group(deck);
    if (engine.getValue(group, "loop_enabled")
            && Math.abs(engine.getValue(group, "beatloop_size") - beats) < 1e-6) {
        engine.setValue(group, "loop_enabled", 0);
        return;
    }
    engine.setValue(group, "beatloop_size", beats);
    engine.setValue(group, "beatloop_activate", 1);
};

DDJ1000.padKeyShift = function (deck, semitones) {
    var group = DDJ1000.group(deck);
    var current = Math.round(engine.getValue(group, "pitch_adjust"));
    engine.setValue(group, "pitch_adjust", current === semitones ? 0 : semitones);
};

// Compute pad colours and send only what changed: the mode on screen every
// tick, every mode when allModes is set (the unit keeps a colour per note).
DDJ1000.renderPads = function (deck, allModes) {
    var state = DDJ1000.deck[deck];
    if (!state || !DDJ1000.opened) {
        return;
    }
    for (var mode = 0; mode < 8; mode++) {
        if (!allModes && mode !== state.mode) {
            continue;
        }
        for (var page = 1; page <= 2; page++) {
            for (var pad = 0; pad < 8; pad++) {
                var color = DDJ1000.settings.padPaletteTest
                    ? DDJ1000.paletteBase + (deck === 2 ? 8 : 0) + pad
                    : DDJ1000.padColor(deck, mode, page, pad);
                var note = mode * 16 + (page - 1) * 8 + pad;
                DDJ1000.send(DDJ1000.padStatus(deck, false), note, color);
                DDJ1000.send(DDJ1000.padStatus(deck, true), note, color);
            }
        }
    }
};

DDJ1000.padColor = function (deck, mode, page, pad) {
    var group = DDJ1000.group(deck);
    var state = DDJ1000.deck[deck];
    var C = DDJ1000.COLOR, M = DDJ1000.MODE;
    var pressed = state.pressed[mode] && state.pressed[mode][pad];

    switch (mode) {
    case M.HOT_CUE: {
        var number = pad + 1 + (page - 1) * 8;
        var status = engine.getValue(group, "hotcue_" + number + "_status");
        if (!status) {
            return C.OFF;
        }
        var color = DDJ1000.rgbToPad(engine.getValue(group, "hotcue_" + number + "_color"));
        var isLoop = engine.getValue(group, "hotcue_" + number + "_type") === 4;
        if (isLoop && status === 2) {
            return DDJ1000.blink ? color : C.OFF; // saved loop running
        }
        return color;
    }
    case M.PAD_FX1:
    case M.PAD_FX2: {
        var fx = (mode === M.PAD_FX1 ? DDJ1000.RB.PAD_FX1 : DDJ1000.RB.PAD_FX2)[page - 1][pad];
        return pressed ? DDJ1000.pressedColor(fx) : fx;
    }
    case M.BEAT_JUMP: {
        var jump = DDJ1000.RB.BEAT_JUMP[page - 1][pad];
        return pressed ? DDJ1000.pressedColor(jump) : jump;
    }
    case M.SAMPLER: {
        var sampler = "[Sampler" + (state.samplerBank * 8 + pad + 1) + "]";
        if (!engine.getValue(sampler, "track_loaded")) {
            return DDJ1000.RB.SAMPLER_EMPTY;
        }
        if (engine.getValue(sampler, "play") || pressed) {
            return DDJ1000.pressedColor(DDJ1000.RB.SAMPLER_LOADED);
        }
        return DDJ1000.RB.SAMPLER_LOADED;
    }
    case M.KEYBOARD:
    case M.KEY_SHIFT: {
        var semitones = DDJ1000.SEMITONES[page - 1][pad];
        if (mode === M.KEYBOARD) { // not captured from rekordbox yet
            if (Math.round(engine.getValue(group, "pitch_adjust")) === semitones) {
                return C.WHITE;
            }
            return semitones === 0 ? C.YELLOW : C.PURPLE;
        }
        // Key shift as in rekordbox: dim colour per page, the selected key blinks.
        if (Math.round(engine.getValue(group, "pitch_adjust")) === semitones) {
            return DDJ1000.blink ? DDJ1000.RB.KEY_SHIFT_CENTRE : C.OFF;
        }
        return pressed ? C.OFF : DDJ1000.RB.KEY_SHIFT[page - 1];
    }
    case M.BEAT_LOOP: {
        var beats = DDJ1000.BEAT_LOOP_BEATS[page - 1][pad];
        var idle = DDJ1000.RB.BEAT_LOOP[page - 1];
        if (pressed || (engine.getValue(group, "loop_enabled")
                && Math.abs(engine.getValue(group, "beatloop_size") - beats) < 1e-6)) {
            return DDJ1000.pressedColor(idle);
        }
        return idle;
    }
    }
    return C.OFF;
};
