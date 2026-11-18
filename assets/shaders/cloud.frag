#version 330 core
// Nuvens de blocos, como as do Minecraft: brancas, sombreado chapado por face (topo claro, lados mais escuros),
// só um leve claro e escuro que deriva no topo e a luz da hora (douradas no entardecer, escuras à noite).
in vec3 v_World;
in float v_Shade;
in float v_Alpha;
out vec4 FragColor;

uniform vec3 u_Tint;
uniform float u_Time;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

void main() {
    vec3 white = vec3(0.97, 0.98, 1.0);
    float drift = 1.0;
    if (v_Shade > 0.99) {
        // o topo: manchas largas e suaves que passam devagar, em pixels de 1/4 de bloco (o ar de textura do jogo)
        vec2 p = floor(v_World.xz * 4.0) / 4.0;
        drift = 0.94 + 0.08 * noise(p * 0.09 + u_Time * vec2(0.05, 0.02));
    }
    vec3 color = white * v_Shade * drift * clamp(u_Tint, 0.0, 1.15);
    FragColor = vec4(color, v_Alpha);
}
