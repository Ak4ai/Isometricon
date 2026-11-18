#version 330 core
// As nuvens da névoa de guerra (src/rendering/cloud_fog.py): posição no mundo, sombra chapada da face, opacidade e
// quanto o vértice está abaixo do topo da nuvem.
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec2 aShadeAlpha;
layout(location = 2) in float aBelow;

uniform mat4 u_MVP;

out vec3 v_World;
out float v_Shade;
out float v_Alpha;
out float v_Below;

void main() {
    v_World = aPos;
    v_Shade = aShadeAlpha.x;
    v_Alpha = aShadeAlpha.y;
    v_Below = aBelow;
    gl_Position = u_MVP * vec4(aPos, 1.0);
}
