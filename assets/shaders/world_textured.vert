#version 330 core

// =============================================================================
// Isometricon - Textured World Vertex Shader (GLSL 330 core)
// Suporte a coordenadas UV para Texture Atlas e Matrizes MVP
// =============================================================================

layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aNormal;
layout (location = 2) in vec2 aTexCoord;
layout (location = 3) in vec3 aColor;

uniform mat4 u_Model;
uniform mat4 u_View;
uniform mat4 u_Projection;

out vec3 v_FragPos;
out vec3 v_Normal;
out vec2 v_TexCoord;
out vec3 v_Color;

void main()
{
    vec4 worldPos = u_Model * vec4(aPos, 1.0);
    v_FragPos = worldPos.xyz;
    v_Normal = mat3(transpose(inverse(u_Model))) * aNormal;
    v_TexCoord = aTexCoord;
    v_Color = aColor;

    gl_Position = u_Projection * u_View * worldPos;
}
