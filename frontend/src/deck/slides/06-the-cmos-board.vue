<template>
<div class="content">
<h2>The CMOS board</h2>
<p class="lead">The audio engine is a model of a physical circuit rather than a
synthesiser imitating one.</p>
<ul class="points">
<li><span class="mark">RING</span><span>Three 40106 Schmitt trigger oscillators, each a
capacitor charging through a resistor until the gate flips. Trimmed a few Hz apart.</span></li>
<li><span class="mark">COUPLING</span><span>Each oscillator drives an LED shining at a
light dependent resistor, and that LDR sits in the next oscillator's timing path. 1 into
2, 2 into 3, 3 into 1, closed.</span></li>
<li><span class="mark">ORGANISM</span><span>Sets how brightly each LED shines. Dim, the
three beat against each other. Bright, they snap into step and become one tone. It is
trimmed to sit just below locking.</span></li>
<li><span class="mark">PLL</span><span>A 4046 chases whichever voice the multiplexer
selects, then holds. That is the fourth voice.</span></li>
</ul>
<h3>Written out as arithmetic, not approximated</h3>
<p>The worklet at /drift is the circuit's physics: the same RC integrator against the same
Schmitt threshold, with the datasheet's hysteresis rather than a guess. Modelling it
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
