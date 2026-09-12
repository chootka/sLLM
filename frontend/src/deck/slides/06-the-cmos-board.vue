<template>
<div class="content">
<h2>The CMOS board</h2>
<p class="lead">The audio engine is a model of a physical circuit rather than a
synthesiser imitating one.</p>
<ul class="points">
<li><span class="mark">RING</span><span>Three 40106 Schmitt trigger oscillators, each a
capacitor charging through a resistor until the gate flips, trimmed a few Hz apart. Each
one drives an LED shining at a light dependent resistor, and that LDR sits in the next
oscillator's timing path. 1 into 2, 2 into 3, 3 into 1, closed.</span></li>
<li><span class="mark">ORGANISM</span><span>Sets how brightly each LED shines. Dim, the
three beat against each other. Bright, they snap into step and become one tone. Trimmed
to sit just below locking.</span></li>
<li><span class="mark">MIXER</span><span>Three 100k resistors into one node, 10uF to
block DC. Three square waves summed, nothing active. That is the left channel.</span></li>
<li><span class="mark">MUX</span><span>A 4051 eight way switch, fed the three
oscillators, two divided copies of the first, an XOR of the first two, the electrode
signal, and one empty input.</span></li>
<li><span class="mark">PLL</span><span>A 4046 hunts until its VCO matches whatever the
multiplexer selected, then holds. That is the right channel, a fourth voice chasing one
of the others.</span></li>
<li><span class="mark">FAILURE</span><span>If the loop will not lock, the design moves
the switch and tries a different reference.</span></li>
</ul>
<h3>Written out as arithmetic, not approximated</h3>
<p>The worklet at /drift is the circuit's physics: the same RC integrator against the
same Schmitt threshold, with the datasheet's hysteresis rather than a guess. Modelling it
raised three things to check at the bench. They fall out of the component values and have
not been observed on the hardware.</p>
</div>
</template>

<script>
export default {
  name: '06_the_cmos_board',
  meta: {
    classes: 'solo',
    section: 'What was built',
    reg: 0.4, fx: 50, fy: 50
  }
}
</script>
