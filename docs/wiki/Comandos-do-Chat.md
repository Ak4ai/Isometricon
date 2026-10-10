# 💬 Comandos do Chat

Abra o chat com **[T]** ou **[/]**; **[TAB]** completa e cicla as opções. Tudo que muda o personagem fica sob
`/skin`. Os comandos são definidos num quadro único em `src/interactive/skin_commands.py`, de onde saem a
execução, o autocompletar e a ajuda.

| Comando | O que faz |
|---|---|
| `/skin corpo <feminino\|masculino>` | troca o corpo |
| `/skin pele <palida\|clara\|bronzeada\|morena\|negra\|#rrggbb\|r,g,b>` | tom de pele, pronto ou qualquer cor |
| `/skin olhos <cor\|#rrggbb\|r,g,b\|estilo>` | azul, verde, castanho, roxo, vermelho, dourado, ciano, rosa, laranja, ambar, turquesa, lilas, cinza, branco, preto, ou qualquer cor; anime, piscando, classico, sem |
| `/skin boca <estilo>` | anime, sorriso, aberta, piscando, neutra, classica, gato, beicinho, vampiro (a anime com presas), sem |
| `/skin cabeca <arredondada\|quadrada>` | formato da cabeça |
| `/skin cabelo <id\|cor\|careca\|raspado\|padrao>` | troca ou pinta o cabelo (a cor também como `#rrggbb` ou `r,g,b`); `raspado` é um cabelo rente, não a cabeça careca; `nudred` veste o cabelo nudred, feito à mão |
| `/skin cabelo posicao <x\|y\|z> <cm>` · `escala [x\|y\|z] <fator>` · `reset` | ajusta o cabelo (como acessório no Roblox) |
| `/skin vestir <id\|link\|nome> [tipo] [refazer]` | veste qualquer item do Roblox no lugar certo, pelo tipo do asset |
| `/skin top <nome\|id\|none>` · `/skin calca ...` | roupa de cima e de baixo |
| `/skin jaqueta <id\|none>` · `folga <mm>` · `puxar <mm>` | peça por cima do top e suas camadas |
| `/skin sapato <pacote\|esquerdo,direito\|none>` | calçado |
| `/skin arma <katana\|id\|none>` | item na mão |
| `/skin tirar <top\|calca\|jaqueta\|sapato\|cabelo\|arma\|tudo>` | remove (tudo mantém o cabelo) |
| `/skin roupas` | lista o que está vestido |
| `/skin preset <padrao\|gato_loiro\|cavaleiro\|rosa\|classico>` · `/skin reset` | aparência pronta (mantém o corpo) |
| `/skin olhos <formato>` | formato dos olhos: padrao, arredondado, grande, feminino, fechado, sonolento, estreito, puxado, caido, suave, suave_redondo; outros modelos: serio, masculino, afiado, redondo, retro, cansado, felino |
| `/skin olho <direito\|esquerdo> <cor\|#rrggbb\|r,g,b>` | cor de um olho só (`/skin olhos <cor>` volta os dois à mesma) |
| `/skin maquiagem <batom\|sombra\|blush> <cor\|#rrggbb\|sem>` · `contorno <suave\|marcado\|sem>` · `sardas <sim\|nao>` · `sem` | maquiagem; cores: vermelho, rosa, nude, vinho, roxo, azul, verde, dourado, marrom, preto, coral, pessego, laranja, lilas, turquesa, prata, ou qualquer uma em `#rrggbb` ou `r,g,b`. Os controles de cada item ficam em `/skin ajuste`: `blush_intensidade`, `blush_tamanho`, `blush_esfumado`, `blush_altura`, `sombra_intensidade`, `sombra_tamanho`, `sombra_esfumado`, e `<item>_matiz`, `<item>_saturacao`, `<item>_brilho`; as sombras do queixo, em `rosto_sombra` |
| `/skin hsr espelhar <sim\|nao>` · `<esconder\|mostrar\|apagar> <pontos>` · `limpar` · `desfazer` · `refazer` | a pele escondida sob a roupa: espelhar os dois lados do corpo, ou corrigir à mão os pontos da cage (o pincel da seção Ajuste fino) |
| `/skin extra <nome\|id\|none>` | veste ou tira uma peça a mais, junto com as outras |
| `/skin raca <humano\|elfo\|anao\|orc\|goblin\|demonio\|vampiro\|tritao\|marciano\|fada\|felino\|lupino\|kitsune\|coelho\|draconato\|reptiliano\|anjo>` | corpo pronto de uma raça sobre o corpo em uso: pele, orelhas, olhos, nariz e proporções |
| `/skin intima <sem\|sim\|branco\|preto\|cinza\|nude\|rosa\|vermelho\|azul\|roxo\|#rrggbb>` | roupa de baixo pintada na pele: cueca no corpo masculino, calcinha e sutiã no feminino |
| `/skin asa <sem\|morcego\|dragao\|anjo\|fada\|borboleta>` · `cor <auto\|pele\|cabelo\|nome\|#rrggbb>` | asas 3D e a cor delas (ajustes em `/skin ajuste`: `asa_tamanho`, `asa_abertura`) |
| `/skin cauda <sem\|felino\|diabo\|tigre\|leao\|lobo\|raposa\|cachorro\|cavalo\|coelho\|reptil\|dragao>` · `cor <auto\|pele\|cabelo\|nome\|#rrggbb>` | cauda 3D e a cor dela (ajustes em `/skin ajuste`: `cauda_tamanho`, `cauda_curva`) |
| `/skin chifre <sem\|demonio\|bode\|carneiro\|touro\|boi\|cervo\|unicornio\|um\|dois\|tres\|um_quebrado>` · `cor <auto\|marfim\|osso\|branco\|cinza\|marrom\|preto\|vermelho\|dourado\|#rrggbb>` | chifres 3D e a cor deles (ajustes em `/skin ajuste`: `chifre_tamanho`, `chifre_curva`) |
| `/skin orelha <sem\|humana\|redonda\|elfo\|elfo_asa\|morcego\|barbatana\|gato\|cachorro\|cachorro_caido\|cachorro_uma_caida\|lobo\|raposa\|coelho\|coelho_uma_caida\|coelho_caidas\|dragao\|reptil>` · `cor <auto\|pele\|cabelo\|branco\|creme\|caramelo\|marrom\|ruivo\|cinza\|preto\|rosa\|#rrggbb>` | orelhas 3D e a cor delas (ajustes em `/skin ajuste`: `orelha_tamanho`, `orelha_altura`, `orelha_abertura`, `orelha_matiz`, `orelha_saturacao`, `orelha_brilho`) |
| `/skin sobrancelha <padrao\|grossa\|decidida\|sem>` | estilo das sobrancelhas |
| `/skin nariz <sim\|nao\|formato\|sombra legado\|sombra calculada>` | nariz 3D e seu formato: padrao, projetado, ponta_larga, narinas_largas, aquilino, arrebitado, fino, largo, botao, longo, botao_largo, botao_arrebitado, narinas_grandes, achatado, batata, aberto, bloco, bloco_narinas; a sombra é a legada (um trecho fixo) ou a calculada pelo contorno do nariz (ajustes em `/skin ajuste`: `nariz_tamanho`, `nariz_altura`, `nariz_projecao`, `nariz_largura`, `nariz_ponte_largura`, `nariz_ponte_altura`, `nariz_ponta_largura`, `nariz_ponta_projecao`, `nariz_base_largura`, `nariz_base_altura`, `nariz_narinas_altura`, `nariz_ponta_cor`, `nariz_sombra`; pele: `vitiligo`, `vitiligo_forma`) |
| `/skin ajuste <nome> <-100 a 100>` · `reset` | proporções: altura, cabeca, pescoco, ombros, peito, cintura, pelve, quadril, bunda, bracos, bracos_comprimento, maos, pernas, pernas_comprimento, pes, folga, olhos_tamanho, olhos_altura, olhos_distancia, sobrancelha_tamanho, sobrancelha_altura, sobrancelha_distancia; bordas das roupas: blusa_barra, calca_cintura, calca_barra |
| `/skin salvar` · `/skin carregar` | grava o personagem em `saves/personagem.json`, ou volta ao gravado |
| `/skin interface` | abre a [[tela de criação de personagem\|Criacao-de-Personagem]] |
| `/ajuda [comando]` | lista por grupo, ou uso e apelidos de um comando |
| `/girar [on\|off]` | rotação automática (só no visualizador `--char`) |

Cada comando aceita também um apelido em inglês (`/skin eyes`, `/skin wear`, `/skin pants`...).

**Removidos em 06/10/2026:** os ajustes que deformavam corpo ou roupa depois do encaixe pela cage (manga, braço,
quadril, cintura, barra, postura) — mexiam só no corpo ou só na roupa e quebravam o encaixe, o HSR e a
animação; e os atalhos soltos no primeiro nível (`/top`, `/eyes`, `/import`, `/x`, `/fora`...).

![Ajuda no chat](images/mundo/chat-ajuda.png)
![Comandos no mundo](images/mundo/comandos-skin.png)
