#version 330 core

// =============================================================================
// Isometricon - Highlight Fragment Shader
// Renderiza cor com transparência ou borda luminosa
// =============================================================================

out vec4 FragColor;

uniform vec4 u_HighlightColor; // Cor RGBA de seleção (ex: vec4(1.0, 0.9, 0.0, 0.4))

void main()
{
    FragColor = u_HighlightColor;
}
