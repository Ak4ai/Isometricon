# 🧰 Scripts do Projeto

## 📌 Resumo

O que há em `scripts/`, para que serve cada arquivo e onde ele está. Levantado em 10/10/2026: cada script foi
verificado quanto a imports e arquivos que cita e quanto a quem o referencia (código, testes, documentação, CI).
"Blender" quer dizer que roda dentro do Blender (`import bpy`), não pelo Python do projeto.

**No repositório ficaram só os 13 scripts que o jogo, a CI e as ferramentas desta wiki usam** (a primeira tabela).
Os outros 58 — pesquisa do encaixe, renderizadores de conferência e exportações antigas — foram para a pasta
`backup/`, na raiz do projeto, que o git ignora: existem só na máquina de quem os tinha e no histórico do git. Junto
foram os nove módulos experimentais de `src/clothing` (`experimental_*.py`, `volumetric_cage.py`), os treze arquivos
de teste deles (52 testes) e o manequim de referência do Roblox (`ClassicMannequin_With-Cages.fbx`). O
`backup/README.md` diz como trazê-los de volta.

Quatro scripts que já não rodavam (importavam módulos de experimento apagados em 06/10/2026) foram removidos de vez:
`batch_compare_roblox.py`, `closeup_compare_roblox.py`, `compare_variants_roblox.py` e `sweep_radial_radius_roblox.py`.

---

## ✅ No repositório (`scripts/`)

| Script | Para que serve |
|---|---|
| `build.py` | Compilação local multiplataforma do jogo (usado pela CI). |
| `audit_animation_robustness.py` | A [[Bateria de Robustez|Bateria-de-Robustez]]: veste cada roupa nos dois corpos, passa por poses e mede esticado, pele furando e buraco; `--report … --compare …` compara duas rodadas. |
| `inspect_flagged_regions.py` | Aproxima a câmera do que a bateria marcou (pele furando, buraco), com e sem marcação. |
| `render_catalog_thumbnails.py` | Miniaturas dos itens e das raças para o editor de personagem. |
| `study_rest_arm_angle.py` | Estudo de quanto os braços precisam abrir em repouso para livrar cada roupa. |
| `render_female_tests.py` | Renderização sem janela das imagens de teste; as funções `look_at` e `perspective` dele são usadas por vários outros scripts. |
| `blender_nudred_hair.py` (Blender) | Gera o cabelo nudred e o raspado sobre as cabeças do jogo e exporta no formato de cabelo encaixado. |
| `build_game_rig.py` (Blender) | Monta o rig do jogo (16 ossos) num corpo aberto no Blender. |
| `export_rig.py` (Blender) | Exporta o rig do jogo para `assets/models/rig_<corpo>.json`. |
| `export_male_body.py` (Blender) | Exporta o corpo masculino e as cages R15 dele ([[Corpo Masculino|Corpo-Masculino]]). |
| `build_male_cage.py` | Constrói a cage R15 masculina a partir da feminina (mesma topologia e UVs). |
| `import_roblox_clothing.py` (Blender) | Baixa, decodifica e importa roupas do Roblox no Blender. |
| `blender_client.py` | Cliente TCP para o servidor MCP do Blender; o `import_roblox_clothing.py` o importa. |

## 🔬 Em `backup/`: pesquisa do encaixe (experimentos e auditorias)

Vieram da fase em que o encaixe por cage foi desenvolvido e validado contra o Roblox. O que se aprendeu com eles
está em [[Histórico de Experimentos|Historico-de-Experimentos]]. O mais provável de voltar a ser útil é o
`compare_roblox_ground_truth.py`: se o encaixe for mexido, é ele que mede de novo a distância para o Roblox Studio.

| Script | Para que serve |
|---|---|
| `compare_roblox_ground_truth.py` | Compara o nosso encaixe no corpo Blocky com a malha exportada do Roblox Studio ([[Validação com Roblox|Validacao-com-Roblox]]). Depende do manequim. |
| `audit_binding_charts.py` | Localiza quebras de borda da roupa entre ilhas de UV da cage. |
| `audit_blocky_radial_influences.py` | Repete o encaixe congelado do Blocky e mede a influência de cada parte. |
| `audit_blocky_target_placement.py` | Auditoria estática de posição e folga no Blocky. |
| `audit_canonical_radial_results.py` | Recalcula a validação a partir de saídas gravadas e localiza falhas por parte da cage. |
| `audit_outer_cage_clearance.py` | Compara a folga da cage externa original com a transferida. |
| `audit_radial_frames.py` | Auditoria reprodutível dos referenciais de entrada. |
| `experimental_wrap_frames.py` | Mapas locais candidatos para a transferência de cage. |
| `benchmark_wrap_frames.py` | Compara algoritmos de referencial da cage em roupas fixas. |
| `radial_validation_metrics.py` | Medidas geométricas offline (penetração sem usar o renderizador). |
| `experiment_canonical_radial.py` | Comparação fixa de seis casos. |
| `experiment_chart_blend.py` | Mistura nas bordas das ilhas de UV. |
| `experiment_dual_cage_prism.py` | Ligação por volume entre as faces das cages interna e externa. |
| `experiment_shell_adaptive.py`, `experiment_shell_global_affine.py` | Controles de transporte local contra volume global. |
| `experiment_synthetic_contact.py`, `experiment_synthetic_wrap.py`, `synthetic_wrap_fixture.py` | Bancadas sintéticas (braço analítico), sem assets reais. |
| `test_r15_shirt_transfer.py` | Transfere uma camisa do catálogo da cage de referência dela para as cages R15 locais. |
| `export_r15_reference_cages.py`, `inspect_classic_mannequin_fbx.py` | Leem as cages de referência de `ClassicMannequin_With-Cages.fbx` (que também está em `backup/`). |
| `robustness_catalog.py` | Baixa uma amostra do catálogo e passa pelo encaixe feminino. |

## 🖼️ Em `backup/`: renderizadores de conferência

Geram folhas de imagens para olhar um aspecto do sistema. Nada os chama; servem para conferir à mão.

| Script | O que renderiza |
|---|---|
| `render_walk.py` | O ciclo de caminhada dos dois corpos vestidos. |
| `render_male_outfits.py` | Conjuntos no corpo masculino ao lado do feminino. |
| `render_layered_outfits.py` | Jaqueta sobre camisa. |
| `render_shoes.py` | Sapatos, de perto. |
| `render_hairs.py` | Cada cabelo encaixado, na cabeça. |
| `render_male_cage.py` | A cage em aramado sobre o corpo, feminino e masculino. |
| `render_catalog_grid.py` | Todas as roupas que vestiram sem erro no corpo feminino. |
| `render_hsr_before_after.py`, `render_hsr_fallback.py` | A pele escondida: regras antigas contra máscaras do Roblox, e a máscara geométrica de reserva. |
| `render_runtime_before_after.py`, `render_new_acceptance.py`, `render_uv_binding_review.py` | Antes e depois de etapas do encaixe (prisma radial, validação do WrapLayer, ligação por UV). |
| `build_catalog_sample.py` | Monta uma amostra do catálogo por tipo de peça. |

## 📦 Em `backup/`: exportações de uma vez só (Blender)

Foram usadas para produzir os corpos, as cages e os pacotes que hoje estão em `assets/models`. Só voltam a ser
necessárias se um corpo ou uma cage for refeito no Blender.

| Script | Para que serviu |
|---|---|
| `export_apose_for_roblox.py`, `export_for_roblox_studio.py` | Exportar o personagem em A-pose ou em repouso para o Roblox Studio. |
| `export_skinned_roblox.py`, `export_skinned_apose_roblox.py`, `export_separated_skinned_roblox.py` | Variações do FBX com skinning aceito pelo Roblox Studio. |
| `export_modular_character.py` | Exportar o personagem em partes. |
| `export_female_apose.py`, `export_female_assets.py`, `export_female_cage_data.py`, `export_perfect_female_cages.py`, `update_female_cage_from_user_obj.py` | O corpo feminino e as cages dele. |
| `export_stage2_clothing_package.py`, `verify_stage2_clothing_package.py`, `test_stage2_runtime_clothing.py` | O pacote "stage 2" (corpo e cages revisados) e a conferência dele. |
| `build_universal_fit.py`, `full_universal_cage_pipeline.py` | A primeira versão do encaixe universal, feita no Blender com shape keys. |
| `render_female_outfits.py`, `render_female_poses.py` | Renderização dos conjuntos e das poses femininas pelo Blender. |
| `test_canonical_dual_cage.py`, `test_canonical_dual_cage_apose.py`, `test_female_dual_cage.py`, `test_office_wraplayer_mapping.py`, `verify_jeans_cage_activity.py` | Verificações pontuais da época do encaixe por duas cages. |

---

## 🗂️ Fora do git

- `backup/` (ignorado): o que está descrito acima. Também guarda as exportações antigas para o Roblox Studio que estavam em
  `assets/models` (doze `.fbx` e um `.json`).
- **O que um clone precisa e o `.gitignore` esconde:** `*.obj` é ignorado, então as malhas que o jogo abre entram no
  git à força (`git add -f`): os corpos (`character_female_clean_apose_stage2.obj`, `character_male_clean_apose.obj`),
  as cages (`female_cages_apose_stage2.obj`, `male_cages_apose.obj`, `roblox_reference_cages.obj`), a cabeça e o corpo
  de referência dos testes (`character_head_rounded.obj`, `character_clean.obj`) e os cabelos padrão, nudred e
  raspado (`clothing/Hair_fitted_*`). Conferido em 10/10/2026 com um clone limpo: o jogo abre nos dois corpos. Ao
  acrescentar uma malha nova que o jogo abre, lembre de adicioná-la à força.
- **O catálogo de exemplo:** sem credencial do Roblox (`ROBLOSECURITY` no `.env`, que não vai para o git) o download
  de roupas responde 401, então um clone só veste o que vem no repositório. Vão 32 peças (roupas, cabelos e a
  katana), cada uma com o `.rbxm`, a textura, a malha de origem (`.obj`, à força) e os dados de cage e de máscara que
  ela lê (`wrap_cages/*.mesh`, `hsr/*.bin`). Conferido num clone limpo e sem credencial: as 32 vestem nos dois
  corpos. Os outros itens baixados nesta máquina, as roupas já encaixadas (`character_native_*`), os cabelos
  encaixados do catálogo e as miniaturas são cache local e ficam fora do git.
- **Testes num clone:** 664 passam e 1 é pulado (precisa de roupas já encaixadas, que são cache).
- `artifacts/` (ignorado): resultados da bateria. Em 10/10/2026 ficaram `robustness_v37` (rodada de 07/10),
  `robustness/2026-10-09` (rodada completa de referência) e `robustness/2026-10-10` e `2026-10-10b` (os dois
  experimentos do cruzamento tronco/braço). `inspecao` é a pasta de saída de `inspect_flagged_regions.py`; estava
  cheia de imagens de depuração antigas e foi esvaziada.
- `assets/models/character_native_*.obj` e `*_hsr.npz` (ignorados): as roupas já encaixadas em cada corpo. São
  refeitas pelo encaixe quando faltam; reencaixar o catálogo inteiro leva perto de uma hora.
- `saves/` (ignorado): o personagem salvo do jogador.
