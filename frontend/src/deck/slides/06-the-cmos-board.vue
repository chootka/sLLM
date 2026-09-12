<template>
<div class="content">
<h2>The CMOS board</h2>
<p class="lead">The audio engine is a model of a physical circuit.</p>
<ul class="points">
<li><span class="mark">RING</span><span>Three 40106 Schmitt trigger oscillators at
roughly 200, 204 and 209 Hz. Each output drives a vactrol LED whose LDR sits in the next
oscillator's timing node. 3 into 1, 1 into 2, 2 into 3.</span></li>
<li><span class="mark">DRIVE</span><span>An MCP4728 DAC, over I2C from the Pi, sets each
vactrol's LED current through a 2N3904. Low, the three beat. High, they lock.</span></li>
<li><span class="mark">MIXER</span><span>Three 100k resistors into one node, 10&micro; to
block the Vdd/2 offset, 10k and 10n to round the edges.</span></li>
<li><span class="mark">MUX</span><span>A 4051 fed the three oscillators, &divide;2 and
&divide;4 copies, an XOR of the first two, the electrode signal, and one empty
input.</span></li>
<li><span class="mark">PLL</span><span>A 4046 hunts until its VCO matches the selected
reference, then holds. VCO on one channel, phase error on the other.</span></li>
<li><span class="mark">FAILURE</span><span>Unlocked, phase pulses free run a spare 40106,
which clocks a 4040 and re-points the mux. Lock clamps it silent.</span></li>
</ul>
<p>The worklet at /drift is the same RC integrator against the same Schmitt threshold,
with the datasheet's hysteresis.</p>
</div>
<figure class="media">
<img src="/deck-media/cmos-breadboard.jpg" alt="The CMOS circuit on a breadboard: chips, trimmers, vactrols and jumper wires">
</figure>
</template>

<script>
export default {
  name: '06_the_cmos_board',
  meta: {
    classes: 'split content-wide',
    section: 'What was built',
    reg: 0.4, fx: 50, fy: 50
  }
}
</script>
