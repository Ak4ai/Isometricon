#version 330 core
// Nuvens de blocos, como as do Minecraft, translúcidas: ralas na beira da manta e densas no miolo (o campo de
// distância até o aberto, u_Distance), com volume (o lado escurece para baixo, o topo tem tufos claros e escuros que
// derivam devagar) e a luz da hora (douradas no entardecer, escuras à noite).
in vec3 v_World;
in float v_Shade;
in float v_Alpha;
in float v_Below;
out vec4 FragColor;

uniform vec3 u_Tint;
uniform float u_Time;
uniform sampler2D u_Distance;   // 0 na beira, 1 a FAR células dela para dentro (filtro linear)
uniform vec2 u_Origin;          // a célula do canto da manta
uniform float u_Window;         // células de lado
uniform float u_Cell;           // blocos por célula
uniform bool u_Moving;          // as células que estão se desfazendo

const float EDGE_ALPHA = 0.42;
const float CORE_ALPHA = 0.97;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

void main() {
    // pixels de 1/4 de bloco: o ar de textura do jogo
    vec2 p = floor(v_World.xz * 4.0 + 0.5) / 4.0;
    vec2 wind = u_Time * vec2(0.05, 0.02);
    float tufts = noise(p * 0.11 + wind) * 0.65 + noise(p * 0.31 - wind * 1.7) * 0.35;

    float shade = v_Shade;
    if (v_Shade > 0.99) {
        shade *= 0.93 + 0.11 * tufts;                       // o topo: tufos claros e escuros que passam
    } else {
        shade *= mix(1.0, 0.84, smoothstep(0.0, 4.0, v_Below));   // o lado: mais escuro para baixo
        shade *= 0.97 + 0.05 * tufts;
    }

    float d = texture(u_Distance, (v_World.xz / u_Cell - u_Origin) / u_Window).r;
    float dense = smoothstep(0.02, 0.6, d);
    float alpha = mix(EDGE_ALPHA, CORE_ALPHA, dense) * (0.90 + 0.10 * tufts);
    if (u_Moving)
        alpha = 0.55 * v_Alpha;

    // a nuvem rala é um pouco mais fria e clara (a luz passa por ela); a densa, branca
    vec3 white = mix(vec3(0.90, 0.94, 1.0), vec3(0.97, 0.98, 1.0), dense);
    vec3 color = white * shade * clamp(u_Tint, 0.0, 1.15);
    FragColor = vec4(color, alpha);
}
