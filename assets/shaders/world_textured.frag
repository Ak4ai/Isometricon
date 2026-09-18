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

out vec4 FragColor;

uniform sampler2D u_TextureAtlas;
uniform vec3 u_LightDir;     // Direção da luz do sol
uniform vec3 u_LightColor;   // Cor da luz do sol
uniform vec3 u_AmbientColor; // Luz ambiente

uniform bool u_UndergroundMode; // Jogador está abaixo da superfície
uniform float u_PlayerY;        // Altura mundial dos pés do jogador
uniform float u_CutawayAlpha;   // Alfa das estruturas acima do jogador
uniform float u_CutawayFade;    // Atenuação vertical das camadas superiores
uniform int u_CutawayPass;      // 0 = opaco; 1 = transparentes acima

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

    // Mantém o piso/teto da camada atual legível e separa laterais escuras
    // dos planos superiores, sem depender de sombras físicas no voxel.
    float diff = max(dot(norm, lightDir), 0.0);
    float top_light = max(norm.y, 0.0);
    float underside_shadow = mix(0.68, 1.0, smoothstep(-0.15, 0.35, norm.y));
    vec3 diffuse = diff * u_LightColor;
    vec3 lighting = (u_AmbientColor + diffuse) * underside_shadow;

    float relative_height = v_FragPos.y - u_PlayerY;
    float current_layer = 1.0 - smoothstep(0.15, 1.1, abs(relative_height));
    float layer_highlight = top_light * current_layer * 0.18;
    lighting += vec3(layer_highlight);

    vec3 material_color = texColor.rgb;
    if (u_CutawayPass == 1) {
        // O modo raio-X usa uma cor fria e desaturada para não confundir
        // paredes distantes com o piso onde o token está.
        float luminance = dot(material_color, vec3(0.299, 0.587, 0.114));
        material_color = mix(material_color, vec3(luminance * 0.72), 0.72);
    }

    vec3 result = lighting * material_color * v_Color;

    FragColor = vec4(result, texColor.a);
}
