<template>
<h2>The schematic</h2>
<div class="chart schematic"><svg viewBox="0 0 1500 1250" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif" stroke-linecap="round">
<defs>
  <g id="rh" stroke="#111" stroke-width="1.6" fill="none">
    <path d="M0 0 h6 l5 -9 l9 18 l9 -18 l9 18 l9 -18 l4.5 9 h8.5"/>
  </g>
  <g id="gnd" stroke="#111" stroke-width="1.6" fill="none">
    <path d="M0 0 v6 M-11 6 h22 M-6.5 11.5 h13 M-2 17 h4"/>
  </g>
</defs>

<!-- ================= analog domain box ================= -->
<rect x="236" y="96" width="716" height="672" fill="none" stroke="#999" stroke-width="1.2" stroke-dasharray="7 5"/>
<text x="246" y="114" font-size="12" fill="#555" font-style="italic">3V3 analog domain — keep clear of 5V / LED wiring</text>

<!-- ================= Raspberry Pi ================= -->
<rect x="50" y="320" width="160" height="420" rx="8" fill="none" stroke="#111" stroke-width="2"/>
<text x="130" y="348" font-size="14" font-weight="600" text-anchor="middle">Raspberry Pi 5</text>
<text x="130" y="364" font-size="10.5" text-anchor="middle" fill="#333">40-pin header</text>

<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="210" y1="390" x2="240" y2="390"/>
  <line x1="210" y1="420" x2="240" y2="420"/>
  <line x1="210" y1="450" x2="240" y2="450"/>
  <line x1="210" y1="480" x2="228" y2="480"/>
  <line x1="210" y1="530" x2="240" y2="530"/>
  <line x1="210" y1="560" x2="240" y2="560"/>
  <line x1="210" y1="590" x2="240" y2="590"/>
</g>
<use href="#gnd" x="228" y="480"/>
<g font-size="10.5" fill="#111">
  <text x="216" y="384">pin 1</text><text x="246" y="394" font-weight="600" font-style="italic">3V3</text>
  <text x="216" y="414">pin 3</text><text x="246" y="424" font-weight="600" font-style="italic">SDA</text>
  <text x="216" y="444">pin 5</text><text x="246" y="454" font-weight="600" font-style="italic">SCL</text>
  <text x="216" y="474">pin 6 GND</text>
  <text x="216" y="524">pin 12</text><text x="246" y="534" font-weight="600" font-style="italic">GPIO18</text>
  <text x="216" y="554">pin 16</text><text x="246" y="564" font-weight="600" font-style="italic">GPIO23</text>
  <text x="216" y="584">pin 32</text><text x="246" y="594" font-weight="600" font-style="italic">GPIO12</text>
</g>
<text x="60" y="716" font-size="10.5" fill="#111">cam0 (CSI ribbon) &rarr;</text>
<text x="60" y="730" font-size="10.5" fill="#111">Pi NoIR v3 camera (850 nm illum.)</text>

<!-- ================= VBIAS divider ================= -->
<text x="292" y="146" font-size="11" font-weight="600" font-style="italic" text-anchor="middle">3V3</text>
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="292" y1="150" x2="292" y2="162"/>
</g>
<use href="#rh" transform="translate(292,162) rotate(90)"/>
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="292" y1="222" x2="292" y2="252"/>
  <line x1="292" y1="236" x2="346" y2="236"/>
</g>
<circle cx="292" cy="236" r="2.8" fill="#111"/>
<text x="352" y="240" font-size="11" font-weight="600" font-style="italic">VBIAS &asymp; 1.65 V</text>
<use href="#rh" transform="translate(292,252) rotate(90)"/>
<g stroke="#111" stroke-width="1.6" fill="none"><line x1="292" y1="312" x2="292" y2="322"/></g>
<use href="#gnd" x="292" y="322"/>
<text x="304" y="192" font-size="10.5">10k</text>
<text x="304" y="282" font-size="10.5">10k</text>
<!-- 10u cap -->
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="292" y1="236" x2="258" y2="236"/>
  <line x1="258" y1="236" x2="258" y2="252"/>
  <line x1="246" y1="252" x2="270" y2="252"/>
  <line x1="246" y1="260" x2="270" y2="260"/>
  <line x1="258" y1="260" x2="258" y2="274"/>
</g>
<use href="#gnd" x="258" y="274"/>
<text x="238" y="248" font-size="10.5" text-anchor="end">10&micro;</text>
<text x="640" y="130" font-size="11.5" fill="#111">MCP604: pin 4 VDD &rarr; 3V3 (+100n) &middot; pin 11 VSS &rarr; GND</text>

<!-- ================= buffer channels ================= -->
<!-- channel template at y: 330 E1/A0, 440 E2/A1, 550 E3/A2, 660 REF/A3 -->
<g id="channels">
  <!-- ===== Channel A : E1 ===== -->
  <circle cx="316" cy="330" r="4" fill="none" stroke="#111" stroke-width="1.6"/>
  <text x="306" y="334" font-size="11" text-anchor="end" font-weight="600">E1</text>
  <g stroke="#111" stroke-width="1.6" fill="none">
    <line x1="320" y1="330" x2="374" y2="330"/>
    <line x1="374" y1="330" x2="374" y2="302"/>
    <line x1="374" y1="242" x2="374" y2="232"/>
    <line x1="374" y1="330" x2="402" y2="330"/>
    <line x1="402" y1="330" x2="402" y2="318"/>
    <line x1="402" y1="318" x2="418" y2="318"/>
    <polygon points="418,306 418,354 474,330"/>
    <line x1="474" y1="330" x2="500" y2="330"/>
    <line x1="490" y1="330" x2="490" y2="366"/>
    <line x1="490" y1="366" x2="404" y2="366"/>
    <line x1="404" y1="366" x2="404" y2="342"/>
    <line x1="404" y1="342" x2="418" y2="342"/>
    <line x1="560" y1="330" x2="600" y2="330"/>
    <line x1="600" y1="330" x2="600" y2="344"/>
    <line x1="588" y1="344" x2="612" y2="344"/>
    <line x1="588" y1="352" x2="612" y2="352"/>
    <line x1="600" y1="352" x2="600" y2="362"/>
    <line x1="600" y1="330" x2="756" y2="330"/>
  </g>
  <use href="#rh" transform="translate(374,242) rotate(90)"/>
  <text x="374" y="228" font-size="10.5" font-weight="600" font-style="italic" text-anchor="middle">VBIAS</text>
  <text x="386" y="276" font-size="10.5">10M</text>
  <use href="#rh" transform="translate(500,330)"/>
  <text x="518" y="320" font-size="10.5">10k</text>
  <circle cx="374" cy="330" r="2.8" fill="#111"/>
  <circle cx="490" cy="330" r="2.8" fill="#111"/>
  <circle cx="600" cy="330" r="2.8" fill="#111"/>
  <use href="#gnd" x="600" y="362"/>
  <text x="618" y="352" font-size="10.5">100n</text>
  <text x="424" y="316" font-size="11">+</text>
  <text x="424" y="348" font-size="12">&minus;</text>
  <text x="438" y="300" font-size="9.5" fill="#333">&frac14; MCP604</text>

  <!-- ===== Channel B : E2 ===== -->
  <circle cx="316" cy="440" r="4" fill="none" stroke="#111" stroke-width="1.6"/>
  <text x="306" y="444" font-size="11" text-anchor="end" font-weight="600">E2</text>
  <g stroke="#111" stroke-width="1.6" fill="none">
    <line x1="320" y1="440" x2="374" y2="440"/>
    <line x1="374" y1="440" x2="374" y2="412"/>
    <line x1="374" y1="352" x2="374" y2="342"/>
    <line x1="374" y1="440" x2="402" y2="440"/>
    <line x1="402" y1="440" x2="402" y2="428"/>
    <line x1="402" y1="428" x2="418" y2="428"/>
    <polygon points="418,416 418,464 474,440"/>
    <line x1="474" y1="440" x2="500" y2="440"/>
    <line x1="490" y1="440" x2="490" y2="476"/>
    <line x1="490" y1="476" x2="404" y2="476"/>
    <line x1="404" y1="476" x2="404" y2="452"/>
    <line x1="404" y1="452" x2="418" y2="452"/>
    <line x1="560" y1="440" x2="600" y2="440"/>
    <line x1="600" y1="440" x2="600" y2="454"/>
    <line x1="588" y1="454" x2="612" y2="454"/>
    <line x1="588" y1="462" x2="612" y2="462"/>
    <line x1="600" y1="462" x2="600" y2="472"/>
    <line x1="600" y1="440" x2="756" y2="440"/>
  </g>
  <use href="#rh" transform="translate(374,352) rotate(90)"/>
  <text x="374" y="338" font-size="10.5" font-weight="600" font-style="italic" text-anchor="middle">VBIAS</text>
  <text x="386" y="386" font-size="10.5">10M</text>
  <use href="#rh" transform="translate(500,440)"/>
  <text x="518" y="430" font-size="10.5">10k</text>
  <circle cx="374" cy="440" r="2.8" fill="#111"/>
  <circle cx="490" cy="440" r="2.8" fill="#111"/>
  <circle cx="600" cy="440" r="2.8" fill="#111"/>
  <use href="#gnd" x="600" y="472"/>
  <text x="618" y="462" font-size="10.5">100n</text>
  <text x="424" y="426" font-size="11">+</text>
  <text x="424" y="458" font-size="12">&minus;</text>

  <!-- ===== Channel C : E3 ===== -->
  <circle cx="316" cy="550" r="4" fill="none" stroke="#111" stroke-width="1.6"/>
  <text x="306" y="554" font-size="11" text-anchor="end" font-weight="600">E3</text>
  <g stroke="#111" stroke-width="1.6" fill="none">
    <line x1="320" y1="550" x2="374" y2="550"/>
    <line x1="374" y1="550" x2="374" y2="522"/>
    <line x1="374" y1="462" x2="374" y2="452"/>
    <line x1="374" y1="550" x2="402" y2="550"/>
    <line x1="402" y1="550" x2="402" y2="538"/>
    <line x1="402" y1="538" x2="418" y2="538"/>
    <polygon points="418,526 418,574 474,550"/>
    <line x1="474" y1="550" x2="500" y2="550"/>
    <line x1="490" y1="550" x2="490" y2="586"/>
    <line x1="490" y1="586" x2="404" y2="586"/>
    <line x1="404" y1="586" x2="404" y2="562"/>
    <line x1="404" y1="562" x2="418" y2="562"/>
    <line x1="560" y1="550" x2="600" y2="550"/>
    <line x1="600" y1="550" x2="600" y2="564"/>
    <line x1="588" y1="564" x2="612" y2="564"/>
    <line x1="588" y1="572" x2="612" y2="572"/>
    <line x1="600" y1="572" x2="600" y2="582"/>
    <line x1="600" y1="550" x2="756" y2="550"/>
  </g>
  <use href="#rh" transform="translate(374,462) rotate(90)"/>
  <text x="374" y="448" font-size="10.5" font-weight="600" font-style="italic" text-anchor="middle">VBIAS</text>
  <text x="386" y="496" font-size="10.5">10M</text>
  <use href="#rh" transform="translate(500,550)"/>
  <text x="518" y="540" font-size="10.5">10k</text>
  <circle cx="374" cy="550" r="2.8" fill="#111"/>
  <circle cx="490" cy="550" r="2.8" fill="#111"/>
  <circle cx="600" cy="550" r="2.8" fill="#111"/>
  <use href="#gnd" x="600" y="582"/>
  <text x="618" y="572" font-size="10.5">100n</text>
  <text x="424" y="536" font-size="11">+</text>
  <text x="424" y="568" font-size="12">&minus;</text>

  <!-- ===== Channel D : REF ===== -->
  <circle cx="316" cy="660" r="4" fill="none" stroke="#111" stroke-width="1.6"/>
  <text x="306" y="664" font-size="11" text-anchor="end" font-weight="600">REF</text>
  <g stroke="#111" stroke-width="1.6" fill="none">
    <line x1="320" y1="660" x2="374" y2="660"/>
    <line x1="374" y1="660" x2="374" y2="632"/>
    <line x1="374" y1="572" x2="374" y2="562"/>
    <line x1="374" y1="660" x2="402" y2="660"/>
    <line x1="402" y1="660" x2="402" y2="648"/>
    <line x1="402" y1="648" x2="418" y2="648"/>
    <polygon points="418,636 418,684 474,660"/>
    <line x1="474" y1="660" x2="500" y2="660"/>
    <line x1="490" y1="660" x2="490" y2="696"/>
    <line x1="490" y1="696" x2="404" y2="696"/>
    <line x1="404" y1="696" x2="404" y2="672"/>
    <line x1="404" y1="672" x2="418" y2="672"/>
    <line x1="560" y1="660" x2="600" y2="660"/>
    <line x1="600" y1="660" x2="600" y2="674"/>
    <line x1="588" y1="674" x2="612" y2="674"/>
    <line x1="588" y1="682" x2="612" y2="682"/>
    <line x1="600" y1="682" x2="600" y2="692"/>
    <line x1="600" y1="660" x2="756" y2="660"/>
  </g>
  <use href="#rh" transform="translate(374,572) rotate(90)"/>
  <text x="374" y="558" font-size="10.5" font-weight="600" font-style="italic" text-anchor="middle">VBIAS</text>
  <text x="386" y="606" font-size="10.5">10M</text>
  <use href="#rh" transform="translate(500,660)"/>
  <text x="518" y="650" font-size="10.5">10k</text>
  <circle cx="374" cy="660" r="2.8" fill="#111"/>
  <circle cx="490" cy="660" r="2.8" fill="#111"/>
  <circle cx="600" cy="660" r="2.8" fill="#111"/>
  <use href="#gnd" x="600" y="692"/>
  <text x="618" y="682" font-size="10.5">100n</text>
  <text x="424" y="646" font-size="11">+</text>
  <text x="424" y="678" font-size="12">&minus;</text>
</g>

<!-- ================= ADS1115 ================= -->
<rect x="756" y="300" width="140" height="400" rx="6" fill="none" stroke="#111" stroke-width="2"/>
<text x="826" y="326" font-size="13.5" font-weight="600" text-anchor="middle">ADS1115</text>
<text x="826" y="342" font-size="10.5" text-anchor="middle" fill="#333">I&sup2;C 0x48</text>
<g font-size="10.5" fill="#111">
  <text x="764" y="334">A0</text>
  <text x="764" y="444">A1</text>
  <text x="764" y="554">A2</text>
  <text x="764" y="664">A3</text>
  <text x="888" y="384" text-anchor="end">VDD</text>
  <text x="888" y="424" text-anchor="end">GND</text>
  <text x="888" y="474" text-anchor="end">SCL</text>
  <text x="888" y="514" text-anchor="end">SDA</text>
  <text x="888" y="564" text-anchor="end">ADDR</text>
</g>
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="896" y1="380" x2="922" y2="380"/>
  <line x1="896" y1="420" x2="914" y2="420"/>
  <line x1="896" y1="470" x2="922" y2="470"/>
  <line x1="896" y1="510" x2="922" y2="510"/>
  <line x1="896" y1="560" x2="914" y2="560"/>
  <line x1="914" y1="560" x2="914" y2="576"/>
</g>
<use href="#gnd" x="914" y="420"/>
<use href="#gnd" x="914" y="576"/>
<g font-size="10.5" font-weight="600" font-style="italic" fill="#111">
  <text x="926" y="384">3V3</text>
  <text x="926" y="474">SCL</text>
  <text x="926" y="514">SDA</text>
</g>
<text x="900" y="596" font-size="9.5" fill="#333">(addr = 0x48)</text>

<!-- ================= FS400 ================= -->
<rect x="1000" y="96" width="180" height="130" rx="6" fill="none" stroke="#111" stroke-width="2"/>
<text x="1090" y="122" font-size="13" font-weight="600" text-anchor="middle">FS400-SHT3x</text>
<text x="1090" y="138" font-size="10.5" text-anchor="middle" fill="#333">temp + RH &middot; I&sup2;C 0x44</text>
<text x="1090" y="152" font-size="9.5" text-anchor="middle" fill="#333">(inside chamber)</text>
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="1000" y1="166" x2="974" y2="166"/>
  <line x1="1000" y1="186" x2="982" y2="186"/>
  <line x1="1000" y1="206" x2="974" y2="206"/>
  <line x1="1010" y1="226" x2="1010" y2="226"/>
</g>
<g stroke="#111" stroke-width="1.6" fill="none"><line x1="1000" y1="206" x2="974" y2="206"/><line x1="1020" y1="226" x2="1020" y2="226"/></g>
<use href="#gnd" x="982" y="186"/>
<g font-size="10.5" fill="#111">
  <text x="1006" y="170">VDD</text>
  <text x="1006" y="190">GND</text>
  <text x="1006" y="210">SCL</text>
</g>
<g stroke="#111" stroke-width="1.6" fill="none"><line x1="1064" y1="226" x2="1064" y2="248"/></g>
<text x="1058" y="244" font-size="10.5">SDA</text>
<g font-size="10.5" font-weight="600" font-style="italic" fill="#111">
  <text x="946" y="170" text-anchor="end">3V3</text>
  <text x="946" y="210" text-anchor="end">SCL</text>
  <text x="1070" y="262">SDA</text>
</g>

<!-- ================= 5V domain ================= -->
<rect x="40" y="800" width="1420" height="360" fill="none" stroke="#999" stroke-width="1.2" stroke-dasharray="7 5"/>
<text x="52" y="820" font-size="12" fill="#555" font-style="italic">5V power domain (Mean Well) — route this wiring physically away from the electrode cable and buffer board</text>

<!-- Mean Well -->
<rect x="60" y="850" width="170" height="90" rx="6" fill="none" stroke="#111" stroke-width="2"/>
<text x="145" y="886" font-size="13" font-weight="600" text-anchor="middle">Mean Well</text>
<text x="145" y="902" font-size="11" text-anchor="middle">5 V &middot; 4 A</text>
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="230" y1="870" x2="256" y2="870"/>
  <line x1="230" y1="915" x2="248" y2="915"/>
</g>
<use href="#gnd" x="248" y="915"/>
<text x="260" y="874" font-size="10.5" font-weight="600" font-style="italic">5V</text>

<!-- bulk cap -->
<text x="330" y="856" font-size="10.5" font-weight="600" font-style="italic" text-anchor="middle">5V</text>
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="330" y1="860" x2="330" y2="880"/>
  <line x1="318" y1="880" x2="342" y2="880"/>
  <line x1="318" y1="888" x2="342" y2="888"/>
  <line x1="330" y1="888" x2="330" y2="902"/>
</g>
<use href="#gnd" x="330" y="902"/>
<text x="348" y="888" font-size="10.5">440&micro; bulk</text>
<text x="312" y="876" font-size="10" text-anchor="end">+</text>

<!-- 74AHCT125 -->
<rect x="470" y="850" width="180" height="200" rx="6" fill="none" stroke="#111" stroke-width="2"/>
<text x="560" y="876" font-size="13" font-weight="600" text-anchor="middle">74AHCT125</text>
<text x="560" y="892" font-size="10" text-anchor="middle" fill="#333">channel 1 used</text>
<text x="560" y="1012" font-size="9" text-anchor="middle" fill="#333">1OE&#773;(1)&rarr;GND &middot; 2A,3A,4A (5,9,12)&rarr;GND</text>
<text x="560" y="1026" font-size="9" text-anchor="middle" fill="#333">2OE&#773;,3OE&#773;,4OE&#773; (4,10,13)&rarr;5V</text>
<!-- VCC / GND -->
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="560" y1="850" x2="560" y2="832"/>
  <line x1="560" y1="1050" x2="560" y2="1068"/>
</g>
<text x="560" y="826" font-size="10.5" font-weight="600" font-style="italic" text-anchor="middle">5V</text>
<text x="572" y="846" font-size="9.5" fill="#333">14</text>
<text x="572" y="1064" font-size="9.5" fill="#333">7</text>
<use href="#gnd" x="560" y="1068"/>
<!-- OE -->
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="470" y1="900" x2="444" y2="900"/>
  <line x1="444" y1="900" x2="444" y2="912"/>
</g>
<use href="#gnd" x="444" y="912"/>
<text x="476" y="904" font-size="10.5">1 &middot; 1OE&#773;</text>
<!-- input -->
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="352" y1="950" x2="376" y2="950"/>
  <line x1="436" y1="950" x2="470" y2="950"/>
</g>
<use href="#rh" transform="translate(376,950)"/>
<text x="348" y="954" font-size="10.5" font-weight="600" font-style="italic" text-anchor="end">GPIO18</text>
<text x="396" y="940" font-size="10.5">330</text>
<text x="476" y="954" font-size="10.5">2 &middot; 1A</text>
<!-- output -->
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="650" y1="950" x2="686" y2="950"/>
  <line x1="746" y1="950" x2="800" y2="950"/>
</g>
<use href="#rh" transform="translate(686,950)"/>
<text x="644" y="944" font-size="10.5" text-anchor="end">3 &middot; 1Y</text>
<text x="706" y="940" font-size="10.5">330</text>

<!-- WS2812 -->
<rect x="800" y="850" width="190" height="200" rx="6" fill="none" stroke="#111" stroke-width="2"/>
<text x="895" y="900" font-size="13" font-weight="600" text-anchor="middle">WS2812 matrix</text>
<text x="895" y="918" font-size="10.5" text-anchor="middle" fill="#333">16 &times; 16 = 256 LEDs</text>
<text x="895" y="1000" font-size="9.5" text-anchor="middle" fill="#333">4 A supply &rArr; cap brightness</text>
<text x="895" y="1014" font-size="9.5" text-anchor="middle" fill="#333">(&asymp;25% max in software)</text>
<text x="806" y="954" font-size="10.5">DIN</text>
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="880" y1="850" x2="880" y2="832"/>
  <line x1="880" y1="1050" x2="880" y2="1068"/>
</g>
<text x="880" y="826" font-size="10.5" font-weight="600" font-style="italic" text-anchor="middle">5V</text>
<use href="#gnd" x="880" y="1068"/>

<!-- relay -->
<rect x="1060" y="850" width="170" height="200" rx="6" fill="none" stroke="#111" stroke-width="2"/>
<text x="1145" y="876" font-size="13" font-weight="600" text-anchor="middle">Relay module</text>
<text x="1145" y="892" font-size="10.5" text-anchor="middle" fill="#333">2 channels</text>
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="1060" y1="912" x2="1034" y2="912"/>
  <line x1="1060" y1="944" x2="1042" y2="944"/>
  <line x1="1060" y1="976" x2="1034" y2="976"/>
  <line x1="1230" y1="912" x2="1256" y2="912"/>
  <line x1="1230" y1="952" x2="1268" y2="952"/>
</g>
<use href="#gnd" x="1042" y="944"/>
<g font-size="10.5" fill="#111">
  <text x="1066" y="916">VCC</text>
  <text x="1066" y="948">GND</text>
  <text x="1066" y="980">IN1</text>
  <text x="1224" y="916" text-anchor="end">COM1</text>
  <text x="1224" y="956" text-anchor="end">NO1</text>
</g>
<text x="1145" y="1030" font-size="9.5" text-anchor="middle" fill="#333">ch 2 spare (atomizer later)</text>
<text x="1030" y="908" font-size="10.5" font-weight="600" font-style="italic" text-anchor="end">5V</text>
<text x="1030" y="980" font-size="10.5" font-weight="600" font-style="italic" text-anchor="end">GPIO23</text>
<text x="1260" y="908" font-size="10.5" font-weight="600" font-style="italic">5V</text>

<!-- fan -->
<rect x="1290" y="900" width="150" height="150" rx="6" fill="none" stroke="#111" stroke-width="2"/>
<text x="1365" y="928" font-size="13" font-weight="600" text-anchor="middle">Noctua fan</text>
<text x="1365" y="944" font-size="10.5" text-anchor="middle" fill="#333">5 V &middot; filtered intake</text>
<g stroke="#111" stroke-width="1.6" fill="none">
  <line x1="1268" y1="952" x2="1268" y2="968"/>
  <line x1="1268" y1="968" x2="1290" y2="968"/>
  <line x1="1290" y1="996" x2="1272" y2="996"/>
  <line x1="1290" y1="1024" x2="1264" y2="1024"/>
</g>
<use href="#gnd" x="1272" y="996"/>
<g font-size="10.5" fill="#111">
  <text x="1296" y="972">red (+5V via NO1)</text>
  <text x="1296" y="1000">black (GND)</text>
  <text x="1296" y="1028">blue (PWM)</text>
</g>
<text x="1260" y="1028" font-size="10.5" font-weight="600" font-style="italic" text-anchor="end">GPIO12</text>

<!-- footer notes -->
<text x="52" y="1140" font-size="10.5" fill="#333">All &#9661; symbols are ONE net: Mean Well &minus;V joined to Pi GND (pin 6). Same-named italic labels are connected nets.</text>
<text x="52" y="1200" font-size="11.5" fill="#111">Camera: Pi NoIR v3 on cam0 CSI ribbon (no schematic wiring — keep ribbon away from the WS2812 harness).</text>
<text x="52" y="1222" font-size="11.5" fill="#111">Electrodes E1&ndash;E3 + REF enter via shielded Cat6; shield &rarr; GND at buffer board only.</text>
</svg></div>
</template>

<script>
export default {
  name: '07_the_schematic',
  meta: {
    classes: 'gallery centered',
    section: 'What was built',
    reg: 0.34, fx: 50, fy: 50
  }
}
</script>
