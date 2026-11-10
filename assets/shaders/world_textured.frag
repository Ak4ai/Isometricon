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
            if (shadowCell(base + vec3(dir.x, 0.0, dir.y) * t) > 0.5)
            {
                occ += axis * (1.0 - 0.22 * float(k));           // a primeira parede achada basta
                break;
            }
        }
    }
    return clamp(occ / 3.2, 0.0, 1.0);
}

// Fração da luz do sol que chega ao ponto (1 = sol inteiro). Três raios um pouco inclinados dão uma borda macia.
float sunVisibility(vec3 worldPos, vec3 worldNormal, vec3 sunDir)
{
    vec3 tilt[3] = vec3[3](vec3(0.0), vec3(0.09, 0.0, -0.05), vec3(-0.09, 0.0, 0.05));
    float visible = 0.0;
    for (int k = 0; k < 3; k++)
    {
        vec3 d = normalize(sunDir + tilt[k]);
        vec3 p = worldPos + worldNormal * 0.1 + d * 0.45;
        float lit = 1.0;
        for (int i = 0; i < 16; i++)
        {
            if (shadowCell(p) > 0.5) { lit = 0.0; break; }
            p += d * 0.75;
        }
        visible += lit;
    }
    return visible / 3.0;
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
    float altitude = mix(0.74, 1.0, smoothstep(1.0, 14.0, worldY));
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
    if (u_WorldStyle) {
        float sunVis = 1.0;
        float contact = 0.0;
        if (u_ShadowStrength > 0.001)
        {
            vec3 worldPos = (u_ShadowInvModel * vec4(v_FragPos, 1.0)).xyz;
            vec3 worldNormal = normalize(mat3(u_ShadowInvModel) * norm);
            contact = contactOcclusion(worldPos, worldNormal);
            if (dot(norm, lightDir) > 0.02)  // a face de costas para o sol já é sombra
            {
                vec3 sunDirWorld = normalize(mat3(u_ShadowInvModel) * lightDir);
                sunVis = sunVisibility(worldPos, worldNormal, sunDirWorld);
            }
        }
        lighting = worldLighting(norm, lightDir, v_FragPos.y, sunVis) * (1.0 - 0.34 * contact * u_ShadowStrength);
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

    vec3 result = lighting * albedo * roomFactor;
    FragColor = vec4(result, texColor.a * u_Alpha);
}
