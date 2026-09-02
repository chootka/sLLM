# Exhibition object — WYSIWYG

The piece as a thing that ships: a sealed Raspberry Pi and touch screen
playing one recorded run of the organism. Written 2026-09-02, touch panel and
hardware settled 2026-09-01.

## Plain English

The artwork is a circuit that a slime mould plays. The organism itself cannot
be sold or shipped, and neither can the rig it grew in, so what the buyer
receives is the instrument and one full day of the organism's activity, frozen
into a file. Plug it in and it plays that day, in real time, forever, from the
hours before the organism reached the first electrode to the hours after it was
taken out.

The screen is a touch panel, and it has exactly two things on it to touch:
one starts the sound, one opens a plain-language note about what is being
heard. Nothing else responds to a touch.

Nothing in the box is alive and nothing in the box needs a network.

## What ships

| | |
|---|---|
| form | sealed unit: Raspberry Pi 4, touch panel, DAC to stereo out, enclosure |
| behaviour | powers on, boots into the piece. Two touch targets, nothing else |
| touch | `SOUND ON/OFF` top right, `SOUND LOG` top left. 56 px minimum targets |
| content | `exhibit/object/` -- page, audio worklet, recording, static server |
| size on disk | 2.1 MB |
| network | none required at any point |
| writes | none at runtime |

## The recording that ships

Run 8, exported by `scripts/export_replay.py` from the electrode CSVs. The
signal chain runs once at export time; the object replays the result.

| | |
|---|---|
| window | 2026-08-27 23:08:34 to 2026-08-29 03:00, 27.9 h |
| loop | real time, one pass per 27.9 h |
| organism | inoculated 2026-08-27 21:47, removed 2026-08-29 00:00 |
| ch0 | connects 02:08:46, holds to 00:56:25 -- 81.8% of the loop |
| ch1 | connects 02:28:58, six runs with gaps -- 63.0% of the loop |
| ch2 | never connected -- silent for the whole loop |
| file | `exhibit/replay.json`, 1.6 MB, signal per second, gate as index runs, period per minute |

What a viewer hears across one pass: three uncoupled notes for the first two
hours, a yellow bloom and the first voice starting to pull as ch0 connects,
twenty hours of the two-minute rhythm with the second voice cutting in and out,
then the drives falling away after the organism is removed and the notes going
still for the last two hours.

## Touch

The object has no pointer, no keyboard and no one to help a visitor who gets
lost, so the page behaves differently when it is running as the object than it
does on the website. `Drift.vue` decides which it is from the presence of the
bundled recording -- the thing that is actually true about the object -- rather
than from a flag on the kiosk URL that could be left off. `?kiosk=1` forces
that behaviour on a laptop for previewing.

| | website | object |
|---|---|---|
| tap the field | toggles fullscreen | does nothing |
| back to the dashboard | present | not rendered |
| cursor | arrow | hidden |
| target size | 27 px | 56 px minimum, larger type |

Three of those are load-bearing:

- **A tap on the field must not toggle fullscreen.** Under kiosk the object is
  already fullscreen, so the only thing a stray tap could do is take it *out*,
  and nothing in the box could put it back.
- **The dashboard link has to go.** There is no API behind it on the object, so
  a tap in the corner would strand a visitor on a broken page with no route
  home.
- **Targets are sized for a finger.** The web sizes are 27 px tall and rely on
  `:hover`, which never fires on glass. The touch sizes are keyed to
  `@media (pointer: coarse)`, so they follow the input device rather than
  object mode, and `:active` gives the only feedback a finger gets that the tap
  landed.

The field also sets `touch-action: manipulation` and suppresses text selection,
the long-press callout and the tap highlight. Without those a finger gets
double-tap zoom, a selection drag across the field, and a context menu, none of
which a sealed object can recover from.

**The object boots silent, by design.** Sound starts on the first touch of
`SOUND ON`, not at power-on. Two consequences to weigh before a show: a visitor
who turns the sound off leaves it off for the next person, and an untouched
object reads as a still image rather than a piece with sound. If either matters
at a given venue, the fixes are an autostart on load and an idle timer that
restores sound and closes the log. Neither is built.

## Build

    ./scripts/py scripts/export_replay.py \
        --start '2026-08-27 23:08:34' --end '2026-08-29 03:00:00' \
        --out exhibit/replay.json --note '...'
    ./exhibit/build.sh                      # -> exhibit/object/
    python3 exhibit/object/serve.py 8080    # test at /drift

`replay.json` is checked for shape, not for status code, so a server that
answers every path with `index.html` cannot fool the page into thinking it has
a recording. With no `replay.json` present the same build runs live against the
API, which is what `sllm.visceral.systems/drift` does.

## On the object

1. Copy `exhibit/object/` to `/home/chootka/drift` on the Pi.
2. `exhibit/drift-server.service` to `/etc/systemd/system/`, enable and start.
3. `exhibit/drift-kiosk.desktop` to `~/.config/autostart/`.
4. Autologin to desktop, screen blanking off (`sudo raspi-config nonint do_blanking 1`).
5. Make the DAC the default ALSA output and prove it before sealing: `aplay -l`
   to find the card, set it in `/etc/asound.conf`, then `speaker-test -c2
   -twav` to hear both channels come out of the actual speakers.
6. Touch the two buttons on the assembled object before it ships. Everything
   above can be right while the panel is still delivering no touch events.

Every flag in `drift-kiosk.desktop` is there for a reason, and the reasons are
written in the file itself. The four that will cost a show if they are dropped:

- `--autoplay-policy=no-user-gesture-required`. The visitor's touch on
  `SOUND ON` is a real gesture, so this is belt and braces rather than the only
  thing holding the sound up -- but Chromium can still refuse a first
  AudioContext on a page it thinks has had no genuine interaction, and the
  failure mode is a piece that looks fine and makes no sound.
- `--disable-session-crashed-bubble` and `--restore-last-session=false`. The
  buyer unplugs it; without these the next boot puts a "Chromium didn't shut
  down correctly" bar across the top of the artwork, and there is no keyboard
  in the box to dismiss it.
- `--disable-pinch` and `--overscroll-history-navigation=0`. A two-finger
  stray zooms the field, and a horizontal swipe navigates the page away.
- `--check-for-update-interval=31536000`. A Chromium update prompt over the
  field is the one piece of platform infrastructure the work does not need.

## Hardware

Settled 2026-09-01: **Raspberry Pi 4, touch panel, DAC for audio out.** Still
to be confirmed against the parts once they are in hand.

- **Audio out.** The DAC decides this, not the Pi. A Pi 4 does have the 3.5 mm
  jack, but the DAC is the better path and it has to be made the *default*
  ALSA device -- Chromium plays to whatever ALSA hands it, so a DAC that is
  present but not default is a silent object with no error anywhere to explain
  it.
- **Screen.** Any HDMI or DSI touch panel. The field is a character grid and
  rescales to whatever it is given. Confirm the panel reports as a touch device
  to Chromium; `--touch-events=enabled` in the launcher forces it on for the
  case where the panel enumerates after the browser starts.
- **Power cycling.** The buyer will unplug it. The launcher now suppresses the
  "Chromium didn't shut down correctly" restore bar, which would otherwise sit
  across the top of the artwork with no keyboard to dismiss it. A read-only
  overlay filesystem is still worth doing; nothing at runtime writes to disk.
- **Stereo, not mono.** The three oscillator voices come out of the left
  channel and the PLL out of the right. Measured on the built object: left peak
  0.25, right 0.04. The sound log describes that split to the viewer in so many
  words, so a mono DAC or a single speaker makes the piece contradict its own
  wall text.

## Playback

Real time by default. `?speed=` on the kiosk URL timelapses the same file
without a rebuild: `?speed=24` plays the 27.9 h in 70 minutes. The panel's
first line states which of the two is running.

## Not in the box

No organism, no agar, no electrodes, no rig. The work is the instrument and the
record. The organism this record came from was removed from the dish on
2026-08-29 and is not part of the sale.

## Draft listing

**Title.** drift — a slime mould plays a CMOS circuit (sealed player, 27.9 h loop)

**Spec.**

- Sealed player: Raspberry Pi, touch screen, stereo audio out. Plug in and it
  runs. Two things to touch: one starts the sound, one explains what you are
  hearing.
- Plays one continuous 27.9 h recording of *Physarum polycephalum* on a loop, in real time.
- Sound and image are generated live from that recording by a software model of
  a CMOS oscillator circuit, not video playback.
- No network, no account, no app, no writes. It runs the same in fifty years as
  it does now, given power.

**Description.** Three metal electrodes sit in agar in a covered dish. A slime
mould is placed on a fourth and grows outward. When it reaches an electrode, a
voltage appears there that rises and falls about every two minutes. This was
recorded once a second for a day and a night, from before the organism arrived
at the first electrode to after it was taken out.

Those measurements drive three oscillators wired in a circle, each leaning on
the next. Pushed hard they collapse into one note; released they slide apart
and beat. The picture is the same three oscillators drawn as interference
rings. It is not a rendering of the data; it is the data pushing a circuit
around.

The recording is dated and specific: the organism reached the first electrode
at 02:08:46 on 2026-08-28. The loop contains that moment, the day of rhythm
that followed, and the silence after removal.
