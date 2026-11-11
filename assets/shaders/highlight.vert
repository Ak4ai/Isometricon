#version 330 core

// =============================================================================
// Isometricon - Highlight Vertex Shader
// Posiciona o wireframe ou cubo translúcido sobre o bloco em foco
// =============================================================================

layout (location = 0) in vec3 aPos;

uniform mat4 u_Model;
uniform mat4 u_View;
uniform mat4 u_Projection;
uniform vec3 u_BlockPosition; // Posição (X, Y, Z) do bloco selecionado
uniform vec3 u_BoxMin = vec3(0.0);  // a caixa da forma dentro da célula (cubo inteiro por padrão)
uniform vec3 u_BoxSize = vec3(1.0);

void main()
{
    // Leve escalonamento (1.002) para evitar Z-fighting com o bloco base
    vec3 center = u_BoxMin + u_BoxSize * 0.5;
    vec3 scaledPos = (u_BoxMin + aPos * u_BoxSize - center) * 1.002 + center;
    vec4 worldPos = u_Model * vec4(scaledPos + u_BlockPosition, 1.0);
    gl_Position = u_Projection * u_View * worldPos;
}
