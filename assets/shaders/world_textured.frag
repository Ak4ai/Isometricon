#version 330 core

// =============================================================================
// Isometricon - Textured World Fragment Shader (GLSL 330 core)
// Amostragem de Texture Atlas com iluminação difusa de Lambert + Luz Ambiente
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

void main()
{
    vec4 texColor = texture(u_TextureAtlas, v_TexCoord);
    
    // Descartar fragmentos 100% transparentes (ex: vidro, folhas, portas)
    if (texColor.a < 0.1) {
        discard;
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
