# 🤖 Testes e Verificações com o Claude

## 📌 Resumo

O código do Isometricon foi escrito pelo autor do projeto, que também tomou todas as decisões técnicas. O **Claude**
(assistente de IA da Anthropic, usado pelo Claude Code) entrou **só como apoio na avaliação**: ajudou a rodar as
medições, ler relatórios e imagens e apontar o que parecia errado depois de cada mudança. Esta página mostra como esse
trabalho foi organizado e leva às páginas que guardam os resultados.

> **Sobre a autoria.** Quem escreveu o código e decidiu o que adotar, descartar ou reverter foi o autor. O Claude
> avaliou os testes e deu o retorno; a decisão final nunca foi dele. Ele não é contribuidor do repositório.

---

## 🧭 Camadas de verificação

| Camada | O que garante | Onde ver |
| :--- | :--- | :--- |
| **Testes automatizados** | Regressão do motor, câmera, mundo, cavernas, colisão, roupas, cabelos, animação, menus e integração: cerca de 450 funções de teste em 36 arquivos de `tests/`, rodadas na CI. | `tests/` e [[Arquitetura do Motor A\|Arquitetura-do-Motor]] |
| **Bateria de robustez** | Veste cada roupa do catálogo nos dois corpos, passa por poses e mede *esticado*, *pele furando* e *buraco* sem depender de olho humano. | [[Bateria de Robustez\|Bateria-de-Robustez]] |
| **Inspeção por imagem** | Aproxima a câmera do que a bateria marcou, com e sem marcação, para separar defeito real de falso alarme. | [[Bateria de Robustez\|Bateria-de-Robustez]] (validação de 06/10/2026) |
| **Ground truth do Roblox Studio** | Compara a malha do nosso motor com a exportada pelo Roblox (erro mediano, percentil, arestas esticadas). | [[Validação com Roblox Studio\|Validacao-com-Roblox]] |
| **Mapa do caminho** | Do primeiro encaixe ao modelo atual: problema, teste que mostrou e ajuste. | [[Mapa de Testes e Ajustes\|Mapa-de-Testes-e-Ajustes]] |
| **Registro de experimentos** | Cada hipótese, o resultado medido e a decisão, **inclusive o que foi descartado**. | [[Histórico de Experimentos\|Historico-de-Experimentos]] |
| **Pendências** | O que os testes mostraram que ainda não está resolvido. | [[Pendências e Roadmap\|Pendencias]] |

---

## 🔁 O ciclo de trabalho

1. **Hipótese:** uma ideia de correção (por exemplo, "pesos harmônicos sobre a malha da roupa").
2. **Medida:** a bateria rodava no catálogo inteiro (204 combinações roupa × corpo), em vez de olhar uma peça só; o
   Claude ajudava a ler os resultados.
3. **Comparação:** a rodada nova era comparada com a anterior peça por peça (`comparacao.md`). A regra do projeto:
   **uma mudança só entra se nenhuma peça piorar**.
4. **Conferência por imagem:** o que a medida marcava era visto de perto, para saber se era defeito real ou falso
   alarme.
5. **Decisão do autor e registro:** adotar, descartar ou reverter, e anotar o porquê no
   [[Histórico de Experimentos|Historico-de-Experimentos]].

---

## 🔎 Exemplos concretos

- **A medida de buraco foi corrigida pela inspeção.** A conferência por imagem mostrou que boa parte dos "buracos"
  era pele escondida com tecido logo abaixo (pés de meia-calça, golas de fantasia). Com a regra dos 3 cm, as falhas
  por buraco caíram de 22 para 6.
- **Uma correção que funcionava foi revertida.** A "forma própria para tecido pendurado" fechou as frestas do
  Long Dress, mas a bateria mostrou capas e fantasias piorando (antebraço da Cloak descoberto, buraco 171 → 818). O
  encaixe voltou à versão anterior (cache v37).
- **A bateria evoluiu junto com o código.** Falhas: 73 → 39 → 33 → 17 → 13 nas rodadas sucessivas; na rodada de
  09/10/2026, 116 ok, 75 atenção e 13 falha, com nenhuma peça pior que na anterior e 89 melhores.
- **Hipóteses negativas também ficaram registradas.** Vários experimentos (suavizar pesos, DQS, colisão por cápsulas)
  não deram resultado e estão documentados para ninguém repetir o caminho.

---

## 🖼️ Galeria de conferência

Durante as verificações, as imagens que o Claude analisou eram salvas automaticamente no arquivo `galeria.md` do
repositório local (gerado pelo `claude-watcher`), com a origem de cada uma. Ele serve de rastro do que foi visto em
cada rodada; as imagens relevantes estão nas páginas acima.

---

## ⚠️ Limites do método

- A avaliação do Claude não é a referência de correção: a referência é o **Roblox Studio** (ground truth) e as medidas objetivas
  da bateria. Leitura de imagem ajuda a triar, não a decidir sozinha.
- Os limites da bateria (600 / 4000 cm² de esticado, 100 / 400 de pele furando, 100 / 500 de buraco) foram fixados
  olhando as miniaturas do catálogo inteiro; mudam se o critério visual mudar.
- Algumas falhas continuam abertas (fantasias de corpo inteiro, frestas na saia do Long Dress); ver
  [[Pendências e Roadmap|Pendencias]].
