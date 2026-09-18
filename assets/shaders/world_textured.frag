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
        texColor.a *= clamp(u_CutawayAlpha, 0.0, 1.0);
    }

    vec3 norm = normalize(v_Normal);
    vec3 lightDir = normalize(u_LightDir);

    // Iluminação difusa (Lambert)
    float diff = max(dot(norm, lightDir), 0.0);
    vec3 diffuse = diff * u_LightColor;

    vec3 lighting = u_AmbientColor + diffuse;
    vec3 result = lighting * texColor.rgb * v_Color;

    FragColor = vec4(result, texColor.a);
}
