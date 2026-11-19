// Loading animation: pecas de armadura de diamante voam e se encaixam num boneco
// (silhueta), que da pulinhos a cada encaixe. Em loop, de baixo pra cima.
// Rodar: effectcraft-cli script build_loading.jsx --empty --save-as loading_diamond.ecproj
var W = 512, H = 512, FPS = 30, DUR = 3.6;
var comp = app.project.items.addComp("Loading Diamond", W, H, 1, DUR, FPS);

function hex(h) {
  return [parseInt(h.substr(1, 2), 16) / 255, parseInt(h.substr(3, 2), 16) / 255, parseInt(h.substr(5, 2), 16) / 255];
}
function tr(layer, id) { return layer.property("ADBE Transform Group").property(id); }

// easing: sobe com leve overshoot e assenta (snap)
function easeOutBack(s) { var c1 = 1.4, c3 = c1 + 1; return 1 + c3 * Math.pow(s - 1, 3) + c1 * Math.pow(s - 1, 2); }
function vec(a, b, e) {
  if (typeof a === "number") return a + (b - a) * e;
  var o = []; for (var i = 0; i < a.length; i++) o.push(a[i] + (b[i] - a[i]) * e); return o; }
// keys amostradas (interpolacao linear + easing calculado aqui)
function sample(prop, t0, t1, from, to, ease, steps) {
  for (var i = 0; i <= steps; i++) {
    var s = i / steps;
    prop.setValueAtTime(t0 + (t1 - t0) * s, vec(from, to, ease(s)));
  }
}

// IMPORTANTE: o engine compensa a posicao do filho pelo transform do pai no momento do
// parentesco; por isso o pai e definido ANTES de posicionar o filho.
function solid(name, r, color, parent) {
  var w = r[2] - r[0], h = r[3] - r[1];
  var l = comp.layers.addSolid(hex(color), name, w, h, 1);
  if (parent) l.parent = parent;
  tr(l, "ADBE Anchor Point").setValue([w / 2, h / 2]);
  tr(l, "ADBE Position").setValue([(r[0] + r[2]) / 2, (r[1] + r[3]) / 2]);
  return l;
}
function nullAt(name, c) {
  var n = comp.layers.addNull();
  n.name = name;
  tr(n, "ADBE Anchor Point").setValue(c);
  tr(n, "ADBE Position").setValue(c);
  return n;
}
function inset(r, d) { return [r[0] + d, r[1] + d, r[2] - d, r[3] - d]; }

// ---- corpo (pulinhos): pivo nos pes ----
var body = nullAt("Body", [256, 446]);

// ---- silhueta ----
var SIL = "#3A4150";
var sil = {
  head: [208, 70, 304, 166], torso: [200, 166, 312, 310],
  armL: [144, 166, 192, 310], armR: [320, 166, 368, 310],
  legL: [200, 310, 252, 446], legR: [260, 310, 312, 446]
};
for (var k in sil) solid("sil_" + k, sil[k], SIL, body);

// ---- pecas: L = instante do encaixe; off = de onde vem; rot = giro inicial ----
var BASE = "#1E9AA3", MID = "#37D0C4", LIGHT = "#9BF7EE";
var pieces = [
  { name: "bootL",   r: [200, 396, 252, 446], L: 0.55, off: [-190, 90],  rot: -200 },
  { name: "bootR",   r: [260, 396, 312, 446], L: 0.55, off: [190, 90],   rot: 200 },
  { name: "pantsL",  r: [200, 310, 252, 396], L: 1.00, off: [-200, -30], rot: -160 },
  { name: "pantsR",  r: [260, 310, 312, 396], L: 1.00, off: [200, -30],  rot: 160 },
  { name: "chest",   r: [200, 166, 312, 310], L: 1.45, off: [0, -260],   rot: 180 },
  { name: "armL",    r: [144, 166, 192, 310], L: 1.45, off: [-230, -60], rot: -220 },
  { name: "armR",    r: [320, 166, 368, 310], L: 1.45, off: [230, -60],  rot: 220 },
  { name: "helmet",  r: [208, 70, 304, 166],  L: 1.90, off: [0, -300],   rot: 360 }
];
var FLIGHT = 0.4, VANISH = 3.0;

for (var i = 0; i < pieces.length; i++) {
  var p = pieces[i], r = p.r;
  var c = [(r[0] + r[2]) / 2, (r[1] + r[3]) / 2];
  var t0 = p.L - FLIGHT, vs = VANISH + i * 0.03, ve = vs + 0.3;
  var pn = nullAt("piece_" + p.name, c);
  pn.parent = body; // corpo em repouso no t=0: sem compensacao

  var layers = [
    solid(p.name + "_base", r, BASE, pn),
    solid(p.name + "_mid", inset(r, 5), MID, pn),
    solid(p.name + "_hi", [r[0] + 9, r[1] + 9, r[2] - 9, r[1] + 17], LIGHT, pn)
  ];
  for (var j = 0; j < layers.length; j++) {
    var op = tr(layers[j], "ADBE Opacity");
    op.setValueAtTime(0, 0);
    op.setValueAtTime(t0, 0);
    op.setValueAtTime(t0 + 0.05, 100);
    op.setValueAtTime(ve - 0.1, 100); // >= 2 frames (keys encaixam em 1/30 s)
    op.setValueAtTime(ve, 0);
  }

  // So animar o pai DEPOIS de criar os filhos (senao o engine compensa o filho
  // pelo transform animado do pai no t=0).
  var pos = tr(pn, "ADBE Position"), rot = tr(pn, "ADBE Rotate Z"), sc = tr(pn, "ADBE Scale");
  var start = [c[0] + p.off[0], c[1] + p.off[1]];
  pos.setValueAtTime(0, start);
  sample(pos, t0, p.L, start, c, easeOutBack, 10);
  rot.setValueAtTime(0, p.rot);
  sample(rot, t0, p.L, p.rot, 0, easeOutBack, 10);
  // squash no encaixe + sai de cena (pop e some)
  sc.setValueAtTime(0, [100, 100]);
  sc.setValueAtTime(p.L - 0.02, [100, 100]);
  sc.setValueAtTime(p.L + 0.03, [116, 84]);
  sc.setValueAtTime(p.L + 0.12, [96, 106]);
  sc.setValueAtTime(p.L + 0.22, [100, 100]);
  sc.setValueAtTime(vs, [100, 100]);
  sc.setValueAtTime(vs + 0.1, [118, 118]);
  sc.setValueAtTime(ve, [0, 0]);
}

// ---- pulinhos do boneco: um por encaixe + 2 de comemoracao ----
var hops = [
  { t: 0.55, h: 14 }, { t: 1.00, h: 16 }, { t: 1.45, h: 18 }, { t: 1.90, h: 20 },
  { t: 2.35, h: 34 }, { t: 2.75, h: 34 }
];
var by = tr(body, "ADBE Position"), bs = tr(body, "ADBE Scale");
by.setValueAtTime(0, [256, 446]);
bs.setValueAtTime(0, [100, 100]);
for (var i = 0; i < hops.length; i++) {
  var t = hops[i].t, h = hops[i].h;
  for (var s = 0; s <= 8; s++) {
    var u = s / 8;
    by.setValueAtTime(t + 0.27 * u, [256, 446 - 4 * h * u * (1 - u)]);
  }
  bs.setValueAtTime(t - 0.05, [100, 100]);
  bs.setValueAtTime(t, [110, 90]);        // agacha
  bs.setValueAtTime(t + 0.07, [95, 107]); // estica no pulo
  bs.setValueAtTime(t + 0.2, [100, 100]);
}
writeLn("layers: " + comp.numLayers);
