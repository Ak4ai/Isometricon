#version 330 core

// =============================================================================
// Isometricon - 2D HUD Vertex Shader (GLSL 330 core)
// Projeção ortográfica de tela em pixels para UI, Chat e Menus
// =============================================================================

layout (location = 0) in vec2 aPos;
layout (location = 1) in vec2 aTexCoord;

uniform mat4 u_Projection;

out vec2 v_TexCoord;

void main()
{
    v_TexCoord = aTexCoord;
    gl_Position = u_Projection * vec4(aPos, 0.0, 1.0);
}
