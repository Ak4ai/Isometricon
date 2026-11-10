#version 330 core

// =============================================================================
// Isometricon - Textured World Fragment Shader (GLSL 330 core)
// Amostragem de Texture Atlas com iluminação difusa de Lambert + Luz Ambiente
// e modo de cutaway para visualização subterrânea.
// =============================================================================

in vec3 v_FragPos;
in vec3 v_Normal;
in vec2 v_TexCoord;
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

float shadowCell(vec3 worldPos)
{
    vec3 c = floor(worldPos - u_ShadowOrigin);
    if (any(lessThan(c, vec3(0.0))) || any(greaterThanEqual(c, u_ShadowSize)))
        return 0.0;
    return texelFetch(u_ShadowMask, ivec3(c), 0).r;
}

// Sombra de contato: o chão escurece junto ao pé de qualquer parede, de qualquer lado e sem depender do sol. É o que
// deixa ler uma descida cujo degrau está de costas para a câmera (o topo de cima e o de baixo teriam o mesmo verde).
// Olha, em volta do ponto, as células logo acima do chão: quanto mais perto e mais numerosas, mais escuro.
float contactOcclusion(vec3 worldPos, vec3 worldNormal)
{
    if (worldNormal.y < 0.6) return 0.0;                         // só no chão (topos de bloco)
    vec3 base = worldPos + vec3(0.0, 0.5, 0.0);                  // meio da célula logo acima do chão
    float occ = 0.0;
    for (int i = 0; i < 8; i++)
    {
        float a = 0.785398 * float(i);
        vec2 dir = vec2(cos(a), sin(a));
        float axis = (i % 2 == 0) ? 1.0 : 0.7;                   // as diagonais pesam menos
        for (int k = 0; k < 4; k++)
        {
            float t = 0.3 + 0.55 * float(k);
            if (shadowCell(base + vec3(dir.x, 0.0, dir.y) * t) > 0.75)
            {
                occ += axis * (1.0 - 0.22 * float(k));           // a primeira parede achada basta
                break;
            }
        }
    }
    return clamp(occ / 3.2, 0.0, 1.0);
}

// Um raio exato pelos voxels (Amanatides-Woo): a fração do sol que chega. Um bloco sólido no caminho corta tudo; a
// água deixa passar, perdendo um pouco a cada bloco atravessado (o fundo de um lago fundo recebe menos sol).
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
    float light = 1.0;
    for (int i = 0; i < 56; i++)
    {
        if (any(lessThan(cell, ivec3(0))) || any(greaterThanEqual(cell, size)))
            return light;                                     // saiu da janela (para cima ou para longe): sol livre
        float value = texelFetch(u_ShadowMask, cell, 0).r;
        if (value > 0.75)
            return 0.0;
        if (value > 0.25)
            light *= WATER_TRANSMIT;
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

// Fração da luz do sol que chega ao ponto (1 = sol inteiro). A nitidez muda ao longo da sombra:
// - a sombra nítida sai do ponto preso ao texel, em degraus de pixel;
// - a borrada sai do ponto exato, com mais raios, cone mais largo e girado por pixel (sem degraus);
// onde a sombra é escura (junto ao bloco) vale a nítida, onde é clara (longe dele) vale a borrada, e no meio as duas
// se misturam aos poucos: nítido, meio nítido, meio borrado, borrado.
float sunVisibility(vec3 snappedPos, vec3 exactPos, vec3 worldNormal, vec3 sunDir)
{
    float sharp = sunCone(snappedPos + worldNormal * 0.04, sunDir, 6, 0.08, 0.0);
    float soft = sunCone(exactPos + worldNormal * 0.04, sunDir, 12, 0.15,
                         interleavedNoise(gl_FragCoord.xy) * 6.2831853);
    float blur = smoothstep(0.1, 0.9, soft);                   // 0 no escuro (nítido) .. 1 no claro (borrado)
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
uniform sampler3D u_RoomMask;   // 255 espaço do jogador, 128 casca de sólido ao redor, 0 fora
uniform vec3 u_RoomOrigin;      // célula do mundo do canto (0,0,0) da máscara
uniform vec3 u_RoomSize;        // tamanho da máscara em células
uniform vec3 u_ViewDir;         // para onde a câmera olha, em coordenadas do mundo
uniform mat4 u_RoomInvModel;    // do espaço desenhado (girado pelo modelo) de volta ao mundo
uniform float u_RoomExterior;   // brilho do que fica fora do espaço (0 preto, 1 normal)

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

void main()
{
    vec4 texColor = texture(u_TextureAtlas, v_TexCoord);

    // Descartar fragmentos 100% transparentes (ex: folhas/vidro quando houver).
    if (texColor.a < 0.1) {
        discard;
    }
    bool water = u_WaterPass > 0 && isWaterTexel(v_TexCoord);
    if ((u_WaterPass == 1 && water) || (u_WaterPass == 2 && !water)) {
        discard;
    }

    // Espaço do jogador: o que está fora é escurecido, e o que tapa a vista dele (teto, parede
    // da frente, terra por cima) some. Um fragmento tapa se, seguindo o raio da câmera para dentro
    // da cena, ele chega ao interior do espaço.
    float roomFactor = 1.0;
    if (u_RoomActive > 0.001)
    {
        vec3 worldPos = (u_RoomInvModel * vec4(v_FragPos, 1.0)).xyz;
        vec3 worldNormal = normalize(mat3(u_RoomInvModel) * v_Normal);
        // a célula do bloco que está sendo desenhado (um pouco para dentro da face)
        vec3 blockCell = floor(worldPos - worldNormal * 0.05);
        float here = roomCell(blockCell + 0.5);
        if (here <= 0.9 && u_RoomActive > roomDither())
        {
            // O raio parte do CENTRO do bloco, e não do pixel: a decisão é a mesma para todas as faces
            // do bloco. Partindo do pixel, uma parede fina com mais espaço atrás era cortada em escada
            // no meio da face (uns pixels acertavam o espaço atrás, outros não).
            vec3 q = blockCell + 0.5 + u_ViewDir * 0.9;
            for (int i = 0; i < 64; i++)
            {
                if (roomCell(q) > 0.9)
                    discard;
                q += u_ViewDir * 0.5;
            }
        }
        float inside = here >= 0.4 ? 1.0 : 0.0;
        roomFactor = mix(1.0, mix(u_RoomExterior, 1.0, inside), u_RoomActive);
    }

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
            if (dot(norm, lightDir) > 0.02 || water)  // a face de costas para o sol já é sombra (a água não tem costas)
            {
                vec3 sunDirWorld = normalize(mat3(u_ShadowInvModel) * lightDir);
                sunVis = sunVisibility(worldPos, exactPos, worldNormal, sunDirWorld);
            }
            if (!water)
                waterAbove = waterRun(worldPos + worldNormal * 0.05, vec3(0.0, 1.0, 0.0));
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
        FragColor = vec4(color * roomFactor, alpha * u_Alpha);
        return;
    }

    vec3 result = lighting * albedo * roomFactor;
    FragColor = vec4(result, texColor.a * u_Alpha);
}
