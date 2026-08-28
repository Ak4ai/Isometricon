# 🎨 Guia de Shaders GLSL (OpenGL 3.3 Core)

## 1. Visão Geral dos Shaders

O *Isometricon* utiliza Shaders escritos em **GLSL 330 core** para implementar a projeção isométrica e iluminação tridimensional de baixo custo computacional.

---

## 2. Shaders do Terreno (`world.vert` e `world.frag`)

### 2.1. Vertex Shader (`world.vert`)
* **Entradas:**
  * `layout(location = 0) in vec3 aPos`: Posição do vértice no espaço do modelo.
  * `layout(location = 1) in vec3 aNormal`: Vetor normal da face do bloco.
  * `layout(location = 2) in vec3 aColor`: Cor base ou atributo do material.
  * `layout(location = 3) in vec3 aOffset`: Deslocamento da instância (se usando Instanced Rendering).
* **Uniforms:**
  * `mat4 u_Model`: Matriz do modelo.
  * `mat4 u_View`: Matriz de visão da câmera isométrica.
  * `mat4 u_Projection`: Matriz ortográfica.
* **Saídas:**
  * `out vec3 v_FragPos`: Posição no espaço de mundo.
  * `out vec3 v_Normal`: Vetor normal transformado.
  * `out vec3 v_Color`: Cor do vértice repassada.

### 2.2. Fragment Shader (`world.frag`)
* **Uniforms:**
  * `vec3 u_LightDir`: Direção normalizada da luz solar (ex: `normalize(vec3(0.5, 1.0, 0.3))`).
  * `vec3 u_LightColor`: Cor da luz (ex: `vec3(1.0, 0.95, 0.85)`).
  * `vec3 u_AmbientColor`: Intensidade da luz ambiente (ex: `vec3(0.35, 0.35, 0.4)`).
* **Cálculo de Iluminação:**
```glsl
float diff = max(dot(normalize(v_Normal), normalize(u_LightDir)), 0.0);
vec3 diffuse = diff * u_LightColor;
vec3 finalColor = (u_AmbientColor + diffuse) * v_Color;
FragColor = vec4(finalColor, 1.0);
```

---

## 3. Shaders de Destaque / Seleção (`highlight.vert` e `highlight.frag`)

Utilizados para desenhar a borda translúcida ou contorno amarelo/branco sobre o bloco selecionado ou em hover do mouse.
* **Modo de Blending:** `glEnable(GL_BLEND)` com `glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)`.
