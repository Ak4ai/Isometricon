# 🧪 Bateria de Robustez das Roupas

## 📌 Resumo

`scripts/audit_animation_robustness.py` veste cada roupa baixada em `assets/models/clothing` (sozinha, e alguns
conjuntos), nos dois corpos, passa por várias poses e mede três defeitos sem olhar imagens. O veredito
(ok / atenção / falha) vale para as poses que o jogo usa; as demais aparecem à parte.

## ▶️ Como rodar

```
python scripts/audit_animation_robustness.py --bodies female --output artifacts/robustness/female
python scripts/audit_animation_robustness.py --bodies male   --output artifacts/robustness/male
python scripts/audit_animation_robustness.py --output artifacts/robustness --report artifacts/robustness/female artifacts/robustness/male
```

- `--only <id> ...` mede só algumas peças (minutos, útil para validar uma mudança).
- Rode um corpo por vez: as duas rodadas juntas já esgotaram a memória da máquina.
- Quando a versão do cache das roupas muda (`Universal Fitted Clothing vNN`), a primeira rodada reencaixa o
  catálogo inteiro (perto de 1 h); depois, ~10 min por corpo.
- Saída: `medidas.json` (cru), `relatorio.json`, `relatorio.md`, `falhas.png` e `atencao.png` com miniaturas
  marcadas (amarelo = esticado, vermelho = pele furando, magenta = buraco).

## 📏 Medidas e limites

| Medida | O que é | Atenção | Falha |
|---|---|---|---|
| Esticado | área (cm²) de triângulos da peça testada com aresta > 2,5× e > 2 cm maior que no encaixe | 600 | 4000 |
| Pele furando | área de pele desenhada com tecido logo abaixo (até 4 cm) e nada por cima (7,5 cm), menos o que já fura na pose de vestir | 100 | 400 |
| Buraco | pele escondida pelo HSR que se vê de fora (≥ 30% das direções livres) e sem nada desenhado até 3 cm abaixo dela, na pose de vestir | 100 | 500 |

- Poses do jogo: descanso e quatro fases da caminhada. Extras: braços a 90°, braços à frente, sentar.
- Os limites foram fixados olhando as miniaturas do catálogo inteiro: até 600 cm² de esticado nada aparece na
  distância do jogo (um suéter estica ~400 sob o braço); acima de 4000 a peça está visivelmente rasgada.
- **Validação por imagem (06/10/2026)** com `scripts/inspect_flagged_regions.py relatorio.json [--names ...]`, que
  aproxima a câmera de cada região marcada e mostra a vista com e sem marcação:
  - **Buraco** marcava sobretudo pele escondida com o tecido logo abaixo (pés de meia-calça e fantasias, a gola
    por dentro do capuz): ali se vê o tecido, não um buraco. Por isso a regra dos 3 cm. Ainda sobram falsos alarmes
    no contorno (pele que sai da silhueta da peça, como no tornozelo da meia-calça) e no forro de capuzes largos;
    o único buraco real confirmado é o pescoço do suéter com laço.
  - **Pele furando** confere: na saia com fenda a perna atravessa o tecido ao andar.
  - **Esticado** confere, mas a causa nas fantasias e na capa é outra (ver abaixo).

![Calibração do esticado](images/bateria/calibracao-esticado.png)

## 📊 Última rodada completa (06/10/2026, cache v34, regra nova de buraco)

204 combinações (102 por corpo): **117 ok, 70 atenção, 17 falha**.

- Tecido rasgado: Sully, Baby Shark, Realistic White Pigeon, Squirrel Suit, Strawberry Onesie, White Cat Costume e
  Cloak.
- Buraco: suéter com laço (real, no pescoço); Goose, Dinosaur e terno Mafioso (masculino) ainda sem confirmação.
- Pele furando: saia longa com fenda e Blue Fish Suit (masculino).

Evolução: 79 ok / 52 / 73 falha → depois dos pesos gerais das roupas 91 / 74 / 39 → 101 / 70 / 33 → regra nova de
buraco 117 / 70 / 17.

![Peças que saíram da falha](images/bateria/recuperadas.png)

## ⚠️ Pendências conhecidas

- **Fantasias de corpo inteiro e Cloak acima do limite de esticado.** O teste que decide se o tecido "envolve o
  membro" não distingue uma manga (tecido em volta só do braço) de um saco ou capa que envolve braço e tronco juntos:
  - Baby Shark: o tecido do lado do tubarão, 18–28 cm atrás do braço, não conta como manga e fica com o tronco; o
    braço balança dentro do saco e a mão sai pela frente.
  - Cloak: a capa em volta do antebraço conta como manga e abre como asa quando o braço balança.
  - White Cat: a manga segue o braço e rasga a lateral do corpo da fantasia no quadril.
  - Caminho provável: só é manga o tecido que tem parede entre o braço e o tronco; em sacos e capas o braço anda
    por dentro (com menos balanço quando a peça é de corpo inteiro).
- Calça de moletom com tênis embutido em atenção (~630 cm²).
- Baggy jeans com o cós ~9 cm longe do corpo e sobretudo com ponta no quadril: vêm do modelo da peça e da
  proporção do nosso corpo (mais estreito que o Blocky); mudar exigiria mexer no encaixe de todas as roupas largas.
