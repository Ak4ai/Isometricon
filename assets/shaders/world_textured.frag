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

    vec3 result = lighting * albedo;
    FragColor = vec4(result, texColor.a * u_Alpha);
}
