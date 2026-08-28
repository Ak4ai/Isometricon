# 🤝 Guia de Contribuição - Isometricon

Agradecemos o interesse em contribuir com o **Isometricon**! Para manter a qualidade e organização do código durante a disciplina de Computação Gráfica, siga as instruções abaixo:

---

## 🌿 Fluxo de Branches

* `main` ou `master`: Código estável e validado.
* `dev`: Branch de desenvolvimento principal para integração contínua.
* `feature/nome-da-feature`: Para novas funcionalidades (ex: `feature/face-culling`, `feature/perlin-noise`).
* `fix/nome-do-bug`: Para correções de bugs gráficos ou matemáticos.

---

## 📝 Padrão de Commits

Utilizamos o padrão de [Conventional Commits](https://www.conventionalcommits.org/):

* `feat(world): adiciona gerador de terreno com Perlin Noise 3D`
* `feat(shader): implementa iluminação direcional difusa`
* `fix(camera): corrige proporção ortográfica ao redimensionar janela`
* `perf(mesh): otimiza Face Culling na CPU reduzindo 70% dos polígonos`
* `docs(arch): atualiza contrato de integração com a Equipe B`

---

## 📐 Padrões de Código em Computação Gráfica

1. **Memória de GPU:** Todo recurso gerado via `glGen*` (buffers, arrays, shaders) deve ter sua correspondente desalocação `glDelete*`.
2. **Nomes Matemáticos Claros:** Variáveis de matrizes e vetores devem seguir convenções claras (`modelMatrix`, `viewMatrix`, `projMatrix`, `normalVec`).
3. **Comentários de Shaders:** Shaders GLSL devem documentar o propósito das variáveis `in`, `out` e `uniform`.
