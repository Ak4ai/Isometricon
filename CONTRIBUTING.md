# 🤝 Guia de Contribuição - Isometricon

Agradecemos o interesse em contribuir com o **Isometricon**! Para manter a qualidade, rastreabilidade e estabilidade do código da equipe, siga o fluxo de desenvolvimento abaixo:

---

## 🌿 1. Como Pegar uma Tarefa (Issue) e Criar sua Branch

Cada funcionalidade ou correção deve ser desenvolvida em uma branch dedicada conectada a uma **Issue**:

### 🥇 Opção 1: Direto pelo GitHub Web (1 Clique)
1. Abra a Issue que você vai fazer no GitHub (ex: [Issue #2](https://github.com/Ak4ai/Isometricon/issues/2)).
2. Na coluna lateral direita, na seção **Development**, clique em **"Create a branch"**.
3. O GitHub criará a branch e fornecerá os dois comandos para rodar no seu terminal:
   ```bash
   git fetch origin
   git checkout <NOME-DA-BRANCH>
   ```

### 🥈 Opção 2: Pelo Terminal via GitHub CLI
```bash
gh issue develop <NUMERO_DA_ISSUE> --checkout
```

---

## 📝 2. Padrão de Commits

Utilizamos o padrão de [Conventional Commits](https://www.conventionalcommits.org/). Ao concluir uma tarefa, inclua o termo `closes #NUMERO` na mensagem:

* `feat(math): implementa matrizes 4x4 com numpy (closes #2)`
* `feat(shader): implementa compilador de shaders GLSL 330 (closes #3)`
* `feat(world): adiciona algoritmo de face culling na CPU (closes #6)`
* `fix(camera): corrige proporção ortográfica ao redimensionar viewport`
* `test(version): adiciona testes unitarios para deteccao de branch`

---

## 🧪 3. Validação Local Antes de Abrir o PR

Antes de enviar sua branch para o GitHub, certifique-se de que tudo está funcionando:

1. **Rode a aplicação**:
   ```bash
   python src/main.py
   ```
2. **Execute a suíte de testes unitários**:
   ```bash
   pytest -v
   ```

---

## 🚀 4. Abrindo o Pull Request (PR)

Envie sua branch para o GitHub:
```bash
git push -u origin <NOME-DA-SUA-BRANCH>
```

Em seguida, abra o Pull Request pelo GitHub Web ou pela CLI:
```bash
gh pr create
```

Assim que a esteira de CI validar os testes e o PR for aprovado e mesclado na `main`, a issue correspondente será fechada automaticamente.

---

## 📐 5. Padrões de Código em Computação Gráfica (OpenGL Raiz)

1. **Memória de GPU:** Todo recurso gerado via `glGen*` (buffers, VAO, VBO, shaders) deve ter sua correspondente desalocação `glDelete*`.
2. **Nomes Matemáticos Claros:** Variáveis de matrizes e vetores devem seguir convenções claras (`model_matrix`, `view_matrix`, `projection_matrix`, `normal_vec`).
3. **Comentários de Shaders:** Shaders GLSL devem documentar o propósito das variáveis `in`, `out` e `uniform`.
