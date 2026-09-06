#!/bin/bash
# Install a cursor theme that contains nothing, and point cage at it.
#
# The object's panel enumerates as a mouse (QDtech MPI7003, Handlers=mouse0),
# so wlroots has a pointer device and draws a cursor for it. That cursor never
# moves -- touches arrive as touch events, not pointer motion -- so it sits
# where wlroots placed it at startup, dead centre of the screen, forever.
#
# It cannot be removed by ignoring the device, because that device is the
# touchscreen. It cannot be hidden from inside the page either: the pointer
# never enters the surface as a pointer, so the client is never asked what
# cursor to draw. And naming a theme that does not exist only makes wlroots
# fall back to a built-in image.
#
# So: a theme that does exist, whose cursor is one fully transparent pixel.
set -euo pipefail
DEST=/usr/share/icons/drift-blank/cursors
sudo mkdir -p "$DEST"
base64 -d > /tmp/drift-blank-cursor <<'B64'
WGN1chAAAAAAAAEAAQAAAAIA/f8BAAAAHAAAACQAAAACAP3/AQAAAAEAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAA=
B64
sudo cp /tmp/drift-blank-cursor "$DEST/default"
rm -f /tmp/drift-blank-cursor
# wlroots asks for these names; all of them point at the same empty image.
for n in left_ptr arrow top_left_arrow pointer text xterm hand1 hand2 grab; do
    sudo ln -sf default "$DEST/$n"
done
sudo tee /usr/share/icons/drift-blank/index.theme >/dev/null <<'THEME'
[Icon Theme]
Name=drift-blank
Comment=One transparent pixel, so the compositor has a cursor and draws nothing
Inherits=
THEME
echo "installed to $DEST"
ls -l "$DEST"
