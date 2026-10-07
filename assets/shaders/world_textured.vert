#version 330 core

// =============================================================================
// Isometricon - Textured World Vertex Shader (GLSL 330 core)
// Suporte a coordenadas UV para Texture Atlas e Matrizes MVP
// =============================================================================

layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aNormal;
layout (location = 2) in vec2 aTexCoord;
layout (location = 3) in vec3 aColor;
layout (location = 4) in vec4 aBones;    // bone numbers of a skinned mesh
layout (location = 5) in vec4 aWeights;  // and how much each one moves the vertex

uniform mat4 u_Model;
uniform mat4 u_View;
uniform mat4 u_Projection;
uniform bool u_Skinned;    // the mesh is in its bind pose and u_Bones poses it
uniform mat4 u_Bones[24];

out vec3 v_FragPos;
out vec3 v_Normal;
out vec2 v_TexCoord;
out vec3 v_Color;

void main()
{
    vec4 localPos = vec4(aPos, 1.0);
    vec3 localNormal = aNormal;
    if (u_Skinned)
    {
        mat4 pose = aWeights.x * u_Bones[int(aBones.x)] + aWeights.y * u_Bones[int(aBones.y)]
                  + aWeights.z * u_Bones[int(aBones.z)] + aWeights.w * u_Bones[int(aBones.w)];
        localPos = pose * localPos;
        localNormal = mat3(pose) * aNormal;
    }
    vec4 worldPos = u_Model * localPos;
    v_FragPos = worldPos.xyz;
    v_Normal = mat3(u_Model) * localNormal;
    v_TexCoord = aTexCoord;
    v_Color = aColor;

    gl_Position = u_Projection * u_View * worldPos;
}
