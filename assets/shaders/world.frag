#version 330 core

// =============================================================================
// Isometricon - World Fragment Shader (GLSL 330 core)
// Iluminação Direcional Lambertiana + Luz Ambiente para faces 3D de blocos
// =============================================================================

in vec3 v_FragPos;
in vec3 v_Normal;
in vec3 v_Color;

out vec4 FragColor;

uniform vec3 u_LightDir;     // Direção da luz do sol normalizada
uniform vec3 u_LightColor;   // Cor da luz incidente
uniform vec3 u_AmbientColor; // Cor e intensidade da luz ambiente

void main()
{
    vec3 norm = normalize(v_Normal);
    vec3 lightDir = normalize(u_LightDir);
    
    // Componente Difuso (Lambertiano)
    float diff = max(dot(norm, lightDir), 0.0);
    vec3 diffuse = diff * u_LightColor;
    
    // Sombreamento final do fragmento
    vec3 result = (u_AmbientColor + diffuse) * v_Color;
    
    FragColor = vec4(result, 1.0);
}
