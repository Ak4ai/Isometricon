#version 330 core
// As nuvens da névoa de guerra (src/rendering/cloud_fog.py): posição no mundo, sombra chapada da face e opacidade.
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec2 aShadeAlpha;

uniform mat4 u_MVP;

out vec3 v_World;
out float v_Shade;
out float v_Alpha;

void main() {
    v_World = aPos;
    v_Shade = aShadeAlpha.x;
    v_Alpha = aShadeAlpha.y;
    gl_Position = u_MVP * vec4(aPos, 1.0);
}
