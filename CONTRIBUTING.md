# 🤝 Guia de Contribuição - Isometricon

Agradecemos o interesse em contribuir com o **Isometricon**! Para manter a qualidade, rastreabilidade e estabilidade do código da equipe, siga o fluxo de desenvolvimento abaixo:

---

## 🌿 1. Como Pegar uma Tarefa (Issue) e Criar sua Branch

Cada funcionalidade ou correção deve ser desenvolvida em uma branch dedicada conectada a uma **Issue**:

### 🥇 Opção 1: Direto pelo GitHub Web (1 Clique - Recomendado)
1. Abra a Issue que você vai fazer no GitHub (ex: [Issue #3](https://github.com/Ak4ai/Isometricon/issues/3)).
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
* `test(version): adiciona testes unitários para detecção de branch`

---

## 🧪 3. Validação Local Antes de Enviar o Código

Antes de enviar sua branch para o GitHub, certifique-se de que tudo está funcionando:

1. **Rode a aplicação**:
   ```bash
   python src/main.py
   ```
   *(Ou pressione **F5** no VS Code).*
2. **Execute a suíte de testes unitários**:
   ```bash
   pytest -v
   ```
3. **(Opcional) Teste a compilação do executável**:
   ```bash
   python scripts/build.py
   ```
   *(Ou pressione **Ctrl + Shift + B** no VS Code).*

---

## 🚀 4. Como Enviar (Push) sem Erros de Terminal

Quando os nomes das branches forem longos, para evitar que o terminal quebre o texto em várias linhas, use o atalho:

```bash
git push -u origin HEAD
```
> 💡 **Dica de Ouro**: O comando `git push -u origin HEAD` envia a sua branch atual diretamente para o GitHub sem você precisar copiar ou digitar o nome dela!

---

## 📋 5. Abrindo e Preenchendo o Pull Request (PR)

1. Acesse o repositório no GitHub: [https://github.com/Ak4ai/Isometricon](https://github.com/Ak4ai/Isometricon)
2. Clique no botão verde **"Compare & pull request"**.
3. O GitHub carregará o **formulário padrão** na caixa de descrição. Preencha-o da seguinte forma:
   - **Issue Vinculada**:
     - Se este PR conclui a issue por completo: coloque `Closes #NUMERO` (ex: `Closes #3`) para fechá-la automaticamente.
     - Se este PR faz apenas parte da tarefa: coloque `Part of #NUMERO` ou `Refs #NUMERO` (a issue continuará aberta).
   - **Tipo de Alteração**: Marque com um `x` entre os colchetes (ex: `- [x] ✨ Nova funcionalidade`).
   - **Checklist de Validação**: Marque com `[x]` os itens que você testou.
4. Clique em **"Create pull request"**.
5. Aguarde a esteira de testes (CI) validar o código em verde ✅.
6. Clique em **"Squash and merge"** -> **"Confirm squash and merge"**.

---

## 🏷️ 6. Lançando uma Nova Release Oficial

Quando a equipe atingir um marco ou Milestone:
1. Abra o arquivo [`VERSION.txt`](VERSION.txt) na raiz e atualize o número de versão (ex: de `0.1.0` para `0.2.0`).
2. Envie o commit para a `main` via Pull Request.
3. O GitHub Actions iniciará automaticamente a pipeline de release e publicará os 3 pacotes compilados (Windows Portable, Windows Installer e Linux) na aba **[Releases](https://github.com/Ak4ai/Isometricon/releases)**.

---

## 📐 7. Padrões de Código em Computação Gráfica (OpenGL Raiz)

1. **Memória de GPU:** Todo recurso gerado via `glGen*` (buffers, VAO, VBO, shaders) deve ter sua correspondente desalocação `glDelete*`.
2. **Nomes Matemáticos Claros:** Variáveis de matrizes e vetores devem seguir convenções claras (`model_matrix`, `view_matrix`, `projection_matrix`, `normal_vec`).
3. **Comentários de Shaders:** Shaders GLSL devem documentar o propósito das variáveis `in`, `out` e `uniform`.
