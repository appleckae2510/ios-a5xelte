# A3 framebuffer Phase A test, native v0.20 baseline

This is a SOURCE diagnostic, not a proof of working iOS UI.

Build: patches/native/0414 is appended after 0413 in tools/a3-native-sources.py.
Enable ONLY for controlled BOOT tests with: sweetfb_testpat=1 sweetfb_noconsole=1
and console log retained. When the first userland swap is presented, draw
eight bars directly through the physical framebuffer mapping, with column
ticks every 64 pixels and horizontal centerline. Skip subsequent surface
presents. No changes to USERDATA, driver registers, or panel scanout.

IMPORTANT: This diagnostic *hides all actual iOS artwork*. A correct pattern
means only that direct writes with fWidth/fHeight/fRowBytes look correct.
It neither fixes the two logos nor proves the renderer, SpringBoard, or
the locationd/dmd/ScreenTimeAgent crashes are fixed.
The graphically correct second step is to inspect s->width, s->height,
s->bytesPerRow, src/dst rects and pixelFormat; target dimensions are
720x1280, physical stride is normally 2880 bytes. 0061's iPhone-X logical
canvas is a centered crop rather than a true scaler.

For comparison run a matching native kernel without testpat on the same
unchanged USERDATA, preserve log/console, and restore v0.20 BOOT for rollback.
Flash BOOT only after independent full BOOT/USERDATA backups.
