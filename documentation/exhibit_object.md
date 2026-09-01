# Exhibition object — WYSIWYG

The piece as a thing that ships: a sealed Raspberry Pi and screen playing one
recorded run of the organism. Written 2026-09-02.

## Plain English

The artwork is a circuit that a slime mould plays. The organism itself cannot
be sold or shipped, and neither can the rig it grew in, so what the buyer
receives is the instrument and one full day of the organism's activity, frozen
into a file. Plug it in and it plays that day, in real time, forever, from the
hours before the organism reached the first electrode to the hours after it was
taken out.

Nothing in the box is alive and nothing in the box needs a network.

## What ships

| | |
|---|---|
| form | sealed unit: Raspberry Pi, small screen, audio out, enclosure |
| behaviour | powers on, boots into the piece, no controls, no interaction |
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

Two flags in the kiosk launcher are load-bearing:

- `--autoplay-policy=no-user-gesture-required`. Without it the browser waits
  for a click that a sealed object will never get, and the piece is silent.
- `--check-for-update-interval=31536000`. A Chromium update prompt over the
  field is the one piece of platform infrastructure the work does not need.

## Hardware notes — verify against the actual parts

- **Audio out.** A Pi 5 has no analogue jack; audio is HDMI-only unless a USB
  or I2S DAC is added. A Pi 4 or Zero 2 W has the 3.5 mm jack. If the panel has
  no speakers, the sound needs its own path either way.
- **Screen.** Any HDMI or DSI panel. The field is a character grid and rescales
  to whatever it is given.
- **Power cycling.** The buyer will unplug it. Consider a read-only overlay
  filesystem; nothing at runtime writes to disk.
- Nothing above is confirmed against parts in hand.

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

- Sealed player: Raspberry Pi, screen, audio out. Plug in, no controls.
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
