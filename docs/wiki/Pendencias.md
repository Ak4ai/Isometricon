# 📌 Pendências e Próximos Passos

## 📌 Resumo

Este documento lista as melhorias técnicas, funcionalidades pendentes e refatorações identificadas para as próximas etapas do projeto Isometricon. O foco das pendências abrange desde a integração com a animação esquelética em tempo real no motor de mundo até suporte a novos formatos proprietários do ecossistema Roblox.

---

## 📋 Lista de Tarefas Prioritárias

### 1. Roupas que ainda esticam ou furam ao animar
- **Situação Atual:** O personagem do mundo anda vestido (ver [[Animação e Esqueleto|Animacao-e-Esqueleto]]); a bateria
  dá 117 ok, 70 atenção e 17 falha (ver [[Bateria de Robustez|Bateria-de-Robustez]]).
- **Pendência:** fantasias de corpo inteiro e Cloak acima do limite de esticado (manga × saco/capa, ver a
  bateria); calça de moletom com tênis em atenção; falsos alarmes de buraco no contorno da silhueta; cós da baggy jeans e ponta do sobretudo no
  quadril (modelo da peça e proporção do corpo).
- **Desempenho:** skinning na CPU custa ~8 ms por quadro; vários personagens pediriam skinning na GPU.

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
- **Pendência:** vários `scripts/audit_*` e `scripts/experiment_*` do encaixe ainda são importados por
  `src/clothing/experimental_coherent_prism.py`; unificar numa CLI antes de apagar.
