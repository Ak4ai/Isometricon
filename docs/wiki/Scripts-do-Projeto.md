# 🧰 Scripts do Projeto

## 📌 Resumo

O que há em `scripts/`, para que serve cada arquivo e se ainda é usado. Levantado em 10/10/2026: cada script foi
verificado quanto a imports e arquivos que cita (existem ou não) e quanto a quem o referencia (código, testes,
documentação, CI). "Blender" quer dizer que roda dentro do Blender (`import bpy`), não pelo Python do projeto.

Nenhum script abaixo está quebrado. Os que estavam (importavam módulos de experimento apagados em 06/10/2026) foram
removidos nesta data: `batch_compare_roblox.py`, `closeup_compare_roblox.py`, `compare_variants_roblox.py` e
`sweep_radial_radius_roblox.py`.

---

## ✅ Em uso (referenciados pelo código, pelos testes, pela CI ou pela wiki)

| Script | Para que serve |
|---|---|
| `build.py` | Compilação local multiplataforma do jogo (usado pela CI). |
| `audit_animation_robustness.py` | A [[Bateria de Robustez|Bateria-de-Robustez]]: veste cada roupa nos dois corpos, passa por poses e mede esticado, pele furando e buraco; `--report … --compare …` compara duas rodadas. |
| `inspect_flagged_regions.py` | Aproxima a câmera do que a bateria marcou (pele furando, buraco), com e sem marcação. |
| `render_catalog_thumbnails.py` | Miniaturas dos itens e das raças para o editor de personagem. |
| `study_rest_arm_angle.py` | Estudo de quanto os braços precisam abrir em repouso para livrar cada roupa. |
| `compare_roblox_ground_truth.py` | Compara o nosso encaixe no corpo Blocky com a malha exportada do Roblox Studio ([[Validação com Roblox|Validacao-com-Roblox]]). |
| `render_female_tests.py` | Renderização sem janela das imagens de teste; as funções `look_at` e `perspective` dele são usadas por vários outros scripts. |
| `blender_nudred_hair.py` (Blender) | Gera o cabelo nudred e o raspado sobre as cabeças do jogo e exporta no formato de cabelo encaixado. |
| `build_game_rig.py` (Blender) | Monta o rig do jogo (16 ossos) num corpo aberto no Blender. |
| `export_rig.py` (Blender) | Exporta o rig do jogo para `assets/models/rig_<corpo>.json`. |
| `export_male_body.py` (Blender) | Exporta o corpo masculino e as cages R15 dele ([[Corpo Masculino|Corpo-Masculino]]). |
| `build_male_cage.py` | Constrói a cage R15 masculina a partir da feminina (mesma topologia e UVs). |
| `import_roblox_clothing.py` (Blender) | Baixa, decodifica e importa roupas do Roblox no Blender. |
| `blender_client.py` | Cliente TCP simples para o servidor MCP do Blender. |

## 🔬 Pesquisa do encaixe (experimentos e auditorias)

Vieram da fase em que o encaixe por cage foi desenvolvido e validado contra o Roblox. Alguns ainda são importados por
testes ou por `src/clothing/experimental_coherent_prism.py`; a pendência de unificá-los numa CLI antes de apagar
continua em [[Pendências|Pendencias]]. O que se aprendeu com eles está em
[[Histórico de Experimentos|Historico-de-Experimentos]].

| Script | Para que serve |
|---|---|
| `audit_binding_charts.py` | Localiza quebras de borda da roupa entre ilhas de UV da cage. |
| `audit_blocky_radial_influences.py` | Repete o encaixe congelado do Blocky e mede a influência de cada parte. |
| `audit_blocky_target_placement.py` | Auditoria estática de posição e folga no Blocky. |
| `audit_canonical_radial_results.py` | Recalcula a validação a partir de saídas gravadas e localiza falhas por parte da cage. |
| `audit_outer_cage_clearance.py` | Compara a folga da cage externa original com a transferida. |
| `audit_radial_frames.py` | Auditoria reprodutível dos referenciais de entrada. |
| `benchmark_wrap_frames.py` | Compara algoritmos de referencial da cage em roupas fixas. |
| `radial_validation_metrics.py` | Medidas geométricas offline (penetração sem usar o renderizador). |
| `experiment_canonical_radial.py` | Comparação fixa de seis casos. |
| `experiment_chart_blend.py` | Mistura nas bordas das ilhas de UV. |
| `experiment_dual_cage_prism.py` | Ligação por volume entre as faces das cages interna e externa. |
| `experiment_shell_adaptive.py`, `experiment_shell_global_affine.py` | Controles de transporte local contra volume global. |
| `experiment_synthetic_contact.py`, `experiment_synthetic_wrap.py`, `synthetic_wrap_fixture.py` | Bancadas sintéticas (braço analítico), sem assets reais. |
| `experimental_wrap_frames.py` | Mapas locais candidatos para a transferência de cage. |
| `test_r15_shirt_transfer.py` | Transfere uma camisa do catálogo da cage de referência dela para as cages R15 locais. |
| `export_r15_reference_cages.py`, `inspect_classic_mannequin_fbx.py` | Leem as cages de referência de `ClassicMannequin_With-Cages.fbx` (na raiz do repositório). |
| `robustness_catalog.py` | Baixa uma amostra do catálogo e passa pelo encaixe feminino. |

## 🖼️ Renderizadores de conferência (íntegros, sem referência)

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

## 📦 Exportações de uma vez só (Blender, sem referência)

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

- `artifacts/` (ignorado): resultados da bateria. Em 10/10/2026 ficaram `robustness_v37` (rodada de 07/10),
  `robustness/2026-10-09` (rodada completa de referência) e `robustness/2026-10-10` e `2026-10-10b` (os dois
  experimentos do cruzamento tronco/braço). `inspecao` é a pasta de saída de `inspect_flagged_regions.py`; estava
  cheia de imagens de depuração antigas e foi esvaziada.
- `assets/models/character_native_*.obj` e `*_hsr.npz` (ignorados): as roupas já encaixadas em cada corpo. São
  refeitas pelo encaixe quando faltam; reencaixar o catálogo inteiro leva perto de uma hora.
- `saves/` (ignorado): o personagem salvo do jogador.
