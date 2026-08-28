# 🔗 Especificação do Contrato de Integração (Equipe A $\leftrightarrow$ Equipe B)

## 1. Visão Geral

Para garantir total independência de desenvolvimento durante os 30 dias e uma integração final simples e sem atritos, definem-se os seguintes contratos de dados e serviços entre a **Equipe A (Motor do Mundo)** e a **Equipe B (Motor Interativo)**.

---

## 2. Contrato de Acesso a Dados do Terreno

A Equipe A expõe métodos de consulta rápida para que a Equipe B possa realizar Raycasting 3D (Mouse Picking) e posicionamento de miniaturas:

### 2.1. Estrutura de Consulta Espacial
```typescript
interface VoxelGridProvider {
  // Retorna o tipo de bloco na coordenada do mundo (x, y, z)
  getBlockAt(worldX: number, worldY: number, worldZ: number): BlockType;
  
  // Retorna se uma coordenada é sólida (não-ar) para colisão de miniatura
  isSolid(worldX: number, worldY: number, worldZ: number): boolean;
  
  // Retorna a altura máxima (Y) do terreno em uma coluna (X, Z) para apoiar miniatura
  getTopSolidBlock(worldX: number, worldZ: number): number;
  
  // Retorna a AABB (Axis-Aligned Bounding Box) de um bloco
  getBlockBoundingBox(worldX: number, worldY: number, worldZ: number): AABB;
}
```

---

## 3. Contrato de Renderização de Destaque (Hover/Seleção)

Quando a Equipe B detectar a interseção do raio do mouse com um bloco $(x, y, z)$, ela pode solicitar à camada de renderização a ativação do efeito de destaque:

```typescript
interface HighlightRenderer {
  // Define o bloco atualmente sob foco do cursor (hover)
  setHighlightedBlock(worldX: number, worldY: number, worldZ: number, color: Vec4): void;
  
  // Limpa a seleção ativa
  clearHighlight(): void;
  
  // Ativa/Desativa a renderização do grid quadriculado no topo dos blocos
  setGridOverlayVisible(visible: boolean): void;
}
```

---

## 4. Matrizes de Câmera Compartilhadas

Para que a Equipe B consiga converter coordenadas de tela $(x_{\text{mouse}}, y_{\text{mouse}})$ em um raio 3D, a Equipe A fornece as matrizes ativas:

* **`mat4 ViewMatrix`**: Matriz de visão da câmera isométrica.
* **`mat4 ProjectionMatrix`**: Matriz de projeção ortográfica.
* **`vec4 Viewport`**: $(x, y, \text{width}, \text{height})$.

$$\text{Ray}_{\text{origin}} = \mathbf{V}^{-1} \times \mathbf{P}^{-1} \times (x_{\text{ndc}}, y_{\text{ndc}}, -1, 1)$$
$$\text{Ray}_{\text{direction}} = \text{normalize}(\mathbf{V}^{-1} \times \mathbf{P}^{-1} \times (x_{\text{ndc}}, y_{\text{ndc}}, 1, 1) - \text{Ray}_{\text{origin}})$$
