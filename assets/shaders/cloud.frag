#version 330 core
// Nuvens de blocos, como as do Minecraft, translúcidas: ralas na beira da manta e densas no miolo (o campo de
// distância até o aberto, u_Distance), com volume (o lado escurece para baixo, o topo tem tufos claros e escuros que
// derivam devagar) e a luz da hora (douradas no entardecer, escuras à noite).
// As nuvens fofas (u_Soft): cada célula é uma caixa quadrada com as quinas e os vértices redondos, emendada nas
// vizinhas da mesma altura (uma nuvem só, redonda por fora e nos degraus); a caixa da malha é só onde procurar, e o raio da câmera anda até a superfície redonda (a distância
// até a caixa redonda mais perto, das células em volta em u_Boxes). A luz é lisa, de nuvem: o topo claro, o lado de
// baixo azulado como o céu, o sol que dá a volta e a sombra no vão entre as caixas.
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
uniform bool u_Soft;            // as nuvens fofas: caixas de quinas e vértices redondos
uniform vec3 u_Light;           // para onde está o sol (no espaço do mundo)
uniform vec3 u_ToCamera;        // para onde está a câmera (no espaço do mundo; a vista é ortográfica)
uniform sampler2D u_Boxes;      // as fofas: por célula (topo, fundo, lados que emendam, 1 se tem nuvem)
uniform float u_Round;          // o raio das quinas e dos vértices, em blocos
uniform mat4 u_MVP;

const float EDGE_ALPHA = 0.42;
const float CORE_ALPHA = 0.97;
const float SOFT_EDGE_ALPHA = 0.38;

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

float roundBox(vec3 p, vec3 bmin, vec3 bmax) {
    vec3 q = abs(p - (bmin + bmax) * 0.5) - ((bmax - bmin) * 0.5 - u_Round);
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0) - u_Round;
}

// a distância até a caixa redonda da célula c (muito longe se a célula não tem nuvem). Onde emenda com a vizinha (da
// mesma altura ou mais alta), a caixa entra nela e as duas viram uma nuvem só; conta só o lado e o canto em que o
// ponto está: se emenda dos dois lados mas o canto entre eles não tem nuvem, a caixa se estica em L (as duas caixas
// esticadas, uma para cada lado) e o canto côncavo fica limpo
float boxDistance(ivec2 c, vec3 p) {
    if (c.x < 0 || c.y < 0 || c.x >= int(u_Window) || c.y >= int(u_Window)) return 1e3;
    vec4 box = texelFetch(u_Boxes, c, 0);
    if (box.a < 0.5) return 1e3;
    vec2 lo = (vec2(c) + u_Origin) * u_Cell, hi = lo + u_Cell;
    int joins = int(box.b + 0.5);
    float reach = u_Round + 0.2;
    bool east = p.x > lo.x + u_Cell * 0.5, south = p.z > lo.y + u_Cell * 0.5;
    bool joinX = (joins & (east ? 1 : 2)) != 0, joinZ = (joins & (south ? 4 : 8)) != 0;
    bool joinXZ = (joins & (east ? (south ? 16 : 64) : (south ? 32 : 128))) != 0;
    vec2 ex = vec2(0.0), ez = vec2(0.0);          // (para baixo, para cima) em x e em z
    if (joinX) { if (east) ex.y = reach; else ex.x = reach; }
    if (joinZ) { if (south) ez.y = reach; else ez.x = reach; }
    float y0 = box.g - 2.0, y1 = box.r;
    if (joinX && joinZ && !joinXZ)
        return min(roundBox(p, vec3(lo.x - ex.x, y0, lo.y), vec3(hi.x + ex.y, y1, hi.y)),
                   roundBox(p, vec3(lo.x, y0, lo.y - ez.x), vec3(hi.x, y1, hi.y + ez.y)));
    return roundBox(p, vec3(lo.x - ex.x, y0, lo.y - ez.x), vec3(hi.x + ex.y, y1, hi.y + ez.y));
}

// a distância até a nuvem: a caixa da célula do ponto e as três vizinhas do lado dele
float cloudDistance(vec3 p) {
    vec2 f = p.xz / u_Cell - u_Origin;
    ivec2 c = ivec2(floor(f));
    vec2 inside = fract(f);
    ivec2 sx = ivec2(inside.x < 0.5 ? -1 : 1, 0), sz = ivec2(0, inside.y < 0.5 ? -1 : 1);
    return min(min(boxDistance(c, p), boxDistance(c + sx, p)), min(boxDistance(c + sz, p), boxDistance(c + sx + sz, p)));
}

// quanto tem nuvem logo ali (0 nada, 1 encostado): a sombra de contato
float occlusion(vec3 p) { return 1.0 - clamp(cloudDistance(p) / 0.45, 0.0, 1.0); }

// a luz de uma face da nuvem: o céu (claro por cima, azulado por baixo) e o sol que dá a volta
vec3 faceLight(vec3 dir, vec3 L, vec3 warm) {
    float wrap = clamp((dot(dir, L) + 0.45) / 1.45, 0.0, 1.0);
    vec3 sky = mix(vec3(0.50, 0.58, 0.74), vec3(1.0, 1.0, 1.0), smoothstep(-0.4, 0.95, dir.y));
    return sky * 0.78 * clamp(u_Tint, 0.25, 1.1) + warm * wrap * 0.28;
}

vec3 cloudNormal(vec3 p) {
    const vec2 k = vec2(1.0, -1.0);
    const float e = 0.02;
    return normalize(k.xyy * cloudDistance(p + k.xyy * e) + k.yyx * cloudDistance(p + k.yyx * e) +
                     k.yxy * cloudDistance(p + k.yxy * e) + k.xxx * cloudDistance(p + k.xxx * e));
}

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
        gl_FragDepth = gl_FragCoord.z;
        FragColor = vec4(white * blocky(tufts, dense) * sun, alpha);
        return;
    }

    // ---- as nuvens fofas ----
    vec3 L = normalize(u_Light);
    vec3 warm = sun * vec3(1.05, 1.0, 0.94);
    vec3 n;
    float rim = 0.0;
    vec3 hit = v_World;
    if (u_Moving) {
        // os tufos que saem e voltam: caixinhas com a mesma luz (sem procurar a superfície)
        n = normalize(cross(dFdx(v_World), dFdy(v_World)));
        if (dot(n, u_ToCamera) < 0.0) n = -n;
        gl_FragDepth = gl_FragCoord.z;
    } else {
        // a caixa da malha é só onde procurar: o raio da câmera anda até a superfície da caixa redonda mais perto
        // (passos curtos, menores que meia célula, porque só as células em volta entram na conta); se sai da nuvem
        // sem achar, aqui é a quina redonda e não tem nuvem
        vec3 dir = -u_ToCamera;
        vec3 p = v_World - dir * 0.02;
        float travelled = 0.0;
        bool found = false;
        for (int i = 0; i < 48; i++) {
            float dist = cloudDistance(p);
            if (dist < 0.004) { found = true; break; }
            float step = clamp(dist, 0.01, 0.5);
            p += dir * step;
            travelled += step;
            if (travelled > 2.5 * u_Cell) break;
        }
        if (!found) discard;
        hit = p;
        n = cloudNormal(hit);
        vec4 clip = u_MVP * vec4(hit + u_ToCamera * 0.03, 1.0);
        gl_FragDepth = clamp(clip.z / clip.w * 0.5 + 0.5, 0.0, 1.0);
        rim = 1.0 - clamp(dot(n, u_ToCamera), 0.0, 1.0);
    }

    // a luz de uma nuvem: o céu por cima (branco) e por baixo (azulado), o sol que dá a volta, e a borda que brilha
    // a luz de cada face (as seis direções), misturada pela normal: a curva da quina fica sempre entre as cores das
    // duas faces que ela liga (com a luz pela normal curva, a quina virada para o sol acendia numa linha clara)
    vec3 w = n * n;
    vec3 color = w.x * faceLight(vec3(sign(n.x), 0.0, 0.0), L, warm)
               + w.y * faceLight(vec3(0.0, sign(n.y), 0.0), L, warm)
               + w.z * faceLight(vec3(0.0, 0.0, sign(n.z)), L, warm);
    // a sombra de contato: no vão entre duas caixas e no pé de um degrau, escurece e azula
    // (por face, como a luz: a curva da quina leva a sombra das faces que ela liga)
    float ao = 0.0;
    if (!u_Moving) {
        vec3 w = n * n;
        ao = w.x * occlusion(hit + vec3(sign(n.x) * 0.45, 0.0, 0.0))
           + w.y * occlusion(hit + vec3(0.0, sign(n.y) * 0.45, 0.0))
           + w.z * occlusion(hit + vec3(0.0, 0.0, sign(n.z) * 0.45));
    }
    color *= mix(vec3(1.0), vec3(0.72, 0.77, 0.88), ao);
    // o gradiente de transparência: rala perto do aberto (onde o grupo está) e opaca para dentro da manta, pela
    // distância até a beira no ponto achado
    if (!u_Moving) {
        float near = texture(u_Distance, cellUV(hit.xz)).r;
        alpha = mix(SOFT_EDGE_ALPHA, 1.0, smoothstep(0.02, 0.7, near));
    }
    FragColor = vec4(color, alpha);
}
