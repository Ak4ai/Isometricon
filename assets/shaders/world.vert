#version 330 core

// =============================================================================
// Isometricon - World Vertex Shader (GLSL 330 core)
// Transforma os vértices dos blocos com matrizes MVP e calcula vetores normais
// =============================================================================

layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aNormal;
layout (location = 2) in vec3 aColor;
layout (location = 3) in vec3 aInstanceOffset; // Para renderização instanciada opcional

uniform mat4 u_Model;
uniform mat4 u_View;
uniform mat4 u_Projection;
uniform bool u_UseInstancing;

out vec3 v_FragPos;
out vec3 v_Normal;
out vec3 v_Color;

void main()
{
    vec3 localPos = aPos;
    if (u_UseInstancing) {
        localPos += aInstanceOffset;
    }
    
    vec4 worldPos = u_Model * vec4(localPos, 1.0);
    v_FragPos = worldPos.xyz;
    
    // Normal no espaço de mundo (matriz normal)
    v_Normal = mat3(transpose(inverse(u_Model))) * aNormal;
    v_Color = aColor;
    
    // Projeção final na tela
    gl_Position = u_Projection * u_View * worldPos;
}
