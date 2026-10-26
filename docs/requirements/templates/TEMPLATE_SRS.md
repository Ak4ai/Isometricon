# Especificação de Requisitos de Software (SRS)

> **Norma de referência:** ISO/IEC/IEEE 29148:2018  
> **Projeto:** `[NOME DO PRODUTO/SISTEMA]`  
> **Versão:** `1.0`  
> **Data:** `DD/MM/AAAA`  
> **Autor:** `[NOME]`

---

## Histórico de Revisões

| Versão | Data | Autor | Alterações |
|--------|------|-------|------------|
| 1.0 | DD/MM/AAAA | `[Nome]` | Rascunho inicial |

---

## 1. Introdução

### 1.1 Propósito (Purpose)
Delinear o propósito do software a ser especificado.

> *Exemplo: Este documento especifica os requisitos do sistema `[Nome do Sistema]`, responsável por [...].*

### 1.2 Escopo (Scope)
Descrever o escopo do software considerando:
- **a)** Identificação do(s) produto(s) de software pelo nome;
- **b)** Explicação do que o produto fará;
- **c)** Descrição da aplicação, incluindo benefícios, objetivos e metas;
- **d)** Consistência com especificações de nível superior (ex: ERS do sistema), se existirem.

### 1.3 Referências (References)
Liste documentos ou endereços web aos quais este SRS se refere (contratos, padrões, ERS, guias de estilo, etc.).

| Referência | Título | Versão | Data | Fonte |
|------------|--------|--------|------|-------|
| [REF-001] | | | | |

### 1.4 Termos (Terms)
Defina termos necessários para interpretar corretamente este documento.

| Termo | Definição |
|-------|-----------|
| | |

### 1.5 Abreviações (Abbreviations)

| Abreviação | Significado |
|------------|-------------|
| SRS | Software Requirements Specification |

---

## 2. Visão Geral do Produto (Product Overview)

### 2.1 Perspectiva do Produto (Product Perspective)
Definir a relação do sistema com outros produtos relacionados. Se o produto for um elemento de um sistema maior:
- Relacione os requisitos do sistema maior à funcionalidade coberta por este SRS;
- Identifique as interfaces entre o produto e o sistema maior;
- Considere um diagrama de blocos mostrando os principais elementos, interconexões e interfaces externas.

Descreva como o software opera dentro das seguintes restrições:

#### 2.1.1 Interfaces de Sistema (System Interfaces)
Liste cada interface de sistema e identifique a funcionalidade do software para atender ao requisito do sistema e a descrição da interface para corresponder ao sistema.

#### 2.1.2 Interfaces de Usuário (User Interfaces)
Especifique as características lógicas de cada interface entre o produto e seus usuários.

> *Nota: Um guia de estilo de interface pode fornecer regras consistentes para organização, codificação e interação do usuário com o sistema.*

#### 2.1.3 Interfaces de Hardware (Hardware Interfaces)
Especifique as características lógicas de cada interface entre o produto e os elementos de hardware do sistema (número de portas, conjuntos de instruções, dispositivos suportados, protocolos, etc.).

#### 2.1.4 Interfaces de Software (Software Interfaces)
Especifique o uso de outros produtos de software necessários e interfaces com outros sistemas. Para cada produto, informe:
- a) Nome;
- b) Mnemônico;
- c) Número da especificação;
- d) Número da versão;
- e) Fonte.

Para cada interface, especifique:
- a) Discussão do propósito do software de interface;
- b) Definição da interface em termos de conteúdo e formato de mensagens.

#### 2.1.5 Interfaces de Comunicação (Communication Interfaces)
Especifique as várias interfaces de comunicação, como protocolos de rede local.

#### 2.1.6 Restrições de Memória (Memory Constraints)
Especifique quaisquer características e limites aplicáveis à memória primária e secundária.

#### 2.1.7 Operações (Operations)
Especifique as operações normais e especiais exigidas pelo usuário, como:
- a) Vários modos de operação na organização do usuário;
- b) Períodos de operação interativa e não assistida;
- c) Funções de suporte ao processamento de dados;
- d) Operações de backup e recuperação.

#### 2.1.8 Requisitos de Adaptação de Site (Site Adaptation Requirements)
Inclua:
- a) Definição dos requisitos para quaisquer sequências de dados ou inicialização específicas de um site;
- b) Especificação dos recursos relacionados ao site ou missão que devem ser modificados para adaptar o software a uma instalação específica.

#### 2.1.9 Interfaces com Serviços (Interfaces with Services)
Especifique interações com serviços (por exemplo, SaaS ou serviços em nuvem).

### 2.2 Funções do Produto (Product Functions)
Forneça um resumo das principais funções que o software executará.

> *Nota: Casos de uso, histórias de usuário e cenários também podem ser usados para descrever as funções do produto.*

Para fins de clareza:
- a) As funções do produto devem ser organizadas de forma compreensível;
- b) Métodos textuais ou gráficos podem ser usados para mostrar as diferentes funções e seus relacionamentos (sem representar design de produto).

### 2.3 Características do Usuário (User Characteristics)
Descreva as características gerais dos grupos de usuários pretendidos, incluindo características que podem influenciar a usabilidade, como nível educacional, experiência, deficiências e expertise técnica.

> *Esta descrição não deve declarar requisitos específicos, mas sim os motivos pelos quais certos requisitos específicos são posteriormente especificados.*

### 2.4 Limitações (Limitations)
Forneça uma descrição geral de quaisquer outros itens que limitarão as opções do fornecedor, incluindo:
- a) Requisitos e políticas regulatórias;
- b) Limitações de hardware;
- c) Interfaces para outras aplicações;
- d) Operação paralela;
- e) Funções de auditoria;
- f) Funções de controle;
- g) Requisitos de linguagem de alto nível;
- h) Protocolos de handshake;
- i) Requisitos de qualidade;
- j) Criticidade da aplicação;
- k) Considerações de segurança;
- l) Considerações físicas/mentais;
- m) Limitações originadas de outros sistemas.

### 2.5 Suposições e Dependências (Assumptions and Dependencies)
Liste cada um dos fatores que afetam os requisitos declarados no SRS. Esses fatores não são restrições de design, mas quaisquer alterações neles podem afetar os requisitos.

> *Exemplo: Uma suposição pode ser a disponibilidade de um sistema operacional específico no hardware designado para o produto de software.*

### 2.6 Distribuição de Requisitos (Apportioning of Requirements)
Distribua os requisitos de software entre elementos de software. Para requisitos que exigirão implementação em vários elementos, ou quando a alocação ainda estiver indefinida, isso deve ser declarado. Uma tabela de referência cruzada por função e elemento de software deve ser usada para resumir as alocações.

Identifique requisitos que possam ser adiados para versões futuras do sistema.

### 2.7 Requisitos Especificados (Specified Requirements)
Especifique os requisitos do sistema de software com um nível de detalhe suficiente para design, desenvolvimento e verificação do incremento ou release em processo.

Os requisitos devem:
- a) Estar em conformidade com todas as características descritas na seção 5.2 da ISO/IEC/IEEE 29148:2018;
- b) Ter referência cruzada com versões anteriores ou documentos relacionados;
- c) Ser identificáveis de forma única;
- d) Descrever cada entrada (estímulo) no sistema, cada saída (resposta) e todas as funções realizadas.

---

## 3. Requisitos Específicos (Specific Requirements)

### 3.1 Interfaces Externas (External Interfaces)
Defina todas as entradas e saídas do sistema de software. A descrição deve complementar (e não repetir) as descrições de interface em 2.1.1 a 2.1.5.

Cada interface definida deve incluir:
- a) Nome do item;
- b) Descrição do propósito;
- c) Fonte da entrada ou destino da saída;
- d) Faixa válida, precisão e/ou tolerância;
- e) Unidades de medida;
- f) Temporização (timing);
- g) Relacionamentos com outras entradas/saídas;
- h) Formatos de dados;
- i) Formatos de comandos;
- j) Itens de dados ou informações incluídas na entrada e saída.

### 3.2 Funções (Functions)
Defina as ações fundamentais que devem ocorrer no software ao aceitar e processar entradas e ao processar e gerar saídas, incluindo:
- a) Verificações de validade nas entradas;
- b) Sequência exata de operações;
- c) Respostas a situações anormais, incluindo:
  1) Overflow;
  2) Falhas em facilidades de comunicação;
  3) Falhas e defeitos de hardware;
  4) Tratamento e recuperação de erros;
- d) Efeito de parâmetros;
- e) Relação de saídas com entradas, incluindo:
  1) Sequências de entrada/saída;
  2) Fórmulas para conversão de entrada em saída.

> *Pode ser apropriado particionar os requisitos funcionais em subfunções. Isso não implica que o design do software também será particionado dessa forma.*

### 3.3 Requisitos de Usabilidade (Usability Requirements)
Defina requisitos e objetivos de usabilidade e qualidade em uso para o sistema de software, que podem incluir critérios mensuráveis de efetividade, eficiência, satisfação e evitação de danos que poderiam surgir do uso em contextos específicos.

> *Nota: Orientações adicionais sobre requisitos de usabilidade podem ser encontradas na ISO/IEC TR 25060.*

### 3.4 Requisitos de Desempenho (Performance Requirements)
Especifique os requisitos numéricos estáticos e dinâmicos impostos ao software ou à interação humana com o software como um todo.

**Requisitos numéricos estáticos** podem incluir:
- a) Número de terminais a serem suportados;
- b) Número de usuários simultâneos a serem suportados;
- c) Quantidade e tipo de informações a serem manipuladas.

**Requisitos numéricos dinâmicos** podem incluir, por exemplo, o número de transações e tarefas e a quantidade de dados a serem processados dentro de certos períodos de tempo, tanto para condições normais quanto de pico.

> **Exemplo de boa prática:**  
> "95% das transações devem ser processadas em menos de 1s."  
> **Ruim:** "O operador não deve ter que esperar pela conclusão da transação."

### 3.5 Requisitos Lógicos de Banco de Dados (Logical Database Requirements)
Especifique os requisitos lógicos para qualquer informação que seja colocada em um banco de dados, incluindo:
- a) Tipos de informações usadas por várias funções;
- b) Frequência de uso;
- c) Capacidades de acesso;
- d) Entidades de dados e seus relacionamentos;
- e) Restrições de integridade;
- f) Segurança;
- g) Requisitos de retenção de dados.

### 3.6 Restrições de Design (Design Constraints)
Especifique restrições ao design do sistema impostas por padrões externos, requisitos regulatórios ou limitações do projeto.

### 3.7 Conformidade com Padrões (Standards Compliance)
Especifique os requisitos derivados de padrões ou regulamentações existentes, incluindo:
- a) Formato de relatórios;
- b) Nomenclatura de dados;
- c) Procedimentos contábeis;
- d) Rastreamento de auditoria (audit tracing).

### 3.8 Atributos do Sistema de Software (Software System Attributes)
Especifique os atributos necessários do produto de software. Exemplos parciais:

- **a) Confiabilidade (Reliability):** Especifique os fatores necessários para estabelecer a confiabilidade do sistema no momento da entrega.
- **b) Disponibilidade (Availability):** Especifique os fatores necessários para garantir um nível definido de disponibilidade, como checkpoint, recuperação e restart.
- **c) Segurança (Security):** Especifique requisitos para proteger o software de acesso, modificação, destruição ou divulgação acidental ou maliciosa. Pode incluir:
  1) Uso de técnicas criptográficas;
  2) Manutenção de logs específicos;
  3) Atribuição de funções a diferentes módulos;
  4) Restrição de comunicações entre áreas;
  5) Verificação de integridade de dados para variáveis críticas;
  6) Garantia de privacidade de dados.
- **d) Manutenibilidade (Maintainability):** Atributos relacionados à facilidade de manutenção (modularidade, limitação de complexidade).
- **e) Portabilidade (Portability):** Atributos relacionados à facilidade de portar para outras máquinas/sistemas operacionais.

---

## 4. Verificação (Verification)
Forneça as abordagens e métodos de verificação planejados para qualificar o software. Os itens de informação para verificação são recomendados a serem apresentados de forma paralela aos itens de informação em 3.1 a 3.8.

> *Exemplo: Para cada requisito funcional, indique o tipo de teste (unitário, integração, sistema, usabilidade) e os critérios de aceitação.*

---

## 5. Informações de Suporte (Supporting Information)
Informações adicionais de suporte a serem consideradas incluem:
- a) Exemplos de formatos de entrada/saída, descrições de estudos de análise de custo ou resultados de pesquisas com usuários;
- b) Informações de suporte ou contexto que possam ajudar os leitores do SRS;
- c) Descrição dos problemas a serem resolvidos pelo software;
- d) Instruções especiais de empacotamento para o código e a mídia.

O SRS deve declarar explicitamente se esses itens são ou não considerados parte dos requisitos.

---

## Apêndice A — Índice (Index)
*(Opcional — pode ser gerado automaticamente.)*

---

## Apêndice B — Modelos de Análise
*(Opcional — inclua diagramas de fluxo de dados, diagramas de classes, diagramas de estado, diagramas ER, etc.)*

---

## Apêndice C — Lista de Itens a Definir (TBD)
Reúna uma lista numerada das referências TBD (a serem definidas) que permanecem no SRS para que possam ser rastreadas até o fechamento.

| ID | Localização | Descrição | Responsável | Prazo |
|----|-------------|-----------|-------------|-------|
| TBD-001 | | | | |
