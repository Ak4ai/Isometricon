# Templates de Documentação — ISO/IEC/IEEE 29148:2018

Esta pasta contém templates em Markdown para documentação de requisitos de software do projeto, alinhados à norma **ISO/IEC/IEEE 29148:2018**.

## Arquivos

| Arquivo | Propósito |
|---------|-----------|
| `TEMPLATE_SRS.md` | Template completo para a **Especificação de Requisitos de Software (SRS)**. Segue a estrutura normativa da seção 9.6 da norma 2018. |
| `TEMPLATE_REQUISITO.md` | Template de **ficha de requisito individual**. Garante que cada requisito atenda às características da seção 5.2.5 e aos atributos da seção 5.2.8. |

## Como usar

### 1. Criar o SRS do projeto
1. Faça uma cópia de `TEMPLATE_SRS.md` para a raiz do projeto (ou pasta `docs/`).
2. Renomeie para algo como `SRS_NOME_DO_PROJETO_v1.0.md`.
3. Preencha as seções 1 e 2 (Introdução e Visão Geral do Produto) primeiro.
4. Para cada requisito identificado, preencha a ficha `TEMPLATE_REQUISITO.md`.
5. Transfira o conteúdo consolidado dos requisitos para as seções 3 e 4 do SRS.

### 2. Criar fichas de requisitos
1. Faça uma cópia de `TEMPLATE_REQUISITO.md` para cada requisito.
2. Nomeie os arquivos de forma consistente: `REQ-[CATEGORIA]-[NNN].md` (ex: `REQ-FUNC-001.md`).
3. Preencha a tabela de **Análise de Conformidade com a Norma** para garantir qualidade antes da aprovação.

## Princípios da norma aplicados

### Características de um bom requisito (ISO/IEC/IEEE 29148:2018 — 5.2.5)
Todo requisito deve ser:
- **Necessário** — essencial para o sistema.
- **Apropriado** — nível de detalhe compatível com a entidade.
- **Não ambíguo** — uma única interpretação possível.
- **Completo** — não depende de informações externas para ser compreendido.
- **Singular** — um requisito por vez.
- **Factível** — realizável dentro das restrições.
- **Verificável** — comprovável de forma objetiva.
- **Correto** — representa fielmente a necessidade.
- **Conforme** — segue o padrão de escrita definido.

### Linguagem a ser evitada (ISO/IEC/IEEE 29148:2018 — 5.2.7)
Evite nos requisitos:
- Superlativos ("melhor", "mais")
- Linguagem subjetiva ("fácil de usar", "amigável")
- Pronomes vagos ("isso", "aquilo")
- Termos abertos ("se aplicável", "no mínimo", "incluindo mas não se limitando a")
- Termos de totalidade ("sempre", "nunca", "todos")
- Comparativos ("melhor que", "maior qualidade")

> **Regra de ouro:** Diga **O QUE** é necessário, não **COMO** fazer.
