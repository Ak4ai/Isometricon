# 📐 Módulo de Câmera (Isometric Camera)

Responsável por calcular e manter as matrizes de transformação de visualização e projeção para a perspectiva isométrica ortográfica:

## Responsabilidades:
1. **Matriz de Projeção Ortográfica (`P_ortho`):**
   - Controla o frustum ortográfico com base no aspecto da janela e fator de zoom.
   - Parâmetros: `left, right, bottom, top, nearPlane, farPlane`.
2. **Matriz de Visão (`View Matrix`):**
   - Posição da câmera em coordenadas esféricas ou transladadas.
   - Rotação padrão: Yaw de $45^\circ$, Pitch de $\approx 35.264^\circ$.
3. **Controles:**
   - Pan (arraste com botão do meio/direito do mouse).
   - Zoom (scroll do mouse alterando os limites ortográficos).
   - Rotação em passos de $90^\circ$ ou contínua em torno do eixo Y.
