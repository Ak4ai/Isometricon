#version 330 core

// Superfície da plataforma + grade + borda + célula sob o cursor.
// Tudo procedural, sem textura: a plataforma é desenhada por shader.

in vec2 v_Local;
out vec4 FragColor;

uniform vec2  u_Size;
uniform vec4  u_BaseColor;
uniform vec4  u_LineColor;
uniform vec4  u_BorderColor;
uniform vec2  u_Cursor;
uniform float u_CursorOn;
uniform vec4  u_CursorColor;
uniform float u_GridOn;
uniform float u_Time;

float grid_line(vec2 p)
{
    vec2 width = fwidth(p) * 1.8 + vec2(1e-4);
    vec2 distance_to_line = abs(fract(p - 0.5) - 0.5) / width;
    return 1.0 - min(min(distance_to_line.x, distance_to_line.y), 1.0);
}

float border_line(vec2 p, vec2 size)
{
    vec2 edge = min(p, size - p);
    vec2 width = fwidth(p) * 2.5 + vec2(1e-4);
    vec2 distance_to_edge = abs(edge) / width;
    return 1.0 - min(min(distance_to_edge.x, distance_to_edge.y), 1.0);
}

void main()
{
    vec2 p = v_Local;
    vec2 cell = floor(p);
    vec2 inside = fract(p);

    // Fundo levemente xadrez para dar noção de escala.
    float checker = mod(cell.x + cell.y, 2.0);
    vec3 base = u_BaseColor.rgb * mix(0.86, 1.0, checker);
    float alpha = u_BaseColor.a;

    float line = grid_line(p) * u_GridOn;
    float border = border_line(p, u_Size);
    vec3 colour = mix(base, u_LineColor.rgb, line * u_LineColor.a);
    alpha = max(alpha, line * u_LineColor.a);

    // Borda do volume de edição, sempre visível.
    colour = mix(colour, u_BorderColor.rgb, border);
    alpha = max(alpha, border * u_BorderColor.a);

    // Célula sob o cursor, com um pulso leve para não parecer estática.
    float cursor_cell = u_CursorOn *
        step(abs(cell.x - u_Cursor.x), 0.25) *
        step(abs(cell.y - u_Cursor.y), 0.25);
    float cursor_inner = cursor_cell *
        step(max(abs(inside.x - 0.5), abs(inside.y - 0.5)), 0.42);
    float pulse = 0.75 + 0.25 * sin(u_Time * 4.0);
    vec3 cursor_rgb = u_CursorColor.rgb * pulse;
    colour = mix(colour, cursor_rgb, cursor_inner * u_CursorColor.a);
    alpha = max(alpha, cursor_inner * u_CursorColor.a);

    if (alpha < 0.01)
        discard;
    FragColor = vec4(colour, alpha);
}
