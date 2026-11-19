#version 330 core

layout(location = 0) in vec3 aPos;

uniform mat4 u_Model;
uniform mat4 u_View;
uniform mat4 u_Projection;

out vec3 v_Pos;   // no espaço desenhado (o mesmo da névoa do shader do mundo)

void main() {
    vec4 drawn = u_Model * vec4(aPos, 1.0);
    v_Pos = drawn.xyz;
    gl_Position = u_Projection * u_View * drawn;
}
