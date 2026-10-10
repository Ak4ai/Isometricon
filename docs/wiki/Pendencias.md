# 📌 Pendências e Próximos Passos

## 📌 Resumo

Este documento lista as melhorias técnicas, funcionalidades pendentes e refatorações identificadas para as próximas etapas do projeto Isometricon. O foco das pendências abrange desde a integração com a animação esquelética em tempo real no motor de mundo até suporte a novos formatos proprietários do ecossistema Roblox.

---

## 📋 Lista de Tarefas Prioritárias

### 1. Roupas que ainda esticam ou furam ao animar
- **Situação Atual:** O personagem do mundo anda vestido (ver [[Animação e Esqueleto|Animacao-e-Esqueleto]]); a bateria
  dá 116 ok, 75 atenção e 13 falha em 09/10/2026 (ver [[Bateria de Robustez|Bateria-de-Robustez]]). As seis peças
  com defeito real ficam marcadas no editor e avisadas ao vestir (`src/clothing/known_defects.py`).
- **Pendência:** fantasias de corpo inteiro que ainda rasgam (Sully, Pigeon, Strawberry); frestas entre os gomos
  da saia do Long Dress (o encaixe do tecido pendurado estica a saia 20% de frente para trás; a correção testada
  piorava capas e fantasias e foi revertida); calça de moletom com tênis em atenção; falsos alarmes de buraco no
  contorno da silhueta; cós da baggy jeans e ponta do sobretudo no
  quadril (modelo da peça e proporção do corpo).
- **Desempenho:** resolvido em 07/10/2026 com skinning na GPU (~0,3 ms por quadro por personagem). O que falta para vários personagens na tela é o jogo criar e posicionar os outros tokens vestidos.

### 1b. Defeitos que vêm do encaixe, não da pele
- **Situação Atual:** medido em 09 e 10/10/2026 (ver "A pele contra o tecido" e as seções seguintes em
  [[Sistema de Roupas|Sistema-de-Roupas]]). Os ajustes automáticos na pele escondida chegaram ao limite: as últimas
  tentativas deram ganhos de poucos cm² ou trocaram um defeito por outro.
- **Pendência:**
  - **Tampas em leque:** o encaixe espalha as cópias do vértice do meio dos leques que fecham cavas e golas (15
    peças); no "Dark Brown Tied Crop Top" isso aparece como pontas dentro da cava. Juntar as cópias foi tentado e
    retirado. Ainda não tentado: não desenhar os triângulos desses leques.
  - **Costuras separadas:** o encaixe separa por centímetros as cópias de mais de 2500 vértices ao longo das costuras
    de UV. Juntá-las depois do encaixe piora o movimento; a correção é o encaixe mover igual o que está no mesmo
    ponto, o que pede reencaixar o catálogo (perto de 1 h) e medir tudo de novo.
  - **Cruzamento tronco/braço na máscara:** a lateral do tronco segue os pontos de dentro do braço (para esconder à
    mão triângulos do tórax, pinta-se embaixo do braço). Corrigir piora casacos; fica como está.

### 2. Cache com Validação de Hash/Versão da Cage
- **Situação Atual:** Os caches binários (`character_native_<id>_<corpo>.obj`, `*.hsr.npz`) são gravados com base no ID da roupa.
- **Pendência:** Adicionar hash das cages base (`female_cages_apose_stage2.obj` e `male_cages_apose.obj`) nos metadados do cache. Se uma cage for alterada, o cache é invalidado e regenerado automaticamente.

### 3. Suporte aos Formatos de Malha Roblox v3 e v6
- **Situação Atual:** Suporte completo aos formatos FileMesh v2, v4 e v5.
- **Pendência:** Adicionar parsing de blocos comprimidos de malhas FileMesh v3 e v6 encontradas em algumas roupas ultra-recentes do catálogo Roblox.

### 4. Acessórios Fora da Cabeça
- **Situação Atual:** Chapéus e cabelos (`HatAttachment`, `HairAttachment`) estão 100% integrados.
- **Pendência:** Estender o pareamento para acessórios de costas (asas, mochilas, espadas), ombros (ombreiras, mascotes) e cintura (cintos utilitários).

### 5. Resolução Dinâmica de Colisão Cabelo × Gola
- **Situação Atual:** Cabelos longos que caem pelas costas podem tocar levemente golas volumosas de sobretudos.
- **Pendência:** Aplicar a outer cage do casaco como superfície de deflexão para as pontas dos cabelos longos.

### 6. Plano B de Roupas sem Cage para o Corpo Masculino
- **Situação Atual:** A maioria das roupas possui inner cage R15 compatível.
- **Pendência:** Algumas peças raras de catálogo não incluem cages de referência válidas. Implementar um gerador automático de cage sintética via voxelização inflada para peças sem cage.

### 7. Scripts de auditoria antigos
- **Situação Atual:** Em 06/10/2026 foram apagados a quarentena, `artifacts/` e os experimentos de pesos e ombro
  (o que se aprendeu está em [[Histórico de Experimentos|Historico-de-Experimentos]]). `artifacts/` agora é ignorado pelo git.
- **Resolvido em 10/10/2026:** os scripts de pesquisa, as exportações antigas, os renderizadores de conferência, os
  módulos `experimental_*` e os testes deles saíram do repositório e foram para `backup/` (ignorado pelo git; ver
  [[Scripts do Projeto|Scripts-do-Projeto]]). No repositório ficaram os 14 scripts em uso e 666 testes.
- **Pendência:** nenhuma. Se o encaixe for mexido de novo, trazer de `backup/` o `compare_roblox_ground_truth.py` e
  a cadeia dele (com o manequim) para medir contra o Roblox Studio.

### 8. Publicação
- **Situação Atual:** o trabalho de roupas e de criação de personagem está em commits locais no branch
  `wip/roblox-ground-truth`, sem envio ao GitHub.
- **Pendência:** enviar o branch e juntar ao `main`; decidir se `assets/models/123.blend` (modificado) entra.
