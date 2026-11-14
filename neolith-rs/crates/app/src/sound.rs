//! The one sound the app makes: Grug landing on the start screen. It is
//! synthesised (a sine falling from 120 to 40 Hz plus a short burst of
//! low-passed noise), so there is no audio file to ship or credit.

/// Gets the audio output ready, so the first thud isn't late.
pub fn warm() {
    imp::warm();
}

/// A thud at `volume` (0 to 1). Silent if there is no audio output, or, on
/// the web, if the browser is still blocking sound because the visitor has
/// not yet clicked or pressed a key.
pub fn thud(volume: f32) {
    imp::thud(volume.clamp(0.0, 1.0));
}

#[cfg(not(target_arch = "wasm32"))]
mod imp {
    use std::cell::RefCell;
    use std::num::NonZero;

    use rodio::buffer::SamplesBuffer;
    use rodio::{DeviceSinkBuilder, MixerDeviceSink};

    const RATE: u32 = 44_100;

    thread_local! {
        /// The open output device; `Some(None)` once opening it has failed.
        static SINK: RefCell<Option<Option<MixerDeviceSink>>> = const { RefCell::new(None) };
    }

    fn with_sink(f: impl FnOnce(&MixerDeviceSink)) {
        SINK.with_borrow_mut(|s| {
            let sink = s.get_or_insert_with(|| {
                let mut sink = DeviceSinkBuilder::open_default_sink().ok()?;
                sink.log_on_drop(false);
                Some(sink)
            });
            if let Some(sink) = sink {
                f(sink);
            }
        });
    }

    pub fn warm() {
        with_sink(|_| {});
    }

    pub fn thud(volume: f32) {
        with_sink(|sink| {
            let rate = NonZero::new(RATE).expect("non-zero");
            let mono = NonZero::new(1).expect("non-zero");
            sink.mixer().add(SamplesBuffer::new(mono, rate, samples(volume)));
        });
    }

    pub fn samples(volume: f32) -> Vec<f32> {
        let n = (RATE as f32 * 0.45) as usize;
        let (mut phase, mut low, mut seed) = (0.0f32, 0.0f32, 0x2545_f491u32);
        (0..n)
            .map(|i| {
                let t = i as f32 / RATE as f32;
                // Pitch falls from 120 Hz towards 40 Hz.
                let hz = 40.0 + 80.0 * (-t * 22.0).exp();
                phase += std::f32::consts::TAU * hz / RATE as f32;
                let body = phase.sin() * (-t * 11.0).exp();
                // Noise through a one-pole low-pass: the slap of the landing.
                seed = seed.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                let white = (seed >> 8) as f32 / (1u32 << 23) as f32 - 1.0;
                low += 0.08 * (white - low);
                let slap = low * 2.5 * (-t * 45.0).exp();
                // A 2 ms fade-in so the start doesn't click.
                let attack = (t / 0.002).min(1.0);
                (0.9 * body + 0.6 * slap).clamp(-1.0, 1.0) * attack * volume
            })
            .collect()
    }
}

#[cfg(target_arch = "wasm32")]
mod imp {
    use wasm_bindgen::prelude::*;

    #[wasm_bindgen(inline_js = r#"
let ctx = null;
function audio() {
  if (!ctx) {
    const C = window.AudioContext || window.webkitAudioContext;
    if (!C) return null;
    ctx = new C();
  }
  return ctx;
}
let listening = false;
// Browsers keep audio suspended until the visitor clicks or presses a key:
// resume on the first such event so later thuds play.
export function neolith_sound_warm() {
  if (listening) return;
  listening = true;
  const unlock = () => { try { const c = audio(); if (c && c.state !== "running") c.resume(); } catch (e) {} };
  for (const ev of ["pointerdown", "keydown", "touchend"]) window.addEventListener(ev, unlock, { capture: true });
}
export function neolith_sound_thud(volume) {
  try {
    const c = audio();
    if (!c || c.state !== "running") return;
    const t = c.currentTime;
    const out = c.createGain();
    out.gain.value = volume;
    out.connect(c.destination);

    const osc = c.createOscillator();
    osc.type = "sine";
    osc.frequency.setValueAtTime(120, t);
    osc.frequency.exponentialRampToValueAtTime(40, t + 0.18);
    const body = c.createGain();
    body.gain.setValueAtTime(0.0001, t);
    body.gain.exponentialRampToValueAtTime(0.9, t + 0.004);
    body.gain.exponentialRampToValueAtTime(0.001, t + 0.45);
    osc.connect(body).connect(out);
    osc.start(t);
    osc.stop(t + 0.5);

    const n = Math.floor(c.sampleRate * 0.12);
    const buf = c.createBuffer(1, n, c.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.exp(-i / (c.sampleRate * 0.022));
    const noise = c.createBufferSource();
    noise.buffer = buf;
    const lp = c.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 600;
    const slap = c.createGain();
    slap.gain.value = 0.7;
    noise.connect(lp).connect(slap).connect(out);
    noise.start(t);
  } catch (e) {}
}
"#)]
    extern "C" {
        fn neolith_sound_warm();
        fn neolith_sound_thud(volume: f32);
    }

    pub fn warm() {
        neolith_sound_warm();
    }

    pub fn thud(volume: f32) {
        neolith_sound_thud(volume);
    }
}

#[cfg(all(test, not(target_arch = "wasm32")))]
mod tests {
    #[test]
    fn thud_is_short_audible_and_ends_quiet() {
        let s = super::imp::samples(1.0);
        assert!(s.len() < 44_100 / 2);
        assert!(s.iter().all(|v| v.abs() <= 1.0));
        assert!(s.iter().any(|v| v.abs() > 0.5));
        assert!(s[s.len() - 200..].iter().all(|v| v.abs() < 0.02));
    }
}
