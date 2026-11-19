#version 330 core
// Nuvens de blocos, como as do Minecraft, translúcidas: ralas na beira da manta e densas no miolo (o campo de
// distância até o aberto, u_Distance), com volume (o lado escurece para baixo, o topo tem tufos claros e escuros que
// derivam devagar) e a luz da hora (douradas no entardecer, escuras à noite).
// As nuvens fofas (u_Soft) são as mesmas caixas, mas com a luz de uma nuvem de verdade: a normal se curva perto das
// quinas (parecem arredondadas), o lado do sol é claro e quente, o da sombra é azulado como o céu, a borda rala brilha
// com a luz que atravessa, e um grão fino de algodão por cima.
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
uniform bool u_Moving;          // os tufos das células que estão se desfazendo (ou se formando)
uniform bool u_Soft;            // as nuvens fofas: bordas arredondadas pela luz, luz do sol que atravessa e grão
uniform vec3 u_Light;           // para onde está o sol (no espaço do mundo)
uniform vec3 u_ToCamera;        // para onde está a câmera (no espaço do mundo; a vista é ortográfica)

const float EDGE_ALPHA = 0.42;
const float CORE_ALPHA = 0.97;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

float blocky(float tufts, float dense) {
    float shade = v_Shade;
    if (v_Shade > 0.99) {
        shade *= 0.93 + 0.11 * tufts;                       // o topo: tufos claros e escuros que passam
    } else {
        shade *= mix(1.0, 0.84, smoothstep(0.0, 4.0, v_Below));   // o lado: mais escuro para baixo
        shade *= 0.97 + 0.05 * tufts;
    }
    return shade;
}

vec2 cellUV(vec2 xz) { return (xz / u_Cell - u_Origin) / u_Window; }

void main() {
    // pixels de 1/4 de bloco: o ar de textura do jogo
    vec2 p = floor(v_World.xz * 4.0 + 0.5) / 4.0;
    vec2 wind = u_Time * vec2(0.05, 0.02);
    float tufts = noise(p * 0.11 + wind) * 0.65 + noise(p * 0.31 - wind * 1.7) * 0.35;

    float d = texture(u_Distance, cellUV(v_World.xz)).r;
    float dense = smoothstep(0.02, 0.6, d);
    float alpha = mix(EDGE_ALPHA, CORE_ALPHA, dense) * (0.90 + 0.10 * tufts);
    if (u_Moving)
        alpha = 0.8 * v_Alpha;
    vec3 white = mix(vec3(0.90, 0.94, 1.0), vec3(0.97, 0.98, 1.0), dense);   // a rala é mais fria e clara
    vec3 sun = clamp(u_Tint, 0.0, 1.15);

    if (!u_Soft) {
        FragColor = vec4(white * blocky(tufts, dense) * sun, alpha);
        return;
    }

    // ---- as nuvens fofas ----
    vec3 n = normalize(cross(dFdx(v_World), dFdy(v_World)));
    if (dot(n, u_ToCamera) < 0.0) n = -n;                  // a face que se vê
    vec3 up = vec3(0.0, 1.0, 0.0);
    // quanto falta até a quina, em blocos: no topo, até a beira da manta (pelo campo de distância); no lado, até o topo
    float edge;
    if (n.y > 0.5) {
        edge = max(d * 4.0 - 0.5, 0.0) * u_Cell;
        float texel = 1.0 / u_Window;
        vec2 uv = cellUV(v_World.xz);
        vec2 grad = vec2(texture(u_Distance, uv + vec2(texel, 0)).r - texture(u_Distance, uv - vec2(texel, 0)).r,
                         texture(u_Distance, uv + vec2(0, texel)).r - texture(u_Distance, uv - vec2(0, texel)).r);
        vec2 outward = length(grad) > 1e-4 ? -normalize(grad) : vec2(0.0);
        if (u_Moving) { edge = 0.35; outward = vec2(0.0); }
        n = normalize(n + vec3(outward.x, 0.0, outward.y) * (1.0 - smoothstep(0.0, 1.1, edge)) * 1.4);
    } else {
        edge = v_Below;
        n = normalize(n + up * (1.0 - smoothstep(0.0, 1.1, edge)) * 1.4);
    }
    float round_edge = 1.0 - smoothstep(0.0, 1.1, edge);

    vec3 L = normalize(u_Light);
    float wrap = clamp((dot(n, L) + 0.5) / 1.5, 0.0, 1.0);          // a luz dá a volta (a nuvem espalha a luz)
    vec3 sky = mix(vec3(0.55, 0.64, 0.82), vec3(0.93, 0.96, 1.0), n.y * 0.5 + 0.5);   // embaixo azulado, em cima claro
    vec3 warm = sun * vec3(1.05, 1.0, 0.94);
    vec3 color = white * (sky * 0.72 * clamp(u_Tint, 0.25, 1.1) + warm * wrap * 0.48);
    color += warm * round_edge * 0.10;                               // a quina arredondada pega mais luz
    // a borda rala e as quinas brilham: o sol atravessa onde a nuvem é fina
    float thin = (1.0 - dense) * 0.6 + round_edge * 0.4;
    color += warm * thin * pow(clamp(dot(L, -u_ToCamera) * 0.5 + 0.7, 0.0, 1.0), 2.0) * 0.22;
    float rim = pow(1.0 - clamp(dot(n, u_ToCamera), 0.0, 1.0), 2.5);
    color += vec3(1.0) * rim * 0.16 * sun;
    // o algodão: um ruído fino e contínuo (no topo pelo chão, no lado pela altura), e os tufos grandes que passam
    vec2 face = n.y > 0.5 ? v_World.xz : vec2(v_World.x + v_World.z, v_World.y);
    float cotton = noise(face * 7.0) * 0.6 + noise(face * 17.0 + 3.1) * 0.4;
    color *= (0.95 + 0.08 * cotton) * (0.96 + 0.06 * tufts);
    // mais densa que a de blocos, e a quina arredondada um pouco mais rala: o contorno não corta seco
    alpha = u_Moving ? alpha : mix(0.55, CORE_ALPHA, dense);
    alpha *= mix(0.75, 1.0, smoothstep(0.0, 0.8, edge));
    FragColor = vec4(color, alpha);
}
