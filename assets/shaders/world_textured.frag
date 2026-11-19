#version 330 core

// =============================================================================
// Isometricon - Textured World Fragment Shader (GLSL 330 core)
// Amostragem de Texture Atlas com iluminação difusa de Lambert + Luz Ambiente
// e modo de cutaway para visualização subterrânea.
// =============================================================================

in vec3 v_FragPos;
in vec3 v_Normal;
centroid in vec2 v_TexCoord;
in vec3 v_Color;
in vec3 v_BindPos;

out vec4 FragColor;

uniform sampler2D u_TextureAtlas;
uniform vec3 u_LightDir;     // Direção da luz do sol
uniform vec3 u_LightColor;   // Cor da luz do sol
uniform vec3 u_AmbientColor; // Luz ambiente

// Vitiligo: how much of the skin has lost its colour (0 = none), which pattern, and the skin's own
// colour (only what has that colour is skin: eyes, mouth and eyebrows on the head's texture are not).
uniform float u_Vitiligo;
uniform float u_VitiligoSeed;
uniform vec3 u_SkinTone;

// Underwear painted on the skin of the trunk and the legs, by where the point is on the unposed
// body: 0 none, 1 the bottom, 2 the bottom and a top.
uniform int u_Underwear = 0;
uniform vec3 u_UnderwearColor;
uniform vec4 u_UnderBottom;     // lowest of the edge between the legs, the waist, half the strip there, the rise to the sides
uniform vec4 u_UnderTop;        // from, to, where the straps are across the body, half their width
uniform float u_UnderShoulder;  // where the straps end
uniform float u_Alpha = 1.0;    // below 1: a see-through part (the clothes, while the skin under them is edited)

uniform bool u_UndergroundMode; // Jogador está abaixo da superfície
uniform float u_PlayerY;        // Altura mundial dos pés do jogador
uniform float u_CutawayAlpha;   // Alfa das estruturas acima do jogador
uniform float u_CutawayFade;    // Atenuação vertical das camadas superiores
uniform bool u_WaterMode;       // Token está dentro de água
uniform int u_CutawayPass;      // 0 = opaco; 1 = transparentes acima

// Estilo do mundo (terreno e construções): luz com o brilho por face do Minecraft, sol quente, cota e
// saturação, pensado para ler a profundidade na vista isométrica. O personagem não usa (fica desligado).
uniform bool u_WorldStyle;

// Sombras do sol (ver src/rendering/sun_shadows.py): blocos sólidos em volta do jogador, em coordenadas do mundo.
uniform sampler3D u_ShadowMask;
uniform vec3 u_ShadowOrigin;
uniform vec3 u_ShadowSize;
uniform mat4 u_ShadowInvModel;   // do espaço desenhado (girado pelo modelo) de volta ao mundo
uniform float u_ShadowStrength;  // 0 sem sombra
// Por coluna (x, z) da janela, um canal por quadrante de rumo (+x+z, +x-z, -x+z, -x-z): a altura a partir da qual um
// raio que sobe pelo menos u_ShadowHorizonRise por célula andada no plano não encontra mais nada (x 255). Ver
// column_horizons em src/rendering/sun_shadows.py.
uniform sampler2D u_ShadowHorizon;
uniform float u_ShadowHorizonRise;
// Qualidade (Configurações > Gráficos): até onde o raio procura (células, até 56) e quantos raios por pixel
// (0 baixa: um raio; 1 média: cone borrado de 8 e nítido de 3; 2 alta: 12 e 6).
uniform int u_ShadowSteps;
uniform int u_ShadowQuality;

float shadowCell(vec3 worldPos)
{
    vec3 c = floor(worldPos - u_ShadowOrigin);
    if (any(lessThan(c, vec3(0.0))) || any(greaterThanEqual(c, u_ShadowSize)))
        return 0.0;
    return texelFetch(u_ShadowMask, ivec3(c), 0).r;
}

// Os blocos que não são cubo inteiro (laje, degrau, bolo, cama) são parciais na máscara (r entre 0.75 e 0.94): o
// canal g diz quais oitavos da célula eles enchem (o bit ox + 2 oy + 4 oz). ``local`` é o ponto dentro da célula (0..1).
bool octantFilled(vec2 texel, vec3 local)
{
    int bits = int(texel.g * 255.0 + 0.5);
    ivec3 o = ivec3(step(vec3(0.5), local));
    return ((bits >> (o.x + 2 * o.y + 4 * o.z)) & 1) != 0;
}

// O ponto está dentro de algo que tapa (um sólido inteiro, ou o pedaço cheio de um parcial)?
bool blockedAt(vec3 worldPos)
{
    vec3 q = worldPos - u_ShadowOrigin;
    vec3 c = floor(q);
    if (any(lessThan(c, vec3(0.0))) || any(greaterThanEqual(c, u_ShadowSize)))
        return false;
    vec2 texel = texelFetch(u_ShadowMask, ivec3(c), 0).rg;
    if (texel.r > 0.94) return true;
    return texel.r > 0.75 && octantFilled(texel, q - c);
}

// Sombra de contato: o chão escurece junto ao pé de qualquer parede, de qualquer lado e sem depender do sol. É o que
// deixa ler uma descida cujo degrau está de costas para a câmera (o topo de cima e o de baixo teriam o mesmo verde).
// Olha, em volta do ponto, as células logo acima do chão: quanto mais perto e mais numerosas, mais escuro.
float contactOcclusion(vec3 worldPos, vec3 worldNormal)
{
    if (worldNormal.y < 0.6) return 0.0;                         // só no chão (topos de bloco)
    // um pouco abaixo do meio da célula logo acima do chão: numa laje vizinha conta a metade de baixo dela, e no
    // degrau de baixo de uma escada conta o degrau de cima, na mesma célula
    vec3 base = worldPos + vec3(0.0, 0.4, 0.0);
    float occ = 0.0;
    for (int i = 0; i < 8; i++)
    {
        float a = 0.785398 * float(i);
        vec2 dir = vec2(cos(a), sin(a));
        float axis = (i % 2 == 0) ? 1.0 : 0.7;                   // as diagonais pesam menos
        for (int k = 0; k < 4; k++)
        {
            float t = 0.3 + 0.55 * float(k);
            if (blockedAt(base + vec3(dir.x, 0.0, dir.y) * t))
            {
                occ += axis * (1.0 - 0.22 * float(k));           // a primeira parede achada basta
                break;
            }
        }
    }
    return clamp(occ / 3.2, 0.0, 1.0);
}

// Um raio exato pelos voxels (Amanatides-Woo): a fração do sol que chega. Um bloco sólido no caminho corta tudo; a
// água deixa passar, perdendo um pouco a cada bloco atravessado (o fundo de um lago fundo recebe menos sol). Num
// bloco parcial o raio só é cortado se passa por um oitavo cheio dele (amostrado ao longo do trecho na célula); na
// célula de onde sai, os oitavos cheios até o primeiro vazio não contam: são o próprio bloco (a face lateral do bolo,
// recuada da borda da célula, começa dentro do oitavo dele).
const int PARTIAL_SAMPLES = 6;
const float WATER_TRANSMIT = 0.82;
float traceSun(vec3 worldPos, vec3 dir)
{
    vec3 q = worldPos - u_ShadowOrigin;                       // em células da janela
    ivec3 cell = ivec3(floor(q));
    ivec3 size = ivec3(u_ShadowSize);
    vec3 safe = vec3(abs(dir.x) < 1e-5 ? 1e-5 : dir.x, abs(dir.y) < 1e-5 ? 1e-5 : dir.y, abs(dir.z) < 1e-5 ? 1e-5 : dir.z);
    ivec3 stepDir = ivec3(sign(safe));
    vec3 tDelta = abs(1.0 / safe);
    vec3 frac = q - floor(q);
    vec3 tMax = vec3(safe.x > 0.0 ? 1.0 - frac.x : frac.x,
                     safe.y > 0.0 ? 1.0 - frac.y : frac.y,
                     safe.z > 0.0 ? 1.0 - frac.z : frac.z) * tDelta;
    // o raio anda sempre no mesmo sentido em x e z: só passa pelas colunas do seu quadrante à frente
    vec4 quadrant = vec4(stepDir.x > 0 && stepDir.z > 0, stepDir.x > 0 && stepDir.z <= 0,
                         stepDir.x <= 0 && stepDir.z > 0, stepDir.x <= 0 && stepDir.z <= 0);
    bool useHorizon = stepDir.y > 0 && safe.y >= u_ShadowHorizonRise * length(safe.xz);
    float light = 1.0;
    float tEnter = 0.0;                                       // onde o raio entrou na célula atual
    for (int i = 0; i < 56; i++)
    {
        if (i >= u_ShadowSteps)
            break;
        if (any(lessThan(cell, ivec3(0))) || any(greaterThanEqual(cell, size)))
            return light;                                     // saiu da janela (para cima ou para longe): sol livre
        // subindo e acima de tudo o que há nas colunas à frente: nada mais o tapa, sol livre
        if (useHorizon && float(cell.y) >= dot(texelFetch(u_ShadowHorizon, cell.xz, 0), quadrant) * 255.0 - 0.5)
            return light;
        vec2 texel = texelFetch(u_ShadowMask, cell, 0).rg;
        float value = texel.r;
        float tExit = min(tMax.x, min(tMax.y, tMax.z));
        if (value > 0.94)
            return 0.0;
        if (value > 0.75)
        {
            bool own = i == 0;                                // ainda dentro do próprio bloco de onde saiu
            for (int k = 0; k < PARTIAL_SAMPLES; k++)
            {
                float t = mix(tEnter, tExit, (float(k) + 0.5) / float(PARTIAL_SAMPLES));
                vec3 local = clamp(q + safe * t - vec3(cell), vec3(0.0), vec3(0.999));
                bool filled = octantFilled(texel, local);
                if (own && filled) continue;
                own = false;
                if (filled) return 0.0;
            }
        }
        else if (value > 0.25)
            light *= WATER_TRANSMIT;
        tEnter = tExit;
        if (tMax.x < tMax.y && tMax.x < tMax.z) { cell.x += stepDir.x; tMax.x += tDelta.x; }
        else if (tMax.y < tMax.z)               { cell.y += stepDir.y; tMax.y += tDelta.y; }
        else                                    { cell.z += stepDir.z; tMax.z += tDelta.z; }
    }
    return light;
}

// --------------------------------------------------------------------------------------------------- água
// A água é desenhada em duas passadas (ver src/main.py): na 1 (opaca) ela é descartada e o fundo recebe a luz que a
// atravessa; na 2 só ela é desenhada, translúcida, sobre o que já está na tela. Um fragmento é água pela região da
// textura dela no atlas.
uniform int u_WaterPass;        // 0 desligado (personagem), 1 passada opaca, 2 passada da água
uniform vec4 u_WaterRect;       // (u mín, v mín, u máx, v máx) da textura da água no atlas
uniform float u_Time;           // segundos, para as ondas e as cáusticas
uniform vec3 u_CameraPos;       // olho da câmera, no espaço desenhado

bool isWaterTexel(vec2 uv)
{
    return uv.x >= u_WaterRect.x - 1e-4 && uv.x <= u_WaterRect.z + 1e-4
        && uv.y >= u_WaterRect.y - 1e-4 && uv.y <= u_WaterRect.w + 1e-4;
}

bool insideShadowWindow(vec3 worldPos)
{
    vec3 c = floor(worldPos - u_ShadowOrigin);
    return all(greaterThanEqual(c, vec3(0.0))) && all(lessThan(c, u_ShadowSize));
}

bool waterCell(vec3 worldPos)
{
    float value = shadowCell(worldPos);
    return value > 0.25 && value < 0.75;
}

// Quantos blocos de água há a partir de ``start`` seguindo ``dir`` (para cima: a coluna sobre o fundo; para baixo: a
// profundidade sob a superfície).
float waterRun(vec3 start, vec3 dir)
{
    float n = 0.0;
    for (int i = 0; i < 16; i++)
    {
        if (!waterCell(start + dir * float(i))) break;
        n += 1.0;
    }
    return n;
}

// Cáusticas: as linhas de luz que a superfície ondulada concentra no fundo. Camadas de ondas que se cruzam, presas à
// grade de texels (16 por bloco) para ficarem com cara de pixel, como o resto do mundo.
float caustics(vec2 p, float t)
{
    p = (floor(p * 16.0) + 0.5) / 16.0;
    vec2 q = p * 1.6;
    float c = 0.0;
    for (int i = 0; i < 3; i++)
    {
        float fi = float(i);
        q += vec2(sin(q.y * 1.9 + t * 0.85 + fi * 1.7), cos(q.x * 1.7 - t * 0.75 + fi * 2.3)) * 0.55;
        c += abs(sin(q.x + q.y + t * 0.3));
    }
    c = 1.0 - c / 3.0;                                          // claro onde as ondas se alinham
    return smoothstep(0.62, 0.95, c);
}

// A normal da superfície com ondas pequenas (soma de senos no plano), também presa aos texels.
vec3 waveNormal(vec2 p, float t)
{
    p = (floor(p * 16.0) + 0.5) / 16.0;
    float dx = 0.055 * cos(p.x * 2.1 + t * 1.3) + 0.035 * cos((p.x + p.y) * 3.3 - t * 1.7) + 0.02 * cos(p.x * 5.7 + t * 2.1);
    float dz = 0.055 * cos(p.y * 1.9 - t * 1.1) + 0.035 * cos((p.x - p.y) * 2.9 + t * 1.5) + 0.02 * cos(p.y * 6.1 - t * 2.3);
    return normalize(vec3(-dx, 1.0, -dz));
}

// Sombras "em pixel", como nos shader packs de Minecraft: o ponto da face é levado ao centro do seu texel (16 por
// bloco), nos dois eixos da face. A sombra, borda e penumbra, passa a andar em quadradinhos da mesma grade da textura.
const float SHADOW_TEXELS = 16.0;
vec3 snapToTexel(vec3 worldPos, vec3 worldNormal)
{
    vec3 snapped = (floor(worldPos * SHADOW_TEXELS) + 0.5) / SHADOW_TEXELS;
    vec3 n = abs(worldNormal);
    return vec3(n.x > 0.5 ? worldPos.x : snapped.x,
                n.y > 0.5 ? worldPos.y : snapped.y,
                n.z > 0.5 ? worldPos.z : snapped.z);            // no eixo da normal o ponto fica na própria face
}

// Ruído de gradiente intercalado: um valor estável 0..1 por pixel da tela, para girar o cone da sombra borrada.
float interleavedNoise(vec2 pixel)
{
    return fract(52.9829189 * fract(dot(pixel, vec2(0.06711056, 0.00583715))));
}

// Fração de um cone de raios que chega ao sol: ``rays`` raios espalhados num disco de raio ``spread``.
float sunCone(vec3 origin, vec3 sunDir, int rays, float spread, float spin)
{
    vec3 t1 = normalize(cross(sunDir, vec3(0.0, 1.0, 0.0)));
    vec3 t2 = cross(sunDir, t1);
    float lit = 0.0;
    for (int k = 0; k < rays; k++)
    {
        float r = sqrt((float(k) + 0.5) / float(rays)) * spread;
        float a = float(k) * 2.3999632 + spin;                 // ângulo áureo: espalha os raios no disco
        lit += traceSun(origin, normalize(sunDir + (t1 * cos(a) + t2 * sin(a)) * r));
    }
    return lit / float(rays);
}

// O cone borrado (``rays`` raios, 0.15) em duas etapas: um a cada quatro, espalhados pelo disco, primeiro; se todos
// chegam ao sol o ponto está no sol pleno e para aí (é a maior parte do chão aberto); senão os outros completam a média.
// Com ``umbra``, se nenhum dos quatro chega o ponto já fica na sombra inteira: dentro de um cômodo é quase tudo (o
// teto tapa), e só perto da porta e das janelas, onde algum passa, a penumbra é calculada inteira.
float softSun(vec3 origin, vec3 sunDir, float spin, int rays, bool umbra)
{
    vec3 t1 = normalize(cross(sunDir, vec3(0.0, 1.0, 0.0)));
    vec3 t2 = cross(sunDir, t1);
    int stride = rays / 4;
    float first = 0.0;
    for (int k = 0; k < 12; k += 1)
    {
        if (k >= rays)
            break;
        if (k % stride != 0)
            continue;
        float r = sqrt((float(k) + 0.5) / float(rays)) * 0.15;
        float a = float(k) * 2.3999632 + spin;
        first += traceSun(origin, normalize(sunDir + (t1 * cos(a) + t2 * sin(a)) * r));
    }
    if (first >= 3.999)
        return 1.0;
    if (umbra && first <= 0.001)
        return 0.0;
    float rest = 0.0;
    for (int k = 0; k < 12; k++)
    {
        if (k >= rays)
            break;
        if (k % stride == 0)
            continue;
        float r = sqrt((float(k) + 0.5) / float(rays)) * 0.15;
        float a = float(k) * 2.3999632 + spin;
        rest += traceSun(origin, normalize(sunDir + (t1 * cos(a) + t2 * sin(a)) * r));
    }
    return (first + rest) / float(rays);
}

// Fração da luz do sol que chega ao ponto (1 = sol inteiro). A nitidez muda ao longo da sombra:
// - a sombra nítida sai do ponto preso ao texel, em degraus de pixel;
// - a borrada sai do ponto exato, com mais raios, cone mais largo e girado por pixel (sem degraus);
// onde a sombra é escura (junto ao bloco) vale a nítida, onde é clara (longe dele) vale a borrada, e no meio as duas
// se misturam aos poucos: nítido, meio nítido, meio borrado, borrado.
float sunVisibility(vec3 snappedPos, vec3 exactPos, vec3 worldNormal, vec3 sunDir, bool indoor)
{
    if (u_ShadowQuality <= 0)
        return traceSun(snappedPos + worldNormal * 0.04, sunDir);   // baixa: um raio, sombra nítida em pixel
    bool high = u_ShadowQuality >= 2;
    float soft = softSun(exactPos + worldNormal * 0.04, sunDir, interleavedNoise(gl_FragCoord.xy) * 6.2831853,
                         high ? 12 : 8, indoor);
    if (indoor && soft <= 0.0)
        return 0.0;                                            // dentro do cômodo, longe das aberturas: sombra
    float blur = smoothstep(0.1, 0.9, soft);                   // 0 no escuro (nítido) .. 1 no claro (borrado)
    if (blur >= 1.0)
        return soft;                                           // só a borrada conta: os 6 raios da nítida sobram
    float sharp = sunCone(snappedPos + worldNormal * 0.04, sunDir, high ? 6 : 3, 0.08, 0.0);
    return mix(sharp, soft, blur);
}

// Brilho da face: topo 1.0, faces em Z 0.82, faces em X 0.64, fundo 0.5 (como no Minecraft), contínuo na normal.
float faceShade(vec3 n)
{
    float top = clamp(n.y, 0.0, 1.0);
    float bottom = clamp(-n.y, 0.0, 1.0);
    float zShare = abs(n.z) / (abs(n.x) + abs(n.z) + 1e-4);
    float side = 1.0 - top - bottom;
    return top + bottom * 0.5 + side * mix(0.64, 0.82, zShare);
}

// Luz do mundo: o brilho da face, com o tom do sol, e um fundo frio vindo do céu nas faces que não pegam sol.
vec3 worldLighting(vec3 n, vec3 l, float worldY, float sunVis)
{
    float shade = faceShade(n);
    float sun = clamp(dot(n, l), 0.0, 1.0);                      // quanto a face olha para o sol
    sun *= sunVis;                                                // à sombra o sol não conta
    shade *= mix(1.0 - 0.38 * u_ShadowStrength, 1.0, sunVis);     // e a face escurece
    vec3 warm = vec3(1.08, 1.00, 0.88);                          // sol
    vec3 cool = vec3(0.86, 0.94, 1.10);                          // céu, nas faces de sombra
    vec3 tint = mix(cool, warm, smoothstep(0.05, 0.6, sun));
    // quanto mais fundo o terreno, mais escuro: numa vista sem perspectiva a altura é a pista de profundidade
    // o que está abaixo dos pés do jogador escurece com a profundidade (≈6% por bloco, até 6 blocos): cada terraço
    // fica com um tom próprio em qualquer altitude do mundo, e quanto mais fundo, mais escuro
    float depth = clamp(u_PlayerY - worldY, 0.0, 6.0);
    float altitude = 1.0 - 0.062 * depth;
    return vec3(0.96) * shade * tint * altitude;
}

// Revelação do espaço do jogador (cômodo, caverna): ver src/world/room_reveal.py.
uniform float u_RoomActive;     // 0 = desligado; 0..1 = intensidade do efeito
uniform sampler3D u_RoomMask;   // 255 espaço do jogador, 192 móvel/degrau, 128 casca, 64 borda pela quina, 0 fora
uniform vec3 u_RoomOrigin;      // célula do mundo do canto (0,0,0) da máscara
uniform vec3 u_RoomSize;        // tamanho da máscara em células
uniform vec3 u_ViewDir;         // para onde a câmera olha, em coordenadas do mundo
uniform mat4 u_RoomInvModel;    // do espaço desenhado (girado pelo modelo) de volta ao mundo
uniform float u_RoomExterior;   // brilho do que fica fora do espaço (0 preto, 1 normal)
uniform float u_RoomCeiling;    // brilho do teto do espaço que sobra do corte do andar (0 preto, 1 normal)

// Valor da máscara na célula que contém o ponto do mundo; -1 fora da janela.
float roomCell(vec3 worldPos)
{
    vec3 c = floor(worldPos - u_RoomOrigin);
    if (any(lessThan(c, vec3(0.0))) || any(greaterThanEqual(c, u_RoomSize)))
        return -1.0;
    return texelFetch(u_RoomMask, ivec3(c), 0).r;
}

// Limiar de dither 4x4 (0..1) do pixel: a entrada e a saída do efeito aparecem como pontilhado.
float roomDither()
{
    int x = int(mod(gl_FragCoord.x, 4.0));
    int y = int(mod(gl_FragCoord.y, 4.0));
    const float bayer[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0,
                                      3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
    return (bayer[y * 4 + x] + 0.5) / 16.0;
}

float hash3(vec3 p)
{
    p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float valueNoise(vec3 p)
{
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), f.x),
                   mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), f.x), f.y),
               mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), f.x),
                   mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}

// Corredor da câmera (como o CameraCorridor do Isocraft): o que fica entre a câmera e o personagem, num cilindro
// em volta dessa linha, some com uma borda pontilhada. Só corta do nível dos pés para cima (o chão em que se pisa
// fica) e só o que está mais perto da câmera que o personagem. A decisão é por bloco (centro da célula), para o
// corte sair em degraus de bloco, como o resto do mundo.
uniform float u_SightActive;     // 0 desligado; 0..1 intensidade
uniform vec3 u_SightTarget;      // peito do personagem, no espaço desenhado
uniform float u_SightFeetY;      // célula y dos pés, no mundo
uniform float u_SightRadius;     // raio do cilindro, em blocos
uniform mat4 u_SightModel;       // mundo -> espaço desenhado
uniform mat4 u_SightInvModel;    // espaço desenhado -> mundo
// Corte do andar (o StoryBand do Isocraft): debaixo de um teto, do teto para cima some tudo num círculo em volta do
// personagem, para ver o andar em que ele está sem os andares, o telhado e as vigas de cima.
uniform float u_StoryActive;     // 0 desligado; 0..1 intensidade (entra e sai com fade)
uniform float u_StoryCutY;       // célula y (mundo) do teto do andar: dela para cima, corta
uniform vec2 u_StoryCenter;      // x, z (mundo) do personagem
uniform float u_StoryRadius;     // raio do círculo cortado, em blocos
uniform vec3 u_StoryView;        // para onde a câmera olha, no mundo

// O bloco tapa o cômodo: seguindo o raio da câmera dele para dentro da cena, cai no espaço do cômodo (só o andar
// do personagem conta, com o corte do andar ligado: o andar de cima, ligado pela escada, não faz sumir o fundo).
bool coversRoom(vec3 c)
{
    vec3 q = c + u_StoryView * 0.9;
    for (int i = 0; i < 64; i++)
    {
        if (u_StoryActive > 0.001 && q.y < u_SightFeetY)
            break;                                      // já passou do chão do andar
        if (roomCell(q) > 0.9 && (u_StoryActive <= 0.001 || q.y < u_StoryCutY))
            return true;
        q += u_StoryView * 0.5;
    }
    return false;
}

// O bloco está na borda do cômodo virada para a câmera (parede da frente, teto): entre ele e a câmera não há espaço
// do cômodo. Um pilar ou um móvel no meio do cômodo tem o cômodo dos dois lados, e fica.
bool facesCamera(vec3 c)
{
    vec3 q = c - u_StoryView * 0.9;
    for (int i = 0; i < 24; i++)
    {
        if (roomCell(q) > 0.9)
            return false;
        q -= u_StoryView * 0.5;
    }
    return true;
}

// Casa de bonecas: acima do teto do andar some o que tapa o cômodo. As paredes do fundo ficam de pé, inteiras, e o
// teto e o andar de cima sobre o cômodo somem. Não depende de onde o personagem está dentro do cômodo: chegar perto
// de uma parede do fundo não a corta (ela só some quando o cômodo atrás dela passa a ser o seu).
// Parede da frente: a face de dentro dela olha para o cômodo do lado oposto ao da câmera (o cômodo fica atrás dela).
// Pega a ponta da parede junto à quina, onde o raio da câmera entra na parede vizinha e nunca chega ao espaço.
bool frontWall(vec3 c)
{
    vec2 f = normalize(u_StoryView.xz);
    return (f.x > 0.3 && roomCell(c + vec3(1.0, 0.0, 0.0)) > 0.9)
        || (f.x < -0.3 && roomCell(c - vec3(1.0, 0.0, 0.0)) > 0.9)
        || (f.y > 0.3 && roomCell(c + vec3(0.0, 0.0, 1.0)) > 0.9)
        || (f.y < -0.3 && roomCell(c - vec3(0.0, 0.0, 1.0)) > 0.9);
}

// O bloco está no fundo do cômodo: andando na horizontal em direção à câmera, passa por cima do chão do cômodo (o
// espaço na altura dos pés). Não depende da altura: a parede do fundo é fundo até o topo.
bool behindRoom(vec3 c)
{
    vec2 toward = -normalize(u_StoryView.xz);
    vec2 q = c.xz + toward * 0.9;
    for (int i = 0; i < 24; i++)
    {
        if (roomCell(vec3(q.x, u_SightFeetY + 0.5, q.y)) > 0.9)
            return true;
        q += toward * 0.5;
    }
    return false;
}

// A coluna (x, z) está sobre o chão do cômodo: na altura dos pés, o espaço (255) ou um móvel/degrau (192).
bool overRoom(vec2 xz)
{
    return roomCell(vec3(xz.x, u_SightFeetY + 0.5, xz.y)) > 0.7;
}

// Beiral: na laje do teto (a célula y do corte), a faixa das paredes do fundo de um vértice a outro. É a aba (coluna
// sobre o cômodo com a parede do fundo ao lado), o topo da parede do fundo (coluna fora do cômodo com o cômodo ao
// lado, do lado da câmera) e as pontas (vizinha de um topo de parede do fundo ao longo da parede: os vértices).
// ``_eave`` em src/world/room_caps.py faz a mesma conta para as tampas.
bool eaveColumn(vec2 xz)
{
    vec2 f = normalize(u_StoryView.xz);
    bool over = overRoom(xz);
    const vec2 axes[4] = vec2[4](vec2(1.0, 0.0), vec2(-1.0, 0.0), vec2(0.0, 1.0), vec2(0.0, -1.0));
    for (int i = 0; i < 4; i++)
    {
        vec2 o = axes[i];
        float d = dot(o, f);
        if (over && d > 0.3 && !overRoom(xz + o))
            return true;                                // a aba
        if (!over && d < -0.3)
        {
            if (overRoom(xz + o))
                return true;                            // o topo da parede do fundo
            vec2 p = vec2(o.y, o.x);                    // ao longo da parede: as pontas
            if (!overRoom(xz + p) && overRoom(xz + p + o))
                return true;
            if (!overRoom(xz - p) && overRoom(xz - p + o))
                return true;
        }
    }
    return false;
}

bool eave(vec3 c)
{
    return floor(c.y) == u_StoryCutY && eaveColumn(c.xz);
}

bool storyCovers(vec3 cell)
{
    if (u_RoomActive <= 0.001)
        return true;
    vec3 c = cell + 0.5;
    // o beiral fica sempre, de um vértice ao outro
    if (eave(c))
        return false;
    // o que não está no fundo do cômodo (a frente, os lados de fora) some inteiro; no fundo, some o que está sobre o
    // cômodo (a laje do teto e o andar de cima, que tapam o cômodo); o que está em cima das paredes do fundo e além
    // delas fica, escurecido como o lado de fora (ver roomFactor)
    return !behindRoom(c) || overRoom(c.xz);
}

uniform bool u_CastShadow;       // a passada do mapa de sombra dos personagens: só a profundidade, vista do sol
uniform sampler2D u_CharShadowMap;    // a profundidade dos personagens vistos do sol (cast_shadow.py)
uniform mat4 u_CharShadowMatrix;      // do espaço desenhado para a textura do mapa
uniform float u_CharShadowTexel;
uniform float u_CharShadowStrength;   // 0 desligado
uniform bool u_DepthOnly;        // pré-passada de profundidade: descarta como sempre e para antes da luz
uniform bool u_KeepVisible;      // portas: nenhum corte de visão as remove

bool sightCarved()
{
    if (u_KeepVisible || (u_SightActive <= 0.001 && u_StoryActive <= 0.001))
        return false;
    vec3 worldPos = (u_SightInvModel * vec4(v_FragPos, 1.0)).xyz;
    vec3 worldNormal = normalize(mat3(u_SightInvModel) * v_Normal);
    vec3 cell = floor(worldPos - worldNormal * 0.05);
    if (u_StoryActive > 0.001 && cell.y >= u_StoryCutY && storyCovers(cell))
    {
        float d = length(cell.xz + 0.5 - u_StoryCenter);
        float keep = smoothstep(u_StoryRadius - 3.0, u_StoryRadius, d);
        if ((1.0 - keep) * u_StoryActive > roomDither())
            return true;
    }
    if (u_SightActive <= 0.001 || cell.y < u_SightFeetY)
        return false;
    if (u_RoomActive > 0.001 && (!coversRoom(cell + 0.5) || cell.y <= u_SightFeetY))
        return false;                                   // num cômodo, o corredor não corta o fundo nem a borda da parede
    vec3 center = (u_SightModel * vec4(cell + 0.5, 1.0)).xyz;
    vec3 line = u_CameraPos - u_SightTarget;
    float len = length(line);
    vec3 dir = line / max(len, 1e-4);
    float t = dot(center - u_SightTarget, dir);        // 0 no personagem, len na câmera
    if (t < 0.9)
        return false;                                   // atrás do personagem, ou colado nele: fica
    float off = length(center - u_SightTarget - dir * t);
    // o cilindro abre um pouco perto do personagem (o corpo inteiro aparece) e fica constante depois
    float radius = u_SightRadius * mix(0.75, 1.0, clamp((t - 0.9) / 3.0, 0.0, 1.0));
    float keep = smoothstep(radius - 0.5, radius, off);  // 0 no meio do corredor, 1 fora (borda curta)
    return (1.0 - keep) * u_SightActive > roomDither();
}

// O quanto de um personagem está entre este ponto (espaço desenhado) e o sol: 0 nada, 1 tudo. A borda é nítida (3x3
// texels só para não serrilhar); a opacidade cai com a distância, ao longo do raio, até a parte do corpo que faz a
// sombra: forte junto aos pés, esmaecendo para a cabeça.
uniform float u_CharShadowDepth;      // a profundidade do mapa, em blocos (converte a diferença de profundidade)
uniform float u_CharShadowLength;     // até onde, ao longo do raio, a sombra esmaece (no máximo uns 4 blocos)
uniform float u_CharShadowTail = 0.15; // a opacidade no fim do esmaecido (0 quando a sombra é comprida: some)
float characterShadow(vec3 drawnPos, vec3 drawnNormal)
{
    vec4 p = u_CharShadowMatrix * vec4(drawnPos + drawnNormal * 0.04, 1.0);
    vec3 c = p.xyz / p.w;
    if (any(lessThan(c, vec3(0.0))) || any(greaterThan(c, vec3(1.0))))
        return 0.0;
    float bias = 0.0006;
    float hidden = 0.0, gap = 0.0;
    for (int dx = -1; dx <= 1; dx++)
        for (int dy = -1; dy <= 1; dy++)
        {
            float d = texture(u_CharShadowMap, c.xy + vec2(dx, dy) * u_CharShadowTexel).r;
            if (c.z - bias > d) { hidden += 1.0; gap += c.z - d; }
        }
    if (hidden < 0.5)
        return 0.0;
    float along = clamp(gap / hidden * u_CharShadowDepth / u_CharShadowLength, 0.0, 1.0);   // 0 nos pés, 1 na cabeça
    return hidden / 9.0 * mix(1.0, u_CharShadowTail, smoothstep(0.0, 1.0, along));   // escuro junto aos pés, cai depois
}

// A ambientação do mestre (/mestre, src/rendering/ambience.py), no fim de tudo: um tom por cima (a luz da hora, a
// claridade e a cor), a saturação, a luz quente do grupo em volta do jogador (não escurece com a noite) e a névoa.
// Nos padrões não muda nada.
uniform vec3 u_EnvTint = vec3(1.0);
uniform float u_EnvSaturation = 1.0;
uniform float u_FogAmount = 0.0;      // 0 sem névoa
uniform vec3 u_FogColor;
uniform vec3 u_FogCenter;             // os pés do jogador, no espaço desenhado
uniform float u_TorchAmount = 0.0;    // 0 sem a luz do grupo
// a névoa de guerra (src/rendering/fog_of_war.py): 0 desligada, 1 o explorado fica limpo (u_FogWarMap), 2 só em volta
uniform int u_FogWar = 0;
uniform sampler2D u_FogWarMap;        // 1 explorado, 0 não; [z][x] a partir de u_FogWarOrigin, em blocos do mundo
uniform mat4 u_FogInvModel;           // do espaço desenhado para o mundo
uniform vec3 u_FogWarColor;
uniform vec2 u_FogWarCenter;          // x, z (mundo) do personagem
uniform float u_FogWarRadius;         // até onde ele enxerga
uniform vec2 u_FogWarOrigin;
uniform float u_FogWarSize;

// os tufos da névoa: ruído que deriva com o tempo, de 0 a 1
float fogWisps(vec2 xz)
{
    vec2 drift = xz * 0.11 + u_Time * vec2(0.22, 0.09);
    return 0.62 * valueNoise(vec3(drift, u_Time * 0.05)) + 0.38 * valueNoise(vec3(drift * 2.3 + 17.0, u_Time * 0.08));
}

// o quanto a névoa de guerra cobre este ponto: 0 visto, 1 coberto. A borda anda com os tufos (não é um recorte).
float fogWarCover(vec3 world, float wisps)
{
    float d = length(world.xz - u_FogWarCenter);
    float seen = 1.0 - smoothstep(u_FogWarRadius - 3.0, u_FogWarRadius + 0.5, d + (wisps - 0.5) * 3.0);
    if (u_FogWar == 1)
    {
        float m = texture(u_FogWarMap, (world.xz - u_FogWarOrigin) / u_FogWarSize).r;
        seen = max(seen, smoothstep(0.25, 0.85, m + (wisps - 0.5) * 0.6));
    }
    return 1.0 - seen;
}

vec3 envGrade(vec3 color, vec3 albedo)
{
    color *= u_EnvTint;
    vec3 offset = v_FragPos - u_FogCenter;
    if (u_TorchAmount > 0.001)
    {
        float radius = 3.0 + 7.0 * u_TorchAmount;
        float near = 1.0 - smoothstep(0.0, radius, length(offset * vec3(1.0, 1.6, 1.0)));
        color += albedo * vec3(1.0, 0.70, 0.40) * near * near * (0.35 + 0.65 * u_TorchAmount);
    }
    float luma = dot(color, vec3(0.299, 0.587, 0.114));
    color = max(mix(vec3(luma), color, u_EnvSaturation), 0.0);
    if (u_FogAmount > 0.001)
    {
        // a névoa densa (estilo cidade na névoa): perto do jogador ainda se vê, e logo depois vira uma parede clara.
        // Cai mais rente ao chão (mais grossa no que fica abaixo dos pés), e anda: tufos de ruído que derivam com o
        // tempo. Muita névoa também traz um grão de filme por cima.
        float amount = u_FogAmount;
        float reach = max(length(offset.xz) - mix(3.0, 1.2, amount), 0.0);
        float density = mix(0.035, 0.34, pow(amount, 1.4));
        float low = 1.0 + 0.7 * clamp(-offset.y / 4.0, 0.0, 1.0);                  // os vales enchem primeiro
        float wisps = fogWisps(v_FragPos.xz);
        density *= low * mix(1.0, 0.55 + 0.9 * wisps, smoothstep(0.15, 0.6, amount));
        float f = 1.0 - exp(-pow(reach * density, 1.5));
        f *= min(1.0, amount * 1.6);                                                // pouca névoa nunca cobre tudo
        color = mix(color, u_FogColor, clamp(f, 0.0, 1.0));
        float grain = fract(sin(dot(gl_FragCoord.xy + fract(u_Time * 7.13) * 97.0, vec2(12.9898, 78.233))) * 43758.5453);
        color += (grain - 0.5) * 0.07 * smoothstep(0.45, 1.0, amount);
    }
    if (u_FogWar > 0)
    {
        // o que ninguém viu: uma névoa quase opaca, mais clara e mais escura nos tufos, com volume e grão
        vec3 world = (u_FogInvModel * vec4(v_FragPos, 1.0)).xyz;
        float wisps = fogWisps(world.xz);
        float cover = fogWarCover(world, wisps);
        if (cover > 0.001)
        {
            float rise = clamp((v_FragPos.y - u_FogCenter.y) / 6.0, 0.0, 1.0);    // os picos furam um pouco a névoa
            vec3 mist = u_FogWarColor * (0.86 + 0.28 * wisps);
            color = mix(color, mist, clamp(cover * (0.97 - 0.18 * rise * (1.0 - wisps)), 0.0, 1.0));
            float grain = fract(sin(dot(gl_FragCoord.xy + fract(u_Time * 5.31) * 61.0, vec2(12.9898, 78.233))) * 43758.5453);
            color += (grain - 0.5) * 0.05 * cover;
        }
    }
    return color;
}

void main()
{
    vec4 texColor = texture(u_TextureAtlas, v_TexCoord);

    // Descartar fragmentos 100% transparentes (ex: folhas/vidro quando houver).
    if (texColor.a < 0.1) {
        discard;
    }
    if (u_CastShadow)
        return;   // o mapa de sombra dos personagens guarda só a profundidade (o transparente já foi descartado)
    bool water = u_WaterPass > 0 && isWaterTexel(v_TexCoord);
    if ((u_WaterPass == 1 && water) || (u_WaterPass == 2 && !water)) {
        discard;
    }

    // Espaço do jogador: o que está fora é escurecido, e o que tapa a vista dele (teto, parede
    // da frente, terra por cima) some. Um fragmento tapa se, seguindo o raio da câmera para dentro
    // da cena, ele chega ao interior do espaço.
    float roomFactor = 1.0;
    float roomLit = 1.0;          // o brilho que o cômodo dá ao fragmento: 1 no espaço, u_RoomExterior fora dele
    if (u_RoomActive > 0.001)
    {
        vec3 worldPos = (u_RoomInvModel * vec4(v_FragPos, 1.0)).xyz;
        vec3 worldNormal = normalize(mat3(u_RoomInvModel) * v_Normal);
        // a célula do bloco que está sendo desenhado (um pouco para dentro da face)
        vec3 blockCell = floor(worldPos - worldNormal * 0.05);
        float here = roomCell(blockCell + 0.5);
        // some só a borda do cômodo virada para a câmera (parede da frente, teto) que tapa o cômodo; o fundo, um
        // pilar ou um mezanino ficam. A decisão parte do CENTRO do bloco, e não do pixel: é a mesma para todas as
        // faces dele (partindo do pixel, uma parede fina era cortada em escada no meio da face).
        // a fileira da parede na altura dos pés fica sempre: a borda que sobra tem a mesma altura em volta toda
        if (!u_KeepVisible && here < 0.7 && blockCell.y > u_SightFeetY && u_RoomActive > roomDither())
        {
            vec3 c = blockCell + 0.5;
            // na metade da frente do cômodo (medida do centro dele) some tudo o que o tapa, até divisórias; do
            // centro para trás, só a borda virada para a câmera (pilar, mezanino e móveis do fundo ficam)
            // (móvel, degrau e piso, 192 na máscara, nunca somem por aqui: só o corte do andar os tira)
            bool frontHalf = dot(c.xz - u_StoryCenter, normalize(u_StoryView.xz)) < -1.0;
            if (coversRoom(c) && (frontHalf || facesCamera(c)))
                discard;
            if ((u_StoryActive <= 0.001 || c.y < u_StoryCutY) && frontWall(c))
                discard;
        }
        float inside = here >= 0.2 ? 1.0 : 0.0;   // o espaço, a casca e a borda pela quina (64)
        float lit = mix(u_RoomExterior, 1.0, inside);
        // do teto do andar para cima é outro andar (a escada liga, mas não é o cômodo): escurece como o lado de fora,
        // até o jogador entrar nele. Só o beiral (a laje do teto do cômodo junto às paredes do fundo) fica com o
        // brilho do teto, para mostrar que há um teto em cima.
        if (blockCell.y >= u_StoryCutY)
        {
            float upper = eave(blockCell + 0.5) ? u_RoomCeiling : u_RoomExterior;
            lit = mix(lit, upper, u_StoryActive);
        }
        roomLit = lit;
        roomFactor = mix(1.0, lit, u_RoomActive);
    }

    if (sightCarved())
        discard;

    bool above_player = v_FragPos.y > u_PlayerY + 0.05;

    // No primeiro passe subterrâneo, mantém apenas a geometria abaixo do
    // jogador para preservar o depth buffer da parte sólida da caverna.
    if (u_UndergroundMode && u_CutawayPass == 0 && above_player) {
        discard;
    }

    // Segundo passe: desenha somente o terreno acima do jogador com alpha
    // reduzido, permitindo visualizar o interior das cavernas sem remover
    // fisicamente os voxels do mundo.
    if (u_CutawayPass == 1) {
        if (!u_UndergroundMode || !above_player) {
            discard;
        }
        float height_above_player = max(v_FragPos.y - u_PlayerY, 0.0);
        float layer_fade = exp(-height_above_player * max(u_CutawayFade, 0.0));
        texColor.a *= clamp(u_CutawayAlpha * layer_fade, 0.04, 1.0);
    }

    // Pré-passada de profundidade (ver src/main.py): só os descartes acima contam; a luz fica para a passada
    // seguinte, que então só sombreia o fragmento da frente de cada pixel.
    if (u_DepthOnly)
        return;

    vec3 norm = normalize(v_Normal);
    vec3 lightDir = normalize(u_LightDir);

    float diff;
    if (u_UndergroundMode) {
        diff = max(dot(norm, lightDir), 0.0);
    } else {
        // Iluminação difusa suave (Half-Lambert) para sombreamento orgânico estilo anime
        float NdotL = dot(norm, lightDir);
        float halfLambert = clamp(NdotL * 0.5 + 0.5, 0.0, 1.0);
        diff = halfLambert * halfLambert;
    }
    vec3 diffuse = diff * u_LightColor;

    float underside_shadow = 1.0;
    if (u_UndergroundMode) {
        underside_shadow = mix(0.68, 1.0, smoothstep(-0.15, 0.35, norm.y));
    }
    vec3 lighting = (u_AmbientColor + diffuse) * underside_shadow;
    float sunVis = 1.0;
    vec3 worldPos = v_FragPos;
    vec3 worldNormal = norm;
    float waterAbove = 0.0;           // blocos de água sobre este fragmento (0 fora da água)
    if (u_WorldStyle) {
        float contact = 0.0;
        if (u_ShadowStrength > 0.001)
        {
            worldNormal = normalize(mat3(u_ShadowInvModel) * norm);
            vec3 exactPos = (u_ShadowInvModel * vec4(v_FragPos, 1.0)).xyz;
            worldPos = snapToTexel(exactPos, worldNormal);
            contact = contactOcclusion(worldPos, worldNormal);
            if (!water)
                waterAbove = waterRun(worldPos + worldNormal * 0.05, vec3(0.0, 1.0, 0.0));
            if (dot(norm, lightDir) > 0.02 || water)  // a face de costas para o sol já é sombra (a água não tem costas)
            {
                vec3 sunDirWorld = normalize(mat3(u_ShadowInvModel) * lightDir);
                // a água (a superfície e o fundo debaixo dela) leva um raio só, do ponto preso ao texel: a sombra
                // fica nítida, em degraus de pixel como a do chão, e as ondas e o tingido escondem a falta da
                // penumbra. Custa um raio em vez de até 18, e o lago pagava isso duas vezes (fundo e superfície).
                // fora do cômodo, escurecido (a 12%), a penumbra quase não aparece: um raio basta
                bool dimmed = u_RoomActive > 0.5 && roomLit < 0.5;
                if (water || waterAbove > 0.0 || dimmed)
                    sunVis = traceSun(worldPos + worldNormal * 0.04, sunDirWorld);
                else
                {
                    // o ar em frente da face é o espaço do jogador: o teto o tapa, a não ser junto às aberturas
                    bool indoor = u_RoomActive > 0.001 && roomCell(worldPos + worldNormal * 0.04) > 0.9;
                    sunVis = sunVisibility(worldPos, exactPos, worldNormal, sunDirWorld, indoor);
                }
            }
        }
        if (u_CharShadowStrength > 0.001 && dot(norm, lightDir) > 0.02)  // a sombra do personagem, em qualquer face
        {
            // ela só tira o sol que chega (sunVis): onde ele não chega não há o que tirar. Numa caverna ou dentro de
            // casa ela fica bem mais clara, quase some: ali a luz é a do ambiente, não a do sol
            float place = (u_UndergroundMode ? 0.15 : 1.0) * (1.0 - 0.8 * clamp(u_RoomActive, 0.0, 1.0));
            sunVis *= 1.0 - u_CharShadowStrength * place * characterShadow(v_FragPos, norm);
        }
        lighting = worldLighting(norm, lightDir, v_FragPos.y, sunVis) * (1.0 - 0.34 * contact * u_ShadowStrength);
        if (waterAbove > 0.0)
        {
            // o fundo debaixo da água: a luz chega tingida (a água absorve primeiro o vermelho) e as ondas da
            // superfície a concentram em cáusticas, mais fracas quanto mais fundo
            vec3 absorb = exp(-waterAbove * vec3(0.38, 0.14, 0.07));
            float sunDown = sunVis * exp(-waterAbove * 0.22);
            lighting = lighting * mix(vec3(0.55, 0.78, 0.95), vec3(1.0), absorb.g) * absorb
                     + vec3(0.85, 0.97, 0.88) * caustics(worldPos.xz, u_Time) * 0.85 * sunDown;
        }
    }

    if (u_UndergroundMode) {
        float top_light = max(norm.y, 0.0);
        float relative_height = v_FragPos.y - u_PlayerY;
        float current_layer = 1.0 - smoothstep(0.15, 1.1, abs(relative_height));
        float layer_highlight = top_light * current_layer * 0.18;
        lighting += vec3(layer_highlight);
    }

    vec3 albedo = texColor.rgb * v_Color;
    if (u_Vitiligo > 0.0)
    {
        // Patches on the unposed body, the same on both sides (as vitiligo often is), with
        // irregular edges; more of them, and larger, as the amount grows.
        vec3 p = vec3(abs(v_BindPos.x), v_BindPos.y, v_BindPos.z) * 7.0 + vec3(u_VitiligoSeed * 9.0);
        float n = 0.62 * valueNoise(p) + 0.26 * valueNoise(p * 2.3 + 11.0) + 0.12 * valueNoise(p * 5.1 + 37.0);
        float edge = mix(0.80, 0.34, clamp(u_Vitiligo, 0.0, 1.0));
        float patch_ = smoothstep(edge, edge + 0.035, n);
        float skin = 1.0 - smoothstep(0.12, 0.24, distance(albedo, u_SkinTone));
        albedo = mix(albedo, mix(albedo, vec3(0.99, 0.93, 0.91), 0.86), patch_ * skin);
    }
    if (u_Underwear > 0)
    {
        float across = abs(v_BindPos.x);
        float height = v_BindPos.y;
        float low = u_UnderBottom.x + u_UnderBottom.w * max(across - u_UnderBottom.z, 0.0);
        bool on = height >= low && height <= u_UnderBottom.y;
        bool trim = on && (height > u_UnderBottom.y - 0.012 || height < low + 0.008);     // the waistband and the leg seams
        if (u_Underwear > 1)
        {
            bool band = height >= u_UnderTop.x && height <= u_UnderTop.y;
            bool strap = height > u_UnderTop.y && height < u_UnderShoulder && abs(across - u_UnderTop.z) < u_UnderTop.w;
            trim = trim || (band && (height < u_UnderTop.x + 0.012 || height > u_UnderTop.y - 0.008));
            on = on || band || strap;
        }
        if (on)
            albedo = u_UnderwearColor * (trim ? 0.86 : 1.0);
    }

    if (u_CutawayPass == 1) {
        // O modo raio-X usa uma cor fria e desaturada para não confundir
        // paredes distantes com o piso onde o token está.
        float luminance = dot(albedo, vec3(0.299, 0.587, 0.114));
        albedo = mix(albedo, vec3(luminance * 0.72), 0.72);
    }

    if (u_WaterMode) {
        // Filtro de imersão: preserva formas, mas deixa claro que o espaço
        // está sendo visto através de água.
        albedo = mix(albedo, vec3(0.12, 0.40, 0.72), 0.42);
        lighting = mix(lighting, lighting * vec3(0.72, 0.88, 1.12), 0.65);
    }

    if (u_WorldStyle) {
        // cores um pouco mais vivas, sem sair do visual do Minecraft
        float luma = dot(albedo, vec3(0.299, 0.587, 0.114));
        albedo = clamp(mix(vec3(luma), albedo, 1.14), 0.0, 1.0);
    }

    if (u_WaterPass == 2)
    {
        // A superfície: cor pela profundidade (rasa e clara, funda e escura), deixa ver o fundo onde é rasa, reflete o
        // céu mais em ângulo raso (Fresnel) e brilha onde reflete o sol.
        bool top = worldNormal.y > 0.5;
        vec3 n = top ? transpose(mat3(u_ShadowInvModel)) * waveNormal(worldPos.xz, u_Time) : norm;
        vec3 v = normalize(u_CameraPos - v_FragPos);
        // fora da janela da máscara não se sabe o fundo: vale como água funda (não deixa ver um fundo sem tinta)
        vec3 below = worldPos - vec3(0.0, 0.5, 0.0);
        float depth = (u_ShadowStrength > 0.001 && insideShadowWindow(below))
                    ? waterRun(below, vec3(0.0, -1.0, 0.0)) : 6.0;
        float deep = 1.0 - exp(-(depth + 0.5) * 0.30);
        float detail = dot(texColor.rgb, vec3(0.299, 0.587, 0.114));
        vec3 body = mix(vec3(0.26, 0.66, 0.84), vec3(0.07, 0.24, 0.50), deep) * mix(1.0, detail * 1.5, 0.25);
        float fresnel = 0.03 + 0.97 * pow(1.0 - clamp(dot(n, v), 0.0, 1.0), 5.0);
        vec3 r = reflect(-v, n);
        vec3 sky = mix(vec3(0.62, 0.76, 0.92), vec3(0.30, 0.50, 0.86), clamp(r.y, 0.0, 1.0));
        float glint = pow(max(dot(r, lightDir), 0.0), 140.0) * 1.8 * sunVis;
        vec3 color = mix(body * lighting, sky * mix(0.55, 1.0, sunVis), fresnel) + vec3(1.0, 0.95, 0.82) * glint;
        float alpha = clamp(mix(0.22, 0.90, deep) + fresnel * 0.40 + glint, 0.0, 1.0);
        FragColor = vec4(envGrade(color * roomFactor, body), alpha * u_Alpha);
        return;
    }

    vec3 result = envGrade(lighting * albedo * roomFactor, albedo * roomFactor);
    FragColor = vec4(result, texColor.a * u_Alpha);
}
