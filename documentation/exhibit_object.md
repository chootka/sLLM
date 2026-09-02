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
| size on disk | 764 KB |
| network | none required at any point |
| writes | none at runtime |

## The recording that ships

Run 8, exported by `scripts/export_replay.py` from the electrode CSVs. The
signal chain runs once at export time; the object replays the result.

| | |
|---|---|
| window | 2026-08-28 06:00:00 to 09:00:00 CEST, 3.0 h |
| loop | 15 minutes, one pass, at `?speed=12` |
| organism | in the dish throughout; inoculated 2026-08-27 21:47, removed 2026-08-29 00:00 |
| ch0 | connected for 100% of the loop |
| ch1 | connected for 62.6% of the loop, cutting in and out |
| ch2 | never connected -- silent for the whole loop |
| file | `exhibit/replay.json`, 171 KB, signal per second, gate as index runs, period per minute |

This is the middle of run 8 rather than the whole of it: the organism is
already on both electrodes when the loop starts and still there when it ends,
so there is no arrival and no removal in the window. What a viewer hears is
three hours of the two-minute rhythm at its most sustained -- the first voice
pushed the whole time, the second cutting in and out as its tube comes and
goes, the third silent -- compressed into fifteen minutes.

The earlier 27.9 h real-time export, which does contain the arrival at
02:08:46 and the silence after removal, is in git history at c6c9ed2 and can be
regenerated with the build command below using
`--start '2026-08-27 23:08:34' --end '2026-08-29 03:00:00'`.

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
        --start '2026-08-28 06:00:00' --end '2026-08-28 09:00:00' \
        --out exhibit/replay.json --note '...'
    ./exhibit/build.sh                      # -> exhibit/object/
    python3 exhibit/object/serve.py 8080    # test at /drift

`replay.json` is checked for shape, not for status code, so a server that
answers every path with `index.html` cannot fool the page into thinking it has
a recording. With no `replay.json` present the same build runs live against the
API, which is what `sllm.visceral.systems/drift` does.

## On the object

1. Copy `exhibit/object/` to `/home/chootka/drift` on the Pi.
2. Both units to `/etc/systemd/system/`, then enable:

        sudo cp exhibit/drift-server.service exhibit/drift-kiosk.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable --now seatd drift-server drift-kiosk

3. Screen blanking off (`sudo raspi-config nonint do_blanking 1`), and set the
   timezone (`sudo timedatectl set-timezone Europe/Berlin`) -- the panel prints
   the recording's date in the object's own timezone.
4. Check it survives a power cut, which is the thing a buyer will actually do:
   `sudo reboot`, and the piece should come back on its own with sound
   available on the first touch.
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

## Raspberry Pi OS Lite

The object runs Lite, which ships no browser, no display server and no audio.
Three packages cover it:

    sudo apt install -y chromium cage seatd pipewire pipewire-pulse wireplumber
    sudo systemctl enable --now seatd
    sudo usermod -aG _seatd,video,input,render chootka   # then log out and in

`cage` is a kiosk Wayland compositor: it runs one fullscreen app straight from
a TTY with no desktop behind it. `seatd` is what lets it take a seat when the
session is not on the physical console -- without it cage fails with
"Could not open target tty: Permission denied", and the `_seatd` group does not
exist until the package is installed.

Trixie calls the browser `chromium`, not `chromium-browser`. Running it by
hand, to check before enabling autostart:

    python3 ~/sLLM/exhibit/object/serve.py 8080 &
    cage -- chromium --kiosk --autoplay-policy=no-user-gesture-required \
        'http://127.0.0.1:8080/drift?speed=12'

Autostart is `exhibit/drift-kiosk.service`, which replaced the old
`drift-kiosk.desktop` -- Lite has no desktop session and no `~/.config/autostart`
to put a .desktop file in. It runs cage on tty1 through a real login session,
which is what lets it take seat0.

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

`?speed=` on the kiosk URL timelapses the file without a rebuild, and the
shipped kiosk URL carries `?speed=12`, which plays the 3 h window in 15
minutes. Drop the parameter and the same file plays in real time over three
hours. The panel's first line states which is running.

The date on that line is rendered in the *viewer's* timezone, so it reads
"August 28" on a Pi set to CEST and "August 27" on a machine in the Americas.
Set the object's timezone before it ships.

**`speed` does not mean the same thing on the website as it does here**, and
the two differ by a factor of five for this window. `advance()` steps `speed`
*array indices* per second, and the arrays are built differently:

| | array | one index is | `speed=12` gives |
|---|---|---|---|
| website | `buckets = min(2000, span)` from the API | 5.4 s of record, for a 3 h window | ~65x real time, a pass every 2.8 min |
| object | `replay.json`, 1 Hz | 1 s of record, always | a true 12x, a pass every 15 min |

So a `speed` that sounded right on `sllm.visceral.systems/drift` is not the
same tempo once the window is frozen, and the object's is the honest one --
the label's "15 minutes" is true here and wrong on the website, where the
bucketing is not accounted for. 12 was chosen on the object after hearing both.

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

The recording is dated and specific: three hours of one morning, 06:00 to
09:00 on 2026-08-28, with the organism on two of the three electrodes
throughout. Fifteen minutes of playing time, then it begins again.
