"""Generate a test track for decoding the DDJ-1000 jog waveform: 120 s of tones in 6 s segments with known
amplitude and frequency, so each of the 600 waveform columns (0.2 s each) can be matched to a known signal.

usage: python make_test_tracks.py [outdir=../testtracks]
Writes wavetest-120s.wav (44.1 kHz, 16 bit, stereo) and wavetest-120s.txt (segment table).
"""
import array, math, os, random, sys, wave

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testtracks')
os.makedirs(out, exist_ok=True)
RATE, SEG = 44100, 6.0

# (label, [(frequency Hz, amplitude 0..1), ...])  -  'noise' = white noise
segments = [
    ('silence', []),
    ('60 Hz a=0.25', [(60, 0.25)]), ('60 Hz a=0.5', [(60, 0.5)]), ('60 Hz a=1.0', [(60, 1.0)]),
    ('1 kHz a=0.25', [(1000, 0.25)]), ('1 kHz a=0.5', [(1000, 0.5)]), ('1 kHz a=1.0', [(1000, 1.0)]),
    ('8 kHz a=0.25', [(8000, 0.25)]), ('8 kHz a=0.5', [(8000, 0.5)]), ('8 kHz a=1.0', [(8000, 1.0)]),
    ('60+1k+8k each 0.33', [(60, 0.33), (1000, 0.33), (8000, 0.33)]),
    ('60+8k each 0.5', [(60, 0.5), (8000, 0.5)]),
    ('noise a=0.5', 'noise'), ('noise a=1.0', 'noise'),
    ('200 Hz a=0.5', [(200, 0.5)]), ('400 Hz a=0.5', [(400, 0.5)]),
    ('2 kHz a=0.5', [(2000, 0.5)]), ('4 kHz a=0.5', [(4000, 0.5)]),
    ('1 kHz a=0.1', [(1000, 0.1)]), ('silence', []),
]
total = len(segments) * SEG
random.seed(1)
samples = array.array('h')
table = []
for k, (label, parts) in enumerate(segments):
    start = k * SEG
    table.append('%6.1f-%6.1f s  columns %3d-%3d  %s' % (start, start + SEG, round(start / 0.2), round((start + SEG) / 0.2) - 1, label))
    n = int(SEG * RATE)
    for i in range(n):
        t = i / RATE
        if parts == 'noise':
            amp = 0.5 if 'a=0.5' in label else 1.0
            v = amp * (random.random() * 2 - 1)
        else:
            v = sum(a * math.sin(2 * math.pi * f * t) for f, a in parts)
        # 20 ms fade in/out so segment edges do not click
        edge = min(i, n - 1 - i) / (0.02 * RATE)
        v *= min(1.0, edge)
        s = int(max(-1, min(1, v)) * 30000)
        samples.append(s)
        samples.append(s)

path = os.path.join(out, 'wavetest-120s.wav')
with wave.open(path, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE)
    w.writeframes(samples.tobytes())
open(os.path.join(out, 'wavetest-120s.txt'), 'w').write('\n'.join(table) + '\n')
print('wrote', path, '(%.0f s)' % total)
print('\n'.join(table))
