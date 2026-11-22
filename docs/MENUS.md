# Menus e mundos

Execute `python src/main.py` para abrir o menu inicial. `--menu` também força o menu; `--terrain`, `--char` e as capturas com `--frames` mantêm os modos de diagnóstico existentes.

- Boas-vindas: painel horizontal para desktop, com criar mundo, continuar, editor de mapa, configurações, créditos e sair. O editor abre no modo `--map-editor`, sem criar um mundo salvo.
- Lista de mundos: botão Excluir por mundo, com confirmação e opção de cancelar; exclui somente o save escolhido.
- Criação: nome e seed numérica ou textual. Seed vazia gera um número aleatório; texto usa SHA-256, de forma estável entre execuções.
- Opções do terreno na criação (0 a 100%): cavernas (0 desliga), planície (100 é chão liso), água (a parte do chão coberta; o nível do mar sai das alturas da própria seed), vegetação (50 é a de sempre) e tamanho do relevo. Ficam em `world["terrain"]` (`src/world/terrain_options.py`); mundos sem elas usam o gerador de sempre. Clique ou arraste a trilha; ← → andam de 5 em 5.
- Prévia do mundo na criação: um recorte isométrico de 36 x 36 blocos do começo do mundo, gerado com o gerador do jogo numa thread (`src/interactive/world_preview.py`) e refeito quando uma opção ou a seed muda. O corte mostra as camadas e os túneis, mais escuros. Com a seed vazia, a prévia sorteia uma (Outra seed troca) e o mundo criado usa essa mesma seed.
- Pausa: ESC durante o jogo, com captura da cena ao fundo. A simulação fica suspensa enquanto qualquer menu está aberto. ESC primeiro fecha chat/editor quando eles estão ativos. O botão **Construções** fecha a pausa e abre o painel do `/schem` na mesma aventura. O painel mostra uma miniatura isométrica da construção, filtros **Tudo / Exportados / Schem** e linhas clicáveis; `E`/`T` trocam o filtro.

Em desempenho, o custo cresce com a cobertura de tela: perto do personagem o terreno ocupa mais pixels e a sombra do sol (até 18 raios por pixel na qualidade alta) pesa. O plano `far` em perspectiva acompanha o zoom, evitando o desaparecimento no zoom máximo.
- Editor: o botão **Editor de mapa** abre uma sessão própria. `F10`/botão **Menu** salva o mapa e volta ao menu; `Shift+F10` volta sem salvar; exporte o objeto com `F2` antes de sair. O menu continua na mesma execução e a nova aventura vê o objeto em `/schem`.
- Controles: cadastro `ACTIONS` em `src/core/game_storage.py`; cada entrada contém ID estável, descrição e tecla padrão. A interface pagina automaticamente. Teclas repetidas são rejeitadas e ESC fica reservado à navegação. O pan continua disponível por Shift + arrastar ou botão central; zoom pela roda também permanece disponível.
- Configurações: VSync, inversão da rotação Q/E, sensibilidade do pan, redução da interpolação da rotação e escala dos textos dos menus. Aplicar grava; sair com alterações abre a opção de descarte. Restaurar padrões só altera o rascunho até Aplicar.
- Som e legendas aparecem como indisponíveis: o motor ainda não implementa esses sistemas.

## O que é salvo

`saves/preferences.json` contém preferências compartilhadas. Cada mundo usa um UUID e arquivo próprio em `saves/worlds/`, com nome, seed, posição do jogador, tempo jogado, data de gravação e aparência/roupas do personagem. Gravação via arquivo temporário e substituição atômica. Arquivos inválidos não impedem abrir a biblioteca.

O terreno é regenerado pela seed. Alterações transitórias dos voxels e o estado de propagação da água não são persistidos nesta versão. O gerador atual deve permanecer compatível para reproduzir o terreno. O salvamento ocorre ao selecionar Salvar e voltar ao menu e ao fechar um mundo normal; não há indicador fictício de autosave. Capturas automatizadas com `--frames` não gravam automaticamente ao encerrar.

## Verificação

`pytest tests/test_game_menus.py -q` cobre seed, persistência, conflitos de teclas, rascunho de preferências e áreas de clique redimensionadas. A aplicação mantém `--screenshot` / `--frames`; `--menu --frames 2 --screenshot menu.png` captura o menu em OpenGL.


## Identidade visual — atlas de aventuras

A vinheta escura atrás da marca cobre a tela inteira (não só o quadro 1320 x 876 do menu), então não corta em telas mais largas ou mais altas. O menu inicial tem uma paisagem 3D de apresentação feita com o gerador, mesher e atlas de texturas do jogo. A geração ocorre em uma thread; somente a criação e desenho de recursos OpenGL ocorrem na thread da janela. Essa paisagem não modifica nenhum mundo salvo. A câmera se move lentamente; Reduzir movimento também desativa esse movimento e as transições de painéis.

Os painéis usam papel procedural, cantos ornamentados, sombra, acentos dourados e ícones desenhados em código. Botões respondem ao foco, hover e pressão; o clique só é confirmado ao soltar sobre o mesmo botão. A sensibilidade permite arrastar o slider, e os interruptores mostram o estado do rascunho até Aplicar.

Ao salvar, uma captura da partida é gravada em `saves/worlds/<uuid>.png`, quando disponível. Na ausência de captura, a biblioteca exibe um pequeno mapa gerado da seed. A exclusão de um mundo remove também sua miniatura. O conteúdo dos créditos permanece preservado.


## Resposta da interface

Papel, sombras e vinheta são reutilizados; os painéis das demais telas são preparados em segundo plano junto da paisagem. Textos e miniaturas possuem cache. A paisagem de apresentação usa uma malha combinada.

No modo OpenGL, a interface permanece na resolução lógica: escala, deslocamento e transparência das transições são aplicados na GPU. As fontes são empacotadas (Inter e JetBrains Mono, OFL) e não dependem de fontes do sistema; o editor e o painel de construções rasterizam em 2× para maior nitidez em telas de alta densidade.

No macOS Retina, `Window.width/height` representam o framebuffer e `Window.get_window_size()` o tamanho lógico. A cena 3D usa o framebuffer; menus e HUDs usam o tamanho lógico. O mundo normal ativa uma variante compatível das sombras: a máscara e o horizonte são mantidos, mas formas parciais bloqueiam a célula inteira. `--compat-shadows` força esse modo e `--full-shadows` tenta o shader completo. Hover e pressão enviam somente os retângulos alterados à textura, sem realocar a textura nem reconstruir a imagem por causa do fade. Mudanças de conteúdo ou de página atualizam a imagem inteira. A sincronização vertical só é reconfigurada quando a preferência muda.
