#version 330 core

// Plataforma do editor: um quad unitário, posicionado e escalado por u_Model.
// v_Local guarda a célula em coordenadas locais (0..u_Size), para a grade
// acompanhar a rotação do tabuleiro sem desalinhar dos voxels.

layout (location = 0) in vec3 aPos;

uniform mat4 u_Model;
uniform mat4 u_View;
uniform mat4 u_Projection;
uniform vec2 u_Size;

out vec2 v_Local;

void main()
{
    v_Local = aPos.xz * u_Size;
    gl_Position = u_Projection * u_View * u_Model * vec4(aPos, 1.0);
}
