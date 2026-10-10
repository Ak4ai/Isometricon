#version 330 core

// =============================================================================
// Isometricon - 2D HUD Fragment Shader (GLSL 330 core)
// Amostragem de textura 2D RGBA com suporte a transparência alpha blending
// =============================================================================

in vec2 v_TexCoord;
out vec4 FragColor;

uniform sampler2D u_Texture;

void main()
{
    vec4 col = texture(u_Texture, v_TexCoord);
    FragColor = col;
}
