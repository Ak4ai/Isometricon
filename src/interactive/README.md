# 🟦 Motor Interativo — Equipe B

> 📖 **Leia também:** [Arquitetura Completa da Equipe B](../docs/EQUIPE_B_ARCHITECTURE.md) | [Contrato de Integração A↔B](../docs/INTEGRATION_SPEC.md)

---

## Visão Geral

O diretório `src/interactive/` contém todos os módulos da **Equipe B (Motor Interativo)**. Enquanto a Equipe A constrói o mundo tridimensional, a Equipe B o torna interativo: detecta cliques, renderiza destaques, posiciona tokens e exibe a UI do VTT.

---

## Módulos

| Arquivo | Responsabilidade | Issue |
|:--- |:--- |:---: |
| `raycasting.py` | Converte clique 2D → raio 3D → bloco selecionado | #27 |
| `highlight.py` | Shaders de hover/seleção com efeito pulsante | #28 |
| `grid_overlay.py` | Grade quadriculada sobre o terreno (GL_LINES) | #29 |
| `token_system.py` | Miniaturas com matrizes TRS e movimento em grade | #30 |
| `ui_overlay.py` | Fichas de RPG e painéis em OpenGL 2D ortográfico | #31 |

---

## Controles da Equipe B

| Ação | Controle |
|:--- |:--- |
| Selecionar bloco / mover token | Clique Esquerdo |
| Selecionar token | Clique Esquerdo sobre token |
| Ligar/Desligar grid | **G** |
| Ligar/Desligar UI | **H** |
| Próximo turno | **Tab** |
| Desselecionar | **ESC** |
| Remover token | **Delete** |
| Adicionar token | **N** + Clique |

---

## Como Iniciar o Desenvolvimento (Equipe B)

1. **Clone e instale:**
   ```bash
   git clone https://github.com/Ak4ai/Isometricon.git
   cd Isometricon
   pip install -r requirements.txt
   ```

2. **Pegue uma issue pelo GitHub:**
   ```bash
   gh issue develop <NUMERO> --checkout
   ```

3. **Rode o projeto:**
   ```bash
   python src/main.py
   ```

4. **Execute os testes:**
   ```bash
   pytest -v
   ```

---

## Arquitetura de Integração

```
src/integration/          ← Bridge A↔B (mantido pela Equipe A)
    voxel_provider.py     ← Consulta de blocos do mundo
    camera_provider.py    ← Estado da câmera (view/proj)
    highlight_bridge.py   ← Ativa shaders de destaque

src/interactive/          ← DOMÍNIO DA EQUIPE B
    raycasting.py
    highlight.py
    grid_overlay.py
    token_system.py
    ui_overlay.py
```

Consulte [INTEGRATION_SPEC.md](../../docs/INTEGRATION_SPEC.md) para o contrato completo de interfaces.
