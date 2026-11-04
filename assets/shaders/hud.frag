#version 330 core

// =============================================================================
// Isometricon - 2D HUD Fragment Shader (GLSL 330 core)
// Amostragem de textura 2D RGBA com suporte a transparência alpha blending
// =============================================================================

in vec2 v_TexCoord;
out vec4 FragColor;

uniform sampler2D u_Texture;
uniform float u_Opacity = 1.0;

void main()
{
    vec4 col = texture(u_Texture, v_TexCoord);
    FragColor = vec4(col.rgb, col.a * u_Opacity);
}
