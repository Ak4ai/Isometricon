#version 330 core

in vec3 v_Pos;
out vec4 FragColor;

uniform vec4 u_GridColor;
uniform float u_FogAmount = 0.0;   // a névoa do /mestre: as linhas somem nela como o terreno (envGrade)
uniform vec3 u_FogCenter;
uniform int u_FogWar = 0;          // a névoa de guerra: as linhas do que ninguém viu somem (fog_of_war.py)
uniform sampler2D u_FogWarMap;
uniform mat4 u_FogInvModel;
uniform vec2 u_FogWarCenter;
uniform float u_FogWarRadius;
uniform vec2 u_FogWarOrigin;
uniform float u_FogWarSize;

void main() {
    float alpha = u_GridColor.a;
    if (u_FogAmount > 0.001) {
        vec3 offset = v_Pos - u_FogCenter;
        float reach = max(length(offset.xz) - mix(3.0, 1.2, u_FogAmount), 0.0);
        float density = mix(0.035, 0.34, pow(u_FogAmount, 1.4)) * (1.0 + 0.7 * clamp(-offset.y / 4.0, 0.0, 1.0));
        float f = (1.0 - exp(-pow(reach * density, 1.5))) * min(1.0, u_FogAmount * 1.6);
        alpha *= 1.0 - clamp(f * 1.15, 0.0, 1.0);
    }
    if (u_FogWar > 0) {
        vec3 world = (u_FogInvModel * vec4(v_Pos, 1.0)).xyz;
        float seen = 1.0 - smoothstep(u_FogWarRadius - 3.0, u_FogWarRadius, length(world.xz - u_FogWarCenter));
        if (u_FogWar == 1)
            seen = max(seen, smoothstep(0.4, 0.9, texture(u_FogWarMap, (world.xz - u_FogWarOrigin) / u_FogWarSize).r));
        alpha *= seen;
    }
    FragColor = vec4(u_GridColor.rgb, alpha);
}
